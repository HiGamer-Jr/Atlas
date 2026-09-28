"""Argon2id credentials; plaintext exists only for the duration of verification."""

from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash(token_urlsafe(32))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    try:
        valid = _hasher.verify(stored or _dummy_hash, password)
        return bool(stored) and valid
    except (VerificationError, InvalidHashError):
        return False


def validate_password(password: str, settings) -> None:
    from app.core.errors import ApiError

    if (
        not settings.password_min_length
        <= len(password)
        <= settings.password_max_length
    ):
        raise ApiError(
            422, "PASSWORD_INVALID", "A senha não atende aos requisitos de tamanho."
        )
