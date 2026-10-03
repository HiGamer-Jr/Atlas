from datetime import datetime
from typing import Literal
from unicodedata import category, normalize
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tenancy.schemas import Input

GrantType = Literal["FINANCIAL_FISCAL", "MAINTENANCE"]
GrantStatus = Literal["ACTIVE", "ENDED", "EXPIRED", "REVOKED"]


class MaintenanceScope(Input):
    action_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    entity_type: Literal["organization_node"]
    entity_id: UUID | None = None


class GrantStart(Input):
    grant_type: GrantType
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, max_length=100)
    scopes: list[MaintenanceScope] = Field(default_factory=list, max_length=20)

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

    @model_validator(mode="after")
    def typed_scope(self):
        if self.grant_type == "MAINTENANCE" and (not self.reference or not self.scopes):
            raise ValueError("Maintenance requires reference and registered scope")
        if self.grant_type == "FINANCIAL_FISCAL" and self.scopes:
            raise ValueError("Financial grant does not accept maintenance scopes")
        if len({s.action_code for s in self.scopes}) != len(self.scopes):
            raise ValueError("Duplicate scope")
        return self


class GrantEnd(Input):
    expected_version: int = Field(ge=1)


class GrantOperator(BaseModel):
    user_id: UUID
    display_name: str
    platform_role: Literal["PLATFORM_ADMIN"]


class GrantHistoryView(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    tenant_name: str
    contract_code: str
    environment: str
    operator: GrantOperator
    grant_type: GrantType
    status: GrantStatus
    reason: str
    reference: str | None
    scopes: list[MaintenanceScope]
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    revoked_at: datetime | None
    version: int


class GrantView(GrantHistoryView):
    context_id: UUID
    parent_context_id: UUID


class GrantHistoryPage(BaseModel):
    items: list[GrantHistoryView]
    total: int
    limit: int
    offset: int


class MaintenanceActionView(BaseModel):
    action_code: str
    label: str
    entity_type: str


class MaintenanceActions(BaseModel):
    items: list[MaintenanceActionView]


class GrantDenialProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    actor_id: UUID
    actor_role: Literal["PLATFORM_ADMIN"]
    tenant_id: UUID
    contract_id: UUID
    environment: Literal["TEST", "STAGING", "PRODUCTION"]
    grant_id: UUID


class GrantDenialEvent(GrantDenialProvenance):
    request_id: UUID
    reason: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,99}$")
