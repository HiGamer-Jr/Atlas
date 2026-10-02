from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps


class Tenant(Timestamps, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_tenants_name"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Contract(Timestamps, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_contract_scope"),
        CheckConstraint(
            "environment IN ('TEST','STAGING','PRODUCTION')",
            name="ck_contract_environment",
        ),
        CheckConstraint("length(btrim(code)) > 0", name="ck_contract_code"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_contract_name"),
        CheckConstraint("version > 0", name="ck_contract_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    environment: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint


class TenantRole(Timestamps, Base):
    __tablename__ = "tenant_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_id", "id", name="uq_tenant_role_scope"),
        UniqueConstraint("contract_id", "code", name="uq_tenant_role_code"),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "classification IN ('STANDARD','ADMINISTRATIVE','FINANCIAL_FISCAL','SENSITIVE')",
            name="ck_role_classification",
        ),
        CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9_]{1,63}$' AND left(code,9) <> 'PLATFORM_'",
            name="ck_tenant_role_code",
        ),
        CheckConstraint("length(btrim(name)) > 0", name="ck_tenant_role_name"),
        CheckConstraint("version > 0", name="ck_tenant_role_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), server_default=text("''"))
    classification: Mapped[str] = mapped_column(
        String(32), server_default=text("'STANDARD'")
    )
    support_assignable: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    sensitivity_locked: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class TenantRolePermission(Base):
    __tablename__ = "tenant_role_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "role_id"],
            ["tenant_roles.tenant_id", "tenant_roles.contract_id", "tenant_roles.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read')",
            name="ck_tenant_capability",
        ),
    )
    role_id: Mapped[UUID] = mapped_column(primary_key=True)
    capability: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Membership(Timestamps, Base):
    invite_requires_admin: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    invitation_pending: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "tenant_id", "contract_id", name="uq_membership_user_scope"
        ),
        UniqueConstraint("tenant_id", "contract_id", "id", name="uq_membership_scope"),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "role_id"],
            ["tenant_roles.tenant_id", "tenant_roles.contract_id", "tenant_roles.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("version > 0", name="ck_membership_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    role_id: Mapped[UUID]
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class AccessContext(Base):
    __tablename__ = "access_contexts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "actor_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("expires_at > created_at", name="ck_context_lifetime"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[UUID]
    actor_id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
