from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NodeKind = Literal[
    "COMPANY",
    "BRANCH",
    "UNIT",
    "STORE",
    "DISTRIBUTION_CENTER",
    "WAREHOUSE",
    "OFFICE",
    "WORKSITE",
]
ModuleCode = Literal[
    "PROCUREMENT", "COMEX", "INVENTORY", "FINANCE", "PROJECTS", "DATAHUB"
]


class ClosedInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, str_strip_whitespace=True
    )


class NodeCreate(ClosedInput):
    kind: NodeKind
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=64)
    parent_id: UUID | None = None
    active: bool = True

    @field_validator("code")
    @classmethod
    def code_format(cls, value):
        import re

        value = value.upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]{0,63}", value):
            raise ValueError("Código inválido.")
        return value


class NodePatch(ClosedInput):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    parent_id: UUID | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def non_nullable(self):
        for field in ("name", "code", "active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("Campo obrigatório.")
        return self


class NodeView(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    parent_id: UUID | None
    parent_name: str | None
    parent_code: str | None
    kind: NodeKind
    name: str
    code: str
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    depth: int
    child_count: int
    active_child_count: int
    scope_membership_count: int
    allowed_actions: list[str]


class NodeList(BaseModel):
    items: list[NodeView]
    total: int
    limit: int
    offset: int


class ModulePatch(ClosedInput):
    contracted: bool
    active: bool
    expected_version: int = Field(ge=0)
    module_id: UUID | None

    @model_validator(mode="after")
    def active_requires_contract(self):
        if self.active and not self.contracted:
            raise ValueError("Módulo ativo deve estar contratado.")
        return self


class ModuleView(BaseModel):
    id: UUID | None
    code: ModuleCode
    label: str
    contracted: bool
    active: bool
    enabled: bool
    operational_available: bool
    version: int
    allowed_actions: list[str]


class ModuleList(BaseModel):
    items: list[ModuleView]


class UnitScopePatch(ClosedInput):
    node_ids: list[UUID] = Field(max_length=100)
    expected_version: int = Field(ge=1)

    @field_validator("node_ids")
    @classmethod
    def unique_nodes(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Unidades duplicadas.")
        return values


class UnitScopeView(BaseModel):
    membership_id: UUID
    node_ids: list[UUID]
    version: int
