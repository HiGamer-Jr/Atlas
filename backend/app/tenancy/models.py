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
