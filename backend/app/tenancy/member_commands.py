"""Only scoped lifecycle commands; global identities never edited by tenant operators."""

from uuid import UUID

from fastapi import Request
from sqlalchemy import select, update

from app.audit.schemas import MembershipStateSnapshot
from app.core.errors import ApiError, error_response
from app.core.security import client_source, require_origin
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
from app.platform.policy import (
    require_capability,
    role_sensitive,
    role_support_eligible,
)
from app.platform.roles import load_role, revoke_contexts
from app.tenancy.contexts import authenticated, permissions, resolve_context
from app.tenancy.member_queries import member_view
from app.tenancy.models import Membership


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
    require_capability(db, principal, scope, "memberships.read")
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


def invite(payload: InviteInput, request: Request, db):
    # Read-only lookup used only for consistent sorted identity locks; never returned.
    candidate = db.scalar(select(User).where(User.email_normalized == payload.email))
    principal, scope = context(db, request, candidate.id if candidate else None)
    require_capability(db, principal, scope, "users.create")
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
    require_capability(db, principal, scope, "users.create")
    return {"status": "accepted"}


def member_command(db, request, member_id):
    # Scope filtering happens before returning anything; only actor/target lock IDs read here.
    target_id = db.scalar(select(Membership.user_id).where(Membership.id == member_id))
    principal, scope = context(db, request, target_id)
    member = target_member(db, scope, member_id)
    require_capability(db, principal, scope, "memberships.read")
    return principal, scope, member


def resend_invite(member_id: UUID, request: Request, db):
    principal, scope, member = member_command(db, request, member_id)
    check_role(db, principal, scope, member.role_id)
    require_capability(db, principal, scope, "users.invite")
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
    require_capability(db, principal, scope, "users.invite")
    return {"status": "accepted"}


def request_reset(member_id: UUID, request: Request, db):
    principal, scope, member = member_command(db, request, member_id)
    role = load_role(db, scope, member.role_id)
    require_capability(db, principal, scope, "users.password_reset")
    if principal.platform_role == "PLATFORM_SUPPORT" and role_sensitive(
        role, permissions(db, role)
    ):
        raise ApiError(403, "ROLE_INELIGIBLE", "Perfil nao permitido.")
    if (
        not member.active
        or member.blocked
        or member.invitation_pending
        or not role.active
    ):
        raise ApiError(409, "RESET_UNAVAILABLE", "Redefinicao indisponivel.")
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
    require_capability(db, principal, scope, "users.password_reset")
    return {"status": "accepted"}


def change_status(
    member_id: UUID, payload: MembershipStatusInput, request: Request, db
):
    principal, scope, member = member_command(db, request, member_id)
    role = load_role(db, scope, member.role_id)
    require_capability(db, principal, scope, "users.status")
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
    return member_view(db, principal, scope, member)
