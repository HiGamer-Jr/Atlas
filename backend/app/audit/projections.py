"""Closed audit projections. Arbitrary historical JSON never becomes an API payload."""

from pydantic import ValidationError

from app.audit.schemas import (
    ContractModuleSnapshot,
    MembershipRoleSnapshot,
    MembershipStateSnapshot,
    MembershipUnitScopeSnapshot,
    OrganizationNodeSnapshot,
    TenantRoleSnapshot,
)
from app.identity.models import User
from app.platform.capabilities import CATALOG

ACCESS_ACTIONS = frozenset(
    {
        "membership.invited",
        "membership.status.changed",
        "membership.role.assigned",
        "access.invite.requested",
        "access.invite.resent",
        "access.invite.consumed",
        "access.invite.invalidated",
        "access.reset.requested",
        "access.reset.resent",
        "access.reset.consumed",
        "access.sessions.revoked",
    }
)
ROLE_ACTIONS = frozenset({"tenant.role.created", "tenant.role.updated"})
SNAPSHOTS = {
    "organization.node.created": OrganizationNodeSnapshot,
    "organization.node.updated": OrganizationNodeSnapshot,
    "contract.module.updated": ContractModuleSnapshot,
    "membership.unit_scope.updated": MembershipUnitScopeSnapshot,
    "membership.status.changed": MembershipStateSnapshot,
    "membership.role.assigned": MembershipRoleSnapshot,
    "tenant.role.created": TenantRoleSnapshot,
    "tenant.role.updated": TenantRoleSnapshot,
}


def state_view(action, value):
    schema = SNAPSHOTS.get(action)
    if not schema or value is None:
        return None
    try:
        result = schema.model_validate(value)
    except ValidationError:
        return None
    if isinstance(result, TenantRoleSnapshot) and (
        result.classification != "STANDARD"
        or result.sensitivity_locked
        or any(
            code not in CATALOG or CATALOG[code].sensitive
            for code in result.permissions
        )
    ):
        return None
    return result.model_dump(mode="json")


def project(db, row, detail=False, support=False):
    # Actor identity is permitted only for internal actors or a member of this scope.
    from sqlalchemy import exists, select

    from app.identity.models import PlatformRoleAssignment
    from app.tenancy.models import Membership

    permitted = row.actor_id and db.scalar(
        select(exists().where(PlatformRoleAssignment.user_id == row.actor_id))
    )
    if row.actor_id and not permitted:
        from app.platform.policy import safe_role_predicate
        from app.tenancy.models import TenantRole

        actor_query = (
            select(Membership.id)
            .join(TenantRole, TenantRole.id == Membership.role_id)
            .where(
                Membership.user_id == row.actor_id,
                Membership.tenant_id == row.tenant_id,
                Membership.contract_id == row.contract_id,
            )
        )
        if support:
            actor_query = actor_query.where(safe_role_predicate())
        permitted = db.scalar(select(actor_query.exists()))
    actor = db.get(User, row.actor_id) if permitted else None
    result = {
        "id": row.id,
        "occurred_at": row.occurred_at,
        "actor_id": actor.id if actor else None,
        "actor_name": actor.display_name if actor else None,
        "action": row.action,
        "outcome": row.outcome,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "reference": None,
        "request_id": row.request_id,
    }
    if detail:
        result.update(
            before=state_view(row.action, row.before_state),
            after=state_view(row.action, row.after_state),
            reason=None,
        )
    return result
