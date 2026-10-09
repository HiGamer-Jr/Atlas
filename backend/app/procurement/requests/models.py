"""Purchase need aggregate and append-only evidence, physically scoped in PostgreSQL."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps

STATUS_SQL = "('DRAFT','SUBMITTED','IN_TRIAGE','AWAITING_APPROVAL','APPROVED','IN_FULFILLMENT','FULFILLED','CLOSED','REJECTED','CANCELLED')"
UOM_SQL = "('UN','KG','G','L','ML','M','M2','M3','CX','PCT')"


def scoped_fk(columns, table, targets=None):
    return ForeignKeyConstraint(
        ["tenant_id", "contract_id", *columns],
        [
            f"{table}.{name}"
            for name in ["tenant_id", "contract_id", *(targets or columns)]
        ],
        ondelete="RESTRICT",
    )


def request_fk():
    return scoped_fk(["request_id"], "purchase_requests", ["id"])


def actor_fk(prefix="actor"):
    return scoped_fk(
        [f"{prefix}_membership_id", f"{prefix}_user_id"],
        "memberships",
        ["id", "user_id"],
    )


class ScopedRecord:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]


class PurchaseRequest(ScopedRecord, Timestamps, Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "id", name="uq_purchase_request_scope"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        actor_fk("requester"),
        scoped_fk(["buyer_membership_id"], "memberships", ["id"]),
        scoped_fk(
            ["approver_membership_id", "approver_user_id"],
            "memberships",
            ["id", "user_id"],
        ),
        scoped_fk(["requesting_node_id"], "organization_nodes", ["id"]),
        CheckConstraint(f"status IN {STATUS_SQL}", name="ck_purchase_request_status"),
        CheckConstraint(
            "priority IN ('NORMAL','HIGH','URGENT')",
            name="ck_purchase_request_priority",
        ),
        CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 200", name="ck_purchase_request_title"
        ),
        CheckConstraint("version>=1", name="ck_purchase_request_version"),
        CheckConstraint(
            "approval_mode IS NULL OR approval_mode IN ('REQUIRED','NOT_REQUIRED')",
            name="ck_purchase_request_approval_mode",
        ),
        CheckConstraint(
            "(approval_mode IS NULL)=(approval_policy_version IS NULL) AND (approval_policy_version IS NULL OR approval_policy_version>=0)",
            name="ck_purchase_request_policy_version",
        ),
        CheckConstraint(
            "approval_decision_kind IS NULL OR approval_decision_kind IN ('HUMAN','POLICY_WAIVER')",
            name="ck_purchase_request_decision_kind",
        ),
        CheckConstraint(
            "COALESCE("
            + (
                "(approver_membership_id IS NULL)=(approver_user_id IS NULL) AND ((approval_decision_kind IS NULL AND approver_user_id IS NULL) OR (approval_decision_kind='HUMAN' AND approval_mode IS NOT NULL AND approval_mode='REQUIRED' AND approver_user_id IS NOT NULL AND approver_user_id<>requester_user_id) OR (approval_decision_kind='POLICY_WAIVER' AND approval_mode IS NOT NULL AND approval_mode='NOT_REQUIRED' AND approver_user_id IS NULL))"
            )
            + ",false)",
            name="ck_purchase_request_approver",
        ),
        Index(
            "ix_purchase_request_scope_status_time",
            "tenant_id",
            "contract_id",
            "status",
            "created_at",
            "id",
        ),
        Index(
            "ix_purchase_request_scope_requester",
            "tenant_id",
            "contract_id",
            "requester_membership_id",
        ),
        Index(
            "ix_purchase_request_scope_node",
            "tenant_id",
            "contract_id",
            "requesting_node_id",
        ),
        Index(
            "ix_purchase_request_scope_buyer",
            "tenant_id",
            "contract_id",
            "buyer_membership_id",
        ),
        Index("ix_purchase_request_needed_on", "tenant_id", "contract_id", "needed_on"),
    )
    requester_user_id: Mapped[UUID]
    requester_membership_id: Mapped[UUID]
    requesting_node_id: Mapped[UUID]
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(4000), server_default=text("''"))
    justification: Mapped[str] = mapped_column(String(4000), server_default=text("''"))
    priority: Mapped[str] = mapped_column(String(8), server_default=text("'NORMAL'"))
    needed_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(String(4000), server_default=text("''"))
    status: Mapped[str] = mapped_column(String(24), server_default=text("'DRAFT'"))
    buyer_membership_id: Mapped[UUID | None]
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    approval_mode: Mapped[str | None] = mapped_column(String(16))
    approval_policy_version: Mapped[int | None]
    approval_decision_kind: Mapped[str | None] = mapped_column(String(16))
    approver_membership_id: Mapped[UUID | None]
    approver_user_id: Mapped[UUID | None]
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triage_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfillment_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PurchaseRequestItem(ScopedRecord, Timestamps, Base):
    __tablename__ = "purchase_request_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "request_id",
            "id",
            name="uq_purchase_request_item_scope",
        ),
        UniqueConstraint(
            "request_id", "position", name="uq_purchase_request_item_position"
        ),
        request_fk(),
        CheckConstraint(
            "position BETWEEN 1 AND 100", name="ck_purchase_request_item_position"
        ),
        CheckConstraint(
            "requested_quantity>0 AND requested_quantity<1000000000000",
            name="ck_purchase_request_item_quantity",
        ),
        CheckConstraint(f"uom_code IN {UOM_SQL}", name="ck_purchase_request_item_uom"),
        CheckConstraint(
            "length(btrim(description))>0 AND (uom_code NOT IN ('CX','PCT') OR length(btrim(specification))>0)",
            name="ck_purchase_request_item_content",
        ),
        Index(
            "ix_purchase_request_item_request", "tenant_id", "contract_id", "request_id"
        ),
    )
    request_id: Mapped[UUID]
    position: Mapped[int]
    description: Mapped[str] = mapped_column(String(2000))
    specification: Mapped[str] = mapped_column(String(4000), server_default=text("''"))
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    uom_code: Mapped[str] = mapped_column(String(4))


class PurchaseRequestEvent(ScopedRecord, Base):
    __tablename__ = "purchase_request_events"
    __table_args__ = (
        request_fk(),
        actor_fk(),
        scoped_fk(["tenant_role_id"], "tenant_roles", ["id"]),
        UniqueConstraint(
            "request_id", "sequence", name="uq_purchase_request_event_sequence"
        ),
        CheckConstraint(
            "sequence>=1 AND aggregate_version>=1",
            name="ck_purchase_request_event_version",
        ),
        CheckConstraint(
            "jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536",
            name="ck_purchase_request_event_payload",
        ),
        CheckConstraint(
            "length(btrim(action))>0", name="ck_purchase_request_event_action"
        ),
        Index(
            "ix_purchase_request_event_history",
            "tenant_id",
            "contract_id",
            "request_id",
            "sequence",
        ),
    )
    request_id: Mapped[UUID]
    sequence: Mapped[int]
    aggregate_version: Mapped[int]
    action: Mapped[str] = mapped_column(String(100))
    actor_user_id: Mapped[UUID]
    actor_membership_id: Mapped[UUID]
    tenant_role_id: Mapped[UUID]
    tenant_role_code: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(String(2000))
    payload: Mapped[dict] = mapped_column(JSONB)
    audit_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("audit_events.id", ondelete="RESTRICT")
    )


class RequestFulfillmentEntry(ScopedRecord, Base):
    __tablename__ = "request_fulfillment_entries"
    __table_args__ = (
        request_fk(),
        actor_fk(),
        scoped_fk(
            ["request_id", "item_id"], "purchase_request_items", ["request_id", "id"]
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "request_id",
            "item_id",
            "id",
            name="uq_request_fulfillment_entry_scope",
        ),
        scoped_fk(
            ["request_id", "item_id", "original_entry_id"],
            "request_fulfillment_entries",
            ["request_id", "item_id", "id"],
        ),
        UniqueConstraint("original_entry_id", name="uq_request_fulfillment_reversal"),
        CheckConstraint(
            "quantity>0 AND quantity<1000000000000",
            name="ck_request_fulfillment_quantity",
        ),
        CheckConstraint(
            "(sign=1 AND original_entry_id IS NULL) OR (sign=-1 AND original_entry_id IS NOT NULL AND original_entry_id<>id)",
            name="ck_request_fulfillment_sign",
        ),
        CheckConstraint(
            "source_kind='MANUAL_EXTERNAL'", name="ck_request_fulfillment_source"
        ),
        CheckConstraint(f"uom_code IN {UOM_SQL}", name="ck_request_fulfillment_uom"),
        CheckConstraint(
            "aggregate_version>=1 AND length(btrim(evidence))>0 AND length(btrim(reason))>0",
            name="ck_request_fulfillment_evidence",
        ),
        Index(
            "ix_request_fulfillment_item",
            "tenant_id",
            "contract_id",
            "request_id",
            "item_id",
        ),
    )
    request_id: Mapped[UUID]
    item_id: Mapped[UUID]
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    sign: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    uom_code: Mapped[str] = mapped_column(String(4))
    original_entry_id: Mapped[UUID | None]
    actor_user_id: Mapped[UUID]
    actor_membership_id: Mapped[UUID]
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_kind: Mapped[str] = mapped_column(
        String(24), server_default=text("'MANUAL_EXTERNAL'")
    )
    evidence: Mapped[str] = mapped_column(String(4000))
    reason: Mapped[str] = mapped_column(String(2000))
    aggregate_version: Mapped[int]


class RequestAttachment(ScopedRecord, Base):
    __tablename__ = "request_attachments"
    __table_args__ = (
        request_fk(),
        actor_fk("uploader"),
        scoped_fk(
            ["request_id", "item_id"], "purchase_request_items", ["request_id", "id"]
        ),
        CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'", name="ck_request_attachment_digest"
        ),
        CheckConstraint(
            "size BETWEEN 1 AND 5242880 AND size=octet_length(content)",
            name="ck_request_attachment_size",
        ),
        CheckConstraint(
            "media_type IN ('application/pdf','image/png','image/jpeg','text/plain')",
            name="ck_request_attachment_type",
        ),
        CheckConstraint(
            "length(btrim(filename))>0 AND filename !~ '[/\\\\]'",
            name="ck_request_attachment_filename",
        ),
        Index(
            "ix_request_attachment_request", "tenant_id", "contract_id", "request_id"
        ),
    )
    request_id: Mapped[UUID]
    item_id: Mapped[UUID | None]
    uploader_user_id: Mapped[UUID]
    uploader_membership_id: Mapped[UUID]
    filename: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RequestCommandReceipt(ScopedRecord, Base):
    __tablename__ = "request_command_receipts"
    __table_args__ = (
        request_fk(),
        scoped_fk(
            ["access_context_id", "auth_session_id", "actor_user_id"],
            "access_contexts",
            ["id", "session_id", "actor_id"],
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "actor_user_id",
            "access_context_id",
            "route",
            "target_id",
            "idempotency_key",
            name="uq_request_command_receipt_key",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'", name="ck_request_command_receipt_digest"
        ),
        CheckConstraint(
            "COALESCE("
            + (
                "jsonb_typeof(result)='object' AND result ?& ARRAY['schema_version','version','id','status','tenant_id','contract_id'] AND result->>'schema_version'='1' AND (result->>'version')::integer>=1 AND result->>'id'=request_id::text AND result->>'tenant_id'=tenant_id::text AND result->>'contract_id'=contract_id::text AND result->>'status' IN "
                + STATUS_SQL
                + " AND octet_length(result::text)<=4194304"
            )
            + ",false)",
            name="ck_request_command_receipt_result",
        ),
        CheckConstraint(
            "response_status BETWEEN 200 AND 299 AND length(btrim(route))>0",
            name="ck_request_command_receipt_response",
        ),
    )
    request_id: Mapped[UUID]
    actor_user_id: Mapped[UUID]
    access_context_id: Mapped[UUID]
    auth_session_id: Mapped[UUID]
    route: Mapped[str] = mapped_column(String(200))
    target_id: Mapped[UUID | None]
    idempotency_key: Mapped[UUID]
    digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    response_status: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContractRequestPolicy(Timestamps, Base):
    __tablename__ = "contract_request_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "approval_mode IN ('REQUIRED','NOT_REQUIRED')",
            name="ck_contract_request_policy_mode",
        ),
        CheckConstraint("version>=1", name="ck_contract_request_policy_version"),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    contract_id: Mapped[UUID] = mapped_column(primary_key=True)
    approval_mode: Mapped[str] = mapped_column(
        String(16), server_default=text("'REQUIRED'")
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
