"""Versioned purchase need commands. All evidence uses the caller transaction."""

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.schemas import Principal
from app.procurement.requests import assignment, events, policy, queries
from app.procurement.requests.approval_policy import effective_approval_policy
from app.procurement.requests.command_schemas import (
    AssignmentCommand,
    DraftPatch,
    NoteCommand,
    ReasonCommand,
    RequestCreate,
    VersionCommand,
)
from app.procurement.requests.idempotency import canonical_digest, run_idempotent
from app.procurement.requests.models import (
    PurchaseRequest,
    PurchaseRequestEvent,
    PurchaseRequestItem,
    RequestAttachment,
    RequestCommandReceipt,
)
from app.procurement.requests.schemas import (
    AssignmentEventPayload,
    ItemsEventPayload,
    NoteEventPayload,
    RequestView,
    TransitionEventPayload,
)
from app.procurement.requests.transitions import RequestAction, transition_target
from app.tenancy.contexts import now
from app.tenancy.schemas import AccessScope


def invalid():
    return ApiError(409, "INVALID_TRANSITION", "Ação indisponível no estado atual.")


def require_version(row, payload):
    if row.version != payload.expected_version:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            "Solicitação alterada. Atualize antes de confirmar.",
        )


def owner(principal, member, row):
    return (
        row.requester_user_id == principal.user_id
        and row.requester_membership_id == member.id
    )


def load_command_row(db, principal, scope, request_id):
    # Authorize unit before the aggregate lock, then refresh after every wait.
    candidate = queries.read_row(db, principal, scope, request_id)
    row = db.scalar(
        queries.scoped(PurchaseRequest, scope)
        .where(PurchaseRequest.id == candidate.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    policy.authorize_request_read(db, principal, scope, row)
    return row


def finish(db, request, principal, scope, row, before, action, details, **changes):
    db.flush()
    after = events.snapshot(db, principal, scope, row, **changes)
    events.append_request_event(
        db, request, principal, scope, row, action, before, after, details
    )
    policy.authorize_request_read(db, principal, scope, row)
    result = queries.project_request(db, scope, row)
    policy.authorize_request_read(db, principal, scope, row)
    return result


def replace_items(db, scope, row, values):
    with db.no_autoflush:
        existing = {
            item.id: item
            for item in db.scalars(
                queries.scoped(PurchaseRequestItem, scope)
                .where(PurchaseRequestItem.request_id == row.id)
                .order_by(PurchaseRequestItem.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        }
        retained = {item.id for item in values if item.id is not None}
        if not retained <= existing.keys():
            raise ApiError(404, "NOT_FOUND", "Item não encontrado.")
        removed = existing.keys() - retained
        attached = (
            db.scalar(
                select(RequestAttachment.id)
                .where(
                    RequestAttachment.tenant_id == scope.tenant_id,
                    RequestAttachment.contract_id == scope.contract_id,
                    RequestAttachment.request_id == row.id,
                    RequestAttachment.item_id.in_(removed),
                )
                .limit(1)
            )
            if removed
            else None
        )
        if attached is not None:
            raise ApiError(
                409, "ITEM_HAS_ATTACHMENTS", "Remova o anexo antes de remover o item."
            )
    # Only ordering uniqueness is deferred; IDs, bounds and scoped FKs stay immediate.
    db.execute(text("SET CONSTRAINTS uq_purchase_request_item_position DEFERRED"))
    for item_id in removed:
        db.delete(existing[item_id])
    items = []
    for position, item in enumerate(values, 1):
        entry = (
            existing[item.id]
            if item.id is not None
            else PurchaseRequestItem(
                id=uuid4(),
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                request_id=row.id,
            )
        )
        entry.position = position
        entry.description = item.description
        entry.specification = item.specification
        entry.requested_quantity = Decimal(item.requested_quantity)
        entry.uom_code = item.uom_code
        db.add(entry)
        items.append(entry.id)
    db.flush()
    db.execute(text("SET CONSTRAINTS uq_purchase_request_item_position IMMEDIATE"))
    return items


def create_request(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    payload: RequestCreate,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    member = policy.require_request_actor(db, principal, scope, "create")
    policy.require_request_unit(
        db, principal, scope, payload.requesting_node_id, "create"
    )

    def operation():
        values = payload.model_dump(exclude={"items", "project_id", "cost_center_id"})
        row = PurchaseRequest(
            id=uuid4(),
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            requester_user_id=principal.user_id,
            requester_membership_id=member.id,
            version=1,
            status="DRAFT",
            **values,
        )
        db.add(row)
        db.flush()
        item_ids = replace_items(db, scope, row, payload.items)
        digest = canonical_digest(payload)
        return finish(
            db,
            request,
            principal,
            scope,
            row,
            None,
            "created",
            ItemsEventPayload(item_ids=item_ids, content_digest=digest),
            item_ids=item_ids,
            content_digest=digest,
        )

    return run_idempotent(
        db, principal, scope, "create", None, key, canonical_digest(payload), operation
    )


def update_draft(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    payload: DraftPatch,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    member = policy.require_request_actor(db, principal, scope, "create")
    row = load_command_row(db, principal, scope, request_id)
    if not owner(principal, member, row):
        raise policy.denied()
    if row.status != "DRAFT":
        raise invalid()
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, "create")
    if payload.requesting_node_id is not None:
        policy.require_request_unit(
            db, principal, scope, payload.requesting_node_id, "create"
        )
    require_version(row, payload)
    before = events.snapshot(db, principal, scope, row)
    values = payload.model_dump(
        exclude_unset=True,
        exclude={"expected_version", "items", "project_id", "cost_center_id"},
    )
    for name, value in values.items():
        setattr(row, name, value)
    item_ids = (
        replace_items(db, scope, row, payload.items)
        if payload.items is not None
        else []
    )
    row.version += 1
    row.updated_at = now(db)
    digest = canonical_digest(payload)
    return finish(
        db,
        request,
        principal,
        scope,
        row,
        before,
        "draft_updated",
        ItemsEventPayload(item_ids=item_ids, content_digest=digest),
        item_ids=item_ids,
        content_digest=digest,
    )


def replay_origin(db, principal, scope, row, command, key):
    receipt = db.scalar(
        select(RequestCommandReceipt).where(
            RequestCommandReceipt.tenant_id == scope.tenant_id,
            RequestCommandReceipt.contract_id == scope.contract_id,
            RequestCommandReceipt.actor_user_id == principal.user_id,
            RequestCommandReceipt.access_context_id == scope.id,
            RequestCommandReceipt.route == command,
            RequestCommandReceipt.target_id == row.id,
            RequestCommandReceipt.idempotency_key == key,
        )
    )
    if receipt is None:
        return row.status
    details = db.scalar(
        select(PurchaseRequestEvent.payload)
        .where(
            PurchaseRequestEvent.tenant_id == scope.tenant_id,
            PurchaseRequestEvent.contract_id == scope.contract_id,
            PurchaseRequestEvent.request_id == row.id,
            PurchaseRequestEvent.aggregate_version == receipt.result["version"],
        )
        .order_by(PurchaseRequestEvent.sequence)
        .limit(1)
    )
    return details.get("from_status", row.status) if details else row.status


def authorize_transition(db, principal, scope, row, command, origin):
    action = {
        "submit": "create",
        "start-triage": "triage",
        "request-approval": "triage",
        "approve": "approve",
        "reject": "triage" if origin == "IN_TRIAGE" else "approve",
        "start-fulfillment": "fulfill",
        "cancel": "cancel",
        "close": "close",
    }.get(command)
    if action is None:
        raise invalid()
    member = policy.require_request_actor(db, principal, scope, action)
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, action)
    is_owner = owner(principal, member, row)
    if command == "submit" and not is_owner:
        raise policy.denied()
    if command == "approve" and row.requester_user_id == principal.user_id:
        raise policy.denied()
    if command == "start-fulfillment":
        if row.buyer_membership_id != member.id:
            raise policy.denied()
        policy.require_request_unit(
            db, principal, scope, row.requesting_node_id, "read_unit"
        )
    if command == "close" and not (is_owner or row.buyer_membership_id == member.id):
        raise policy.denied()
    if command == "cancel":
        if origin == "DRAFT" and not is_owner:
            raise policy.denied()
        if origin == "IN_FULFILLMENT" or (origin != "DRAFT" and not is_owner):
            policy.require_request_actor(db, principal, scope, "triage")
    return member


def transition_request(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    command: RequestAction,
    payload: VersionCommand | ReasonCommand,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = load_command_row(db, principal, scope, request_id)
    origin = replay_origin(db, principal, scope, row, command, key)
    authorize_transition(db, principal, scope, row, command, origin)

    def operation():
        policy.authorize_request_read(db, principal, scope, row)
        authorize_transition(db, principal, scope, row, command, row.status)
        require_version(row, payload)
        before = events.snapshot(db, principal, scope, row)
        approval = (
            effective_approval_policy(db, scope)
            if command == "request-approval"
            else None
        )
        authorize_transition(db, principal, scope, row, command, row.status)
        target = transition_target(
            row.status,
            command,
            approval_mode=approval.approval_mode if approval else "REQUIRED",
        )
        if command == "submit":
            items = list(
                db.scalars(
                    queries.scoped(PurchaseRequestItem, scope)
                    .where(PurchaseRequestItem.request_id == row.id)
                    .order_by(PurchaseRequestItem.position)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            if (
                not row.description
                or not row.justification
                or row.needed_on is None
                or not 1 <= len(items) <= 100
            ):
                raise ApiError(
                    422, "VALIDATION_ERROR", "Preencha a necessidade e seus itens."
                )
            if row.priority == "URGENT" and not getattr(payload, "reason", "").strip():
                raise ApiError(422, "VALIDATION_ERROR", "Informe o motivo de urgência.")
        if (
            command in {"reject", "cancel"}
            and not getattr(payload, "reason", "").strip()
        ):
            raise ApiError(422, "VALIDATION_ERROR", "Motivo obrigatório.")
        changes = {}
        action = {
            "submit": "submitted",
            "start-triage": "triage_started",
            "request-approval": "approval_requested",
            "approve": "approved",
            "reject": "rejected",
            "start-fulfillment": "fulfillment_started",
            "cancel": "cancelled",
            "close": "closed",
        }[command]
        if approval:
            row.approval_mode = approval.approval_mode
            row.approval_policy_version = approval.version
            if approval.approval_mode == "NOT_REQUIRED":
                row.approval_decision_kind = "POLICY_WAIVER"
                action = "approval_waived"
            changes = {
                "approval_mode": row.approval_mode,
                "approval_policy_version": row.approval_policy_version,
                "approval_decision_kind": row.approval_decision_kind,
            }
        if command == "approve":
            # A pending REQUIRED decision remains human even after a policy patch.
            member = policy.tenant_actor(db, principal, scope)
            row.approver_membership_id = member.id
            row.approver_user_id = principal.user_id
            row.approval_decision_kind = "HUMAN"
            changes = {
                "approval_mode": row.approval_mode,
                "approval_policy_version": row.approval_policy_version,
                "approval_decision_kind": "HUMAN",
            }
        timestamp = {
            "submit": "submitted_at",
            "start-triage": "triage_started_at",
            "request-approval": "approval_requested_at",
            "approve": "approved_at",
            "start-fulfillment": "fulfillment_started_at",
            "close": "closed_at",
        }.get(command)
        if timestamp and getattr(row, timestamp) is None:
            setattr(row, timestamp, now(db))
        if target == "APPROVED" and row.approved_at is None:
            row.approved_at = now(db)
        row.status = target
        row.version += 1
        row.updated_at = now(db)
        request.state.purchase_request_reason = getattr(payload, "reason", None)
        details = TransitionEventPayload(
            from_status=before.status, to_status=target, **changes
        )
        return finish(
            db, request, principal, scope, row, before, action, details, **changes
        )

    return run_idempotent(
        db,
        principal,
        scope,
        command,
        request_id,
        key,
        canonical_digest(payload),
        operation,
    )


def assign_buyer(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    payload: AssignmentCommand,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id, payload.buyer_membership_id)
    row = load_command_row(db, principal, scope, request_id)
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, "assign")
    assignment.validate_candidate(
        db, principal, scope, row.requesting_node_id, payload.buyer_membership_id
    )

    def operation():
        candidate = assignment.validate_candidate(
            db, principal, scope, row.requesting_node_id, payload.buyer_membership_id
        )
        policy.authorize_request_read(db, principal, scope, row)
        require_version(row, payload)
        if row.status not in {"APPROVED", "IN_FULFILLMENT"}:
            raise invalid()
        before = events.snapshot(db, principal, scope, row)
        row.buyer_membership_id = candidate.id
        row.assigned_at = row.assigned_at or now(db)
        row.updated_at = now(db)
        row.version += 1
        return finish(
            db,
            request,
            principal,
            scope,
            row,
            before,
            "assigned",
            AssignmentEventPayload(buyer_membership_id=candidate.id),
        )

    return run_idempotent(
        db,
        principal,
        scope,
        "assign",
        request_id,
        key,
        canonical_digest(payload),
        operation,
    )


def add_note(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    request_id: UUID,
    payload: NoteCommand,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = load_command_row(db, principal, scope, request_id)
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, "comment")

    def operation():
        require_version(row, payload)
        if row.status in {"DRAFT", "CLOSED"}:
            raise invalid()
        before = events.snapshot(db, principal, scope, row)
        row.version += 1
        row.updated_at = now(db)
        digest = canonical_digest({"text": payload.text})
        return finish(
            db,
            request,
            principal,
            scope,
            row,
            before,
            "note_added",
            NoteEventPayload(text=payload.text, content_digest=digest),
            content_digest=digest,
        )

    return run_idempotent(
        db,
        principal,
        scope,
        "notes",
        request_id,
        key,
        canonical_digest(payload),
        operation,
    )
