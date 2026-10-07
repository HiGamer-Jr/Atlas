"""Import evidence and typed informational records; no operational business tables."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps

DATASET_CHECK = "dataset_code IN ('PRODUCTS','PARTNERS','DEMANDS','STOCK_POSITIONS','COMEX_REFERENCES','FINANCIAL_FORECASTS')"


class Scoped:
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    contract_id: Mapped[UUID] = mapped_column(index=True)


class DataHubImport(Scoped, Timestamps, Base):
    __tablename__ = "datahub_imports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_id", "id", name="uq_dh_import_scope"),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "access_context_id",
                "auth_session_id",
                "actor_user_id",
            ],
            [
                "access_contexts.tenant_id",
                "access_contexts.contract_id",
                "access_contexts.id",
                "access_contexts.session_id",
                "access_contexts.actor_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('RECEIVED','VALIDATING','READY_FOR_CONFIRMATION','REJECTED','EXPIRED','COMMITTED','FAILED')",
            name="ck_dh_import_status",
        ),
        CheckConstraint("connector_code='XLSX'", name="ck_dh_import_connector"),
        CheckConstraint(
            "template_id IN ('COORDENACAO','SUPERVISAO','COMPRADOR_NACIONAL','COMPRADOR_INTERNACIONAL','FINANCEIRO','DIRETORIA','LOJA','CENTRO_DISTRIBUICAO')",
            name="ck_dh_import_template",
        ),
        CheckConstraint(
            "template_version=1 AND version>=1", name="ck_dh_import_version"
        ),
        CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="ck_dh_import_digest"),
        CheckConstraint("preview_expires_at>created_at", name="ck_dh_import_expiry"),
        CheckConstraint(
            "validated_at IS NULL OR validated_at>=created_at",
            name="ck_dh_import_validated",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at>=created_at",
            name="ck_dh_import_finished",
        ),
        CheckConstraint(
            "(status='COMMITTED')=(committed_at IS NOT NULL)",
            name="ck_dh_import_committed",
        ),
        CheckConstraint(
            "committed_at IS NULL OR (committed_at>=created_at AND finished_at IS NOT NULL AND idempotency_key IS NOT NULL)",
            name="ck_dh_import_commit_time",
        ),
        CheckConstraint(
            "row_count>=0 AND inserted_count>=0 AND skipped_count>=0 AND error_count>=0 AND warning_count>=0",
            name="ck_dh_import_counts",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    access_context_id: Mapped[UUID]
    auth_session_id: Mapped[UUID]
    actor_user_id: Mapped[UUID]
    connector_code: Mapped[str] = mapped_column(String(16), server_default="XLSX")
    template_id: Mapped[str] = mapped_column(String(32))
    template_version: Mapped[int] = mapped_column(Integer)
    source_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), server_default="RECEIVED")
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    request_id: Mapped[UUID]
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preview_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[UUID | None]
    result_code: Mapped[str] = mapped_column(String(64), server_default="NONE")
    row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    inserted_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    skipped_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    warning_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class DataHubImportFile(Scoped, Timestamps, Base):
    __tablename__ = "datahub_import_files"
    __table_args__ = (
        UniqueConstraint("import_id", name="uq_dh_one_file"),
        UniqueConstraint(
            "tenant_id", "contract_id", "id", "import_id", name="uq_dh_file_scope"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "import_id"],
            [
                "datahub_imports.tenant_id",
                "datahub_imports.contract_id",
                "datahub_imports.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$' AND size_bytes>0", name="ck_dh_file_digest_size"
        ),
        CheckConstraint(
            "raw_expires_at>created_at AND (raw_deleted_at IS NULL OR raw_deleted_at>=created_at)",
            name="ck_dh_file_retention",
        ),
        CheckConstraint(
            "(raw_reference IS NULL)=(raw_deleted_at IS NOT NULL)",
            name="ck_dh_file_reference",
        ),
        CheckConstraint(
            "format='XLSX' AND sheet_count>=0 AND entry_count>=0",
            name="ck_dh_file_metadata",
        ),
        CheckConstraint("retention_policy='TEMPORARY'", name="ck_dh_file_policy"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    import_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(200))
    digest: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(8), server_default="XLSX")
    sheet_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    entry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    raw_reference: Mapped[UUID | None]
    retention_policy: Mapped[str] = mapped_column(
        String(16), server_default="TEMPORARY"
    )
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataHubImportRow(Scoped, Timestamps, Base):
    __tablename__ = "datahub_import_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "unit_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
            name="fk_dh_row_unit",
        ),
        CheckConstraint(
            "(unit_id IS NULL)=(unit_version IS NULL) AND (unit_version IS NULL OR unit_version>0)",
            name="ck_dh_row_unit_version",
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "id",
            "import_id",
            "file_id",
            "dataset_code",
            name="uq_dh_row_origin",
        ),
        UniqueConstraint(
            "tenant_id", "contract_id", "id", "import_id", name="uq_dh_row_issue_scope"
        ),
        UniqueConstraint("import_id", "sheet", "source_row", name="uq_dh_source_row"),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "file_id", "import_id"],
            [
                "datahub_import_files.tenant_id",
                "datahub_import_files.contract_id",
                "datahub_import_files.id",
                "datahub_import_files.import_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "record_id", "dataset_code"],
            [
                "datahub_records.tenant_id",
                "datahub_records.contract_id",
                "datahub_records.id",
                "datahub_records.dataset_code",
            ],
            name="fk_dh_row_record",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        CheckConstraint(DATASET_CHECK, name="ck_dh_row_dataset"),
        CheckConstraint(
            "schema_version=1 AND source_row>=13", name="ck_dh_row_schema_position"
        ),
        CheckConstraint(
            "validation_status IN ('VALID','INVALID','SKIPPED')",
            name="ck_dh_row_status",
        ),
        CheckConstraint(
            "jsonb_typeof(normalized_payload)='object'", name="ck_dh_row_payload"
        ),
        CheckConstraint(
            "fingerprint IS NULL OR fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_dh_row_fingerprint",
        ),
        CheckConstraint(
            "validation_status='INVALID' OR fingerprint IS NOT NULL",
            name="ck_dh_row_valid_digest",
        ),
        CheckConstraint(
            "validation_status<>'INVALID' OR record_id IS NULL",
            name="ck_dh_row_invalid_record",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    import_id: Mapped[UUID]
    file_id: Mapped[UUID]
    dataset_code: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    sheet: Mapped[str] = mapped_column(String(31))
    source_row: Mapped[int] = mapped_column(Integer)
    normalized_payload: Mapped[dict] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    unit_id: Mapped[UUID | None]
    unit_version: Mapped[int | None]
    record_id: Mapped[UUID | None]


class DataHubImportIssue(Scoped, Timestamps, Base):
    __tablename__ = "datahub_import_issues"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "import_id"],
            [
                "datahub_imports.tenant_id",
                "datahub_imports.contract_id",
                "datahub_imports.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "import_row_id", "import_id"],
            [
                "datahub_import_rows.tenant_id",
                "datahub_import_rows.contract_id",
                "datahub_import_rows.id",
                "datahub_import_rows.import_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("severity IN ('ERROR','WARNING')", name="ck_dh_issue_severity"),
        CheckConstraint(
            "stable_error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_dh_issue_code"
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    import_id: Mapped[UUID]
    import_row_id: Mapped[UUID | None]
    sheet: Mapped[str | None] = mapped_column(String(31))
    source_row: Mapped[int | None] = mapped_column(Integer)
    column: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(8))
    stable_error_code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(300))


class DataHubRecord(Scoped, Timestamps, Base):
    __tablename__ = "datahub_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "id",
            "dataset_code",
            name="uq_dh_record_scope_kind",
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "dataset_code",
            "business_key",
            name="uq_dh_record_business_key",
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "source_row_id",
                "source_import_id",
                "source_file_id",
                "dataset_code",
            ],
            [
                "datahub_import_rows.tenant_id",
                "datahub_import_rows.contract_id",
                "datahub_import_rows.id",
                "datahub_import_rows.import_id",
                "datahub_import_rows.file_id",
                "datahub_import_rows.dataset_code",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(DATASET_CHECK, name="ck_dh_record_dataset"),
        CheckConstraint("schema_version=1 AND version>=1", name="ck_dh_record_version"),
        CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$' AND length(business_key)>0",
            name="ck_dh_record_key_digest",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    dataset_code: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    business_key: Mapped[str] = mapped_column(String(512))
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_import_id: Mapped[UUID]
    source_file_id: Mapped[UUID]
    source_row_id: Mapped[UUID]
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


def detail_constraints(kind: str):
    return (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "record_id", "dataset_code"],
            [
                "datahub_records.tenant_id",
                "datahub_records.contract_id",
                "datahub_records.id",
                "datahub_records.dataset_code",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "contract_id", "record_id", name=f"uq_dh_{kind.lower()}_scope"
        ),
        CheckConstraint(f"dataset_code='{kind}'", name=f"ck_dh_{kind.lower()}_kind"),
    )


class Detail(Scoped):
    record_id: Mapped[UUID] = mapped_column(primary_key=True)
    dataset_code: Mapped[str] = mapped_column(String(32))


class DataHubProduct(Detail, Base):
    __tablename__ = "datahub_products"
    __table_args__ = detail_constraints("PRODUCTS") + (
        CheckConstraint(
            "unidade_medida IN ('UN','KG','TON','L','M','M2','M3','CX','PAL')",
            name="ck_dh_product_uom",
        ),
    )
    codigo: Mapped[str] = mapped_column(String(64))
    descricao: Mapped[str] = mapped_column(String(200))
    unidade_medida: Mapped[str] = mapped_column(String(8))
    categoria: Mapped[str] = mapped_column(String(120), server_default="")
    ativo: Mapped[bool] = mapped_column(Boolean)


class DataHubPartner(Detail, Base):
    __tablename__ = "datahub_partners"
    __table_args__ = detail_constraints("PARTNERS") + (
        CheckConstraint(
            "tipo IN ('FORNECEDOR','CLIENTE','TRANSPORTADOR') AND pais_iso ~ '^[A-Z]{2}$'",
            name="ck_dh_partner_type_country",
        ),
    )
    codigo: Mapped[str] = mapped_column(String(64))
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(16))
    pais_iso: Mapped[str] = mapped_column(String(2))
    ativo: Mapped[bool] = mapped_column(Boolean)


def unit_fk():
    return ForeignKeyConstraint(
        ["tenant_id", "contract_id", "unit_id"],
        [
            "organization_nodes.tenant_id",
            "organization_nodes.contract_id",
            "organization_nodes.id",
        ],
        ondelete="RESTRICT",
    )


def product_fk():
    return ForeignKeyConstraint(
        ["tenant_id", "contract_id", "product_id"],
        [
            "datahub_products.tenant_id",
            "datahub_products.contract_id",
            "datahub_products.record_id",
        ],
        ondelete="RESTRICT",
    )


class DataHubDemand(Detail, Base):
    __tablename__ = "datahub_demands"
    __table_args__ = detail_constraints("DEMANDS") + (
        unit_fk(),
        product_fk(),
        CheckConstraint(
            "quantidade>0 AND modalidade IN ('NACIONAL','INTERNACIONAL') AND prioridade IN ('BAIXA','NORMAL','ALTA','URGENTE')",
            name="ck_dh_demand_values",
        ),
    )
    codigo: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[UUID]
    unit_id: Mapped[UUID]
    quantidade: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    data_necessidade: Mapped[date] = mapped_column(Date)
    modalidade: Mapped[str] = mapped_column(String(16))
    prioridade: Mapped[str] = mapped_column(String(8))


class DataHubStockPosition(Detail, Base):
    __tablename__ = "datahub_stock_positions"
    __table_args__ = detail_constraints("STOCK_POSITIONS") + (
        unit_fk(),
        product_fk(),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "product_id",
            "unit_id",
            "data_referencia",
            name="uq_dh_stock_position",
        ),
        CheckConstraint("quantidade_disponivel>=0", name="ck_dh_stock_amount"),
    )
    product_id: Mapped[UUID]
    unit_id: Mapped[UUID]
    quantidade_disponivel: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    data_referencia: Mapped[date] = mapped_column(Date)


class DataHubComexReference(Detail, Base):
    __tablename__ = "datahub_comex_references"
    __table_args__ = detail_constraints("COMEX_REFERENCES") + (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "partner_id"],
            [
                "datahub_partners.tenant_id",
                "datahub_partners.contract_id",
                "datahub_partners.record_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "moeda IN ('BRL','USD','EUR','GBP','CNY') AND incoterm IN ('EXW','FCA','CPT','CIP','DAP','DPU','DDP','FAS','FOB','CFR','CIF') AND status IN ('PLANEJADO','EM_ANDAMENTO','CONCLUIDO','CANCELADO')",
            name="ck_dh_comex_values",
        ),
    )
    codigo: Mapped[str] = mapped_column(String(64))
    partner_id: Mapped[UUID]
    moeda: Mapped[str] = mapped_column(String(3))
    incoterm: Mapped[str] = mapped_column(String(3))
    data_prevista: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))


class DataHubFinancialForecast(Detail, Base):
    __tablename__ = "datahub_financial_forecasts"
    __table_args__ = detail_constraints("FINANCIAL_FORECASTS") + (
        unit_fk(),
        CheckConstraint(
            "valor>0 AND moeda IN ('BRL','USD','EUR','GBP','CNY') AND natureza IN ('ENTRADA','SAIDA')",
            name="ck_dh_financial_values",
        ),
    )
    codigo: Mapped[str] = mapped_column(String(64))
    referencia_externa: Mapped[str] = mapped_column(String(128), server_default="")
    unit_id: Mapped[UUID]
    moeda: Mapped[str] = mapped_column(String(3))
    valor: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    vencimento: Mapped[date] = mapped_column(Date)
    natureza: Mapped[str] = mapped_column(String(8))
