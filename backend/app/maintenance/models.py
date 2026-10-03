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


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
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
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "context_id",
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
        ),
        ForeignKeyConstraint(
            ["operator_session_id", "operator_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "grant_id",
                "context_id",
                "operator_session_id",
                "operator_id",
                "grant_type",
            ],
            [
                "temporary_privileged_grants.tenant_id",
                "temporary_privileged_grants.contract_id",
                "temporary_privileged_grants.id",
                "temporary_privileged_grants.context_id",
                "temporary_privileged_grants.operator_session_id",
                "temporary_privileged_grants.operator_id",
                "temporary_privileged_grants.grant_type",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "grant_id",
                "action_code",
                "entity_type",
                "entity_id",
            ],
            [
                "maintenance_grant_scopes.tenant_id",
                "maintenance_grant_scopes.contract_id",
                "maintenance_grant_scopes.grant_id",
                "maintenance_grant_scopes.action_code",
                "maintenance_grant_scopes.entity_type",
                "maintenance_grant_scopes.entity_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "contract_id",
                "source_run_id",
                "action_code",
                "entity_type",
                "entity_id",
            ],
            [
                "processing_runs.tenant_id",
                "processing_runs.contract_id",
                "processing_runs.id",
                "processing_runs.action_code",
                "processing_runs.entity_type",
                "processing_runs.entity_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "id",
            "action_code",
            "entity_type",
            "entity_id",
            name="uq_processing_source_scope",
        ),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "source_run_id",
            "idempotency_key",
            name="uq_processing_idempotency",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','UNKNOWN')",
            name="ck_processing_status",
        ),
        CheckConstraint(
            "result_code IN ('NONE','COMPLETED','HANDLER_FAILED','NOT_ELIGIBLE') AND message_code IN ('NONE','COMPLETED','HANDLER_FAILED','NOT_ELIGIBLE')",
            name="ck_processing_codes",
        ),
        CheckConstraint(
            "classification IN ('STANDARD','SENSITIVE')",
            name="ck_processing_classification",
        ),
        CheckConstraint(
            "operator_role='PLATFORM_ADMIN'", name="ck_processing_operator"
        ),
        CheckConstraint("entity_type='organization_node'", name="ck_processing_entity"),
        CheckConstraint(
            "action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_processing_action"
        ),
        CheckConstraint("version>=1", name="ck_processing_version"),
        CheckConstraint(
            "source_run_id IS NULL OR source_run_id<>id",
            name="ck_processing_source_self",
        ),
        CheckConstraint(
            "(source_run_id IS NULL AND idempotency_key IS NULL AND command_fingerprint IS NULL) OR (source_run_id IS NOT NULL AND idempotency_key IS NOT NULL AND command_fingerprint IS NOT NULL AND idempotency_key ~ '^[A-Za-z0-9_:-]{1,100}$' AND command_fingerprint ~ '^[0-9a-f]{64}$' AND grant_id IS NOT NULL AND grant_type='MAINTENANCE')",
            name="ck_processing_retry",
        ),
        CheckConstraint(
            "(grant_id IS NULL)=(grant_type IS NULL)", name="ck_processing_grant"
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at>=created_at", name="ck_processing_started"
        ),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND finished_at>=started_at)",
            name="ck_processing_finished",
        ),
        Index(
            "ix_processing_scope_time", "tenant_id", "contract_id", "created_at", "id"
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    action_code: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID]
    source_run_id: Mapped[UUID | None]
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    command_fingerprint: Mapped[str | None] = mapped_column(String(64))
    operator_id: Mapped[UUID]
    operator_session_id: Mapped[UUID]
    operator_role: Mapped[str] = mapped_column(String(32))
    context_id: Mapped[UUID]
    grant_id: Mapped[UUID | None]
    grant_type: Mapped[str | None] = mapped_column(String(32))
    request_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(16))
    result_code: Mapped[str] = mapped_column(String(32), default="NONE")
    message_code: Mapped[str] = mapped_column(String(32), default="NONE")
    classification: Mapped[str] = mapped_column(String(16), default="STANDARD")
    reason: Mapped[str | None] = mapped_column(String(1000))
    reference: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
