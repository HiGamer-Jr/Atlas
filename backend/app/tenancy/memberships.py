"""Only scoped lifecycle commands; global identities never edited by tenant operators."""

from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import or_, select, update

from app.audit.schemas import MembershipStateSnapshot
from app.core.errors import ApiError, error_response
from app.core.security import client_source, require_origin
from app.identity.dependencies import Database
from app.identity.email_schemas import InviteInput, MembershipStatusInput
from app.identity.models import EmailOutbox, PlatformRoleAssignment, SecurityToken, User
from app.identity.sessions import lock_users, session_candidate
from app.identity.tokens import (
    access_limit,
    event,
    lifecycle_lock,
    queue_access_email,
    require_mail,
)
from app.platform.policy import role_sensitive, role_support_eligible
from app.platform.roles import load_role, revoke_contexts
from app.tenancy.contexts import authenticated, permissions, resolve_context
from app.tenancy.models import Membership

router = APIRouter()


def context(db, request, target_id=None):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
    lifecycle_lock(db)
    candidate = session_candidate(db, request)
    if candidate:
        lock_users(db, [candidate.user_id] + ([target_id] if target_id else []))
    principal = authenticated(db, request)
    scope = resolve_context(db, request, principal)
    if principal.platform_role not in {"PLATFORM_ADMIN", "PLATFORM_SUPPORT"}:
        raise ApiError(403, "CAPABILITY_DENIED", "Acao nao permitida neste contexto.")
    return principal, scope


def target_member(db, scope, member_id):
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
    if not member:
        raise ApiError(404, "NOT_FOUND", "Registro nao encontrado.")
    if db.get(PlatformRoleAssignment, member.user_id):
        raise ApiError(
            403, "INTERNAL_IDENTITY", "Identidade indisponivel para esta operacao."
        )
    return member


def check_role(db, principal, scope, role_id):
    role = load_role(db, scope, role_id)
    if not role.active or (
        principal.platform_role == "PLATFORM_SUPPORT"
        and not role_support_eligible(role, permissions(db, role))
    ):
        raise ApiError(403, "ROLE_INELIGIBLE", "Perfil nao permitido.")
    return role


def rate(db, request, email, purpose):
    if access_limit(
        db,
        purpose,
        email,
        client_source(request),
        request.app.state.clock(),
        request.app.state.settings,
    ):
        return error_response(
            request,
            ApiError(429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente."),
        )
    return None


@router.post("/memberships", status_code=202)
def invite(payload: InviteInput, request: Request, db: Database):
    # Read-only lookup used only for consistent sorted identity locks; never returned.
    candidate = db.scalar(select(User).where(User.email_normalized == payload.email))
    principal, scope = context(db, request, candidate.id if candidate else None)
    settings = request.app.state.settings
    require_mail(settings, request.app.state.email_transport)
    check_role(db, principal, scope, payload.role_id)
    limited = rate(db, request, payload.email, "invite")
    if limited is not None:
        return limited
    # Re-read after lifecycle serialization: concurrent creation must reuse the identity.
    user = db.scalar(
        select(User).where(User.email_normalized == payload.email).with_for_update()
    )
    if user and (
        db.get(PlatformRoleAssignment, user.id) or not user.active or user.blocked
    ):
        # Neutral for existing global state: never disclose other associations.
        return {"status": "accepted"}
    if user is None:
        user = User(
            email_normalized=payload.email,
            display_name=payload.display_name,
            active=True,
            blocked=False,
        )
        db.add(user)
        db.flush()
    member = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
        .with_for_update()
    )
    if member and not member.invitation_pending:
        return {"status": "accepted"}
    if member is None:
        member = Membership(
            user_id=user.id,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            role_id=payload.role_id,
            active=True,
            blocked=False,
            invitation_pending=True,
        )
        db.add(member)
        db.flush()
        event(
            db,
            user.id,
            "membership.invited",
            request.state.request_id,
            principal.platform_role,
            member,
            principal.user_id,
        )
    elif member.blocked or not member.active:
        return {"status": "accepted"}
    else:
        check_role(db, principal, scope, member.role_id)
    queue_access_email(
        db,
        settings,
        user,
        "INVITE",
        request.app.state.clock(),
        request.state.request_id,
        member,
        principal.platform_role,
        principal.user_id,
    )
    return {"status": "accepted"}


def member_command(db, request, member_id):
    # Scope filtering happens before returning anything; only actor/target lock IDs read here.
    target_id = db.scalar(select(Membership.user_id).where(Membership.id == member_id))
    principal, scope = context(db, request, target_id)
    member = target_member(db, scope, member_id)
    return principal, scope, member


@router.post("/memberships/{member_id}/invite", status_code=202)
def resend_invite(member_id: UUID, request: Request, db: Database):
    principal, scope, member = member_command(db, request, member_id)
    check_role(db, principal, scope, member.role_id)
    require_mail(request.app.state.settings, request.app.state.email_transport)
    if not member.invitation_pending or member.blocked or not member.active:
        raise ApiError(409, "INVITE_UNAVAILABLE", "Convite indisponivel.")
    user = db.get(User, member.user_id)
    limited = rate(db, request, user.email_normalized, "invite")
    if limited is not None:
        return limited
    queue_access_email(
        db,
        request.app.state.settings,
        user,
        "INVITE",
        request.app.state.clock(),
        request.state.request_id,
        member,
        principal.platform_role,
        principal.user_id,
    )
    return {"status": "accepted"}


@router.post("/memberships/{member_id}/reset-password", status_code=202)
def request_reset(member_id: UUID, request: Request, db: Database):
    principal, _, member = member_command(db, request, member_id)
    require_mail(request.app.state.settings, request.app.state.email_transport)
    user = db.get(User, member.user_id)
    limited = rate(db, request, user.email_normalized, "reset")
    if limited is not None:
        return limited
    if user.active and not user.blocked and user.password_hash:
        queue_access_email(
            db,
            request.app.state.settings,
            user,
            "PASSWORD_RESET",
            request.app.state.clock(),
            request.state.request_id,
            member,
            principal.platform_role,
            principal.user_id,
        )
    return {"status": "accepted"}


@router.patch("/memberships/{member_id}/status")
def change_status(
    member_id: UUID, payload: MembershipStatusInput, request: Request, db: Database
):
    principal, scope, member = member_command(db, request, member_id)
    role = load_role(db, scope, member.role_id)
    if principal.platform_role == "PLATFORM_SUPPORT" and role_sensitive(
        role, permissions(db, role)
    ):
        raise ApiError(403, "ROLE_INELIGIBLE", "Perfil nao permitido.")
    if member.version != payload.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "Registro alterado. Atualize antes de confirmar."
        )
    before = MembershipStateSnapshot(
        active=member.active,
        blocked=member.blocked,
        invitation_pending=member.invitation_pending,
        version=member.version,
    )
    if payload.active is not None:
        member.active = payload.active
    if payload.blocked is not None:
        member.blocked = payload.blocked
    member.version += 1
    revoke_contexts(db, scope, [member.user_id])
    if member.blocked or not member.active:
        tokens = list(
            db.scalars(
                select(SecurityToken).where(
                    SecurityToken.membership_id == member.id,
                    SecurityToken.purpose == "INVITE",
                    SecurityToken.consumed_at.is_(None),
                    SecurityToken.invalidated_at.is_(None),
                )
            )
        )
        for token in tokens:
            token.invalidated_at = request.app.state.clock()
        db.execute(
            update(EmailOutbox)
            .where(
                EmailOutbox.token_id.in_([token.id for token in tokens]),
                EmailOutbox.status.in_(["QUEUED", "DISPATCHING"]),
            )
            .values(status="CANCELLED", ciphertext=None)
        )
    event(
        db,
        member.user_id,
        "membership.status.changed",
        request.state.request_id,
        principal.platform_role,
        member,
        principal.user_id,
        before=before,
        after=MembershipStateSnapshot(
            active=member.active,
            blocked=member.blocked,
            invitation_pending=member.invitation_pending,
            version=member.version,
        ),
    )
    return {
        "id": member.id,
        "user_id": member.user_id,
        "role_id": member.role_id,
        "active": member.active,
        "blocked": member.blocked,
        "version": member.version,
    }


@router.get("/memberships")
def list_memberships(
    request: Request,
    db: Database,
    search: str = Query(default="", max_length=128),
    status: str | None = Query(
        default=None, pattern="^(ACTIVE|INACTIVE|BLOCKED|PENDING)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    _, scope = context(db, request)
    query = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
    )
    if search:
        query = query.where(
            or_(
                User.email_normalized.icontains(search, autoescape=True),
                User.display_name.icontains(search, autoescape=True),
            )
        )
    if status == "ACTIVE":
        query = query.where(
            Membership.active.is_(True),
            Membership.blocked.is_(False),
            Membership.invitation_pending.is_(False),
        )
    elif status == "INACTIVE":
        query = query.where(Membership.active.is_(False))
    elif status == "BLOCKED":
        query = query.where(Membership.blocked.is_(True))
    elif status == "PENDING":
        query = query.where(Membership.invitation_pending.is_(True))
    rows = db.execute(
        query.order_by(User.email_normalized, Membership.id).limit(limit).offset(offset)
    )
    return {
        "items": [
            {
                "id": member.id,
                "user_id": member.user_id,
                "role_id": member.role_id,
                "active": member.active,
                "blocked": member.blocked,
                "version": member.version,
                "invitation_pending": member.invitation_pending,
                "email": user.email_normalized,
                "display_name": user.display_name,
            }
            for member, user in rows
        ]
    }
