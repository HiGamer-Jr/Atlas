from app.core.errors import ApiError
from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from app.tenancy.contexts import permissions, revalidate


def role_sensitive(role, granted):
    return (
        role.sensitivity_locked
        or role.classification != "STANDARD"
        or any(code not in CATALOG or CATALOG[code].sensitive for code in granted)
    )


def role_support_eligible(role, granted):
    return role.active and role.support_assignable and not role_sensitive(role, granted)


def effective_capabilities(db, principal, scope):
    fresh, _, _, _, role = revalidate(db, principal, scope)
    if fresh.platform_role in INTERNAL_GRANTS:
        return set(INTERNAL_GRANTS[fresh.platform_role])
    return {
        code
        for code in permissions(db, role)
        if code in CATALOG and CATALOG[code].tenant_enabled
    }


def require_capability(db, principal, scope, capability):
    if capability not in effective_capabilities(db, principal, scope):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida neste contexto.")


def require_global(principal, capability):
    if capability not in INTERNAL_GRANTS.get(principal.platform_role, frozenset()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
