"""Single mailbox validation, shared by access inputs and transport envelopes."""

from email.errors import HeaderParseError
from email.headerregistry import Address


def single_mailbox(value: str) -> str:
    normalized = value.strip().lower()
    if any(char in normalized for char in ',;<>:"\\') or any(
        char.isspace() or ord(char) < 32 for char in normalized
    ):
        raise ValueError("Invalid mailbox")
    try:
        parsed = Address(addr_spec=normalized)
    except (ValueError, IndexError, HeaderParseError):
        raise ValueError("Invalid mailbox") from None
    if (
        not parsed.username
        or not parsed.domain
        or parsed.addr_spec != normalized
        or len(normalized) > 320
    ):
        raise ValueError("Invalid mailbox")
    return normalized
