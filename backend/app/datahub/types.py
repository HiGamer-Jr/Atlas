from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.datahub.schemas import NormalizedPayload


class DatasetCode(StrEnum):
    PRODUCTS = "PRODUCTS"
    PARTNERS = "PARTNERS"
    DEMANDS = "DEMANDS"
    STOCK_POSITIONS = "STOCK_POSITIONS"
    COMEX_REFERENCES = "COMEX_REFERENCES"
    FINANCIAL_FORECASTS = "FINANCIAL_FORECASTS"


class Operation(StrEnum):
    READ = "READ"
    TEMPLATE = "TEMPLATE"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class ImportStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DatasetDefinition:
    code: DatasetCode
    version: int
    label: str
    sheet: str
    schema: type[BaseModel]
    business_key_fields: tuple[str, ...]
    module_code: str | None = None
    sensitive: bool = False

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(self.schema.model_fields)


@dataclass(frozen=True)
class TemplateDefinition:
    code: str
    version: int
    label: str
    datasets: tuple[DatasetCode, ...]
    importable: bool = True
    modality: str | None = None


@dataclass(frozen=True)
class AuthorizedUnit:
    id: UUID
    code: str
    name: str
    version: int


@dataclass(frozen=True)
class AuthorizedSelection:
    template_id: str
    template_version: int
    datasets: tuple[DatasetCode, ...]
    role_name: str
    units: tuple[AuthorizedUnit, ...]
    tenant_name: str
    contract_code: str
    environment: str


class WorkbookLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    max_uncompressed_bytes: int = Field(
        default=50 * 1024 * 1024, ge=1, le=500 * 1024 * 1024
    )
    max_entries: int = Field(default=1000, ge=1, le=10000)
    max_sheets: int = Field(default=12, ge=1, le=30)
    max_rows: int = Field(default=10000, ge=1, le=100000)
    max_cells: int = Field(default=250000, ge=1, le=1000000)
    preview_seconds: int = Field(default=1800, ge=1, le=86400)
    raw_seconds: int = Field(default=86400, ge=1, le=604800)
    orphan_grace_seconds: int = Field(default=3600, ge=60, le=86400)
    page_size: int = Field(default=50, ge=1, le=100)
    max_page_size: int = Field(default=100, ge=1, le=100)
    max_export_rows: int = Field(default=10000, ge=1, le=100000)


@dataclass(frozen=True)
class WorkbookContext:
    company: str
    contract: str
    role: str
    unit_scope: str
    generated_at: datetime


@dataclass(frozen=True)
class NormalizedRow:
    dataset: DatasetCode
    schema_version: int
    sheet: str
    source_row: int
    payload: NormalizedPayload


CellValue = str | bool | int | float | Decimal | date | datetime | None


@dataclass(frozen=True)
class ParsedRow:
    dataset: DatasetCode
    schema_version: int
    sheet: str
    source_row: int
    values: Mapping[str, CellValue]


@dataclass(frozen=True)
class WorkbookIssue:
    code: str
    message: str
    sheet: str | None = None
    source_row: int | None = None
    column: str | None = None
    severity: str = "ERROR"


@dataclass(frozen=True)
class ParsedWorkbook:
    template_id: str
    template_version: int
    datasets: tuple[DatasetCode, ...]
    rows: tuple[ParsedRow, ...]
    issues: tuple[WorkbookIssue, ...]
    sheet_count: int
    entry_count: int
