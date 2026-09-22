"""Import models once to register metadata for Alembic and application services."""

from app.audit.models import AccessEvent, AuditEvent
from app.db.base import Base
from app.identity.models import (
    AuthPreauth,
    AuthRateLimit,
    AuthSession,
    PlatformRoleAssignment,
    User,
)
from app.tenancy.models import Contract, Tenant

__all__ = [
    "AccessEvent",
    "AuditEvent",
    "AuthPreauth",
    "AuthRateLimit",
    "AuthSession",
    "Base",
    "Contract",
    "PlatformRoleAssignment",
    "Tenant",
    "User",
]
