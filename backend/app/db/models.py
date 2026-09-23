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
from app.tenancy.models import (
    AccessContext,
    Contract,
    Membership,
    Tenant,
    TenantRole,
    TenantRolePermission,
)

__all__ = [
    "AccessContext",
    "AccessEvent",
    "AuditEvent",
    "AuthPreauth",
    "AuthRateLimit",
    "AuthSession",
    "Base",
    "Contract",
    "Membership",
    "PlatformRoleAssignment",
    "Tenant",
    "TenantRole",
    "TenantRolePermission",
    "User",
]
