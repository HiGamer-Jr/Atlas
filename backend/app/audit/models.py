from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.base import Base


class EventColumns:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str | None] = mapped_column(String(32))
    tenant_id: Mapped[UUID | None]
    contract_id: Mapped[UUID | None]
    environment: Mapped[str | None] = mapped_column(String(16))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[UUID]
    support_session_id: Mapped[UUID | None]
    reason: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(String(200))

    @declared_attr.directive
    def __table_args__(cls):
        name = cls.__tablename__
        return (
            ForeignKeyConstraint(
                ["tenant_id", "contract_id"],
                ["contracts.tenant_id", "contracts.id"],
                ondelete="RESTRICT",
                name=f"fk_{name}_scope",
            ),
            CheckConstraint(
                "(tenant_id IS NULL) = (contract_id IS NULL)", name=f"ck_{name}_context"
            ),
            CheckConstraint(
                "outcome IN ('SUCCESS','DENIED','FAILURE')", name=f"ck_{name}_outcome"
            ),
            CheckConstraint(
                "environment IS NULL OR environment IN ('TEST','STAGING','PRODUCTION')",
                name=f"ck_{name}_environment",
            ),
            CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')",
                name=f"ck_{name}_actor_role",
            ),
            CheckConstraint("length(btrim(action)) > 0", name=f"ck_{name}_action"),
            Index(
                f"ix_{name}_scope_time", "tenant_id", "contract_id", "occurred_at", "id"
            ),
        )


class AuditEvent(EventColumns, Base):
    __tablename__ = "audit_events"
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)


class AccessEvent(EventColumns, Base):
    __tablename__ = "access_events"
