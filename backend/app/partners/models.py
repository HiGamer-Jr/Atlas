from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps


class PartnerOrganization(Timestamps, Base):
    __tablename__ = "partner_organizations"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_partner_organization_name"),
        CheckConstraint(
            "category IN ('TRADE','CUSTOMS_BROKER','LOGISTICS_OPERATOR','FREIGHT_FORWARDER','OTHER')",
            name="ck_partner_organization_category",
        ),
        CheckConstraint("version > 0", name="ck_partner_organization_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PartnerMembership(Timestamps, Base):
    __tablename__ = "partner_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", name="uq_partner_membership_user_org"
        ),
        UniqueConstraint("organization_id", "id", name="uq_partner_membership_scope"),
        CheckConstraint("version > 0", name="ck_partner_membership_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("partner_organizations.id", ondelete="RESTRICT")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    invitation_pending: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PartnerMembershipPermission(Base):
    __tablename__ = "partner_membership_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["partner_memberships.organization_id", "partner_memberships.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "code IN ('partner.processes.read','partner.timeline.read','partner.logistics.update','partner.processes.closure_report','partner.documents.create','partner.documents.read','partner.payment_requests.create','partner.payment_requests.read_org','partner.payment_requests.submit','partner.payment_requests.withdraw')",
            name="ck_partner_permission_code",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class PartnerLifecycleReceipt(Base):
    __tablename__ = "partner_lifecycle_receipts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            "route",
            "target_id",
            "key",
            name="uq_partner_lifecycle_receipt_key",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'", name="ck_partner_lifecycle_receipt_digest"
        ),
        CheckConstraint(
            "status_code BETWEEN 200 AND 299 AND length(btrim(route)) > 0",
            name="ck_partner_lifecycle_receipt_response",
        ),
        CheckConstraint(
            "jsonb_typeof(response_json)='object' AND octet_length(response_json::text)<=65536",
            name="ck_partner_lifecycle_receipt_body",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="RESTRICT")
    )
    route: Mapped[str] = mapped_column(String(200))
    target_id: Mapped[UUID | None]
    key: Mapped[UUID]
    digest: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict] = mapped_column(JSONB)
    status_code: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
