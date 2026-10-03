from datetime import datetime
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
    description: str = Field(default="", max_length=2000)
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


class OrganizationNodeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    kind: Literal[
        "COMPANY",
        "BRANCH",
        "UNIT",
        "STORE",
        "DISTRIBUTION_CENTER",
        "WAREHOUSE",
        "OFFICE",
        "WORKSITE",
    ]
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=64)
    parent_id: UUID | None
    active: bool
    version: int = Field(ge=1)


class ContractModuleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    code: Literal["PROCUREMENT", "COMEX", "INVENTORY", "FINANCE", "PROJECTS", "DATAHUB"]
    contracted: bool
    active: bool
    version: int = Field(ge=0)


class MembershipUnitScopeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    node_ids: list[UUID] = Field(max_length=100)
    version: int = Field(ge=1)


class SupportSessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    operator_id: UUID
    operator_role: PlatformRole
    viewed_membership_id: UUID
    viewed_user_id: UUID
    mode: Literal["READ_ONLY"]
    status: Literal["ACTIVE", "ENDED", "EXPIRED", "REVOKED"]
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None


class PrivilegedScopeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    action_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    entity_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    entity_id: UUID | None = None


class PrivilegedGrantSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    operator_id: UUID
    operator_role: Literal["PLATFORM_ADMIN"]
    grant_type: Literal["FINANCIAL_FISCAL", "MAINTENANCE"]
    status: Literal["ACTIVE", "ENDED", "EXPIRED", "REVOKED"]
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    revoked_at: datetime | None
    version: int = Field(ge=1)
    scopes: list[PrivilegedScopeSnapshot] = Field(max_length=20)


class AuditInput(BaseModel):
    """Internal service input, never a request-body schema."""

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )
    support_session_id: UUID | None = None
    actor_id: UUID
    actor_role: PlatformRole | None
    tenant_id: UUID | None = None
    contract_id: UUID | None = None
    action: Literal[
        "privileged_grant.started",
        "privileged_grant.ended",
        "privileged_grant.expired",
        "privileged_grant.revoked",
        "support.session.started",
        "support.session.ended",
        "support.session.expired",
        "support.session.revoked",
        "access.invite.requested",
        "access.invite.resent",
        "access.invite.consumed",
        "access.reset.requested",
        "access.reset.resent",
        "access.reset.consumed",
        "access.sessions.revoked",
        "membership.status.changed",
        "membership.invited",
        "organization.node.created",
        "organization.node.updated",
        "contract.module.updated",
        "membership.unit_scope.updated",
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
        "privileged_grant",
        "support_session",
        "tenant",
        "contract",
        "access_context",
        "tenant_role",
        "organization_node",
        "contract_module",
        "membership",
    ]
    entity_id: UUID
    before: (
        PrivilegedGrantSnapshot
        | SupportSessionSnapshot
        | IdentitySnapshot
        | TenantSnapshot
        | ContractSnapshot
        | ContextSnapshot
        | TenantRoleSnapshot
        | MembershipRoleSnapshot
        | MembershipStateSnapshot
        | OrganizationNodeSnapshot
        | ContractModuleSnapshot
        | MembershipUnitScopeSnapshot
        | None
    ) = None
    after: (
        PrivilegedGrantSnapshot
        | SupportSessionSnapshot
        | IdentitySnapshot
        | TenantSnapshot
        | ContractSnapshot
        | ContextSnapshot
        | TenantRoleSnapshot
        | MembershipRoleSnapshot
        | MembershipStateSnapshot
        | OrganizationNodeSnapshot
        | ContractModuleSnapshot
        | MembershipUnitScopeSnapshot
        | None
    ) = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    reference: str | None = Field(default=None, min_length=1, max_length=200)
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.tenant_id is None) != (self.contract_id is None):
            raise ValueError("tenant_id and contract_id must be supplied together")
        if self.action.startswith("privileged_grant."):
            if (self.tenant_id is None or self.entity_type != "privileged_grant"
                or not isinstance(self.after, PrivilegedGrantSnapshot)
                or self.after.operator_id != self.actor_id or self.after.operator_role != self.actor_role):
                raise ValueError("Privileged action requires typed real operator provenance")
            if self.action != "privileged_grant.started" and not isinstance(self.before, PrivilegedGrantSnapshot):
                raise ValueError("Terminal grant action requires before state")
        if self.action.startswith("support.session."):
            if (
                self.tenant_id is None
                or self.entity_type != "support_session"
                or self.support_session_id != self.entity_id
                or not isinstance(self.after, SupportSessionSnapshot)
                or self.after.operator_id != self.actor_id
                or self.after.operator_role != self.actor_role
            ):
                raise ValueError("Support action requires bound typed provenance")
            if self.action != "support.session.started" and not isinstance(
                self.before, SupportSessionSnapshot
            ):
                raise ValueError("Terminal support action requires before state")
        registered = {
            "organization.node.created": (
                "organization_node",
                OrganizationNodeSnapshot,
            ),
            "organization.node.updated": (
                "organization_node",
                OrganizationNodeSnapshot,
            ),
            "contract.module.updated": ("contract_module", ContractModuleSnapshot),
            "membership.unit_scope.updated": (
                "membership",
                MembershipUnitScopeSnapshot,
            ),
        }.get(self.action)
        if registered:
            entity, snapshot = registered
            if (
                self.tenant_id is None
                or self.entity_type != entity
                or not isinstance(self.after, snapshot)
            ):
                raise ValueError("Action requires its registered scoped snapshot")
            if self.before is not None and not isinstance(self.before, snapshot):
                raise ValueError("Before state must use the registered snapshot")
            if self.action != "organization.node.created" and self.before is None:
                raise ValueError("Update requires a before state")
        return self


class SystemCancellationAuditInput(AuditInput):
    """Narrow system provenance: never impersonate a human for worker revalidation."""

    actor_id: None = None
    actor_role: None = None
    action: Literal["access.invite.invalidated"] = "access.invite.invalidated"
    reason: Literal["POLICY_REVALIDATION"] = "POLICY_REVALIDATION"
