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


class TenantSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    name: str = Field(min_length=1, max_length=200)
    active: bool


class ContractSnapshot(TenantSnapshot):
    tenant_id: UUID
    code: str = Field(min_length=1, max_length=64)
    environment: Literal["TEST", "STAGING", "PRODUCTION"]


class ContextSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    revoked: bool


class TenantRoleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    code: str
    name: str = Field(min_length=1, max_length=200)
    classification: Literal[
        "STANDARD", "ADMINISTRATIVE", "FINANCIAL_FISCAL", "SENSITIVE"
    ]
    support_assignable: bool
    sensitivity_locked: bool
    active: bool
    permissions: list[str]
    version: int


class MembershipRoleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    role_id: UUID
    version: int


class MembershipStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    active: bool
    blocked: bool
    invitation_pending: bool
    version: int


class AuditInput(BaseModel):
    """Internal service input, never a request-body schema."""

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )
    actor_id: UUID
    actor_role: PlatformRole | None
    tenant_id: UUID | None = None
    contract_id: UUID | None = None
    action: Literal[
        "access.invite.requested",
        "access.invite.resent",
        "access.invite.consumed",
        "access.reset.requested",
        "access.reset.resent",
        "access.reset.consumed",
        "access.sessions.revoked",
        "membership.status.changed",
        "membership.invited",
        "tenant.created",
        "contract.created",
        "context.selected",
        "context.closed",
        "tenant.role.created",
        "tenant.role.updated",
        "membership.role.assigned",
        "identity.bootstrap",
        "platform.role.changed",
        "platform.operator.status.changed",
    ]
    outcome: Literal["SUCCESS", "DENIED", "FAILURE"] = "SUCCESS"
    entity_type: Literal[
        "user",
        "platform_role",
        "tenant",
        "contract",
        "access_context",
        "tenant_role",
        "membership",
    ]
    entity_id: UUID
    before: (
        IdentitySnapshot
        | TenantSnapshot
        | ContractSnapshot
        | ContextSnapshot
        | TenantRoleSnapshot
        | MembershipRoleSnapshot
        | MembershipStateSnapshot
        | None
    ) = None
    after: (
        IdentitySnapshot
        | TenantSnapshot
        | ContractSnapshot
        | ContextSnapshot
        | TenantRoleSnapshot
        | MembershipRoleSnapshot
        | MembershipStateSnapshot
        | None
    ) = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    reference: str | None = Field(default=None, min_length=1, max_length=200)
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.tenant_id is None) != (self.contract_id is None):
            raise ValueError("tenant_id and contract_id must be supplied together")
        return self


class SystemCancellationAuditInput(AuditInput):
    """Narrow system provenance: never impersonate a human for worker revalidation."""

    actor_id: None = None
    actor_role: None = None
    action: Literal["access.invite.invalidated"] = "access.invite.invalidated"
    reason: Literal["POLICY_REVALIDATION"] = "POLICY_REVALIDATION"
