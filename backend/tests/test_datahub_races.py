from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.core.errors import ApiError
from app.datahub.models import DataHubRecord
from tests.test_datahub_confirmation import confirm, count
from tests.test_datahub_preview import policy_configured as _policy_fixture
from tests.test_datahub_preview import preview_case as _preview_case_fixture
from tests.test_datahub_preview import product, upload
from tests.test_phase7_races import wait_for_lock

preview_case = _preview_case_fixture
policy_configured = _policy_fixture


def test_two_confirms_have_one_commit(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    key = uuid4()
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=5)
        return confirm(db_runtime, preview_case, preview, key=key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=20) for f in [pool.submit(run), pool.submit(run)]]
    assert results[0] == results[1]
    assert count(db_runtime, DataHubRecord) == 1
    with Session(db_runtime) as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(AuditEvent).where(
                            AuditEvent.action == "datahub.import.committed"
                        )
                    )
                )
            )
            == 1
        )


def test_expired_while_waiting_lock_denied(preview_case, db_runtime):
    from datetime import UTC, datetime, timedelta

    preview = upload(db_runtime, preview_case, (product(),))
    current = [datetime.now(UTC)]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT id FROM datahub_imports WHERE id=:id FOR UPDATE"),
            {"id": preview.id},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                confirm, db_runtime, preview_case, preview, clock=lambda: current[0]
            )
            try:
                wait_for_lock(db_runtime)
                current[0] = preview.preview_expires_at + timedelta(seconds=1)
                tx.commit()
                with pytest.raises(ApiError):
                    future.result(timeout=20)
            finally:
                if tx.is_active:
                    tx.rollback()
    assert count(db_runtime, DataHubRecord) == 0


@pytest.mark.parametrize(
    "cause", ["module", "permission", "context", "contract", "membership", "session"]
)
def test_current_state_changed_while_lock_waits(preview_case, db_runtime, cause):
    preview = upload(db_runtime, preview_case, (product(),))
    ids = preview_case[0]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        if cause == "module":
            holder.execute(
                text(
                    "SELECT id FROM contract_modules WHERE contract_id=:id AND code='DATAHUB' FOR UPDATE"
                ),
                {"id": ids["contract_a"]},
            )
            update = (
                "UPDATE contract_modules SET active=false WHERE contract_id=:id AND code='DATAHUB'",
                ids["contract_a"],
            )
        elif cause == "permission":
            holder.execute(
                text(
                    "SELECT role_id FROM tenant_role_permissions WHERE role_id=:id AND capability='datahub.products.import' FOR UPDATE"
                ),
                {"id": ids["role_basic"]},
            )
            update = (
                "UPDATE tenant_role_permissions SET active=false WHERE role_id=:id AND capability='datahub.products.import'",
                ids["role_basic"],
            )
        elif cause == "context":
            holder.execute(
                text("SELECT id FROM access_contexts WHERE id=:id FOR UPDATE"),
                {"id": preview_case[1]["X-HiAtlas-Context"]},
            )
            update = (
                "UPDATE access_contexts SET revoked_at=now() WHERE id=:id",
                preview_case[1]["X-HiAtlas-Context"],
            )
        elif cause == "contract":
            holder.execute(
                text("SELECT id FROM contracts WHERE id=:id FOR UPDATE"),
                {"id": ids["contract_a"]},
            )
            update = (
                "UPDATE contracts SET active=false WHERE id=:id",
                ids["contract_a"],
            )
        elif cause == "membership":
            holder.execute(
                text("SELECT id FROM memberships WHERE id=:id FOR UPDATE"),
                {"id": ids["member_a"]},
            )
            update = (
                "UPDATE memberships SET blocked=true WHERE id=:id",
                ids["member_a"],
            )
        else:
            identity = holder.execute(
                text("SELECT session_id FROM access_contexts WHERE id=:id"),
                {"id": preview_case[1]["X-HiAtlas-Context"]},
            ).scalar_one()
            holder.execute(
                text("SELECT id FROM auth_sessions WHERE id=:id FOR UPDATE"),
                {"id": identity},
            )
            update = (
                "UPDATE auth_sessions SET revoked_at=now() WHERE id=:id",
                identity,
            )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(confirm, db_runtime, preview_case, preview)
            try:
                wait_for_lock(db_runtime)
                holder.execute(text(update[0]), {"id": update[1]})
                tx.commit()
                with pytest.raises(ApiError) as error:
                    pending.result(timeout=20)
                assert error.value.status in (401, 403)
            finally:
                if tx.is_active:
                    tx.rollback()
    assert count(db_runtime, DataHubRecord) == 0


def test_distinct_previews_concurrent_collision_has_one_record(
    preview_case, db_runtime
):
    previews = [
        upload(db_runtime, preview_case, (product(description=d),))
        for d in ("Produto sintético A", "Produto sintético B")
    ]
    barrier = Barrier(2)

    def run(preview):
        barrier.wait(timeout=5)
        try:
            return confirm(db_runtime, preview_case, preview).status
        except ApiError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=20) for f in [pool.submit(run, p) for p in previews]
        ]
    assert sorted(results, key=str) == [409, "COMMITTED"]
    assert count(db_runtime, DataHubRecord) == 1
