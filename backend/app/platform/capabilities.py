"""Closed server catalogue. Reserved codes grant no access by themselves."""

from types import MappingProxyType

from app.platform.types import Capability

CATALOG = MappingProxyType(
    {
        item.code: item
        for item in (
            Capability("contracts.read", "platform"),
            Capability("tenants.create", "platform", True),
            Capability("contracts.create", "platform", True),
            Capability(
                "memberships.read", "access", tenant_role=True, tenant_enabled=True
            ),
            Capability("roles.read", "access", tenant_role=True, tenant_enabled=True),
            Capability("roles.manage", "access", True, True, False),
            Capability("roles.assign", "access", True),
            Capability("roles.support_assignable.manage", "access", True),
            Capability("finance.read", "finance", True, True, False),
            Capability("fiscal.read", "fiscal", True, True, False),
            *[
                Capability(code, domain, sensitive)
                for code, domain, sensitive in (
                    ("modules.read", "contract", False),
                    ("modules.manage", "contract", True),
                    ("features.manage", "contract", True),
                    ("organization.manage", "contract", True),
                    ("parameters.manage", "contract", True),
                    ("integrations.manage", "contract", True),
                    ("users.create", "access", False),
                    ("users.invite", "access", False),
                    ("users.status", "access", False),
                    ("users.password_reset", "access", False),
                    ("users.mfa_reset", "access", False),
                    ("operators.manage", "platform", True),
                    ("logs.support.read", "diagnostics", False),
                    ("logs.technical.read", "diagnostics", True),
                    ("logs.access.read", "diagnostics", False),
                    ("audit.read", "audit", False),
                    ("jobs.read", "maintenance", False),
                    ("errors.read", "diagnostics", False),
                    ("imports.manage", "maintenance", True),
                    ("corrections.execute", "maintenance", True),
                    ("reprocess.execute", "maintenance", True),
                    ("support.session.start", "support", False),
                    ("maintenance.authorize", "maintenance", True),
                )
            ],
        )
    }
)
PHASE3_ADMIN = frozenset(
    {
        "contracts.read",
        "tenants.create",
        "contracts.create",
        "memberships.read",
        "roles.read",
        "roles.manage",
        "roles.assign",
        "roles.support_assignable.manage",
    }
)
PHASE3_SUPPORT = frozenset(
    {"contracts.read", "memberships.read", "roles.read", "roles.assign"}
)
PHASE6_ACCESS = frozenset(
    {
        "users.create",
        "users.invite",
        "users.status",
        "users.password_reset",
        "audit.read",
        "logs.access.read",
    }
)
INTERNAL_GRANTS = MappingProxyType(
    {
        "PLATFORM_ADMIN": PHASE3_ADMIN
        | PHASE6_ACCESS
        | frozenset({"organization.manage", "modules.read", "modules.manage"}),
        "PLATFORM_SUPPORT": PHASE3_SUPPORT
        | PHASE6_ACCESS
        | frozenset({"modules.read"}),
    }
)
