"""Atomic aggregate evidence and central audit; private text stays in history."""

from sqlalchemy import func, select

from app.audit.schemas import AuditInput, RequestAuditChanges, RequestAuditSnapshot
from app.audit.service import append_event
from app.procurement.requests.models import PurchaseRequestEvent
from app.procurement.requests.schemas import ClosedRequestEventPayload
from app.tenancy.contexts import membership_role

type RequestEventPayload = ClosedRequestEventPayload


def snapshot(db, principal, scope, row, **changes):
    member, role = membership_role(
        db, principal.user_id, scope.tenant_id, scope.contract_id
    )
    return RequestAuditSnapshot(
        request_id=row.id,
        tenant_id=row.tenant_id,
        contract_id=row.contract_id,
        version=row.version,
        status=row.status,
        requesting_node_id=row.requesting_node_id,
        requester_user_id=row.requester_user_id,
        requester_membership_id=row.requester_membership_id,
        buyer_membership_id=row.buyer_membership_id,
        actor_membership_id=member.id,
        tenant_role_id=role.id,
        tenant_role_code=role.code,
        changes=RequestAuditChanges(**changes),
    )


def append_request_event(
    db,
    request,
    principal,
    scope,
    row,
    action: str,
    before: RequestAuditSnapshot | None,
    after: RequestAuditSnapshot,
    details: RequestEventPayload,
) -> None:
    action = (
        action
        if action.startswith("procurement.request.")
        else f"procurement.request.{action}"
    )
    # Free text belongs only to the private request event. The central audit receives hashes.
    audit_id = append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=None,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            entity_type="purchase_request",
            entity_id=row.id,
            action=action,
            before=before,
            after=after,
            request_id=request.state.request_id,
        ),
    )
    sequence = (
        db.scalar(
            select(func.coalesce(func.max(PurchaseRequestEvent.sequence), 0)).where(
                PurchaseRequestEvent.tenant_id == scope.tenant_id,
                PurchaseRequestEvent.contract_id == scope.contract_id,
                PurchaseRequestEvent.request_id == row.id,
            )
        )
        + 1
    )
    db.add(
        PurchaseRequestEvent(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            request_id=row.id,
            sequence=sequence,
            aggregate_version=row.version,
            action=action,
            actor_user_id=principal.user_id,
            actor_membership_id=after.actor_membership_id,
            tenant_role_id=after.tenant_role_id,
            tenant_role_code=after.tenant_role_code,
            reason=getattr(request.state, "purchase_request_reason", None),
            payload=details.model_dump(mode="json"),
            audit_event_id=audit_id,
        )
    )
    db.flush()
