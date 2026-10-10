"""Private scoped projections; pagination tokens never stand in for authorization."""

import base64
import binascii
import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.models import PlatformRoleAssignment, User
from app.identity.schemas import Principal
from app.organization.models import MembershipUnitScope, OrganizationNode
from app.organization.unit_authorization import resolve_unit_scope
from app.procurement.requests import policy
from app.procurement.requests.models import (
    PurchaseRequest,
    PurchaseRequestEvent,
    PurchaseRequestItem,
    RequestAttachment,
)
from app.procurement.requests.schemas import (
    ActorView,
    AttachmentView,
    BuyerCandidatePage,
    BuyerCandidateView,
    ItemView,
    RequestFilters,
    RequestHistoryEventView,
    RequestHistoryPage,
    RequestingNodeView,
    RequestPage,
    RequestView,
)
from app.tenancy.models import Membership, TenantRole, TenantRolePermission
from app.tenancy.schemas import AccessScope


def invalid_cursor():
    return ApiError(422, "CURSOR_INVALID", "Cursor inválido neste contexto.")


def page_offset(principal, scope, context, limit, cursor):
    if not 1 <= limit <= 100:
        raise ApiError(422, "VALIDATION_ERROR", "Limite inválido.")
    signature = hashlib.sha256(
        json.dumps(
            [
                str(principal.user_id),
                str(scope.id),
                str(scope.tenant_id),
                str(scope.contract_id),
                context,
                limit,
            ],
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    if cursor is None:
        return signature, 0
    try:
        if len(cursor) > 2048:
            raise ValueError
        decoded = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"v", "scope", "offset"}
            or decoded["v"] != 1
            or decoded["scope"] != signature
            or type(decoded["offset"]) is not int
            or not 0 <= decoded["offset"] <= 1_000_000_000
        ):
            raise ValueError
        return signature, decoded["offset"]
    except (ValueError, TypeError, binascii.Error, UnicodeError):
        raise invalid_cursor() from None


def next_cursor(signature, offset, limit, total):
    if offset + limit >= total:
        return None
    return base64.urlsafe_b64encode(
        json.dumps(
            {"v": 1, "scope": signature, "offset": offset + limit},
            separators=(",", ":"),
        ).encode()
    ).decode()


def scoped(model, scope):
    return select(model).where(
        model.tenant_id == scope.tenant_id, model.contract_id == scope.contract_id
    )


def actor_view(db, scope, membership_id, user_id):
    name = db.scalar(
        select(User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.id == membership_id,
            Membership.user_id == user_id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
    )
    return ActorView(membership_id=membership_id, user_id=user_id, display_name=name)


def candidate_query(scope, node_id):
    permissions = [
        select(TenantRolePermission.role_id)
        .where(
            TenantRolePermission.tenant_id == scope.tenant_id,
            TenantRolePermission.contract_id == scope.contract_id,
            TenantRolePermission.role_id == Membership.role_id,
            TenantRolePermission.active.is_(True),
            TenantRolePermission.capability == f"procurement.requests.{action}",
        )
        .exists()
        for action in ("read_unit", "fulfill")
    ]
    grant = (
        select(MembershipUnitScope.membership_id)
        .where(
            MembershipUnitScope.tenant_id == scope.tenant_id,
            MembershipUnitScope.contract_id == scope.contract_id,
            MembershipUnitScope.membership_id == Membership.id,
            MembershipUnitScope.node_id == node_id,
            MembershipUnitScope.active.is_(True),
        )
        .exists()
    )
    internal = (
        select(PlatformRoleAssignment.user_id)
        .where(
            PlatformRoleAssignment.user_id == User.id,
            PlatformRoleAssignment.active.is_(True),
        )
        .exists()
    )
    return (
        select(Membership.id.label("membership_id"), User.display_name)
        .join(
            User,
            User.id == Membership.user_id,
        )
        .join(
            TenantRole,
            and_(
                TenantRole.id == Membership.role_id,
                TenantRole.tenant_id == Membership.tenant_id,
                TenantRole.contract_id == Membership.contract_id,
            ),
        )
        .where(
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
            Membership.active.is_(True),
            Membership.blocked.is_(False),
            Membership.invitation_pending.is_(False),
            TenantRole.active.is_(True),
            User.active.is_(True),
            User.blocked.is_(False),
            ~internal,
            *permissions,
            or_(
                Membership.unit_scope_mode == "ALL",
                and_(Membership.unit_scope_mode == "RESTRICTED", grant),
            ),
        )
    )


def project_request(db, scope, row):
    node = db.scalar(
        scoped(OrganizationNode, scope).where(
            OrganizationNode.id == row.requesting_node_id
        )
    )
    items = list(
        db.scalars(
            scoped(PurchaseRequestItem, scope)
            .where(PurchaseRequestItem.request_id == row.id)
            .order_by(PurchaseRequestItem.position)
        )
    )
    from app.procurement.requests.fulfillment import (
        fulfillment_state,
        fulfillment_totals,
    )

    quantities = fulfillment_totals(db, scope, row.id)
    item_views = [
        ItemView(
            id=item.id,
            position=item.position,
            description=item.description,
            specification=item.specification,
            requested_quantity=str(item.requested_quantity),
            fulfilled_quantity=str(quantities.get(item.id, Decimal(0))),
            remaining_quantity=str(
                item.requested_quantity - quantities.get(item.id, Decimal(0))
            ),
            uom_code=item.uom_code,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]
    buyer = None
    if row.buyer_membership_id:
        candidate = (
            db.execute(
                candidate_query(scope, row.requesting_node_id).where(
                    Membership.id == row.buyer_membership_id
                )
            )
            .mappings()
            .first()
        )
        if candidate:
            buyer = BuyerCandidateView(**candidate)
    attachment_columns = [
        getattr(RequestAttachment, name) for name in AttachmentView.model_fields
    ]
    attachments = [
        AttachmentView(**entry)
        for entry in db.execute(
            select(*attachment_columns)
            .where(
                RequestAttachment.tenant_id == scope.tenant_id,
                RequestAttachment.contract_id == scope.contract_id,
                RequestAttachment.request_id == row.id,
            )
            .order_by(RequestAttachment.created_at, RequestAttachment.id)
        ).mappings()
    ]
    fields = {
        name: getattr(row, name)
        for name in RequestView.model_fields
        if hasattr(row, name) and name not in {"items", "attachments"}
    }
    return RequestView(
        **fields,
        requester=actor_view(
            db, scope, row.requester_membership_id, row.requester_user_id
        ),
        requesting_node=RequestingNodeView(
            id=node.id, name=node.name, code=node.code, kind=node.kind
        ),
        buyer=buyer,
        items=item_views,
        attachments=attachments,
        fulfillment_state=fulfillment_state(item_views),
    )


def read_row(db, principal, scope, request_id):
    policy.tenant_actor(db, principal, scope)
    row = db.scalar(
        scoped(PurchaseRequest, scope)
        .where(PurchaseRequest.id == request_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    policy.authorize_request_read(db, principal, scope, row)
    return row


def get_request(
    db: Session, principal: Principal, scope: AccessScope, request_id: UUID
) -> RequestView:
    row = read_row(db, principal, scope, request_id)
    result = project_request(db, scope, row)
    policy.authorize_request_read(db, principal, scope, row)
    return result


def list_requests(
    db: Session, principal: Principal, scope: AccessScope, filters: RequestFilters
) -> RequestPage:
    action = "read_unit" if filters.visibility == "unit" else "read_own"
    try:
        member = policy.require_request_actor(db, principal, scope, action)
    except ApiError as error:
        if action != "read_own" or error.code != "CAPABILITY_DENIED":
            raise
        # Unit readers may narrow to their own requests, including own drafts.
        action = "read_unit"
        member = policy.require_request_actor(db, principal, scope, action)
    if filters.visibility == "own" and (
        filters.requester_membership_id or filters.buyer_membership_id
    ):
        raise ApiError(422, "VALIDATION_ERROR", "Filtro exige leitura por unidade.")
    nodes = resolve_unit_scope(db, scope, member).nodes
    policy.require_request_actor(db, principal, scope, action)
    query = scoped(PurchaseRequest, scope).where(
        PurchaseRequest.requesting_node_id.in_(
            [node.id for node in nodes if node.kind in policy.REQUEST_NODE_KINDS]
        )
    )
    owner = and_(
        PurchaseRequest.requester_user_id == principal.user_id,
        PurchaseRequest.requester_membership_id == member.id,
    )
    query = query.where(
        owner
        if filters.visibility == "own"
        else or_(PurchaseRequest.status != "DRAFT", owner)
    )
    for name, value in [
        ("status", filters.status),
        ("requesting_node_id", filters.node_id),
        ("requester_membership_id", filters.requester_membership_id),
        ("buyer_membership_id", filters.buyer_membership_id),
    ]:
        if value is not None:
            query = query.where(getattr(PurchaseRequest, name) == value)
    signature, offset = page_offset(
        principal,
        scope,
        ["requests", filters.model_dump(mode="json", exclude={"cursor"})],
        filters.limit,
        filters.cursor,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = list(
        db.scalars(
            query.order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
            .offset(offset)
            .limit(filters.limit)
            .execution_options(populate_existing=True)
        )
    )
    views = [project_request(db, scope, row) for row in rows]
    for row in rows:
        policy.authorize_request_read(db, principal, scope, row)
    policy.require_request_actor(db, principal, scope, action)
    return RequestPage(
        items=views,
        total=total,
        limit=filters.limit,
        next_cursor=next_cursor(signature, offset, filters.limit, total),
    )


def request_history(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    limit: int,
    cursor: str | None,
) -> RequestHistoryPage:
    row = read_row(db, principal, scope, request_id)
    signature, offset = page_offset(
        principal, scope, ["history", str(request_id)], limit, cursor
    )
    query = scoped(PurchaseRequestEvent, scope).where(
        PurchaseRequestEvent.request_id == request_id
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    events = list(
        db.scalars(
            query.order_by(PurchaseRequestEvent.sequence).offset(offset).limit(limit)
        )
    )
    views = [
        RequestHistoryEventView(
            id=event.id,
            sequence=event.sequence,
            aggregate_version=event.aggregate_version,
            action=event.action,
            actor=actor_view(db, scope, event.actor_membership_id, event.actor_user_id),
            tenant_role_id=event.tenant_role_id,
            tenant_role_code=event.tenant_role_code,
            occurred_at=event.occurred_at,
            reason=event.reason,
            payload=event.payload,
        )
        for event in events
    ]
    policy.authorize_request_read(db, principal, scope, row)
    return RequestHistoryPage(
        items=views,
        total=total,
        limit=limit,
        next_cursor=next_cursor(signature, offset, limit, total),
    )


def buyer_candidates(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    node_id: UUID,
    limit: int,
    cursor: str | None,
) -> BuyerCandidatePage:
    policy.require_request_unit(db, principal, scope, node_id, "read_unit")
    policy.require_request_unit(db, principal, scope, node_id, "assign")
    signature, offset = page_offset(
        principal, scope, ["buyers", str(node_id)], limit, cursor
    )
    query = candidate_query(scope, node_id)
    # Discovery does not lock candidates or grant assignment authority. Refresh
    # the caller after unit/authorization waits, then read current eligibility
    # in SQL before count, limit, and minimal name projection.
    policy.require_request_unit(db, principal, scope, node_id, "read_unit")
    policy.require_request_unit(db, principal, scope, node_id, "assign")
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        db.execute(query.order_by(Membership.id).offset(offset).limit(limit))
        .mappings()
        .all()
    )
    return BuyerCandidatePage(
        items=[BuyerCandidateView(**row) for row in rows],
        total=total,
        limit=limit,
        next_cursor=next_cursor(signature, offset, limit, total),
    )
