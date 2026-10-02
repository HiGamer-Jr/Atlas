from datetime import timedelta
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select

from app.audit.models import AccessEvent
from app.core.errors import ApiError
from app.core.security import SESSION_COOKIE, token_hash
from app.identity.models import AuthSession, PlatformRoleAssignment, User
from app.identity.schemas import IdentityView, Principal


def record_access(db, request, action, outcome, user_id=None, role=None, reason=None):
    db.add(
        AccessEvent(
            actor_id=user_id,
            actor_role=role,
            action=action,
            outcome=outcome,
            request_id=getattr(request.state, "request_id", uuid4()),
            reason=reason,
        )
    )
    db.flush()


def session_candidate(db, request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 128:
        return None
    return db.scalar(
        select(AuthSession)
        .where(AuthSession.token_hash == token_hash(token))
        .execution_options(populate_existing=True)
    )


def lock_users(db, user_ids):
    return list(
        db.scalars(
            select(User)
            .where(User.id.in_(user_ids))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def current_role(db, user_id):
    return db.scalar(
        select(PlatformRoleAssignment.role).where(
            PlatformRoleAssignment.user_id == user_id,
            PlatformRoleAssignment.active.is_(True),
        )
    )


def authenticate(db, request: Request, touch=True):
    session = session_candidate(db, request)
    if session is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    users = lock_users(db, [session.user_id])
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == session.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = request.app.state.clock()
    user = users[0] if users else None
    if (
        session is None
        or user is None
        or not user.active
        or user.blocked
        or session.revoked_at is not None
        or now >= session.expires_at
        or now
        >= session.last_seen_at
        + timedelta(seconds=request.app.state.settings.session_idle_seconds)
    ):
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    if touch and not getattr(request.state, "support_no_touch", False):
        session.last_seen_at = now
    principal = Principal(user.id, session.id, current_role(db, user.id))
    request.state.principal = principal
    return principal, user, session


def identity_view(principal, user):
    return IdentityView(
        user_id=user.id,
        display_name=user.display_name,
        platform_role=principal.platform_role,
    )
