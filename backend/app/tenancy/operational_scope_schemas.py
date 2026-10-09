"""Discovery descriptions are never reusable authorization credentials."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.organization.schemas import ModuleCode, NodeKind


class ScopeTenant(BaseModel):
    id: UUID
    name: str


class ScopeContract(ScopeTenant):
    code: str
    environment: str


class ScopeRole(ScopeTenant):
    code: str


class ScopeNode(ScopeRole):
    kind: NodeKind
    parent_id: UUID | None


class ScopeModule(BaseModel):
    code: ModuleCode
    label: str
    contracted: Literal[True]
    active: bool
    operational_available: bool


class UnitPolicy(BaseModel):
    mode: Literal["ALL", "RESTRICTED"]


class CustomerScope(BaseModel):
    role: ScopeRole
    unit_scope: UnitPolicy
    organization_nodes: list[ScopeNode]
    modules: list[ScopeModule]
    capabilities: list[str]


class OperationalScopeView(BaseModel):
    schema_version: Literal[1] = 1
    actor_kind: Literal["TENANT", "INTERNAL"]
    context_id: UUID
    tenant: ScopeTenant
    contract: ScopeContract
    customer_scope: CustomerScope | None

    @model_validator(mode="after")
    def separate_actors(self):
        if (self.actor_kind == "TENANT") != (self.customer_scope is not None):
            raise ValueError("Invalid actor scope")
        return self
