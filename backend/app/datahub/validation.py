"""Two-pass normalization and contextual references; only typed payloads survive."""

from dataclasses import dataclass, field
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.datahub.catalog import DATASETS, TEMPLATES
from app.datahub.duplicates import business_key, fingerprint
from app.datahub.models import DataHubPartner, DataHubProduct
from app.datahub.normalization import normalize_row
from app.datahub.repositories import existing_records
from app.datahub.schemas import NormalizedPayload
from app.datahub.types import (
    AuthorizedSelection,
    DatasetCode,
    ParsedWorkbook,
    WorkbookIssue,
)
from app.platform.policy import effective_capabilities
from app.tenancy.schemas import AccessScope


@dataclass
class ValidatedRow:
    dataset: DatasetCode
    schema_version: int
    sheet: str
    source_row: int
    payload: NormalizedPayload | None
    status: str = "VALID"
    key: str | None = None
    fingerprint: str | None = None
    unit_id: UUID | None = None
    unit_version: int | None = None
    record_id: UUID | None = None
    issues: list[WorkbookIssue] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    rows: tuple[ValidatedRow, ...]
    issues: tuple[WorkbookIssue, ...]

    @property
    def error_count(self):
        return sum(i.severity == "ERROR" for i in self.issues)

    @property
    def warning_count(self):
        return sum(i.severity == "WARNING" for i in self.issues)


def add_issue(row, code, column=None, *, warning=False):
    messages = {
        "INVALID_FIELD": "Campo inválido ou obrigatório não preenchido.",
        "REFERENCE_UNAVAILABLE": "Referência indisponível no escopo autorizado.",
        "DUPLICATE_CONFLICT": "Chave duplicada com conteúdo diferente; não será sobrescrita.",
        "DUPLICATE_IDENTICAL": "Linha idêntica será ignorada, preservando a origem existente.",
        "MODALITY_INCOMPATIBLE": "Modalidade incompatível com este template.",
    }
    row.issues.append(
        WorkbookIssue(
            code,
            messages[code],
            row.sheet,
            row.source_row,
            column,
            "WARNING" if warning else "ERROR",
        )
    )
    if not warning:
        row.status, row.fingerprint = "INVALID", None


def compare_duplicates(db, scope, selection, rows):
    for dataset in dict.fromkeys(r.dataset for r in rows):
        candidates = [r for r in rows if r.dataset == dataset and r.status == "VALID"]
        for row in candidates:
            row.key = business_key(row.dataset, row.payload, row.unit_id)
            row.fingerprint = fingerprint(row.dataset, row.payload, row.unit_id)
        records = existing_records(
            db,
            scope,
            dataset,
            (r.key for r in candidates),
            tuple(u.id for u in selection.units),
        )
        seen = {}
        for row in candidates:
            other = seen.get(row.key)
            if other is not None:
                if other.status == "INVALID" or row.fingerprint != other.fingerprint:
                    add_issue(row, "DUPLICATE_CONFLICT")
                    if other.status != "INVALID":
                        add_issue(other, "DUPLICATE_CONFLICT")
                else:
                    row.status, row.record_id = "SKIPPED", other.record_id
                    add_issue(row, "DUPLICATE_IDENTICAL", warning=True)
                continue
            seen[row.key] = row
            existing = records.get(row.key)
            if existing is not None:
                if existing.fingerprint != row.fingerprint:
                    add_issue(row, "DUPLICATE_CONFLICT")
                else:
                    row.status, row.record_id = "SKIPPED", existing.id
                    add_issue(row, "DUPLICATE_IDENTICAL", warning=True)


def validate_rows(
    db: Session, selection: AuthorizedSelection, parsed: ParsedWorkbook
) -> ValidationResult:
    # Scope is server-bound by the service; connector metadata cannot supply it.
    scope: AccessScope = db.info["datahub_scope"]
    principal = db.info["datahub_principal"]
    rows = []
    for source in parsed.rows:
        definition = DATASETS[source.dataset]
        values = {
            k: v
            for k, v in source.values.items()
            if v is not None or definition.schema.model_fields[k].is_required()
        }
        row = ValidatedRow(
            source.dataset, source.schema_version, source.sheet, source.source_row, None
        )
        try:
            row.payload = normalize_row(definition, values)
        except ValidationError as exc:
            for error in exc.errors(include_input=False, include_context=False):
                column = (
                    error["loc"][0]
                    if error["loc"] and error["loc"][0] in definition.fields
                    else None
                )
                add_issue(row, "INVALID_FIELD", column)
        for issue in parsed.issues:
            if issue.sheet == row.sheet and issue.source_row == row.source_row:
                row.issues.append(issue)
                row.status = "INVALID"
        rows.append(row)
    base = [
        r for r in rows if r.dataset in (DatasetCode.PRODUCTS, DatasetCode.PARTNERS)
    ]
    compare_duplicates(db, scope, selection, base)
    caps = effective_capabilities(db, principal, scope)
    refs = {}
    for code, cls, reference_field in (
        (DatasetCode.PRODUCTS, DataHubProduct, "produto_codigo"),
        (DatasetCode.PARTNERS, DataHubPartner, "parceiro_codigo"),
    ):
        allowed = f"datahub.{code.lower()}.read" in caps
        wanted = {
            getattr(r.payload, reference_field)
            for r in rows
            if r.payload is not None and hasattr(r.payload, reference_field)
        }
        existing = (
            set(
                db.scalars(
                    select(cls.codigo).where(
                        cls.tenant_id == scope.tenant_id,
                        cls.contract_id == scope.contract_id,
                        cls.codigo.in_(wanted),
                        cls.ativo.is_(True),
                    )
                )
            )
            if allowed
            else set()
        )
        local = (
            {
                r.payload.codigo
                for r in base
                if r.dataset == code and r.status != "INVALID" and r.payload.ativo
            }
            if allowed
            else set()
        )
        refs[reference_field] = existing | local
    units = {u.code: u for u in selection.units}
    dependent = [
        r for r in rows if r.dataset not in (DatasetCode.PRODUCTS, DatasetCode.PARTNERS)
    ]
    for row in dependent:
        if row.payload is None or row.status == "INVALID":
            continue
        payload = row.payload
        if hasattr(payload, "unidade_codigo"):
            unit = units.get(payload.unidade_codigo)
            if unit is None:
                add_issue(row, "REFERENCE_UNAVAILABLE", "unidade_codigo")
            else:
                row.unit_id, row.unit_version = unit.id, unit.version
        for attr, available in refs.items():
            if hasattr(payload, attr) and getattr(payload, attr) not in available:
                add_issue(row, "REFERENCE_UNAVAILABLE", attr)
        modality = TEMPLATES[selection.template_id].modality
        if (
            hasattr(payload, "modalidade")
            and modality
            and payload.modalidade != modality
        ):
            add_issue(row, "MODALITY_INCOMPATIBLE", "modalidade")
    compare_duplicates(db, scope, selection, dependent)
    issues = tuple(i for r in rows for i in r.issues)
    if not rows:
        issues += (
            WorkbookIssue("EMPTY_IMPORT", "A planilha não contém linhas de dados."),
        )
    return ValidationResult(tuple(rows), issues)
