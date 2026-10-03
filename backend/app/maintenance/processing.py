"""Synchronous domain processing. No generic worker, executable payload, or retry loop."""

import json
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select

from app.audit.schemas import AuditInput, ProcessingSnapshot
from app.audit.service import append_event
from app.core.errors import ApiError
from app.maintenance.corrections import authorize, grant, snapshot, typed_action
from app.maintenance.models import ProcessingRun
from app.maintenance.schemas import ProcessingView
from app.platform.capabilities import INTERNAL_GRANTS
from app.tenancy.contexts import now, revalidate


def permitted_diagnostics(db, principal, scope):
    principal, *_ = revalidate(db, principal, scope)
    if "jobs.read" not in INTERNAL_GRANTS.get(principal.platform_role, ()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    from app.support.services import support_for_context, validate_bound

    support = support_for_context(db, scope.id)
    if support:
        validate_bound(db, principal, support)
    row = grant(db, scope)
    if row:
        from app.grants.services import validate_bound as validate_grant

        if row.grant_type != "MAINTENANCE":
            raise ApiError(
                403, "GRANT_CONTEXT_INVALID", "Acesso temporário indisponível."
            )
        validate_grant(db, principal, row)
    return (
        principal,
        principal.platform_role == "PLATFORM_SUPPORT" or support is not None,
    )


def support_visible_actions(request):
    from app.maintenance.registry import MaintenanceHandler
    from app.platform.capabilities import CATALOG

    return [
        action.action_code
        for action in request.app.state.maintenance_registry.list()
        if isinstance(action.handler, MaintenanceHandler)
        and action.handler.diagnostics_safe
        and action.module_code != "FINANCE"
        and action.capability in CATALOG
        and CATALOG[action.capability].domain not in {"finance", "fiscal"}
    ]


def scoped_query(scope, support=False, request=None):
    query = select(ProcessingRun).where(
        ProcessingRun.tenant_id == scope.tenant_id,
        ProcessingRun.contract_id == scope.contract_id,
    )
    if support:
        query = query.where(
            ProcessingRun.classification == "STANDARD",
            ProcessingRun.action_code.in_(support_visible_actions(request)),
        )
    return query


def lineage_available(db, scope, row):
    root = row
    seen = {row.id}
    while root.source_run_id is not None:
        if root.source_run_id in seen:
            return False
        seen.add(root.source_run_id)
        root = db.scalar(
            scoped_query(scope).where(ProcessingRun.id == root.source_run_id)
        )
        if root is None:
            return False
    lineage = (
        select(ProcessingRun.id, ProcessingRun.status)
        .where(
            ProcessingRun.id == root.id,
            ProcessingRun.tenant_id == scope.tenant_id,
            ProcessingRun.contract_id == scope.contract_id,
        )
        .cte("processing_lineage", recursive=True)
    )
    lineage = lineage.union(
        select(ProcessingRun.id, ProcessingRun.status)
        .join(lineage, ProcessingRun.source_run_id == lineage.c.id)
        .where(
            ProcessingRun.tenant_id == scope.tenant_id,
            ProcessingRun.contract_id == scope.contract_id,
        )
    )
    blocked = db.scalar(
        select(lineage.c.id)
        .where(
            lineage.c.id != row.id,
            lineage.c.status.in_(["PENDING", "RUNNING", "SUCCEEDED", "UNKNOWN"]),
        )
        .limit(1)
    )
    return blocked is None


def eligible(action, row):
    if action.handler.reprocess is None:
        return False
    if row.status == "FAILED":
        return (
            True
            if action.handler.retry_eligible is None
            else bool(action.handler.retry_eligible(row))
        )
    # UNKNOWN is blocked by default and needs a domain-specific proof of eligibility.
    return (
        row.status == "UNKNOWN"
        and action.handler.retry_eligible is not None
        and bool(action.handler.retry_eligible(row))
    )


def projection(request, row, *, support=False, can_reprocess=False):
    codes = {"NONE", "COMPLETED", "HANDLER_FAILED", "NOT_ELIGIBLE"}
    known = {
        action.action_code for action in request.app.state.maintenance_registry.list()
    }
    return ProcessingView(
        id=row.id,
        action_code=row.action_code if row.action_code in known else "UNAVAILABLE",
        status=row.status
        if row.status in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"}
        else "UNKNOWN",
        result_code=row.result_code if row.result_code in codes else "NONE",
        message_code=row.message_code if row.message_code in codes else "NONE",
        request_id=row.request_id,
        entity_id=None if support else row.entity_id,
        source_run_id=None if support else row.source_run_id,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        version=row.version,
        can_reprocess=False if support else can_reprocess,
    )


def can_retry(db, request, principal, scope, row, support):
    if support or grant(db, scope) is None:
        return False
    try:
        action = typed_action(request, row.action_code)
        authorize(db, request, principal, scope, action, row.entity_id)
        return eligible(action, row) and lineage_available(db, scope, row)
    except ApiError:
        return False


def list_runs(db, request, principal, scope, limit, offset):
    principal, support = permitted_diagnostics(db, principal, scope)
    query = scoped_query(scope, support, request)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        projection(
            request,
            row,
            support=support,
            can_reprocess=can_retry(db, request, principal, scope, row, support),
        )
        for row in rows
    ]
    permitted_diagnostics(db, principal, scope)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def detail(db, request, principal, scope, run_id):
    principal, support = permitted_diagnostics(db, principal, scope)
    row = db.scalar(
        scoped_query(scope, support, request).where(ProcessingRun.id == run_id)
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    result = projection(
        request,
        row,
        support=support,
        can_reprocess=can_retry(db, request, principal, scope, row, support),
    )
    permitted_diagnostics(db, principal, scope)
    return result


def request_reprocess(db, request, principal, scope, run_id, command):
    source = db.scalar(scoped_query(scope).where(ProcessingRun.id == run_id))
    if source is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    action = typed_action(request, source.action_code)
    authorize(db, request, principal, scope, action, source.entity_id)
    source = db.scalar(
        scoped_query(scope)
        .where(ProcessingRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    action = typed_action(request, source.action_code)
    authorize(db, request, principal, scope, action, source.entity_id)
    entity = action.handler.load_scoped(db, scope, source.entity_id, lock=True)
    current_grant = authorize(db, request, principal, scope, action, source.entity_id)
    if entity is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    fingerprint = sha256(
        json.dumps(
            {
                "source": str(source.id),
                "action_code": source.action_code,
                "entity_id": str(source.entity_id),
                "command": command.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    existing = db.scalar(
        scoped_query(scope)
        .where(
            ProcessingRun.source_run_id == source.id,
            ProcessingRun.idempotency_key == command.idempotency_key,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if existing:
        authorize(db, request, principal, scope, action, source.entity_id)
        if existing.command_fingerprint != fingerprint:
            raise ApiError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Esta chave já foi usada com outra solicitação.",
            )
        return projection(request, existing)
    if source.version != command.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "O processamento foi alterado. Revise novamente."
        )
    if not eligible(action, source) or not lineage_available(db, scope, source):
        raise ApiError(
            409, "PROCESSING_INELIGIBLE", "Este processamento não permite repetição."
        )
    before = snapshot(action.handler, entity)
    clock = now(db)
    row = ProcessingRun(
        id=uuid4(),
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        action_code=source.action_code,
        entity_type=source.entity_type,
        entity_id=source.entity_id,
        source_run_id=source.id,
        idempotency_key=command.idempotency_key,
        command_fingerprint=fingerprint,
        operator_id=principal.user_id,
        operator_session_id=principal.session_id,
        operator_role=principal.platform_role,
        context_id=scope.id,
        grant_id=current_grant.id,
        grant_type="MAINTENANCE",
        request_id=request.state.request_id,
        status="RUNNING",
        classification=source.classification,
        reason=command.reason,
        reference=command.reference,
        version=1,
        created_at=clock,
        started_at=clock,
    )
    db.add(row)
    db.flush()
    savepoint = db.begin_nested()
    failed = False
    try:
        action.handler.reprocess(db, entity, source)
        db.flush()
        after = snapshot(action.handler, entity)
        if after.version != before.version + 1:
            raise RuntimeError("Handler must advance the domain version exactly once")
    except Exception:  # noqa: BLE001 -- rollback domain state and persist only closed failure codes
        savepoint.rollback()
        failed = True
    else:
        savepoint.commit()
    authorize(db, request, principal, scope, action, source.entity_id)
    if failed:
        row.status = "FAILED"
        row.result_code = row.message_code = "HANDLER_FAILED"
        row.finished_at = now(db)
        row.version += 1
        state = ProcessingSnapshot(
            run_id=row.id,
            action_code=row.action_code,
            status="FAILED",
            result_code="HANDLER_FAILED",
            message_code="HANDLER_FAILED",
            version=row.version,
        )
        append_event(
            db,
            AuditInput(
                actor_id=principal.user_id,
                actor_role=principal.platform_role,
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                entity_type=action.entity_type,
                entity_id=entity.id,
                action="maintenance.processing.failed",
                outcome="FAILURE",
                after=state,
                reason=command.reason,
                reference=command.reference,
                request_id=request.state.request_id,
            ),
        )
        db.flush()
        return projection(request, row)
    row.status = "SUCCEEDED"
    row.result_code = row.message_code = "COMPLETED"
    row.finished_at = now(db)
    row.version += 1
    append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            entity_type=action.entity_type,
            entity_id=entity.id,
            action="maintenance.processing.succeeded",
            before=before,
            after=after,
            reason=command.reason,
            reference=command.reference,
            request_id=request.state.request_id,
        ),
    )
    db.flush()
    return projection(request, row)
