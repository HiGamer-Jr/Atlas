"""Current-rights projections. Never return retained objects or raw paths."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.datahub.catalog import DATASETS
from app.datahub.connectors.excel import ExcelConnector
from app.datahub.models import (
    DataHubComexReference,
    DataHubDemand,
    DataHubImport,
    DataHubImportFile,
    DataHubImportIssue,
    DataHubImportRow,
    DataHubPartner,
    DataHubProduct,
    DataHubStockPosition,
)
from app.datahub.policy import UNIT_DATASETS, authorize_selection
from app.datahub.schemas import (
    ExportInput,
    ImportDetail,
    ImportIssueView,
    ImportPage,
    ImportQuery,
    ImportRowView,
    PagedIssues,
    PagedRows,
)
from app.datahub.services import summary
from app.datahub.types import (
    DatasetCode,
    NormalizedRow,
    Operation,
    WorkbookContext,
    WorkbookDownload,
)
from app.tenancy.contexts import now


def selection_for(
    db,
    principal,
    scope,
    operation=Operation.READ,
    template="COORDENACAO",
    version=1,
    nodes=(),
):
    settings = db.info.get("settings")
    if settings is not None and not settings.datahub_enabled:
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    return authorize_selection(
        db, principal, scope, operation, template, version, nodes
    )


def visible_imports(db, principal, scope):
    selected = selection_for(db, principal, scope)
    unit_ids = tuple(u.id for u in selected.units)
    rows = DataHubImportRow
    forbidden = exists(
        select(rows.id).where(
            rows.import_id == DataHubImport.id,
            or_(
                rows.dataset_code.not_in(selected.datasets),
                and_(
                    rows.dataset_code.in_(UNIT_DATASETS),
                    or_(
                        and_(rows.unit_id.is_not(None), rows.unit_id.not_in(unit_ids)),
                        and_(
                            rows.unit_id.is_(None),
                            DataHubImport.actor_user_id != principal.user_id,
                        ),
                    ),
                ),
            ),
        )
    )
    any_rows = exists(select(rows.id).where(rows.import_id == DataHubImport.id))
    return select(DataHubImport).where(
        DataHubImport.tenant_id == scope.tenant_id,
        DataHubImport.contract_id == scope.contract_id,
        ~forbidden,
        or_(any_rows, DataHubImport.actor_user_id == principal.user_id),
    )


def detail(db, row):
    file = db.scalar(
        select(DataHubImportFile).where(DataHubImportFile.import_id == row.id)
    )
    return ImportDetail(
        **summary(row, db).model_dump(),
        filename=file.name,
        created_at=row.created_at,
        committed_at=row.committed_at,
        actor_user_id=row.actor_user_id,
    )


def list_imports(db: Session, principal, scope, query: ImportQuery) -> ImportPage:
    base = visible_imports(db, principal, scope)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(DataHubImport.created_at.desc(), DataHubImport.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return ImportPage(
        items=[detail(db, r) for r in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


def get_import(db, principal, scope, import_id: UUID) -> ImportDetail:
    row = db.scalar(
        visible_imports(db, principal, scope).where(DataHubImport.id == import_id)
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Importação não encontrada.")
    return detail(db, row)


def list_rows(db, principal, scope, import_id, query: ImportQuery) -> PagedRows:
    get_import(db, principal, scope, import_id)
    base = select(DataHubImportRow).where(
        DataHubImportRow.import_id == import_id,
        DataHubImportRow.tenant_id == scope.tenant_id,
        DataHubImportRow.contract_id == scope.contract_id,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(DataHubImportRow.sheet, DataHubImportRow.source_row)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return PagedRows(
        items=[
            ImportRowView(
                id=r.id,
                dataset=r.dataset_code,
                sheet=r.sheet,
                source_row=r.source_row,
                validation_status=r.validation_status,
                payload=r.normalized_payload,
            )
            for r in rows
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


def list_issues(db, principal, scope, import_id, query: ImportQuery) -> PagedIssues:
    get_import(db, principal, scope, import_id)
    base = select(DataHubImportIssue).where(
        DataHubImportIssue.import_id == import_id,
        DataHubImportIssue.tenant_id == scope.tenant_id,
        DataHubImportIssue.contract_id == scope.contract_id,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    issues = db.scalars(
        base.order_by(DataHubImportIssue.source_row, DataHubImportIssue.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return PagedIssues(
        items=[
            ImportIssueView(
                sheet=r.sheet,
                source_row=r.source_row,
                column=r.column,
                severity=r.severity,
                code=r.stable_error_code,
                message=r.message,
            )
            for r in issues
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


DETAILS = {
    DatasetCode.PRODUCTS: DataHubProduct,
    DatasetCode.PARTNERS: DataHubPartner,
    DatasetCode.DEMANDS: DataHubDemand,
    DatasetCode.STOCK_POSITIONS: DataHubStockPosition,
    DatasetCode.COMEX_REFERENCES: DataHubComexReference,
}


def export_workbook(db, principal, scope, command: ExportInput) -> WorkbookDownload:
    selected = selection_for(
        db,
        principal,
        scope,
        Operation.EXPORT,
        command.template_id,
        command.template_version,
        command.node_ids,
    )
    settings = db.info.get("settings") or Settings()
    budget = settings.datahub_limits.max_export_rows
    units = {u.id: u.code for u in selected.units}
    normalized = []
    for code in selected.datasets:
        model = DETAILS[code]
        query = (
            select(model)
            .where(
                model.tenant_id == scope.tenant_id,
                model.contract_id == scope.contract_id,
            )
            .order_by(model.record_id)
        )
        if code in UNIT_DATASETS:
            query = query.where(model.unit_id.in_(units))
        from app.datahub.catalog import TEMPLATES

        modality = TEMPLATES[selected.template_id].modality
        if code == DatasetCode.DEMANDS and modality is not None:
            query = query.where(DataHubDemand.modalidade == modality)
        remaining = budget - len(normalized)
        records = list(db.scalars(query.limit(remaining + 1)))
        if len(records) > remaining:
            raise ApiError(
                413,
                "EXPORT_LIMIT",
                "A exportação excede o limite permitido. Selecione um escopo menor.",
            )
        definition = DATASETS[code]
        for r in records:
            values = {
                name: getattr(r, name) for name in definition.fields if hasattr(r, name)
            }
            if code in UNIT_DATASETS:
                values["unidade_codigo"] = units[r.unit_id]
                values["produto_codigo"] = db.scalar(
                    select(DataHubProduct.codigo).where(
                        DataHubProduct.record_id == r.product_id,
                        DataHubProduct.tenant_id == scope.tenant_id,
                        DataHubProduct.contract_id == scope.contract_id,
                    )
                )
            if code == DatasetCode.COMEX_REFERENCES:
                values["parceiro_codigo"] = db.scalar(
                    select(DataHubPartner.codigo).where(
                        DataHubPartner.record_id == r.partner_id,
                        DataHubPartner.tenant_id == scope.tenant_id,
                        DataHubPartner.contract_id == scope.contract_id,
                    )
                )
            normalized.append(
                NormalizedRow(
                    code,
                    1,
                    definition.sheet,
                    13,
                    definition.schema.model_validate(values),
                )
            )
    # Recheck after database work, including expiry and unit/module/capabilities.
    selection_for(
        db,
        principal,
        scope,
        Operation.EXPORT,
        command.template_id,
        command.template_version,
        command.node_ids,
    )
    logo = (
        settings.datahub_logo_path
        or Path(__file__).resolve().parents[3] / "frontend/src/assets/hiatlas-light.png"
    )
    context = WorkbookContext(
        selected.tenant_name,
        selected.contract_code,
        selected.role_name,
        ", ".join(u.code for u in selected.units) or "Contrato",
        now(db),
    )
    content = ExcelConnector(logo).generate(selected, context, normalized)
    selection_for(
        db,
        principal,
        scope,
        Operation.EXPORT,
        command.template_id,
        command.template_version,
        command.node_ids,
    )
    return WorkbookDownload(content, "HiAtlas-exportacao.xlsx")


def template_catalog(db, principal, scope):
    from app.datahub.catalog import TEMPLATES
    from app.datahub.schemas import TemplateCatalog, TemplateView, UnitView

    current = selection_for(db, principal, scope)
    items = []
    for definition in TEMPLATES.values():
        permitted = None
        flags = {}
        for operation in (Operation.TEMPLATE, Operation.IMPORT, Operation.EXPORT):
            try:
                selected = selection_for(
                    db, principal, scope, operation, definition.code, definition.version
                )
                permitted = permitted or selected
                flags[operation] = True
            except ApiError as exc:
                if exc.status != 403:
                    raise
                flags[operation] = False
        items.append(
            TemplateView(
                id=definition.code,
                version=definition.version,
                label=definition.label,
                available=permitted is not None,
                can_download=flags[Operation.TEMPLATE],
                can_import=flags[Operation.IMPORT],
                can_export=flags[Operation.EXPORT],
                datasets=[str(d) for d in permitted.datasets] if permitted else [],
            )
        )
    return TemplateCatalog(
        items=items,
        profile=current.role_name,
        units=[UnitView(id=u.id, code=u.code, name=u.name) for u in current.units],
    )


def download_template(db, principal, scope, template_id, command):
    selected = selection_for(
        db,
        principal,
        scope,
        Operation.TEMPLATE,
        template_id,
        command.template_version,
        command.node_ids,
    )
    settings = db.info["settings"]
    logo = (
        settings.datahub_logo_path
        or Path(__file__).resolve().parents[3] / "frontend/src/assets/hiatlas-light.png"
    )
    context = WorkbookContext(
        selected.tenant_name,
        selected.contract_code,
        selected.role_name,
        ", ".join(u.code for u in selected.units) or "Contrato",
        now(db),
    )
    content = ExcelConnector(logo).generate(selected, context, ())
    selection_for(
        db,
        principal,
        scope,
        Operation.TEMPLATE,
        template_id,
        command.template_version,
        command.node_ids,
    )
    return WorkbookDownload(content, "HiAtlas-modelo.xlsx")
