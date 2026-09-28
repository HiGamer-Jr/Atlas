from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError

from app.audit.schemas import MembershipRoleSnapshot, TenantRoleSnapshot
from app.core.errors import ApiError
from app.identity.models import PlatformRoleAssignment
from app.platform.policy import (
    require_capability,
    role_sensitive,
    role_support_eligible,
)
from app.platform.role_schemas import RoleView
from app.tenancy.contexts import now, permissions, revalidate
from app.tenancy.models import (
    AccessContext,
    Membership,
    TenantRole,
    TenantRolePermission,
)
from app.tenancy.schemas import MembershipView
from app.tenancy.services import audit


def load_role(db, scope, role_id):
    role = db.scalar(
        select(TenantRole)
        .where(
            TenantRole.id == role_id,
            TenantRole.tenant_id == scope.tenant_id,
            TenantRole.contract_id == scope.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if role is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    return role


def role_snapshot(role, granted):
    return TenantRoleSnapshot(
        code=role.code,
        name=role.name,
        classification=role.classification,
        support_assignable=role.support_assignable,
        sensitivity_locked=role.sensitivity_locked,
        active=role.active,
        permissions=sorted(granted),
        version=role.version,
    )


def view(role, granted):
    return RoleView(
        id=role.id,
        **role_snapshot(role, granted).model_dump(),
        support_eligible=role_support_eligible(role, granted),
    )


def list_roles(db, principal, scope, assignable, limit, offset):
    require_capability(
        db, principal, scope, "roles.assign" if assignable else "roles.read"
    )
    fresh, *_ = revalidate(db, principal, scope)
    # Bound the returned page, not eligibility correctness: filter in SQL for support.
    query = select(TenantRole).where(
        TenantRole.tenant_id == scope.tenant_id,
        TenantRole.contract_id == scope.contract_id,
    )
    if assignable:
        query = query.where(TenantRole.active.is_(True))
        if fresh.platform_role == "PLATFORM_SUPPORT":
            from app.platform.capabilities import CATALOG

            safe = [
                code
                for code, cap in CATALOG.items()
                if not cap.sensitive and cap.tenant_role
            ]
            sensitive = exists(
                select(TenantRolePermission.role_id).where(
                    TenantRolePermission.role_id == TenantRole.id,
                    TenantRolePermission.active.is_(True),
                    TenantRolePermission.capability.not_in(safe),
                )
            )
            query = query.where(
                TenantRole.support_assignable.is_(True),
                TenantRole.classification == "STANDARD",
                TenantRole.sensitivity_locked.is_(False),
                ~sensitive,
            )
    rows = db.scalars(
        query.order_by(TenantRole.code, TenantRole.id)
        .limit(limit)
        .offset(offset)
        .with_for_update()
    )
    items = []
    for role in rows:
        granted = permissions(db, role)
        if (
            not assignable
            or fresh.platform_role != "PLATFORM_SUPPORT"
            or role_support_eligible(role, granted)
        ):
            items.append(view(role, granted))
    return {"items": items}


def set_permissions(db, role, desired):
    rows = list(
        db.scalars(
            select(TenantRolePermission)
            .where(
                TenantRolePermission.role_id == role.id,
                TenantRolePermission.tenant_id == role.tenant_id,
                TenantRolePermission.contract_id == role.contract_id,
            )
            .with_for_update()
        )
    )
    for row in rows:
        row.active = row.capability in desired
    present = {row.capability for row in rows}
    for code in desired - present:
        db.add(
            TenantRolePermission(
                role_id=role.id,
                tenant_id=role.tenant_id,
                contract_id=role.contract_id,
                capability=code,
                active=True,
            )
        )
    db.flush()


def revoke_contexts(db, scope, users):
    internal = select(PlatformRoleAssignment.user_id).where(
        PlatformRoleAssignment.active.is_(True)
    )
    db.execute(
        update(AccessContext)
        .where(
            AccessContext.tenant_id == scope.tenant_id,
            AccessContext.contract_id == scope.contract_id,
            AccessContext.actor_id.in_(users),
            AccessContext.actor_id.not_in(internal),
            AccessContext.revoked_at.is_(None),
        )
        .values(revoked_at=now(db))
    )


def create_role(db, request, principal, scope, payload):
    require_capability(db, principal, scope, "roles.manage")
    if payload.support_assignable:
        require_capability(db, principal, scope, "roles.support_assignable.manage")
    desired = set(payload.permissions)
    role = TenantRole(
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        **payload.model_dump(exclude={"permissions"}),
        sensitivity_locked=False,
        version=1,
    )
    role.sensitivity_locked = role_sensitive(role, desired)
    if role.support_assignable and role.sensitivity_locked:
        raise ApiError(
            422, "ROLE_INELIGIBLE", "Perfil sensível não pode ser elegível ao suporte."
        )
    db.add(role)
    try:
        db.flush()
    except IntegrityError:
        raise ApiError(
            409, "CONFLICT", "Código de perfil indisponível neste contrato."
        ) from None
    set_permissions(db, role, desired)
    audit(
        db,
        request,
        principal,
        "tenant.role.created",
        "tenant_role",
        role.id,
        after=role_snapshot(role, desired),
        scope=scope,
    )
    return view(role, desired)


def patch_role(db, request, principal, scope, role_id, payload):
    require_capability(db, principal, scope, "roles.manage")
    if "support_assignable" in payload.model_fields_set:
        require_capability(db, principal, scope, "roles.support_assignable.manage")
    role = load_role(db, scope, role_id)
    if role.version != payload.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "O registro mudou; atualize antes de confirmar."
        )
    previous = permissions(db, role)
    require_capability(db, principal, scope, "roles.manage")
    before = role_snapshot(role, previous)
    was_sensitive = role_sensitive(role, previous)
    desired = set(payload.permissions) if payload.permissions is not None else previous
    for name in payload.model_fields_set - {"expected_version", "permissions"}:
        setattr(role, name, getattr(payload, name))
    role.sensitivity_locked = was_sensitive or role_sensitive(role, desired)
    if role.sensitivity_locked and role.support_assignable:
        raise ApiError(
            422, "ROLE_INELIGIBLE", "Perfil sensível não pode ser elegível ao suporte."
        )
    role.version += 1
    set_permissions(db, role, desired)
    if not role_support_eligible(role, desired):
        from app.identity.tokens import cancel_member_invites

        for pending in db.scalars(
            select(Membership)
            .where(
                Membership.role_id == role.id, Membership.invitation_pending.is_(True)
            )
            .with_for_update()
        ):
            cancel_member_invites(db, pending, now(db), requires_admin=True)
    users = select(Membership.user_id).where(
        Membership.role_id == role.id,
        Membership.tenant_id == scope.tenant_id,
        Membership.contract_id == scope.contract_id,
    )
    revoke_contexts(db, scope, users)
    audit(
        db,
        request,
        principal,
        "tenant.role.updated",
        "tenant_role",
        role.id,
        before=before,
        after=role_snapshot(role, desired),
        scope=scope,
    )
    return view(role, desired)


def assign_role(db, request, principal, scope, member_id, payload):
    require_capability(db, principal, scope, "roles.assign")
    fresh, *_ = revalidate(db, principal, scope)
    member = db.scalar(
        select(Membership)
        .where(
            Membership.id == member_id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if member is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    if db.scalar(
        select(exists().where(PlatformRoleAssignment.user_id == member.user_id))
    ):
        raise ApiError(
            403,
            "INTERNAL_IDENTITY",
            "Identidades internas não são geridas por perfis de cliente.",
        )
    role = load_role(db, scope, payload.role_id)
    current = load_role(db, scope, member.role_id)
    granted = permissions(db, role)
    if not role.active:
        raise ApiError(403, "ROLE_INELIGIBLE", "Perfil indisponível.")
    if fresh.platform_role == "PLATFORM_SUPPORT" and (
        not role_support_eligible(role, granted)
        or role_sensitive(current, permissions(db, current))
    ):
        raise ApiError(403, "ROLE_INELIGIBLE", "Perfil não permitido ao suporte.")
    if member.version != payload.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "O registro mudou; atualize antes de confirmar."
        )
    require_capability(db, principal, scope, "roles.assign")
    before = MembershipRoleSnapshot(role_id=member.role_id, version=member.version)
    if member.invitation_pending:
        from app.identity.tokens import cancel_member_invites

        cancel_member_invites(
            db, member, now(db), requires_admin=role_sensitive(role, granted)
        )
    member.role_id = role.id
    member.version += 1
    revoke_contexts(db, scope, [member.user_id])
    audit(
        db,
        request,
        fresh,
        "membership.role.assigned",
        "membership",
        member.id,
        before=before,
        after=MembershipRoleSnapshot(role_id=member.role_id, version=member.version),
        scope=scope,
    )
    return MembershipView(
        id=member.id,
        user_id=member.user_id,
        role_id=member.role_id,
        active=member.active,
        blocked=member.blocked,
        version=member.version,
    )
