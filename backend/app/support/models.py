"""Persistent support sessions bind the operator, HTTP session and exact target scope."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportSession(Base):
    __tablename__ = "support_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["operator_session_id", "operator_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "viewed_membership_id", "viewed_user_id"],
            [
                "memberships.tenant_id",
                "memberships.contract_id",
                "memberships.id",
                "memberships.user_id",
            ],
            ondelete="RESTRICT",
        ),
        *[
            ForeignKeyConstraint(
                [
                    "tenant_id",
                    "contract_id",
                    name,
                    "operator_session_id",
                    "operator_id",
                ],
                [
                    "access_contexts.tenant_id",
                    "access_contexts.contract_id",
                    "access_contexts.id",
                    "access_contexts.session_id",
                    "access_contexts.actor_id",
                ],
                ondelete="RESTRICT",
            )
            for name in ("parent_context_id", "context_id")
        ],
        UniqueConstraint("context_id", name="uq_support_derived_context"),
        CheckConstraint("mode = 'READ_ONLY'", name="ck_support_mode"),
        CheckConstraint(
            "operator_role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')",
            name="ck_support_operator_role",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','ENDED','EXPIRED','REVOKED')", name="ck_support_status"
        ),
        CheckConstraint(
            "(status='ACTIVE') = (ended_at IS NULL)", name="ck_support_terminal"
        ),
        CheckConstraint(
            "expires_at > started_at AND (ended_at IS NULL OR ended_at >= started_at)",
            name="ck_support_lifetime",
        ),
        CheckConstraint("parent_context_id <> context_id", name="ck_support_contexts"),
        CheckConstraint("operator_id <> viewed_user_id", name="ck_support_target"),
        CheckConstraint(
            "length(btrim(reason)) BETWEEN 3 AND 1000", name="ck_support_reason"
        ),
        CheckConstraint(
            "reference IS NULL OR length(reference) BETWEEN 1 AND 100",
            name="ck_support_reference",
        ),
        Index(
            "uq_support_active_parent",
            "parent_context_id",
            unique=True,
            postgresql_where=text("status='ACTIVE'"),
        ),
        Index("ix_support_scope_time", "tenant_id", "contract_id", "started_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    operator_id: Mapped[UUID]
    operator_session_id: Mapped[UUID]
    operator_role: Mapped[str] = mapped_column(String(32))
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    parent_context_id: Mapped[UUID]
    context_id: Mapped[UUID]
    viewed_membership_id: Mapped[UUID]
    viewed_user_id: Mapped[UUID]
    mode: Mapped[str] = mapped_column(String(16), default="READ_ONLY")
    reason: Mapped[str] = mapped_column(String(1000))
    reference: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
