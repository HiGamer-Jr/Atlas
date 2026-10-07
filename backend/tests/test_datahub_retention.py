from datetime import UTC, datetime, timedelta
from importlib.util import find_spec

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.datahub.models import DataHubImport, DataHubImportFile, DataHubImportRow
from app.datahub.raw_store import RawStore
from tests.test_datahub_confirmation import confirm
from tests.test_datahub_preview import policy_configured as _policy_fixture
from tests.test_datahub_preview import preview_case as _case_fixture
from tests.test_datahub_preview import product, upload

policy_configured = _policy_fixture
preview_case = _case_fixture


def cleanup(engine, case, *, advance=0, limit=20):
    assert find_spec("app.datahub.retention"), "Retention service missing"
    from cryptography.fernet import Fernet

    from app.core.config import Settings
    from app.datahub.retention import cleanup_raw

    settings = Settings(
        datahub_enabled=True,
        datahub_raw_root=case[2] / "raw",
        datahub_raw_key=Fernet.generate_key().decode(),
    )
    store = RawStore(settings)
    with Session(engine) as db, db.begin():
        db.info.update(
            settings=settings,
            clock=lambda: datetime.now(UTC) + timedelta(seconds=advance),
        )
        return cleanup_raw(db, store, limit)


def test_raw_expiry_preserves_normalized_preview(preview_case, db_runtime):
    preview = upload(
        db_runtime,
        preview_case,
        (product(),),
        settings_overrides={"datahub_limits": {"raw_seconds": 1}},
    )
    result = cleanup(db_runtime, preview_case, advance=2)
    assert result.deleted == 1
    with Session(db_runtime) as db:
        assert db.scalar(select(DataHubImportFile)).raw_reference is None
        assert (
            db.scalar(select(DataHubImportRow)).normalized_payload["codigo"] == "000123"
        )
        assert db.get(DataHubImport, preview.id).status == "READY_FOR_CONFIRMATION"
    assert confirm(db_runtime, preview_case, preview).status == "COMMITTED"


def test_cleanup_retry_and_orphans(preview_case, db_runtime, monkeypatch):
    upload(
        db_runtime,
        preview_case,
        (product(),),
        settings_overrides={"datahub_limits": {"raw_seconds": 1}},
    )
    original = RawStore.remove
    monkeypatch.setattr(
        RawStore,
        "remove",
        lambda *_: (_ for _ in ()).throw(OSError("private synthetic failure")),
    )
    assert cleanup(db_runtime, preview_case, advance=2).failed == 1
    monkeypatch.setattr(RawStore, "remove", original)
    assert cleanup(db_runtime, preview_case, advance=2).deleted == 1
    assert cleanup(db_runtime, preview_case, advance=2).deleted == 0
    import os
    from uuid import uuid4

    path = preview_case[2] / "raw" / f"{uuid4()}.enc"
    path.write_bytes(b"synthetic orphan")
    os.utime(path, (0, 0))
    assert cleanup(db_runtime, preview_case).orphans_deleted == 1


def test_expired_preview_terminal_and_audited(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    cleanup(db_runtime, preview_case, advance=2000)
    with Session(db_runtime) as db:
        assert db.get(DataHubImport, preview.id).status == "EXPIRED"
        from app.audit.models import AuditEvent

        assert db.scalar(
            select(AuditEvent.id).where(AuditEvent.action == "datahub.import.expired")
        )


def test_cleanup_cursor_cannot_starve_later_orphan(preview_case, db_runtime):
    upload(db_runtime, preview_case, (product(),))
    import os

    path = preview_case[2] / "raw" / "ffffffff-ffff-ffff-ffff-ffffffffffff.enc"
    path.write_bytes(b"synthetic orphan")
    os.utime(path, (0, 0))
    # Deterministic ordering reproduces a persistent live prefix.
    from pathlib import Path

    original = Path.iterdir
    from unittest.mock import patch

    with patch.object(
        Path, "iterdir", lambda self: iter(sorted(original(self), key=lambda p: p.name))
    ):
        result = [cleanup(db_runtime, preview_case, limit=1) for _ in range(3)]
    assert sum(r.orphans_deleted for r in result) == 1
