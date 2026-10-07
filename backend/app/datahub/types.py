from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


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
