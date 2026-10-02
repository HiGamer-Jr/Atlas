"""Import models once to register metadata for Alembic and application services."""

from app.audit.models import AccessEvent, AuditEvent
from app.db.base import Base
from app.identity.models import (
    AuthPreauth,
    AuthRateLimit,
    AuthSession,
    EmailOutbox,
    PlatformRoleAssignment,
    SecurityToken,
    User,
)
from app.organization.models import (
    ContractModule,
    MembershipUnitScope,
    OrganizationNode,
)
from app.support.models import SupportSession
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
    "ContractModule",
    "EmailOutbox",
    "Membership",
    "MembershipUnitScope",
    "OrganizationNode",
    "PlatformRoleAssignment",
    "SecurityToken",
    "SupportSession",
    "Tenant",
    "TenantRole",
    "TenantRolePermission",
    "User",
]
