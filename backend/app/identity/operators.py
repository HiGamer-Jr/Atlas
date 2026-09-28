"""Internal platform operators only. Tenant roles and scoped RBAC live in Phase 3."""

from datetime import timedelta

from sqlalchemy import func, select, text

from app.audit.schemas import AuditInput, IdentitySnapshot
from app.audit.service import append_event
from app.core.errors import ApiError, error_response
from app.core.security import client_source, require_csrf, require_origin
from app.identity.models import PlatformRoleAssignment, User
from app.identity.passwords import verify_password
from app.identity.rate_limits import lock_buckets, record_failure
from app.identity.schemas import OperatorView
from app.identity.sessions import (
    authenticate,
    lock_users,
    record_access,
    session_candidate,
)

OPERATOR_LOCK = 720260922


def lock_operator_population(db):
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": OPERATOR_LOCK})


def snapshot(user, role):
    return IdentitySnapshot(
        user_id=user.id,
        active=user.active,
        blocked=user.blocked,
        platform_role=role.role if role and role.active else None,
    )


def operator_context(db, request, target_id, password=None):
    require_origin(request)
    candidate = session_candidate(db, request)
    if candidate is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    require_csrf(request, candidate.csrf_hash)
    # All role/status changes and bootstrap serialize before user/session row locks.
    lock_operator_population(db)
    actor = db.get(User, candidate.user_id)
    buckets, limited = [], None
    if password is not None:
        buckets, limited = lock_buckets(
            db,
            actor.email_normalized,
            client_source(request),
            request.app.state.clock(),
            request.app.state.settings,
        )
    lock_users(db, [candidate.user_id, target_id])
    principal, actor, session = authenticate(db, request)
    require_csrf(request, session.csrf_hash)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )
    target = db.get(User, target_id)
    if target is None:
        raise ApiError(404, "OPERATOR_NOT_FOUND", "Identidade não encontrada.")
    role = db.get(PlatformRoleAssignment, target_id, populate_existing=True)
    if limited:
        record_access(
            db,
            request,
            "platform.operator.authentication",
            "DENIED",
            principal.user_id,
            principal.platform_role,
            limited.code,
        )
        return None, error_response(request, limited)
    if password is not None:
        if not verify_password(actor.password_hash, password):
            record_failure(buckets)
            record_access(
                db,
                request,
                "platform.operator.authentication",
                "FAILURE",
                principal.user_id,
                principal.platform_role,
            )
            return None, error_response(
                request, ApiError(401, "AUTH_INVALID", "Credenciais inválidas.")
            )
        session.reauthenticated_at = request.app.state.clock()
    elif (
        session.reauthenticated_at is None
        or request.app.state.clock()
        >= session.reauthenticated_at + timedelta(minutes=5)
    ):
        raise ApiError(403, "REAUTH_REQUIRED", "Confirme sua senha novamente.")
    return (principal, target, role), None


def protect_last_admin(db, target, role, new_role, active, blocked):
    was_admin = (
        role
        and role.active
        and role.role == "PLATFORM_ADMIN"
        and target.active
        and not target.blocked
    )
    remains_admin = new_role == "PLATFORM_ADMIN" and active and not blocked
    if was_admin and not remains_admin:
        count = db.scalar(
            select(func.count())
            .select_from(User)
            .join(PlatformRoleAssignment, PlatformRoleAssignment.user_id == User.id)
            .where(
                User.active.is_(True),
                User.password_hash.is_not(None),
                User.blocked.is_(False),
                PlatformRoleAssignment.active.is_(True),
                PlatformRoleAssignment.role == "PLATFORM_ADMIN",
            )
        )
        if count <= 1:
            raise ApiError(
                409,
                "LAST_PLATFORM_ADMIN",
                "É necessário manter um administrador HiAtlas ativo.",
            )


def finish_change(db, request, principal, target, before, role, action):
    from app.identity.tokens import revoke_sessions

    revoke_sessions(db, target.id, request.app.state.clock())
    after = snapshot(target, role)
    append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            action=action,
            entity_type="user",
            entity_id=target.id,
            before=before,
            after=after,
            request_id=request.state.request_id,
        ),
    )
    return OperatorView(
        user_id=target.id,
        platform_role=after.platform_role,
        active=target.active,
        blocked=target.blocked,
    )


def change_role(db, request, target_id, payload):
    context, denied = operator_context(
        db, request, target_id, payload.password.get_secret_value()
    )
    if denied is not None:
        return denied
    principal, target, role = context
    if (
        payload.confirmation.target_user_id != target_id
        or payload.confirmation.target_role != payload.role
    ):
        raise ApiError(
            422,
            "CONFIRMATION_MISMATCH",
            "A confirmação deve corresponder ao usuário e papel selecionados.",
        )
    if target_id == principal.user_id and payload.role == "PLATFORM_ADMIN":
        raise ApiError(403, "SELF_PROMOTION_FORBIDDEN", "Autopromoção não permitida.")
    protect_last_admin(db, target, role, payload.role, target.active, target.blocked)
    before = snapshot(target, role)
    if role is None:
        role = PlatformRoleAssignment(user_id=target.id, role=payload.role, active=True)
        db.add(role)
    else:
        role.role, role.active = payload.role, True
    return finish_change(
        db, request, principal, target, before, role, "platform.role.changed"
    )


def change_status(db, request, target_id, payload):
    context, denied = operator_context(db, request, target_id)
    if denied is not None:
        return denied
    principal, target, role = context
    if role is None:
        raise ApiError(404, "OPERATOR_NOT_FOUND", "Operador interno não encontrado.")
    active = payload.active if payload.active is not None else target.active
    blocked = payload.blocked if payload.blocked is not None else target.blocked
    protect_last_admin(
        db, target, role, role.role if role.active else None, active, blocked
    )
    before = snapshot(target, role)
    target.active, target.blocked = active, blocked
    return finish_change(
        db, request, principal, target, before, role, "platform.operator.status.changed"
    )
