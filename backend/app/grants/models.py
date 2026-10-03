"""Privileged grants preserve exact operator, HTTP session and context ownership."""

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


class TemporaryPrivilegedGrant(Base):
    __tablename__ = "temporary_privileged_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["operator_session_id", "operator_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
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
        UniqueConstraint("context_id", name="uq_grant_context"),
        UniqueConstraint("tenant_id", "contract_id", "id", name="uq_grant_scope"),
        CheckConstraint("operator_role='PLATFORM_ADMIN'", name="ck_grant_operator"),
        CheckConstraint(
            "grant_type IN ('FINANCIAL_FISCAL','MAINTENANCE')", name="ck_grant_type"
        ),
        CheckConstraint(
            "status IN ('ACTIVE','ENDED','EXPIRED','REVOKED')", name="ck_grant_status"
        ),
        CheckConstraint(
            "(status='ACTIVE') = (ended_at IS NULL)", name="ck_grant_terminal"
        ),
        CheckConstraint(
            "(status='REVOKED') = (revoked_at IS NOT NULL)", name="ck_grant_revoked"
        ),
        CheckConstraint(
            "expires_at > started_at AND (ended_at IS NULL OR ended_at >= started_at)",
            name="ck_grant_lifetime",
        ),
        CheckConstraint("parent_context_id <> context_id", name="ck_grant_contexts"),
        CheckConstraint("version >= 1", name="ck_grant_version"),
        CheckConstraint(
            "length(btrim(reason)) BETWEEN 3 AND 1000", name="ck_grant_reason"
        ),
        CheckConstraint(
            "reference IS NULL OR length(btrim(reference)) BETWEEN 1 AND 100",
            name="ck_grant_reference",
        ),
        CheckConstraint(
            "grant_type <> 'MAINTENANCE' OR reference IS NOT NULL",
            name="ck_grant_maintenance_reference",
        ),
        Index(
            "uq_grant_active_parent",
            "parent_context_id",
            unique=True,
            postgresql_where=text("status='ACTIVE'"),
        ),
        Index("ix_grant_scope_time", "tenant_id", "contract_id", "started_at", "id"),
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
    grant_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    reason: Mapped[str] = mapped_column(String(1000))
    reference: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class MaintenanceGrantScope(Base):
    __tablename__ = "maintenance_grant_scopes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "grant_id"],
            [
                "temporary_privileged_grants.tenant_id",
                "temporary_privileged_grants.contract_id",
                "temporary_privileged_grants.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_maintenance_action"
        ),
        CheckConstraint(
            "entity_type='organization_node'", name="ck_maintenance_entity"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "entity_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("grant_id", "action_code", name="uq_maintenance_action_scope"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    grant_id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    action_code: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID | None]
