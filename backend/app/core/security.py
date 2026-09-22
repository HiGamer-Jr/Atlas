from hashlib import sha256
from hmac import compare_digest
from ipaddress import ip_address
from secrets import token_urlsafe

from fastapi import Request, Response

from app.core.errors import ApiError

SESSION_COOKIE = "__Host-hiatlas-session"
CSRF_COOKIE = "__Host-hiatlas-csrf"
PREAUTH_COOKIE = "__Host-hiatlas-preauth"


def token_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def new_token() -> tuple[str, str]:
    value = token_urlsafe(32)
    return value, token_hash(value)


def matches(value: str | None, expected_hash: str) -> bool:
    return bool(
        value and len(value) <= 128 and compare_digest(token_hash(value), expected_hash)
    )


def set_cookie(response: Response, name: str, value: str, seconds: int):
    response.set_cookie(
        name,
        value,
        max_age=seconds,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )


def require_origin(request: Request):
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        raise ApiError(403, "CSRF_INVALID", "Origem ou token de segurança inválido.")


def require_csrf(request: Request, expected_hash: str):
    require_origin(request)
    if not matches(request.headers.get("x-csrf-token"), expected_hash):
        raise ApiError(403, "CSRF_INVALID", "Origem ou token de segurança inválido.")


def client_source(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    # Only an explicitly trusted, single-hop proxy may provide one address.
    if peer in request.app.state.settings.trusted_proxy_ips:
        forwarded = request.headers.get("x-forwarded-for", "")
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return peer[:128]
