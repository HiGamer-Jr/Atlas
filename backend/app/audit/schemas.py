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


class RecoverySnapshot(IdentitySnapshot):
    technical_operator: str = Field(min_length=3, max_length=200)
    database_role: str = Field(min_length=1, max_length=200)
    incident_evidence: str = Field(min_length=10, max_length=1000)
    credential_loss_attested: bool = False
    normal_recovery_unavailable: bool = False


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
    mode: Literal["ALL", "RESTRICTED"] = "RESTRICTED"
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


class ProcessingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    run_id: UUID
    action_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"]
    result_code: Literal["NONE", "COMPLETED", "HANDLER_FAILED", "NOT_ELIGIBLE"]
    message_code: Literal["NONE", "COMPLETED", "HANDLER_FAILED", "NOT_ELIGIBLE"]
    version: int = Field(ge=1)


class DataHubImportSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    id: UUID
    status: Literal[
        "RECEIVED",
        "VALIDATING",
        "READY_FOR_CONFIRMATION",
        "REJECTED",
        "EXPIRED",
        "COMMITTED",
        "FAILED",
    ]
    version: int = Field(ge=1)
    template_id: str = Field(max_length=32)
    template_version: int = Field(ge=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)


class RequestAuditChanges(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_mode: Literal["REQUIRED", "NOT_REQUIRED"] | None = None
    approval_policy_version: int | None = Field(default=None, ge=0)
    approval_decision_kind: Literal["HUMAN", "POLICY_WAIVER"] | None = None
    item_ids: list[UUID] = Field(default_factory=list, max_length=100)
    attachment_id: UUID | None = None
    entry_id: UUID | None = None
    quantity: str | None = Field(default=None, max_length=32)


class RequestAuditSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    request_id: UUID
    tenant_id: UUID
    contract_id: UUID
    version: int = Field(ge=1)
    status: Literal[
        "DRAFT",
        "SUBMITTED",
        "IN_TRIAGE",
        "AWAITING_APPROVAL",
        "APPROVED",
        "IN_FULFILLMENT",
        "FULFILLED",
        "CLOSED",
        "REJECTED",
        "CANCELLED",
    ]
    requesting_node_id: UUID
    requester_user_id: UUID
    requester_membership_id: UUID
    buyer_membership_id: UUID | None = None
    actor_membership_id: UUID
    tenant_role_id: UUID
    tenant_role_code: str = Field(max_length=64)
    changes: RequestAuditChanges = Field(default_factory=RequestAuditChanges)


class RequestPolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    approval_mode: Literal["REQUIRED", "NOT_REQUIRED"]
    version: int = Field(ge=0)


class PartnerOrganizationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    schema_version: Literal[1] = 1
    actor_kind: Literal["INTERNAL"] = "INTERNAL"
    partner_org_id: UUID
    name: str = Field(min_length=1, max_length=200)
    category: Literal[
        "TRADE", "CUSTOMS_BROKER", "LOGISTICS_OPERATOR", "FREIGHT_FORWARDER", "OTHER"
    ]
    active: bool
    version: int = Field(ge=1)


class PartnerMembershipSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)
    schema_version: Literal[1] = 1
    actor_kind: Literal["INTERNAL"] = "INTERNAL"
    partner_org_id: UUID
    partner_membership_id: UUID
    user_id: UUID
    active: bool
    blocked: bool
    invitation_pending: bool
    version: int = Field(ge=1)
    permissions: list[str] = Field(max_length=10)


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
        "partner.organization.created",
        "partner.membership.created",
        "partner.membership.replaced",
        "procurement.request.created",
        "procurement.request.draft_updated",
        "procurement.request.submitted",
        "procurement.request.triage_started",
        "procurement.request.approval_requested",
        "procurement.request.approved",
        "procurement.request.approval_waived",
        "procurement.request.rejected",
        "procurement.request.assigned",
        "procurement.request.fulfillment_started",
        "procurement.request.fulfillment_recorded",
        "procurement.request.fulfillment_reversed",
        "procurement.request.fulfilled",
        "procurement.request.cancelled",
        "procurement.request.closed",
        "procurement.request.note_added",
        "procurement.request.attachment_added",
        "procurement.request.attachment_removed",
        "procurement.request_policy.updated",
        "datahub.import.received",
        "datahub.import.validated",
        "datahub.import.failed",
        "datahub.import.committed",
        "datahub.import.expired",
        "maintenance.correction.applied",
        "maintenance.processing.succeeded",
        "maintenance.processing.failed",
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
        "partner_organization",
        "partner_membership",
        "purchase_request",
        "contract_request_policy",
        "datahub_import",
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
        PartnerOrganizationSnapshot
        | PartnerMembershipSnapshot
        | RequestAuditSnapshot
        | RequestPolicySnapshot
        | DataHubImportSnapshot
        | ProcessingSnapshot
        | PrivilegedGrantSnapshot
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
        PartnerOrganizationSnapshot
        | PartnerMembershipSnapshot
        | RequestAuditSnapshot
        | RequestPolicySnapshot
        | DataHubImportSnapshot
        | ProcessingSnapshot
        | PrivilegedGrantSnapshot
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
        if self.action.startswith("procurement.request."):
            if (
                self.tenant_id is None
                or self.entity_type != "purchase_request"
                or self.actor_role is not None
                or not isinstance(self.after, RequestAuditSnapshot)
                or self.after.request_id != self.entity_id
                or self.after.tenant_id != self.tenant_id
                or self.after.contract_id != self.contract_id
            ):
                raise ValueError("Request action requires scoped tenant provenance")
            if self.before is not None and (
                not isinstance(self.before, RequestAuditSnapshot)
                or self.before.request_id != self.entity_id
                or self.before.tenant_id != self.tenant_id
                or self.before.contract_id != self.contract_id
            ):
                raise ValueError(
                    "Request before snapshot must belong to the same aggregate"
                )
            if self.action != "procurement.request.created" and self.before is None:
                raise ValueError("Request update requires before state")
        if self.action == "procurement.request_policy.updated" and (
            self.tenant_id is None
            or self.entity_type != "contract_request_policy"
            or self.entity_id != self.contract_id
            or not isinstance(self.before, RequestPolicySnapshot)
            or not isinstance(self.after, RequestPolicySnapshot)
        ):
            raise ValueError("Policy action requires scoped snapshots")
        if self.action.startswith("datahub.import."):
            if (
                self.tenant_id is None
                or self.entity_type != "datahub_import"
                or not isinstance(self.after, DataHubImportSnapshot)
                or self.after.id != self.entity_id
            ):
                raise ValueError("Data Hub action requires scoped typed provenance")
            if self.action != "datahub.import.received" and (
                not isinstance(self.before, DataHubImportSnapshot)
                or self.before.id != self.entity_id
            ):
                raise ValueError("Data Hub transition requires its previous state")
        if self.action.startswith("privileged_grant."):
            if (
                self.tenant_id is None
                or self.entity_type != "privileged_grant"
                or not isinstance(self.after, PrivilegedGrantSnapshot)
                or self.after.operator_id != self.actor_id
                or self.after.operator_role != self.actor_role
            ):
                raise ValueError(
                    "Privileged action requires typed real operator provenance"
                )
            if self.action != "privileged_grant.started" and not isinstance(
                self.before, PrivilegedGrantSnapshot
            ):
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
        if self.action == "maintenance.processing.failed" and (
            self.tenant_id is None
            or self.entity_type != "organization_node"
            or not isinstance(self.after, ProcessingSnapshot)
            or self.after.status != "FAILED"
            or self.outcome != "FAILURE"
        ):
            raise ValueError("Processing failure requires typed scoped state")
        if self.action.startswith("partner."):
            organization = self.action == "partner.organization.created"
            snapshot_type = (
                PartnerOrganizationSnapshot
                if organization
                else PartnerMembershipSnapshot
            )
            entity_type = (
                "partner_organization" if organization else "partner_membership"
            )

            def snapshot_matches(value):
                return (
                    isinstance(value, snapshot_type)
                    and (
                        value.partner_org_id
                        if organization
                        else value.partner_membership_id
                    )
                    == self.entity_id
                )

            if (
                self.actor_role != "PLATFORM_ADMIN"
                or self.tenant_id is not None
                or self.support_session_id is not None
                or self.entity_type != entity_type
                or not snapshot_matches(self.after)
                or (self.before is not None and not snapshot_matches(self.before))
                or (self.action.endswith(".replaced") and self.before is None)
                or (self.action.endswith(".created") and self.before is not None)
            ):
                raise ValueError("Partner lifecycle requires typed internal provenance")
        registered = {
            "maintenance.correction.applied": (
                "organization_node",
                OrganizationNodeSnapshot,
            ),
            "maintenance.processing.succeeded": (
                "organization_node",
                OrganizationNodeSnapshot,
            ),
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


class RecoveryAuditInput(AuditInput):
    """Offline infrastructure actor; never impersonate the recovered human."""

    actor_id: None = None
    actor_role: None = None
    action: Literal["identity.admin.recovered"] = "identity.admin.recovered"
    entity_type: Literal["user"] = "user"
    environment: Literal["TEST", "STAGING", "PRODUCTION"]
    before: IdentitySnapshot
    after: RecoverySnapshot
    reason: str = Field(min_length=3, max_length=1000)
    reference: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def verified_recovery(self):
        if (
            self.tenant_id is not None
            or self.support_session_id is not None
            or self.before.user_id != self.entity_id
            or self.after.user_id != self.entity_id
            or self.after.platform_role != "PLATFORM_ADMIN"
            or not self.after.active
            or self.after.blocked
            or self.outcome != "SUCCESS"
            or (
                self.after.credential_loss_attested
                and not self.after.normal_recovery_unavailable
            )
        ):
            raise ValueError(
                "Recovery requires its real target and technical provenance"
            )
        return self
