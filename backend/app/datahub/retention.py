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
    examined = 0
    for path in store.root.iterdir():
        if examined >= limit:
            break
        examined += 1
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
