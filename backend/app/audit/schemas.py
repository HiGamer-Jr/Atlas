from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

PlatformRole = Literal["PLATFORM_ADMIN", "PLATFORM_SUPPORT"]


class IdentitySnapshot(BaseModel):
    """Allowlisted identity state: no free-form credential/payload fields."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    user_id: UUID
    active: bool
    blocked: bool
    platform_role: PlatformRole | None = None


class AuditInput(BaseModel):
    """Internal service input, never a request-body schema."""

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )
    actor_id: UUID
    actor_role: PlatformRole
    tenant_id: UUID | None = None
    contract_id: UUID | None = None
    action: Literal[
        "identity.bootstrap",
        "platform.role.changed",
        "platform.operator.status.changed",
    ]
    outcome: Literal["SUCCESS", "DENIED", "FAILURE"] = "SUCCESS"
    entity_type: Literal["user", "platform_role"]
    entity_id: UUID
    before: IdentitySnapshot | None = None
    after: IdentitySnapshot | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    reference: str | None = Field(default=None, min_length=1, max_length=200)
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.tenant_id is None) != (self.contract_id is None):
            raise ValueError("tenant_id and contract_id must be supplied together")
        return self
