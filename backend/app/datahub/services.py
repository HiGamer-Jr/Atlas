"""Data Hub mutations. Transaction ownership always remains with the caller."""

import hashlib
import re
import unicodedata
from datetime import timedelta
from uuid import UUID, uuid4

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
from app.datahub.schemas import ConfirmationInput, ConfirmationResult, ImportSummary
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
    transaction = db.get_transaction()
    if (
        transaction is None
        or transaction.origin.name != "BEGIN"
        or db.in_nested_transaction()
    ):
        raise ApiError(
            500, "TRANSACTION_BOUNDARY_INVALID", "Unidade de trabalho inválida."
        )
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
    event.listen(db, "after_transaction_end", rollback_file)
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


def confirm_import(
    db: Session,
    request: Request,
    principal: Principal,
    scope: AccessScope,
    import_id: UUID,
    command: ConfirmationInput,
) -> ConfirmationResult:
    from types import MappingProxyType

    from pydantic import ValidationError

    from app.datahub.catalog import DATASETS
    from app.datahub.duplicates import fingerprint
    from app.datahub.models import (
        DataHubComexReference,
        DataHubDemand,
        DataHubPartner,
        DataHubProduct,
        DataHubRecord,
        DataHubStockPosition,
    )
    from app.datahub.normalization import normalize_row
    from app.datahub.types import DatasetCode, ParsedRow
    from app.identity.tokens import lifecycle_lock

    if not request.app.state.settings.datahub_enabled:
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    lifecycle_lock(db)
    bound = select(DataHubImport).where(
        DataHubImport.id == import_id,
        DataHubImport.tenant_id == scope.tenant_id,
        DataHubImport.contract_id == scope.contract_id,
        DataHubImport.access_context_id == scope.id,
        DataHubImport.auth_session_id == principal.session_id,
        DataHubImport.actor_user_id == principal.user_id,
    )
    candidate = db.scalar(bound)
    if candidate is None:
        raise ApiError(404, "NOT_FOUND", "Importação não encontrada.")
    authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        candidate.template_id,
        candidate.template_version,
        (),
    )
    row = db.scalar(bound.with_for_update().execution_options(populate_existing=True))
    # Locks may have waited. Re-evaluate every dataset/module and all unit rights.
    selection = authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        row.template_id,
        row.template_version,
        (),
    )
    stored = tuple(
        db.scalars(
            select(DataHubImportRow)
            .where(
                DataHubImportRow.import_id == row.id,
                DataHubImportRow.tenant_id == scope.tenant_id,
                DataHubImportRow.contract_id == scope.contract_id,
            )
            .order_by(DataHubImportRow.sheet, DataHubImportRow.source_row)
            .with_for_update()
        )
    )
    if not {r.dataset_code for r in stored} <= set(selection.datasets):
        raise ApiError(403, "DATASET_DENIED", "Datasets não autorizados.")
    units = {u.id: u for u in selection.units}
    if any(r.unit_id is not None and r.unit_id not in units for r in stored):
        raise ApiError(403, "UNIT_SCOPE_DENIED", "Escopo indisponível.")
    if row.status == "COMMITTED":
        if (
            row.idempotency_key != command.idempotency_key
            or row.version != command.expected_version + 1
        ):
            raise ApiError(
                409,
                "CONFIRMATION_CONFLICT",
                "A confirmação não corresponde ao resultado existente.",
            )
        return ConfirmationResult.model_validate(summary(row).model_dump())
    if now(db) >= row.preview_expires_at:
        raise ApiError(
            409, "PREVIEW_EXPIRED", "O preview expirou. Gere uma nova importação."
        )
    if (
        row.status != "READY_FOR_CONFIRMATION"
        or row.version != command.expected_version
        or not stored
    ):
        raise ApiError(
            409,
            "PREVIEW_CONFLICT",
            "O preview não pode ser confirmado. Gere uma nova importação.",
        )
    if any(
        r.unit_id is not None and units[r.unit_id].version != r.unit_version
        for r in stored
    ):
        raise ApiError(
            409, "UNIT_CHANGED", "O escopo foi alterado. Gere uma nova importação."
        )
    parsed_rows = []
    for source in stored:
        if source.validation_status not in {"VALID", "SKIPPED"}:
            raise ApiError(
                409, "PREVIEW_CONFLICT", "O preview não pode ser confirmado."
            )
        definition = DATASETS[DatasetCode(source.dataset_code)]
        try:
            payload = normalize_row(definition, source.normalized_payload)
        except ValidationError:
            raise ApiError(
                409, "PREVIEW_CHANGED", "O preview precisa ser gerado novamente."
            ) from None
        if fingerprint(definition.code, payload, source.unit_id) != source.fingerprint:
            raise ApiError(
                409, "PREVIEW_CHANGED", "O preview precisa ser gerado novamente."
            )
        parsed_rows.append(
            ParsedRow(
                definition.code,
                source.schema_version,
                source.sheet,
                source.source_row,
                MappingProxyType(payload.model_dump()),
            )
        )
    # Freeze referenced informational records as well as the import. Scope predicates
    # precede locks; no valid foreign ID is returned through a reference lookup.
    for cls, field in (
        (DataHubProduct, "produto_codigo"),
        (DataHubPartner, "parceiro_codigo"),
    ):
        codes = {r.values[field] for r in parsed_rows if field in r.values}
        if codes:
            list(
                db.scalars(
                    select(cls)
                    .where(
                        cls.tenant_id == scope.tenant_id,
                        cls.contract_id == scope.contract_id,
                        cls.codigo.in_(codes),
                    )
                    .order_by(cls.record_id)
                    .with_for_update()
                )
            )
    fresh, *_ = revalidate(db, principal, scope)
    selection = authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        row.template_id,
        row.template_version,
        (),
    )
    if now(db) >= row.preview_expires_at:
        raise ApiError(
            409, "PREVIEW_EXPIRED", "O preview expirou. Gere uma nova importação."
        )
    parsed = ParsedWorkbook(
        row.template_id,
        row.template_version,
        tuple(dict.fromkeys(r.dataset for r in parsed_rows)),
        tuple(parsed_rows),
        (),
        0,
        0,
    )
    db.info.update(datahub_scope=scope, datahub_principal=principal)
    validated = validate_rows(db, selection, parsed)
    if validated.error_count:
        raise ApiError(
            409, "DATA_CONFLICT", "Os dados foram alterados. Gere uma nova importação."
        )
    before = snapshot(row)
    by_source = {(r.sheet, r.source_row): r for r in stored}
    resolved = {}
    detail_types = {
        DatasetCode.PRODUCTS: DataHubProduct,
        DatasetCode.PARTNERS: DataHubPartner,
        DatasetCode.DEMANDS: DataHubDemand,
        DatasetCode.STOCK_POSITIONS: DataHubStockPosition,
        DatasetCode.COMEX_REFERENCES: DataHubComexReference,
    }
    # Base datasets precede dependent ones, regardless of workbook sheet order.
    ordered = sorted(
        validated.rows,
        key=lambda r: (
            r.dataset not in (DatasetCode.PRODUCTS, DatasetCode.PARTNERS),
            r.sheet,
            r.source_row,
        ),
    )
    inserted, skipped = 0, 0
    for item in ordered:
        source = by_source[(item.sheet, item.source_row)]
        key = (item.dataset, item.key)
        identity = item.record_id or resolved.get(key)
        if item.status == "SKIPPED" and identity is not None:
            skipped += 1
            source.record_id, source.validation_status = identity, "SKIPPED"
            resolved[key] = identity
            continue
        if item.status != "VALID":
            raise ApiError(
                409, "DATA_CONFLICT", "O preview precisa ser gerado novamente."
            )
        identity = uuid4()
        db.add(
            DataHubRecord(
                id=identity,
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                dataset_code=item.dataset,
                schema_version=item.schema_version,
                business_key=item.key,
                fingerprint=item.fingerprint,
                source_import_id=row.id,
                source_file_id=source.file_id,
                source_row_id=source.id,
                version=1,
            )
        )
        flush_records(db)
        values = item.payload.model_dump()
        if "unidade_codigo" in values:
            values.pop("unidade_codigo")
            values["unit_id"] = item.unit_id
        for field, code, cls, output in (
            ("produto_codigo", DatasetCode.PRODUCTS, DataHubProduct, "product_id"),
            ("parceiro_codigo", DatasetCode.PARTNERS, DataHubPartner, "partner_id"),
        ):
            if field in values:
                reference_code = values.pop(field)
                target = resolved.get((code, reference_code))
                if target is None:
                    target = db.scalar(
                        select(cls.record_id).where(
                            cls.tenant_id == scope.tenant_id,
                            cls.contract_id == scope.contract_id,
                            cls.codigo == reference_code,
                            cls.ativo.is_(True),
                        )
                    )
                if target is None:
                    raise ApiError(
                        409, "REFERENCE_CHANGED", "Uma referência foi alterada."
                    )
                values[output] = target
        cls = detail_types.get(item.dataset)
        if cls is None:
            raise ApiError(403, "DATASET_DENIED", "Dataset não autorizado.")
        db.add(
            cls(
                record_id=identity,
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                dataset_code=item.dataset,
                **values,
            )
        )
        flush_records(db)
        source.record_id, source.validation_status = identity, "VALID"
        resolved[key] = identity
        inserted += 1
    fresh, *_ = revalidate(db, principal, scope)
    authorize_selection(
        db,
        principal,
        scope,
        Operation.IMPORT,
        row.template_id,
        row.template_version,
        (),
    )
    if now(db) >= row.preview_expires_at:
        raise ApiError(
            409, "PREVIEW_EXPIRED", "O preview expirou. Gere uma nova importação."
        )
    row.status, row.result_code = "COMMITTED", "IMPORT_COMMITTED"
    row.inserted_count, row.skipped_count = inserted, skipped
    row.idempotency_key, row.committed_at, row.finished_at = (
        command.idempotency_key,
        now(db),
        now(db),
    )
    row.version += 1
    db.flush()
    audit(db, request, fresh, scope, row, "datahub.import.committed", before)
    return ConfirmationResult.model_validate(summary(row).model_dump())


def flush_records(db):
    from sqlalchemy.exc import IntegrityError

    try:
        db.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ApiError(
                409,
                "DATA_CONFLICT",
                "Os dados não podem ser confirmados. Gere uma nova importação.",
            ) from None
        raise
