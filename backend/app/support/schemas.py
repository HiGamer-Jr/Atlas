from datetime import datetime
from typing import Literal
from unicodedata import category, normalize
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tenancy.schemas import Input


class SupportStart(Input):
    membership_id: UUID
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, max_length=100)
    mode: Literal["READ_ONLY"] = "READ_ONLY"

    @field_validator("reason", "reference", mode="before")
    @classmethod
    def plain_text(cls, value):
        if value is None:
            return None
        if not isinstance(value, str) or any(
            category(char).startswith("C") for char in value
        ):
            raise ValueError("Plain text required")
        return normalize("NFC", value).strip() or None


class SupportOperator(BaseModel):
    user_id: UUID
    display_name: str
    platform_role: Literal["PLATFORM_ADMIN", "PLATFORM_SUPPORT"]


class ViewedMember(BaseModel):
    membership_id: UUID
    user_id: UUID
    display_name: str
    role_id: UUID
    role_name: str


class SupportHistoryView(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    tenant_name: str
    contract_code: str
    environment: str
    operator: SupportOperator
    viewed: ViewedMember
    mode: Literal["READ_ONLY"]
    reason: str
    reference: str | None
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    status: Literal["ACTIVE", "ENDED", "EXPIRED", "REVOKED"]


class SupportSessionView(SupportHistoryView):
    context_id: UUID
    parent_context_id: UUID


class SupportHistoryPage(BaseModel):
    items: list[SupportHistoryView]
    total: int
    limit: int
    offset: int


class EffectiveAccess(BaseModel):
    read_only: Literal[True] = True
    capabilities: list[str]


class WorkspaceModule(BaseModel):
    code: str
    label: str
    contracted: bool
    active: bool
    enabled: bool
    operational_available: bool


class SupportWorkspace(BaseModel):
    effective_access: EffectiveAccess
    modules: list[WorkspaceModule]


class SupportDenialProvenance(BaseModel):
    """Server-only allowlist, populated after exact cookie/HTTP owner binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    actor_id: UUID
    actor_role: Literal["PLATFORM_ADMIN", "PLATFORM_SUPPORT"]
    tenant_id: UUID
    contract_id: UUID
    environment: Literal["TEST", "STAGING", "PRODUCTION"]
    support_session_id: UUID


class SupportDenialEvent(SupportDenialProvenance):
    request_id: UUID
    reason: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,99}$")
