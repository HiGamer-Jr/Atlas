from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text

from app.core.errors import ApiError
from app.core.security import require_csrf
from app.identity.models import AuthSession
from app.identity.operators import OPERATOR_LOCK
from app.identity.schemas import Principal
from app.identity.sessions import authenticate, current_role, lock_users
from app.tenancy.models import (
    AccessContext,
    Contract,
    Membership,
    Tenant,
    TenantRole,
    TenantRolePermission,
)
from app.tenancy.schemas import AccessScope


def now(db):
    return db.info.get("clock", lambda: datetime.now(UTC))()


def authenticated(db, request):
    # Must precede all identity row locks; shared with operator population updates.
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    principal, _, session = authenticate(db, request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_csrf(request, session.csrf_hash)
    return principal


def contract_rows(db, contract_id):
    tenant_id = db.scalar(select(Contract.tenant_id).where(Contract.id == contract_id))
    if tenant_id is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    contract = db.scalar(
        select(Contract)
        .where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not tenant or not contract:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    return tenant, contract


def membership_role(db, user_id, tenant_id, contract_id):
    membership = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
            Membership.contract_id == contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not membership or not membership.active or membership.blocked:
        return None, None
    role = db.scalar(
        select(TenantRole)
        .where(
            TenantRole.id == membership.role_id,
            TenantRole.tenant_id == tenant_id,
            TenantRole.contract_id == contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not role or not role.active:
        return None, None
    return membership, role


def permissions(db, role):
    return set(
        db.scalars(
            select(TenantRolePermission.capability)
            .where(
                TenantRolePermission.role_id == role.id,
                TenantRolePermission.tenant_id == role.tenant_id,
                TenantRolePermission.contract_id == role.contract_id,
                TenantRolePermission.active.is_(True),
            )
            .with_for_update()
        )
    )


def revalidate(db, principal, scope):
    # Principal/scope carry identity references, never cached authorization.
    users = lock_users(db, [principal.user_id])
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.id == principal.session_id,
            AuthSession.user_id == principal.user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    clock = now(db)
    idle = getattr(db.info.get("settings"), "session_idle_seconds", 1800)
    if (
        not users
        or not users[0].active
        or users[0].blocked
        or session is None
        or session.revoked_at is not None
        or session.expires_at <= clock
        or session.last_seen_at + timedelta(seconds=idle) <= clock
    ):
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    candidate = db.scalar(
        select(AccessContext)
        .where(
            AccessContext.id == scope.id,
            AccessContext.session_id == principal.session_id,
            AccessContext.actor_id == principal.user_id,
            AccessContext.tenant_id == scope.tenant_id,
            AccessContext.contract_id == scope.contract_id,
        )
        .execution_options(populate_existing=True)
    )
    if (
        not candidate
        or scope.session_id != principal.session_id
        or scope.actor_id != principal.user_id
    ):
        raise ApiError(403, "CONTEXT_INVALID", "Contexto indisponível.")
    tenant, contract = contract_rows(db, candidate.contract_id)
    context = db.scalar(
        select(AccessContext)
        .where(AccessContext.id == scope.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        context.revoked_at is not None
        or context.expires_at <= clock
        or not contract.active
        or not tenant.active
    ):
        raise ApiError(403, "CONTEXT_INVALID", "Contexto indisponível.")
    fresh = Principal(
        principal.user_id, principal.session_id, current_role(db, principal.user_id)
    )
    role = None
    if fresh.platform_role is None:
        _, role = membership_role(db, fresh.user_id, tenant.id, contract.id)
        if role is None:
            raise ApiError(403, "CONTEXT_INVALID", "Contexto indisponível.")
    return fresh, context, tenant, contract, role


def resolve_context(db, request, principal):
    raw = request.headers.get("X-HiAtlas-Context")
    try:
        context_id = UUID(raw) if raw else None
    except ValueError:
        context_id = None
    if context_id is None:
        raise ApiError(403, "CONTEXT_REQUIRED", "Selecione um contexto válido.")
    context = db.scalar(
        select(AccessContext).where(
            AccessContext.id == context_id,
            AccessContext.session_id == principal.session_id,
            AccessContext.actor_id == principal.user_id,
        )
    )
    if context is None:
        raise ApiError(403, "CONTEXT_INVALID", "Contexto indisponível.")
    scope = AccessScope(
        context.id,
        context.tenant_id,
        context.contract_id,
        context.session_id,
        context.actor_id,
    )
    revalidate(db, principal, scope)
    return scope
