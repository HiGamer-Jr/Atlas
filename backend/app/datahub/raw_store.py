"""Private encrypted XLSX retention; paths and keys never form public DTOs."""

import os
from dataclasses import dataclass
from uuid import UUID, uuid4

from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class RawFileReference:
    id: UUID


class RawStore:
    def __init__(self, settings: Settings):
        if (
            not settings.datahub_enabled
            or not settings.datahub_raw_root
            or not settings.datahub_raw_key
        ):
            raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
        self.root = settings.datahub_raw_root
        self.cipher = Fernet(settings.datahub_raw_key.get_secret_value().encode())
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.check_root()

    def check_root(self):
        if (
            any(
                p.is_symlink() or p.is_junction()
                for p in (self.root, *self.root.parents)
            )
            or not self.root.is_dir()
        ):
            raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")

    def path(self, reference: RawFileReference):
        if not isinstance(reference.id, UUID):
            raise TypeError("Invalid raw reference")
        self.check_root()
        path = self.root / f"{reference.id}.enc"
        if path.is_symlink() or path.is_junction():
            raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
        return path

    def put(self, import_id: UUID, content: bytes) -> RawFileReference:
        if not isinstance(import_id, UUID):
            raise TypeError("Invalid import identity")
        reference = RawFileReference(uuid4())
        path = self.path(reference)
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_BINARY", 0)
        )
        created = False
        try:
            descriptor = os.open(path, flags, 0o600)
            created = True
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self.cipher.encrypt(content))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            if created:
                path.unlink(missing_ok=True)
            raise ApiError(
                503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível."
            ) from None
        return reference

    def remove(self, reference: RawFileReference) -> None:
        self.path(reference).unlink(missing_ok=True)
