"""Data Hub mutations. Transaction ownership always remains with the caller."""

import hashlib
import re
import unicodedata
from datetime import timedelta
from uuid import uuid4

from fastapi import Request
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.audit.schemas import AuditInput, DataHubImportSnapshot
from app.core.errors import ApiError
from app.datahub.connectors.base import WorkbookRejected
from app.datahub.models import (
    DataHubImport,
    DataHubImportFile,
    DataHubImportIssue,
    DataHubImportRow,
)
from app.datahub.policy import authorize_selection
from app.datahub.schemas import ImportSummary
from app.datahub.types import Operation, ParsedWorkbook
from app.datahub.validation import validate_rows
from app.identity.models import AuthSession
from app.identity.schemas import Principal
from app.tenancy.contexts import now, revalidate
from app.tenancy.schemas import AccessScope


def sanitized_filename(value: str) -> str:
    name = unicodedata.normalize("NFC", value.replace("\\", "/").rsplit("/", 1)[-1])
    name = re.sub(r"[^\w .()-]", "_", name).strip(" .")
    if not name.lower().endswith(".xlsx"):
        name = "planilha.xlsx"
    return name[:195].removesuffix(".xlsx") + ".xlsx" if len(name) > 200 else name


def summary(row: DataHubImport) -> ImportSummary:
    return ImportSummary.model_validate(
        {k: getattr(row, k) for k in ImportSummary.model_fields}
    )


def snapshot(row: DataHubImport) -> DataHubImportSnapshot:
    return DataHubImportSnapshot.model_validate(
        {k: getattr(row, k) for k in DataHubImportSnapshot.model_fields}
    )


def audit(db, request, principal, scope, row, action, before=None):
    audit_service.append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            entity_type="datahub_import",
            entity_id=row.id,
            action=action,
            outcome="FAILURE" if action == "datahub.import.failed" else "SUCCESS",
            before=before,
            after=snapshot(row),
            request_id=request.state.request_id,
        ),
    )


def receive_preview(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    filename: str,
    content: bytes,
    parsed: ParsedWorkbook,
) -> DataHubImport:
    settings = request.app.state.settings
    if not settings.datahub_enabled:
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    selection = authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        parsed.template_id,
        parsed.template_version,
        (),
    )
    if not set(parsed.datasets) <= set(selection.datasets):
        raise ApiError(
            403, "DATASET_DENIED", "A planilha contém datasets não autorizados."
        )
    fresh, context, *_ = revalidate(db, principal, scope)
    session = db.get(AuthSession, principal.session_id)
    clock = now(db)
    expires = min(
        clock + timedelta(seconds=settings.datahub_limits.preview_seconds),
        context.expires_at,
        session.expires_at,
        session.last_seen_at + timedelta(seconds=settings.session_idle_seconds),
    )
    if expires <= clock:
        raise ApiError(403, "CONTEXT_INVALID", "Contexto indisponível.")
    identity = uuid4()
    reference = request.app.state.datahub_raw_store.put(identity, content)

    # An uncommitted receipt never leaves its encrypted object orphaned.
    committed = False

    def receipt_committed(session):
        nonlocal committed
        if not session.in_nested_transaction():
            committed = True

    def rollback_file(session, previous_transaction):
        if previous_transaction.parent is None and not committed:
            request.app.state.datahub_raw_store.remove(reference)

    event.listen(db, "after_soft_rollback", rollback_file)
    event.listen(db, "after_commit", receipt_committed)
    digest = hashlib.sha256(content).hexdigest()
    row = DataHubImport(
        id=identity,
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        access_context_id=scope.id,
        auth_session_id=principal.session_id,
        actor_user_id=principal.user_id,
        template_id=parsed.template_id,
        template_version=parsed.template_version,
        connector_code="XLSX",
        source_digest=digest,
        status="RECEIVED",
        version=1,
        request_id=request.state.request_id,
        preview_expires_at=expires,
        created_at=clock,
        updated_at=clock,
        row_count=0,
        inserted_count=0,
        skipped_count=0,
        error_count=0,
        warning_count=0,
        result_code="NONE",
    )
    db.add(row)
    db.flush()
    db.add(
        DataHubImportFile(
            id=uuid4(),
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            import_id=identity,
            name=sanitized_filename(filename),
            digest=digest,
            size_bytes=len(content),
            sheet_count=parsed.sheet_count,
            entry_count=parsed.entry_count,
            raw_reference=reference.id,
            raw_expires_at=clock
            + timedelta(seconds=settings.datahub_limits.raw_seconds),
            created_at=clock,
            updated_at=clock,
        )
    )
    db.flush()
    audit(db, request, fresh, scope, row, "datahub.import.received")
    row.status, row.version = "VALIDATING", 2
    db.flush()
    return row


def create_preview(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    filename: str,
    content: bytes,
) -> ImportSummary:
    settings = request.app.state.settings
    if not settings.datahub_enabled:
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    parsed = db.info.get("datahub_parsed")
    if parsed is None:
        try:
            parsed = request.app.state.datahub_connector.parse(
                content, settings.datahub_limits
            )
        except WorkbookRejected as exc:
            raise ApiError(
                422, exc.code, "Planilha incompatível ou inválida."
            ) from None
    selection = authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        parsed.template_id,
        parsed.template_version,
        (),
    )
    if not set(parsed.datasets) <= set(selection.datasets):
        raise ApiError(
            403, "DATASET_DENIED", "A planilha contém datasets não autorizados."
        )
    receipt_id = db.info.get("datahub_import_id")
    if receipt_id:
        row = db.scalar(
            select(DataHubImport)
            .where(
                DataHubImport.id == receipt_id,
                DataHubImport.tenant_id == scope.tenant_id,
                DataHubImport.contract_id == scope.contract_id,
                DataHubImport.access_context_id == scope.id,
                DataHubImport.auth_session_id == principal.session_id,
                DataHubImport.actor_user_id == principal.user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            row is None
            or row.status != "VALIDATING"
            or row.source_digest != hashlib.sha256(content).hexdigest()
        ):
            raise ApiError(409, "PREVIEW_CONFLICT", "A análise não pode ser retomada.")
    else:
        row = receive_preview(db, request, principal, scope, filename, content, parsed)
    before = snapshot(row)
    fresh, *_ = revalidate(db, principal, scope)
    if now(db) >= row.preview_expires_at:
        row.status, row.result_code, row.finished_at = (
            "EXPIRED",
            "PREVIEW_EXPIRED",
            now(db),
        )
        row.version += 1
        audit(db, request, fresh, scope, row, "datahub.import.expired", before)
        return summary(row)
    db.info.update(datahub_scope=scope, datahub_principal=principal)
    result = validate_rows(db, selection, parsed)
    source_file = db.scalar(
        select(DataHubImportFile).where(DataHubImportFile.import_id == row.id)
    )
    row_ids = {}
    for item in result.rows:
        identity = uuid4()
        row_ids[(item.sheet, item.source_row)] = identity
        db.add(
            DataHubImportRow(
                id=identity,
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                import_id=row.id,
                file_id=source_file.id,
                dataset_code=item.dataset,
                schema_version=item.schema_version,
                sheet=item.sheet,
                source_row=item.source_row,
                normalized_payload=item.payload.model_dump(mode="json")
                if item.payload
                else {},
                validation_status=item.status,
                fingerprint=item.fingerprint,
                unit_id=item.unit_id,
                unit_version=item.unit_version,
                record_id=item.record_id,
            )
        )
    db.flush()
    for issue in result.issues:
        db.add(
            DataHubImportIssue(
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                import_id=row.id,
                import_row_id=row_ids.get((issue.sheet, issue.source_row)),
                sheet=issue.sheet,
                source_row=issue.source_row,
                column=issue.column,
                severity=issue.severity,
                stable_error_code=issue.code,
                message=issue.message,
            )
        )
    fresh, *_ = revalidate(db, principal, scope)
    expired = now(db) >= row.preview_expires_at
    row.status = (
        "EXPIRED"
        if expired
        else ("REJECTED" if result.error_count else "READY_FOR_CONFIRMATION")
    )
    row.result_code = (
        "PREVIEW_EXPIRED"
        if expired
        else ("VALIDATION_REJECTED" if result.error_count else "PREVIEW_READY")
    )
    row.row_count, row.error_count, row.warning_count = (
        len(result.rows),
        result.error_count,
        result.warning_count,
    )
    row.skipped_count = sum(item.status == "SKIPPED" for item in result.rows)
    row.validated_at, row.updated_at = now(db), now(db)
    row.finished_at = now(db) if expired or result.error_count else None
    row.version += 1
    db.flush()
    audit(
        db,
        request,
        fresh,
        scope,
        row,
        "datahub.import.expired" if expired else "datahub.import.validated",
        before,
    )
    return summary(row)
