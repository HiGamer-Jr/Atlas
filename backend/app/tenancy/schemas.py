from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True
    )


class TenantCreate(Input):
    name: str = Field(min_length=1, max_length=200)


class ContractCreate(TenantCreate):
    code: str = Field(min_length=1, max_length=64)
    environment: Literal["TEST", "STAGING", "PRODUCTION"]


class ContextCreate(Input):
    contract_id: UUID


@dataclass(frozen=True)
class AccessScope:
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    session_id: UUID
    actor_id: UUID


class TenantView(BaseModel):
    id: UUID
    name: str


class ContractView(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    name: str
    code: str
    environment: str


class ContractList(BaseModel):
    items: list[ContractView]


class ContextCreated(BaseModel):
    id: UUID


class ContextView(BaseModel):
    support_session_id: UUID | None = None
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    tenant_name: str
    contract_name: str
    contract_code: str
    environment: str
    expires_at: datetime
    capabilities: list[str]


class MembershipView(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    active: bool
    blocked: bool
    version: int


class ManagedMembershipView(MembershipView):
    display_name: str
    email: str
    role_name: str
    invitation_pending: bool
    allowed_actions: list[str]
    last_access_at: datetime | None
    invitation_status: (
        Literal[
            "QUEUED", "SENT", "FAILED", "CANCELLED", "UNKNOWN", "CONSUMED", "EXPIRED"
        ]
        | None
    )
