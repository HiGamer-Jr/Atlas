"""Bounded local retention; normalized evidence is never removed."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.audit.schemas import AuditInput
from app.audit.service import append_event
from app.core.errors import ApiError
from app.datahub.models import DataHubImport, DataHubImportFile
from app.datahub.raw_store import RawFileReference
from app.datahub.schemas import RetentionSummary
from app.datahub.services import snapshot
from app.identity.tokens import lifecycle_lock
from app.tenancy.contexts import now


def cleanup_raw(db, store, limit: int) -> RetentionSummary:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Invalid cleanup limit")
    lifecycle_lock(db)
    store.check_root()
    clock = now(db)
    deleted = failed = expired = orphans = 0
    pending = list(
        db.scalars(
            select(DataHubImport)
            .where(
                DataHubImport.status.in_(
                    ("RECEIVED", "VALIDATING", "READY_FOR_CONFIRMATION")
                ),
                DataHubImport.preview_expires_at <= clock,
            )
            .order_by(DataHubImport.preview_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for row in pending:
        before = snapshot(row)
        row.status, row.result_code, row.finished_at = (
            "EXPIRED",
            "PREVIEW_EXPIRED",
            clock,
        )
        row.version += 1
        append_event(
            db,
            AuditInput(
                actor_id=row.actor_user_id,
                actor_role=None,
                tenant_id=row.tenant_id,
                contract_id=row.contract_id,
                entity_type="datahub_import",
                entity_id=row.id,
                action="datahub.import.expired",
                reason="Expiração automática do preview; nenhum comando do usuário.",
                outcome="SUCCESS",
                before=before,
                after=snapshot(row),
                request_id=uuid4(),
            ),
        )
        expired += 1
    files = db.scalars(
        select(DataHubImportFile)
        .where(
            DataHubImportFile.raw_expires_at <= clock,
            DataHubImportFile.raw_deleted_at.is_(None),
        )
        .order_by(DataHubImportFile.raw_expires_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    for file in files:
        try:
            store.remove(RawFileReference(file.raw_reference))
        except (OSError, ApiError):
            failed += 1
            continue
        file.raw_reference = None
        file.raw_deleted_at = clock
        deleted += 1
    db.flush()
    grace = db.info["settings"].datahub_limits.orphan_grace_seconds
    # Only canonical UUID.enc regular files in the configured private directory.
    for path in scan_batch(store, limit):
        if (
            path.suffix != ".enc"
            or path.is_symlink()
            or path.is_junction()
            or not path.is_file()
        ):
            continue
        try:
            identity = UUID(path.stem)
            if str(identity) != path.stem or datetime.fromtimestamp(
                path.stat().st_mtime, UTC
            ) > clock - timedelta(seconds=grace):
                continue
            if db.scalar(
                select(DataHubImportFile.id).where(
                    DataHubImportFile.raw_reference == identity
                )
            ):
                continue
            store.remove(RawFileReference(identity))
            orphans += 1
        except (OSError, ValueError, ApiError):
            failed += 1
    return RetentionSummary(
        deleted=deleted, failed=failed, orphans_deleted=orphans, expired=expired
    )


def scan_batch(store, limit):
    """Rotate bounded metadata/deletion work; directory names are enumerated."""
    import os

    cursor = store.root / ".retention-cursor"
    if cursor.is_symlink() or cursor.is_junction():
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    after = ""
    if cursor.exists():
        try:
            descriptor = os.open(
                cursor,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
            )
            with os.fdopen(descriptor, "rb") as stream:
                raw = stream.read(64).decode("ascii")
            if raw.endswith(".enc") and str(UUID(raw[:-4])) + ".enc" == raw:
                after = raw
        except (OSError, ValueError, UnicodeError):
            after = ""
    names = []
    for path in store.root.iterdir():
        try:
            if path.suffix == ".enc" and str(UUID(path.stem)) == path.stem:
                names.append(path.name)
        except ValueError:
            continue
    names.sort()
    selected = [name for name in names if name > after][:limit]
    if not selected:
        selected = names[:limit]
    if selected:
        temporary = store.root / (str(uuid4()) + ".cursor-tmp")
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(selected[-1].encode("ascii"))
                stream.flush()
                os.fsync(stream.fileno())
            store.check_root()
            temporary.replace(cursor)
        finally:
            temporary.unlink(missing_ok=True)
    return [store.root / name for name in selected]
