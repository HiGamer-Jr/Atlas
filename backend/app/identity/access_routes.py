from datetime import timedelta
from time import monotonic, sleep

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.core.errors import ApiError, error_response
from app.core.security import client_source, require_origin
from app.identity.dependencies import Database
from app.identity.email_schemas import (
    AcceptInput,
    OperatorInviteInput,
    RecoveryInput,
    ResetInput,
    ValidateTokenInput,
)
from app.identity.models import User
from app.identity.passwords import hash_password, validate_password
from app.identity.routes import csrf_scope
from app.identity.sessions import authenticate, record_access, session_candidate
from app.identity.tokens import (
    access_limit,
    consume,
    event,
    lifecycle_lock,
    load_token,
    queue_access_email,
    require_mail,
    revoke_sessions,
)
from app.tenancy.models import Membership

router = APIRouter()
NEUTRAL = {
    "status": "accepted",
    "message": "Se houver uma conta elegivel para este endereco, enviaremos as instrucoes de recuperacao.",
}


def protect(db, request):
    require_origin(request)
    lifecycle_lock(db)
    csrf_scope(db, request)


def token_limit(db, request, raw):
    return access_limit(
        db,
        "token",
        raw,
        client_source(request),
        request.app.state.clock(),
        request.app.state.settings,
    )


@router.get("/auth/password-policy")
def password_policy(request: Request):
    settings = request.app.state.settings
    return {
        "min_length": settings.password_min_length,
        "max_length": settings.password_max_length,
    }


@router.post("/auth/recovery", status_code=202)
def recovery(payload: RecoveryInput, request: Request, db: Database):
    started = monotonic()
    protect(db, request)
    settings, now = request.app.state.settings, request.app.state.clock()
    require_mail(settings, request.app.state.email_transport)
    limited = access_limit(
        db, "reset", payload.email, client_source(request), now, settings
    )
    if not limited:
        user = db.scalar(
            select(User).where(User.email_normalized == payload.email).with_for_update()
        )
        if user and user.active and not user.blocked and user.password_hash:
            queue_access_email(
                db, settings, user, "PASSWORD_RESET", now, request.state.request_id
            )
    record_access(db, request, "access.reset.requested", "SUCCESS")
    # Fixed floor hides the small eligible/ineligible DB/encryption difference; no account-dependent hash work.
    sleep(max(0, settings.recovery_response_floor_seconds - (monotonic() - started)))
    return NEUTRAL


@router.post("/auth/token/validate")
def validate_token(payload: ValidateTokenInput, request: Request, db: Database):
    protect(db, request)
    if token_limit(db, request, payload.token.get_secret_value()):
        return error_response(
            request,
            ApiError(429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente."),
        )
    try:
        _, user = load_token(
            db,
            payload.token.get_secret_value(),
            payload.purpose,
            request.app.state.clock(),
        )
    except ApiError as exc:
        record_access(db, request, "access.token.rejected", "DENIED", reason=exc.code)
        return error_response(request, exc)
    return {
        "requires_authentication": bool(
            payload.purpose == "INVITE" and user.password_hash
        )
    }


@router.post("/auth/reset-password", status_code=204)
def reset_password(payload: ResetInput, request: Request, db: Database):
    protect(db, request)
    if token_limit(db, request, payload.token.get_secret_value()):
        return error_response(
            request,
            ApiError(429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente."),
        )
    try:
        token, user = load_token(
            db,
            payload.token.get_secret_value(),
            "PASSWORD_RESET",
            request.app.state.clock(),
        )
        validate_password(
            payload.new_password.get_secret_value(), request.app.state.settings
        )
    except ApiError as exc:
        record_access(db, request, "access.reset.rejected", "DENIED", reason=exc.code)
        return error_response(request, exc)
    now = request.app.state.clock()
    user.password_hash = hash_password(payload.new_password.get_secret_value())
    consume(db, token, now)
    revoke_sessions(db, user.id, now)
    member = db.get(Membership, token.membership_id) if token.membership_id else None
    event(db, user.id, "access.reset.consumed", request.state.request_id, member=member)
    event(
        db, user.id, "access.sessions.revoked", request.state.request_id, member=member
    )
    return Response(status_code=204)


@router.post("/auth/accept-invite", status_code=204)
def accept_invite(payload: AcceptInput, request: Request, db: Database):
    protect(db, request)
    if token_limit(db, request, payload.token.get_secret_value()):
        return error_response(
            request,
            ApiError(429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente."),
        )
    now, settings = request.app.state.clock(), request.app.state.settings
    from app.identity.operators import lock_operator_population

    lock_operator_population(db)
    candidate = session_candidate(db, request)
    try:
        token, user = load_token(
            db,
            payload.token.get_secret_value(),
            "INVITE",
            now,
            candidate.user_id if candidate else None,
        )
        if user.password_hash:
            if not candidate or candidate.user_id != user.id:
                raise ApiError(
                    401,
                    "INVITE_AUTH_REQUIRED",
                    "Entre com sua conta para aceitar o convite.",
                )
            _, _, session = authenticate(db, request)
            if (
                session.reauthenticated_at is None
                or session.reauthenticated_at
                + timedelta(seconds=settings.reauthentication_seconds)
                <= now
            ):
                raise ApiError(
                    401,
                    "INVITE_AUTH_REQUIRED",
                    "Confirme sua senha para aceitar o convite.",
                )
            if payload.new_password is not None:
                raise ApiError(
                    422,
                    "INVITE_PASSWORD_FORBIDDEN",
                    "A senha da identidade existente deve ser preservada.",
                )
        else:
            if payload.new_password is None:
                raise ApiError(422, "PASSWORD_INVALID", "Defina sua senha.")
            validate_password(payload.new_password.get_secret_value(), settings)
            user.password_hash = hash_password(payload.new_password.get_secret_value())
    except ApiError as exc:
        record_access(db, request, "access.invite.rejected", "DENIED", reason=exc.code)
        return error_response(request, exc)
    member = db.get(Membership, token.membership_id) if token.membership_id else None
    if member:
        member.invitation_pending = False
        member.version += 1
    if member is None:
        from app.identity.models import PlatformRoleAssignment

        assignment = db.get(PlatformRoleAssignment, user.id, with_for_update=True)
        if assignment is not None and not assignment.active:
            assignment.active = True
            event(db, user.id, "platform.role.changed", request.state.request_id)
    consume(db, token, now)
    event(
        db, user.id, "access.invite.consumed", request.state.request_id, member=member
    )
    return Response(status_code=204)


@router.post("/platform/operators/invite", status_code=202)
def invite_operator(payload: OperatorInviteInput, request: Request, db: Database):
    from app.identity.models import PlatformRoleAssignment
    from app.identity.operators import lock_operator_population
    from app.identity.passwords import verify_password
    from app.identity.rate_limits import lock_buckets, record_failure

    protect(db, request)
    lock_operator_population(db)
    candidate = session_candidate(db, request)
    if candidate is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticacao necessaria.")
    user = db.get(User, candidate.user_id)
    settings, now = request.app.state.settings, request.app.state.clock()
    buckets, limited = lock_buckets(
        db, user.email_normalized, client_source(request), now, settings
    )
    principal, actor, session = authenticate(db, request)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operacao restrita a administracao HiAtlas."
        )
    if limited:
        return error_response(request, limited)
    if not verify_password(actor.password_hash, payload.password.get_secret_value()):
        record_failure(buckets)
        record_access(
            db,
            request,
            "access.operator.invite.denied",
            "DENIED",
            actor.id,
            principal.platform_role,
        )
        return error_response(
            request, ApiError(401, "AUTH_INVALID", "Credenciais invalidas.")
        )
    if (
        payload.confirmation.email != payload.email
        or payload.confirmation.role != payload.role
    ):
        raise ApiError(
            422,
            "CONFIRMATION_MISMATCH",
            "Confirme o destinatario e o papel solicitado.",
        )
    require_mail(settings, request.app.state.email_transport)
    if access_limit(db, "invite", payload.email, client_source(request), now, settings):
        return error_response(
            request,
            ApiError(429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente."),
        )
    session.reauthenticated_at = now
    existing = db.scalar(select(User).where(User.email_normalized == payload.email))
    if existing is not None:
        assignment = db.get(PlatformRoleAssignment, existing.id)
        if (
            existing.password_hash is None
            and existing.active
            and not existing.blocked
            and assignment is not None
            and not assignment.active
            and assignment.role == payload.role
        ):
            queue_access_email(
                db,
                settings,
                existing,
                "INVITE",
                now,
                request.state.request_id,
                issuer_role=principal.platform_role,
                actor_id=principal.user_id,
            )
        return {"status": "accepted"}
    user = User(
        email_normalized=payload.email,
        display_name=payload.display_name,
        active=True,
        blocked=False,
    )
    db.add(user)
    db.flush()
    db.add(PlatformRoleAssignment(user_id=user.id, role=payload.role, active=False))
    event(
        db,
        user.id,
        "platform.role.changed",
        request.state.request_id,
        principal.platform_role,
        actor_id=principal.user_id,
    )
    queue_access_email(
        db,
        settings,
        user,
        "INVITE",
        now,
        request.state.request_id,
        issuer_role=principal.platform_role,
        actor_id=principal.user_id,
    )
    return {"status": "accepted"}
