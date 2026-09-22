from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select

from app.core.errors import ApiError, error_response
from app.core.security import (
    CSRF_COOKIE,
    PREAUTH_COOKIE,
    SESSION_COOKIE,
    client_source,
    matches,
    new_token,
    require_csrf,
    require_origin,
    set_cookie,
    token_hash,
)
from app.identity.dependencies import Database, require_principal
from app.identity.models import AuthPreauth, AuthSession, User
from app.identity.passwords import verify_password
from app.identity.rate_limits import lock_buckets, record_failure
from app.identity.schemas import (
    CsrfView,
    IdentityView,
    LoginInput,
    PasswordInput,
    Principal,
)
from app.identity.sessions import (
    authenticate,
    current_role,
    identity_view,
    lock_users,
    record_access,
    session_candidate,
)

router = APIRouter()


def csrf_scope(db, request, lock=False):
    now = request.app.state.clock()
    candidate = session_candidate(db, request)
    if (
        candidate is not None
        and candidate.revoked_at is None
        and candidate.expires_at > now
        and candidate.last_seen_at
        + timedelta(seconds=request.app.state.settings.session_idle_seconds)
        > now
    ):
        require_csrf(request, candidate.csrf_hash)
        return candidate
    raw = request.cookies.get(PREAUTH_COOKIE)
    if not raw or len(raw) > 128:
        raise ApiError(403, "CSRF_INVALID", "Origem ou token de segurança inválido.")
    query = select(AuthPreauth).where(AuthPreauth.token_hash == token_hash(raw))
    if lock:
        query = query.with_for_update()
    preauth = db.scalar(query.execution_options(populate_existing=True))
    if preauth is None or preauth.expires_at <= now:
        raise ApiError(403, "CSRF_INVALID", "Origem ou token de segurança inválido.")
    require_csrf(request, preauth.csrf_hash)
    return preauth


@router.get("/auth/csrf", response_model=CsrfView)
def csrf(request: Request, response: Response, db: Database):
    now, settings = request.app.state.clock(), request.app.state.settings
    try:
        _, _, session = authenticate(db, request, touch=False)
    except ApiError as error:
        if error.status != 401:
            raise
        session = None
    supplied = request.cookies.get(CSRF_COOKIE)
    if session is not None:
        if matches(supplied, session.csrf_hash):
            return CsrfView(token=supplied)
        raw, hashed = new_token()
        session.csrf_hash = hashed
        set_cookie(
            response,
            CSRF_COOKIE,
            raw,
            max(1, int((session.expires_at - now).total_seconds())),
        )
        return CsrfView(token=raw)
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
    )
    db.execute(delete(AuthPreauth).where(AuthPreauth.expires_at <= now))
    existing_raw = request.cookies.get(PREAUTH_COOKIE)
    existing = (
        db.get(AuthPreauth, token_hash(existing_raw))
        if existing_raw and len(existing_raw) <= 128
        else None
    )
    if existing and existing.expires_at > now and matches(supplied, existing.csrf_hash):
        return CsrfView(token=supplied)
    raw, hashed = new_token()
    csrf_raw, csrf_hashed = new_token()
    db.add(
        AuthPreauth(
            token_hash=hashed,
            csrf_hash=csrf_hashed,
            expires_at=now + timedelta(seconds=settings.preauth_seconds),
        )
    )
    set_cookie(response, PREAUTH_COOKIE, raw, settings.preauth_seconds)
    set_cookie(response, CSRF_COOKIE, csrf_raw, settings.preauth_seconds)
    return CsrfView(token=csrf_raw)


@router.post("/auth/login", response_model=IdentityView)
def login(payload: LoginInput, request: Request, response: Response, db: Database):
    require_origin(request)
    initial_scope = csrf_scope(db, request)
    now, settings = request.app.state.clock(), request.app.state.settings
    buckets, limited = lock_buckets(
        db, payload.email, client_source(request), now, settings
    )
    if limited:
        record_access(db, request, "auth.login", "DENIED", reason=limited.code)
        return error_response(request, limited)
    user = db.scalar(select(User).where(User.email_normalized == payload.email))
    user_ids = [user.id] if user else []
    if isinstance(initial_scope, AuthSession):
        user_ids.append(initial_scope.user_id)
    lock_users(db, user_ids)
    scope = csrf_scope(db, request, lock=True)
    if isinstance(scope, AuthSession):
        authenticate(db, request, touch=False)
    valid = verify_password(
        user.password_hash if user else None, payload.password.get_secret_value()
    )
    if not valid or user is None or not user.active or user.blocked:
        record_failure(buckets)
        record_access(db, request, "auth.login", "FAILURE")
        return error_response(
            request, ApiError(401, "AUTH_INVALID", "Credenciais inválidas.")
        )
    role = current_role(db, user.id)
    if isinstance(scope, AuthSession):
        scope.revoked_at = now
    else:
        db.delete(scope)
    token, hashed = new_token()
    csrf_raw, csrf_hashed = new_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hashed,
        csrf_hash=csrf_hashed,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=settings.session_absolute_seconds),
        reauthenticated_at=now,
    )
    db.add(session)
    db.flush()
    record_access(db, request, "auth.login", "SUCCESS", user.id, role)
    set_cookie(response, SESSION_COOKIE, token, settings.session_absolute_seconds)
    set_cookie(response, CSRF_COOKIE, csrf_raw, settings.session_absolute_seconds)
    response.delete_cookie(
        PREAUTH_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
    )
    return identity_view(Principal(user.id, session.id, role), user)


@router.get("/auth/me", response_model=IdentityView)
def me(principal: Annotated[Principal, Depends(require_principal)], db: Database):
    return identity_view(principal, db.get(User, principal.user_id))


@router.post("/auth/logout", status_code=204)
def logout(request: Request, db: Database):
    principal, _, session = authenticate(db, request)
    require_csrf(request, session.csrf_hash)
    session.revoked_at = request.app.state.clock()
    record_access(
        db,
        request,
        "auth.logout",
        "SUCCESS",
        principal.user_id,
        principal.platform_role,
    )
    response = Response(status_code=204)
    for name in (SESSION_COOKIE, CSRF_COOKIE, PREAUTH_COOKIE):
        response.delete_cookie(
            name, path="/", secure=True, httponly=True, samesite="strict"
        )
    return response


@router.post("/auth/reauthenticate", status_code=204)
def reauthenticate(payload: PasswordInput, request: Request, db: Database):
    require_origin(request)
    candidate = session_candidate(db, request)
    if candidate is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    require_csrf(request, candidate.csrf_hash)
    user = db.get(User, candidate.user_id)
    now = request.app.state.clock()
    buckets, limited = lock_buckets(
        db,
        user.email_normalized,
        client_source(request),
        now,
        request.app.state.settings,
    )
    if limited:
        record_access(db, request, "auth.reauthenticate", "DENIED", reason=limited.code)
        return error_response(request, limited)
    principal, user, session = authenticate(db, request)
    require_csrf(request, session.csrf_hash)
    if not verify_password(user.password_hash, payload.password.get_secret_value()):
        record_failure(buckets)
        record_access(
            db,
            request,
            "auth.reauthenticate",
            "FAILURE",
            user.id,
            principal.platform_role,
        )
        return error_response(
            request, ApiError(401, "AUTH_INVALID", "Credenciais inválidas.")
        )
    session.reauthenticated_at = now
    record_access(
        db, request, "auth.reauthenticate", "SUCCESS", user.id, principal.platform_role
    )
    return Response(status_code=204)
