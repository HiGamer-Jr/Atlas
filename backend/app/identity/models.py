from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email_normalized = lower(btrim(email_normalized)) AND length(email_normalized) > 0",
            name="ck_users_email_normalized",
        ),
        CheckConstraint("length(btrim(display_name)) > 0", name="ck_users_name"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email_normalized: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class PlatformRoleAssignment(Timestamps, Base):
    __tablename__ = "platform_role_assignments"
    __table_args__ = (
        CheckConstraint(
            "role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')", name="ck_platform_role"
        ),
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
