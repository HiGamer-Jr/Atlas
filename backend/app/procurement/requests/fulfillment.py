"""Manual attestation of actual delivery; immutable entries, never stock or orders."""

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.schemas import Principal
from app.procurement.requests import assignment, commands, events, policy, queries
from app.procurement.requests.command_schemas import FulfillmentCommand, ReasonCommand
from app.procurement.requests.idempotency import canonical_digest, run_idempotent
from app.procurement.requests.models import PurchaseRequestItem, RequestFulfillmentEntry
from app.procurement.requests.schemas import (
    ItemView,
    QuantityEventPayload,
    RequestView,
    TransitionEventPayload,
)
from app.tenancy.contexts import now
from app.tenancy.schemas import AccessScope


def fulfillment_totals(
    db: Session, scope: AccessScope, request_id: UUID
) -> dict[UUID, Decimal]:
    return dict(
        db.execute(
            select(
                RequestFulfillmentEntry.item_id,
                func.sum(
                    RequestFulfillmentEntry.quantity * RequestFulfillmentEntry.sign
                ),
            )
            .where(
                RequestFulfillmentEntry.tenant_id == scope.tenant_id,
                RequestFulfillmentEntry.contract_id == scope.contract_id,
                RequestFulfillmentEntry.request_id == request_id,
            )
            .group_by(RequestFulfillmentEntry.item_id)
        ).all()
    )


def fulfillment_state(items: list[ItemView]) -> Literal["NONE", "PARTIAL", "COMPLETE"]:
    if items and all(
        Decimal(item.fulfilled_quantity) >= Decimal(item.requested_quantity)
        for item in items
    ):
        return "COMPLETE"
    if any(Decimal(item.fulfilled_quantity) > 0 for item in items):
        return "PARTIAL"
    return "NONE"


def authorize(db, principal, scope, row):
    policy.authorize_request_read(db, principal, scope, row)
    member = policy.require_request_actor(db, principal, scope, "fulfill")
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, "fulfill")
    policy.require_request_unit(
        db, principal, scope, row.requesting_node_id, "read_unit"
    )
    if row.buyer_membership_id != member.id:
        raise policy.denied()
    return member


def lock_items(db, scope, row):
    return {
        item.id: item
        for item in db.scalars(
            queries.scoped(PurchaseRequestItem, scope)
            .where(PurchaseRequestItem.request_id == row.id)
            .order_by(PurchaseRequestItem.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }


def check_command(db, principal, scope, row, payload):
    member = authorize(db, principal, scope, row)
    commands.require_version(row, payload)
    if row.status != "IN_FULFILLMENT":
        raise commands.invalid()
    return member


def append_entry(
    db,
    request,
    principal,
    scope,
    row,
    member,
    item,
    quantity,
    evidence,
    reason,
    *,
    original=None,
):
    before = events.snapshot(db, principal, scope, row)
    row.version += 1
    row.updated_at = now(db)
    entry = RequestFulfillmentEntry(
        id=uuid4(),
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        request_id=row.id,
        item_id=item.id,
        quantity=quantity,
        sign=-1 if original else 1,
        uom_code=item.uom_code,
        original_entry_id=original.id if original else None,
        actor_user_id=principal.user_id,
        actor_membership_id=member.id,
        source_kind="MANUAL_EXTERNAL",
        evidence=evidence,
        reason=reason,
        aggregate_version=row.version,
    )
    db.add(entry)
    db.flush()
    complete = queries.project_request(db, scope, row).fulfillment_state == "COMPLETE"
    if complete:
        row.status = "FULFILLED"
        row.fulfilled_at = row.fulfilled_at or now(db)
    request.state.purchase_request_reason = reason
    quantity_text = format(quantity, ".6f")
    changes = {
        "item_ids": [item.id],
        "entry_id": entry.id,
        "quantity": quantity_text,
        "content_digest": canonical_digest({"evidence": evidence, "reason": reason}),
    }
    result = commands.finish(
        db,
        request,
        principal,
        scope,
        row,
        before,
        "fulfillment_reversed" if original else "fulfillment_recorded",
        QuantityEventPayload(
            item_id=item.id,
            entry_id=entry.id,
            original_entry_id=entry.original_entry_id,
            quantity=quantity_text,
            uom_code=item.uom_code,
        ),
        **changes,
    )
    if complete:
        events.append_request_event(
            db,
            request,
            principal,
            scope,
            row,
            "fulfilled",
            before,
            events.snapshot(db, principal, scope, row),
            TransitionEventPayload(from_status=before.status, to_status="FULFILLED"),
        )
    authorize(db, principal, scope, row)
    return result


def record_fulfillment(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    payload: FulfillmentCommand,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = commands.load_command_row(db, principal, scope, request_id)
    authorize(db, principal, scope, row)

    def operation():
        member = check_command(db, principal, scope, row, payload)
        items = lock_items(db, scope, row)
        item = items.get(payload.item_id)
        if item is None:
            raise ApiError(404, "NOT_FOUND", "Item não encontrado.")
        totals = fulfillment_totals(db, scope, row.id)
        if payload.quantity > item.requested_quantity - totals.get(item.id, Decimal(0)):
            raise ApiError(
                409,
                "FULFILLMENT_EXCEEDS_REMAINING",
                "Quantidade excede o saldo do item.",
            )
        authorize(db, principal, scope, row)
        return append_entry(
            db,
            request,
            principal,
            scope,
            row,
            member,
            item,
            payload.quantity,
            payload.evidence,
            payload.reason,
        )

    return run_idempotent(
        db,
        principal,
        scope,
        "fulfillments",
        request_id,
        key,
        canonical_digest(payload),
        operation,
    )


def reverse_fulfillment(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    entry_id: UUID,
    payload: ReasonCommand,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = commands.load_command_row(db, principal, scope, request_id)
    authorize(db, principal, scope, row)

    def operation():
        member = check_command(db, principal, scope, row, payload)
        items = lock_items(db, scope, row)
        # Immutable evidence needs no UPDATE privilege: the aggregate lock
        # serializes every append/reversal, and originals cannot be edited/deleted.
        original = db.scalar(
            queries.scoped(RequestFulfillmentEntry, scope)
            .where(
                RequestFulfillmentEntry.request_id == row.id,
                RequestFulfillmentEntry.id == entry_id,
            )
            .execution_options(populate_existing=True)
        )
        if original is None:
            raise ApiError(404, "NOT_FOUND", "Atendimento não encontrado.")
        if original.sign != 1 or original.original_entry_id is not None:
            raise ApiError(
                409,
                "INVALID_FULFILLMENT_ENTRY",
                "Somente atendimento original pode ser revertido.",
            )
        compensation = db.scalar(
            queries.scoped(RequestFulfillmentEntry, scope).where(
                RequestFulfillmentEntry.request_id == row.id,
                RequestFulfillmentEntry.original_entry_id == entry_id,
            )
        )
        if compensation is not None:
            raise ApiError(
                409, "FULFILLMENT_ALREADY_REVERSED", "Atendimento já revertido."
            )
        totals = fulfillment_totals(db, scope, row.id)
        if original.quantity > totals.get(original.item_id, Decimal(0)):
            raise ApiError(
                409, "INVALID_FULFILLMENT_ENTRY", "Compensação excede o saldo atendido."
            )
        authorize(db, principal, scope, row)
        return append_entry(
            db,
            request,
            principal,
            scope,
            row,
            member,
            items[original.item_id],
            original.quantity,
            original.evidence,
            payload.reason,
            original=original,
        )

    return run_idempotent(
        db,
        principal,
        scope,
        f"fulfillments/{entry_id}/reverse",
        request_id,
        key,
        canonical_digest(payload),
        operation,
    )
