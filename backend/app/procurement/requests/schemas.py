"""Closed public representations of private purchase request records."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RequestStatus = Literal[
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
Priority = Literal["NORMAL", "HIGH", "URGENT"]
UomCode = Literal["UN", "KG", "G", "L", "ML", "M", "M2", "M3", "CX", "PCT"]
ApprovalMode = Literal["REQUIRED", "NOT_REQUIRED"]
ApprovalDecisionKind = Literal["HUMAN", "POLICY_WAIVER"]


class ClosedSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, str_strip_whitespace=True
    )


class ApprovalPolicyView(ClosedSchema):
    approval_mode: ApprovalMode = "REQUIRED"
    version: int = Field(default=0, ge=0)


class ActorView(ClosedSchema):
    membership_id: UUID
    user_id: UUID
    display_name: str


class RequestingNodeView(ClosedSchema):
    id: UUID
    name: str
    code: str
    kind: str


class BuyerCandidateView(ClosedSchema):
    membership_id: UUID
    display_name: str


class ItemView(ClosedSchema):
    id: UUID
    position: int
    description: str
    specification: str
    requested_quantity: str
    fulfilled_quantity: str
    remaining_quantity: str
    uom_code: UomCode
    created_at: datetime
    updated_at: datetime


class AttachmentView(ClosedSchema):
    id: UUID
    item_id: UUID | None
    filename: str
    media_type: str
    digest: str
    size: int
    uploader_membership_id: UUID
    created_at: datetime


class RequestView(ClosedSchema):
    schema_version: Literal[1] = 1
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    requester: ActorView
    requesting_node: RequestingNodeView
    buyer: BuyerCandidateView | None
    title: str
    description: str
    justification: str
    priority: Priority
    needed_on: date | None
    notes: str
    status: RequestStatus
    version: int = Field(ge=1)
    fulfillment_state: Literal["NONE", "PARTIAL", "COMPLETE"] = "NONE"
    approval_mode: ApprovalMode | None = None
    approval_policy_version: int | None = Field(default=None, ge=0)
    approval_decision_kind: ApprovalDecisionKind | None = None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None
    triage_started_at: datetime | None = None
    approval_requested_at: datetime | None = None
    approved_at: datetime | None = None
    assigned_at: datetime | None = None
    fulfillment_started_at: datetime | None = None
    fulfilled_at: datetime | None = None
    closed_at: datetime | None = None
    items: list[ItemView] = Field(default_factory=list, max_length=100)
    attachments: list[AttachmentView] = Field(default_factory=list, max_length=10)


class RequestEventPayload(ClosedSchema):
    """Typed bounded business evidence; bytes and authorization contexts never appear."""

    schema_version: Literal[1] = 1
    from_status: RequestStatus | None = None
    to_status: RequestStatus | None = None
    item_id: UUID | None = None
    entry_id: UUID | None = None
    original_entry_id: UUID | None = None
    attachment_id: UUID | None = None
    buyer_membership_id: UUID | None = None
    quantity: str | None = Field(default=None, max_length=32)
    uom_code: UomCode | None = None
    text: str | None = Field(default=None, max_length=4000)
    approval_mode: ApprovalMode | None = None
    approval_policy_version: int | None = Field(default=None, ge=0)
    approval_decision_kind: ApprovalDecisionKind | None = None
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class TransitionEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    from_status: RequestStatus | None = None
    to_status: RequestStatus
    approval_mode: ApprovalMode | None = None
    approval_policy_version: int | None = Field(default=None, ge=0)
    approval_decision_kind: ApprovalDecisionKind | None = None
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AssignmentEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    buyer_membership_id: UUID


class ItemsEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    item_ids: list[UUID] = Field(default_factory=list, max_length=100)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class NoteEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    text: str = Field(min_length=1, max_length=4000)
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class QuantityEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    item_id: UUID
    entry_id: UUID
    original_entry_id: UUID | None = None
    quantity: str = Field(max_length=32)
    uom_code: UomCode


class AttachmentEventPayload(ClosedSchema):
    schema_version: Literal[1] = 1
    from_status: RequestStatus
    attachment_id: UUID
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


ClosedRequestEventPayload = (
    TransitionEventPayload
    | AssignmentEventPayload
    | ItemsEventPayload
    | NoteEventPayload
    | QuantityEventPayload
    | AttachmentEventPayload
)


class RequestHistoryEventView(ClosedSchema):
    id: UUID
    sequence: int = Field(ge=1)
    aggregate_version: int = Field(ge=1)
    action: str
    actor: ActorView
    tenant_role_id: UUID
    tenant_role_code: str
    occurred_at: datetime
    reason: str | None
    payload: ClosedRequestEventPayload


class RequestPage(ClosedSchema):
    items: list[RequestView]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None


class RequestHistoryPage(ClosedSchema):
    items: list[RequestHistoryEventView]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None


class BuyerCandidatePage(ClosedSchema):
    items: list[BuyerCandidateView]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None


class RequestFilters(ClosedSchema):
    visibility: Literal["own", "unit"] = "own"
    status: RequestStatus | None = None
    node_id: UUID | None = None
    requester_membership_id: UUID | None = None
    buyer_membership_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2048)
