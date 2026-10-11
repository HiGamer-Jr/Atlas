"""Curated partner invitations; caller owns transaction, never browser identity."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import require_csrf
from app.identity.models import User
from app.identity.operators import lock_operator_population
from app.identity.passwords import hash_password, validate_password
from app.identity.schemas import Principal
from app.identity.sessions import authenticate, current_role
from app.identity.tokens import (
    consume,
    lifecycle_lock,
    load_token,
    partner_invitation_event,
    queue_access_email,
    require_mail,
)
from app.partners.lifecycle import identity_locks, organization_lock, revalidate
from app.partners.models import PartnerMembership
from app.tenancy.contexts import now


def invalid():
    return ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")


def eligible_partner_member(db, token, user):
    candidate = db.execute(
        select(PartnerMembership.organization_id, PartnerMembership.user_id).where(
            PartnerMembership.id == token.partner_membership_id
        )
    ).first()
    if candidate is None:
        raise invalid()
    try:
        organization = organization_lock(db, candidate.organization_id)
    except ApiError:
        raise invalid() from None
    member = db.scalar(
        select(PartnerMembership)
        .where(PartnerMembership.id == token.partner_membership_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    issuer = (
        db.get(User, token.issuer_user_id, populate_existing=True)
        if token.issuer_user_id
        else None
    )
    if (
        token.purpose != "INVITE"
        or token.membership_id is not None
        or token.issuer_role != "PLATFORM_ADMIN"
        or issuer is None
        or not issuer.active
        or issuer.blocked
        or current_role(db, issuer.id) != "PLATFORM_ADMIN"
        or member is None
        or member.organization_id != organization.id
        or member.user_id != user.id
        or not organization.active
        or not member.active
        or member.blocked
        or not member.invitation_pending
    ):
        raise invalid()
    return member


def settings_and_transport(db):
    request = db.info.get("request")
    settings = db.info.get("settings")
    transport = (
        request.app.state.email_transport if request else db.info.get("email_transport")
    )
    if settings is None or transport is None:
        raise ApiError(503, "EMAIL_UNAVAILABLE", "Servico de e-mail indisponivel.")
    require_mail(settings, transport)
    return settings


def request_id(db):
    request = db.info.get("request")
    return getattr(request.state, "request_id", uuid4()) if request else uuid4()


def issue_partner_invitation(
    db: Session, principal: Principal, membership_id: UUID
) -> None:
    with db.begin_nested():
        lifecycle_lock(db)
        candidate = db.execute(
            select(PartnerMembership.organization_id, PartnerMembership.user_id).where(
                PartnerMembership.id == membership_id
            )
        ).first()
        capability = "partners.memberships.manage"
        identity_locks(
            db, principal, capability, candidate.user_id if candidate else None
        )
        if candidate is None:
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        organization = organization_lock(db, candidate.organization_id)
        member = db.scalar(
            select(PartnerMembership)
            .where(PartnerMembership.id == membership_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        user = db.get(User, candidate.user_id, populate_existing=True)
        revalidate(db, principal, capability)
        if (
            member is None
            or member.organization_id != organization.id
            or member.user_id != candidate.user_id
            or not organization.active
            or not member.active
            or member.blocked
            or user is None
            or not user.active
            or user.blocked
        ):
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        settings = settings_and_transport(db)
        if not member.invitation_pending:
            member.invitation_pending = True
            member.version += 1
        queue_access_email(
            db,
            settings,
            user,
            "INVITE",
            now(db),
            request_id(db),
            issuer_role="PLATFORM_ADMIN",
            actor_id=principal.user_id,
            partner_member=member,
        )


def authenticated_recipient(db, user, authenticated_user_id):
    request = db.info.get("request")
    if authenticated_user_id != user.id or request is None:
        raise ApiError(
            401, "INVITE_AUTH_REQUIRED", "Entre com sua conta para aceitar o convite."
        )
    principal, _, session = authenticate(db, request, touch=False)
    require_csrf(request, session.csrf_hash)
    clock = now(db)
    if (
        principal.user_id != user.id
        or session.reauthenticated_at is None
        or session.reauthenticated_at
        + timedelta(seconds=db.info["settings"].reauthentication_seconds)
        <= clock
    ):
        raise ApiError(
            401, "INVITE_AUTH_REQUIRED", "Confirme sua senha para aceitar o convite."
        )


def accept_partner_invitation(
    db: Session,
    raw_token: str,
    authenticated_user_id: UUID | None,
    new_password: str | None,
) -> PartnerMembership:
    with db.begin_nested():
        lifecycle_lock(db)
        lock_operator_population(db)
        token, user = load_token(
            db, raw_token, "INVITE", now(db), authenticated_user_id
        )
        if token.partner_membership_id is None:
            raise invalid()
        member = eligible_partner_member(db, token, user)
        if user.password_hash:
            authenticated_recipient(db, user, authenticated_user_id)
            if new_password is not None:
                raise ApiError(
                    422,
                    "INVITE_PASSWORD_FORBIDDEN",
                    "A senha da identidade existente deve ser preservada.",
                )
        else:
            if new_password is None:
                raise ApiError(422, "PASSWORD_INVALID", "Defina sua senha.")
            validate_password(new_password, db.info["settings"])
            user.password_hash = hash_password(new_password)
        clock = now(db)
        consume(db, token, clock)
        member.invitation_pending = False
        member.version += 1
        actor_role = current_role(db, user.id)
        partner_invitation_event(
            db,
            token,
            member,
            "access.invite.consumed",
            request_id(db),
            user.id,
            actor_role,
            "INTERNAL" if actor_role else "PARTNER",
        )
        return member
