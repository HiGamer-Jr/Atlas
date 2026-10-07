from app.core.errors import ApiError
from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from app.tenancy.contexts import membership_role, permissions, revalidate


def role_sensitive(role, granted):
    return (
        role.sensitivity_locked
        or role.classification != "STANDARD"
        or any(code not in CATALOG or CATALOG[code].sensitive for code in granted)
    )


def role_support_eligible(role, granted):
    return role.active and role.support_assignable and not role_sensitive(role, granted)


def effective_capabilities(db, principal, scope):
    from sqlalchemy import select

    from app.grants.models import TemporaryPrivilegedGrant
    from app.grants.services import effective_access as grant_access
    from app.support.services import effective_access, support_for_context

    grant = db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.context_id == scope.id
        )
    )
    if grant is not None:
        return grant_access(db, principal, grant)
    support = support_for_context(db, scope.id)
    if support and support.context_id == scope.id:
        return effective_access(db, principal, support)
    if support_for_context(db, scope.id, active_only=True):
        return set()
    fresh, _, _, _, role = revalidate(db, principal, scope)
    if fresh.platform_role in INTERNAL_GRANTS:
        internal = set(INTERNAL_GRANTS[fresh.platform_role])
        # Internal administration never grants tenant operational data rights.
        if fresh.platform_role == "PLATFORM_ADMIN":
            _, tenant_role = membership_role(
                db, fresh.user_id, scope.tenant_id, scope.contract_id
            )
            if tenant_role is not None:
                internal |= {
                    code
                    for code in permissions(db, tenant_role)
                    if code in CATALOG
                    and CATALOG[code].domain == "datahub"
                    and CATALOG[code].tenant_enabled
                }
            revalidate(db, principal, scope)
        return internal
    granted = {
        code
        for code in permissions(db, role)
        if code in CATALOG and CATALOG[code].tenant_enabled
    }
    revalidate(
        db, principal, scope
    )  # Permission locks may outlive session/context validity.
    return granted


def require_capability(
    db, principal, scope, capability, *, module_code=None, organization_node_id=None
):
    # Capabilities are checked first: configuration never grants financial access.
    if capability not in effective_capabilities(db, principal, scope):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida neste contexto.")
    if module_code is None:
        module_code = {
            "finance.read": "FINANCE",
            "fiscal.read": "FINANCE",
        }.get(capability)
    if module_code is not None:
        from sqlalchemy import select

        from app.organization.models import ContractModule
        from app.organization.modules import (
            CONTRACT_MODULE_CATALOG,
            OPERATIONAL_MODULES,
        )

        if module_code not in CONTRACT_MODULE_CATALOG:
            raise ApiError(
                403, "MODULE_UNAVAILABLE", "Módulo indisponível neste contexto."
            )
        row = db.scalar(
            select(ContractModule)
            .where(
                ContractModule.tenant_id == scope.tenant_id,
                ContractModule.contract_id == scope.contract_id,
                ContractModule.code == module_code,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        # Re-check session/context/contract after waiting on module state.
        if capability not in effective_capabilities(db, principal, scope):
            raise ApiError(
                403, "CAPABILITY_DENIED", "Ação não permitida neste contexto."
            )
        if (
            row is None
            or not row.contracted
            or not row.active
            or module_code not in OPERATIONAL_MODULES
        ):
            raise ApiError(
                403, "MODULE_UNAVAILABLE", "Módulo indisponível neste contexto."
            )
    if organization_node_id is not None:
        from sqlalchemy import select

        from app.organization.models import MembershipUnitScope, OrganizationNode
        from app.tenancy.models import Membership

        node = db.scalar(
            select(OrganizationNode)
            .where(
                OrganizationNode.id == organization_node_id,
                OrganizationNode.tenant_id == scope.tenant_id,
                OrganizationNode.contract_id == scope.contract_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        permitted = db.scalar(
            select(MembershipUnitScope)
            .join(
                Membership,
                (Membership.id == MembershipUnitScope.membership_id)
                & (Membership.tenant_id == MembershipUnitScope.tenant_id)
                & (Membership.contract_id == MembershipUnitScope.contract_id),
            )
            .where(
                MembershipUnitScope.tenant_id == scope.tenant_id,
                MembershipUnitScope.contract_id == scope.contract_id,
                MembershipUnitScope.node_id == organization_node_id,
                MembershipUnitScope.active.is_(True),
                Membership.user_id == principal.user_id,
                Membership.active.is_(True),
                Membership.blocked.is_(False),
                Membership.invitation_pending.is_(False),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        active = node is not None and node.active
        if active:
            from app.organization.services import ancestors

            active = all(
                parent.active
                for parent in ancestors(db, scope, node.parent_id, node.id)
            )
        if capability not in effective_capabilities(db, principal, scope):
            raise ApiError(
                403, "CAPABILITY_DENIED", "Ação não permitida neste contexto."
            )
        if not active or permitted is None:
            raise ApiError(
                403, "UNIT_SCOPE_DENIED", "Unidade indisponível neste contexto."
            )


def require_global(principal, capability):
    if capability not in INTERNAL_GRANTS.get(principal.platform_role, frozenset()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")


def safe_role_predicate():
    """Filter sensitive roles before count/pagination; unknown capabilities fail closed."""
    from sqlalchemy import exists, select

    from app.tenancy.models import TenantRole, TenantRolePermission

    safe = [
        code for code, cap in CATALOG.items() if not cap.sensitive and cap.tenant_role
    ]
    unsafe = exists(
        select(TenantRolePermission.role_id).where(
            TenantRolePermission.role_id == TenantRole.id,
            TenantRolePermission.active.is_(True),
            TenantRolePermission.capability.not_in(safe),
        )
    )
    return (
        (TenantRole.classification == "STANDARD")
        & TenantRole.sensitivity_locked.is_(False)
        & ~unsafe
    )


def require_contracted_module(db, principal, scope, module_code):
    """Informational datasets need a contracted module, not a fictitious domain."""
    from sqlalchemy import select

    from app.organization.models import ContractModule
    from app.organization.modules import CONTRACT_MODULE_CATALOG

    revalidate(db, principal, scope)
    if module_code not in CONTRACT_MODULE_CATALOG:
        raise ApiError(403, "MODULE_UNAVAILABLE", "Módulo indisponível neste contexto.")
    row = db.scalar(
        select(ContractModule)
        .where(
            ContractModule.tenant_id == scope.tenant_id,
            ContractModule.contract_id == scope.contract_id,
            ContractModule.code == module_code,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    revalidate(db, principal, scope)
    if row is None or not row.contracted or not row.active:
        raise ApiError(403, "MODULE_UNAVAILABLE", "Módulo indisponível neste contexto.")
