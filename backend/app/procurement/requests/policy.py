"""Fresh tenant policy for purchase requests; names and client claims grant nothing."""

from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.grants.models import TemporaryPrivilegedGrant
from app.identity.models import User
from app.identity.schemas import Principal
from app.identity.sessions import current_role
from app.organization.models import OrganizationNode
from app.organization.unit_authorization import require_authorized_node
from app.platform.policy import require_capability
from app.procurement.requests.models import PurchaseRequest
from app.support.models import SupportSession
from app.tenancy.contexts import membership_role, permissions, revalidate
from app.tenancy.models import Membership
from app.tenancy.schemas import AccessScope

REQUEST_ACTIONS = frozenset(
    {
        "create",
        "read_own",
        "read_unit",
        "triage",
        "approve",
        "assign",
        "fulfill",
        "cancel",
        "close",
        "comment",
    }
)
REQUEST_NODE_KINDS = frozenset(
    {
        "UNIT",
        "STORE",
        "DISTRIBUTION_CENTER",
        "WAREHOUSE",
        "OFFICE",
        "WORKSITE",
        "BRANCH",
    }
)


def denied() -> ApiError:
    return ApiError(403, "CAPABILITY_DENIED", "Ação não permitida neste contexto.")


def tenant_actor(db: Session, principal: Principal, scope: AccessScope) -> Membership:
    fresh, _, _, _, _ = revalidate(db, principal, scope)
    # Reject INTERNAL and derived support/grant contexts before inspecting powers.
    if (
        fresh.platform_role is not None
        or db.scalar(
            select(SupportSession.id).where(SupportSession.context_id == scope.id)
        )
        or db.scalar(
            select(TemporaryPrivilegedGrant.id).where(
                TemporaryPrivilegedGrant.context_id == scope.id
            )
        )
    ):
        raise denied()
    member, role = membership_role(
        db, fresh.user_id, scope.tenant_id, scope.contract_id
    )
    if member is None or role is None:
        raise denied()
    return member


def require_request_actor(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    action: str,
) -> Membership:
    member = tenant_actor(db, principal, scope)
    if action not in REQUEST_ACTIONS:
        raise denied()
    require_capability(
        db,
        principal,
        scope,
        f"procurement.requests.{action}",
        module_code="PROCUREMENT",
    )
    return member


def require_request_unit(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    node_id: UUID,
    action: str,
) -> OrganizationNode:
    member = require_request_actor(db, principal, scope, action)
    node = require_authorized_node(db, scope, member, node_id)
    if node.kind not in REQUEST_NODE_KINDS:
        raise ApiError(403, "UNIT_SCOPE_DENIED", "Unidade indisponível neste contexto.")
    # Node/grant waits may have outlived context/session validity.
    require_request_actor(db, principal, scope, action)
    return node


def authorize_request_read(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    row: PurchaseRequest,
) -> None:
    member = tenant_actor(db, principal, scope)
    if row.tenant_id != scope.tenant_id or row.contract_id != scope.contract_id:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    owner = (
        row.requester_user_id == principal.user_id
        and row.requester_membership_id == member.id
    )
    if row.status == "DRAFT" and not owner:
        raise denied()
    if owner:
        try:
            require_request_unit(
                db, principal, scope, row.requesting_node_id, "read_own"
            )
            return
        except ApiError as error:
            if error.code != "CAPABILITY_DENIED":
                raise
    require_request_unit(db, principal, scope, row.requesting_node_id, "read_unit")


def candidate_user(db: Session, user_id: UUID) -> None:
    # Commands must prelock all involved identities before context revalidation.
    # Never add an inverted candidate User lock after taking contract/member locks.
    user = db.scalar(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    if (
        user is None
        or not user.active
        or user.blocked
        or current_role(db, user_id) is not None
    ):
        raise denied()


def require_buyer_candidate(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    node_id: UUID,
    buyer_membership_id: UUID,
) -> Membership:
    require_request_unit(db, principal, scope, node_id, "assign")
    candidate = db.scalar(
        select(Membership)
        .where(
            Membership.id == buyer_membership_id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
        .execution_options(populate_existing=True)
    )
    if candidate is None:
        raise denied()
    candidate_user(db, candidate.user_id)
    member, role = membership_role(
        db, candidate.user_id, scope.tenant_id, scope.contract_id
    )
    if member is None or role is None:
        raise denied()
    if not {
        "procurement.requests.fulfill",
        "procurement.requests.read_unit",
    } <= permissions(db, role):
        raise denied()
    # Unit policy binds membership.user_id to scope.actor_id. This is only a
    # server-side unit check, never a candidate authentication/context credential.
    candidate_scope = replace(scope, actor_id=member.user_id)
    require_authorized_node(db, candidate_scope, member, node_id)
    candidate_user(db, member.user_id)
    require_request_unit(db, principal, scope, node_id, "assign")
    return member
