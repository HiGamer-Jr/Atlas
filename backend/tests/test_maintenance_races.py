from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.test_correction_handlers import apply, name, preview
from tests.test_phase7_races import wait_for_lock
from tests.test_reprocessing import retry


def test_concurrent_same_key_runs_one_domain_effect(admin, processing_case, db_runtime):
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=5)
        return retry(admin, processing_case)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=20) for f in [pool.submit(run), pool.submit(run)]]
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json()["id"] == results[1].json()["id"]
    assert name(db_runtime, processing_case) == ("Reprocessed controlled node", 2)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                {"id": processing_case["run"]},
            ).scalar_one()
            == 1
        )
        assert (
            db.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='maintenance.processing.succeeded'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("cause", ["expiry", "version", "domain"])
def test_waiting_correction_revalidates_after_entity_lock(
    admin, correction_case, db_runtime, clock, cause
):
    receipt = preview(admin, correction_case).json()["preview_receipt"]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT id FROM organization_nodes WHERE id=:id FOR UPDATE"),
            {"id": correction_case["node"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(apply, admin, correction_case, receipt)
            try:
                wait_for_lock(db_runtime)
                if cause == "expiry":
                    clock.advance(seconds=1801)
                elif cause == "version":
                    holder.execute(
                        text(
                            "UPDATE organization_nodes SET name='Concurrent',version=2 WHERE id=:id"
                        ),
                        {"id": correction_case["node"]},
                    )
                else:
                    holder.execute(
                        text("UPDATE organization_nodes SET active=false WHERE id=:id"),
                        {"id": correction_case["node"]},
                    )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            assert pending.result(timeout=20).status_code in (403, 404, 409)
    assert name(db_runtime, correction_case).name != "Corrected"


@pytest.mark.parametrize("cause", ["expiry", "source-status", "source-version"])
def test_waiting_reprocess_revalidates_after_source_lock(
    admin, processing_case, db_runtime, clock, cause
):
    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT id FROM processing_runs WHERE id=:id FOR UPDATE"),
            {"id": processing_case["run"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(retry, admin, processing_case)
            try:
                wait_for_lock(db_runtime)
                if cause == "expiry":
                    clock.advance(seconds=1801)
                elif cause == "source-status":
                    holder.execute(
                        text(
                            "UPDATE processing_runs SET status='UNKNOWN' WHERE id=:id"
                        ),
                        {"id": processing_case["run"]},
                    )
                else:
                    holder.execute(
                        text("UPDATE processing_runs SET version=2 WHERE id=:id"),
                        {"id": processing_case["run"]},
                    )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            assert pending.result(timeout=20).status_code in (403, 409)
    assert name(db_runtime, processing_case) == ("Original", 1)


def test_locked_source_re_resolves_registered_handler(
    admin, processing_case, db_runtime, app
):
    from app.grants.registry import MaintenanceActionRegistry

    action = app.state.maintenance_registry.list()[0]

    def fresh(db, entity, source):
        entity.name = "Fresh registered handler"
        entity.version += 1

    second = replace(
        action,
        action_code="FIXTURE_NODE_SECOND",
        handler=replace(action.handler, reprocess=fresh),
    )
    app.state.maintenance_registry = MaintenanceActionRegistry([action, second])
    with db_runtime.begin() as db:
        db.execute(
            text(
                "INSERT INTO maintenance_grant_scopes(grant_id,tenant_id,contract_id,action_code,entity_type,entity_id) SELECT grant_id,tenant_id,contract_id,'FIXTURE_NODE_SECOND',entity_type,entity_id FROM maintenance_grant_scopes WHERE grant_id=:id"
            ),
            {"id": processing_case["grant"]["id"]},
        )
    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT id FROM processing_runs WHERE id=:id FOR UPDATE"),
            {"id": processing_case["run"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(retry, admin, processing_case)
            try:
                wait_for_lock(db_runtime)
                holder.execute(
                    text(
                        "UPDATE processing_runs SET action_code='FIXTURE_NODE_SECOND' WHERE id=:id"
                    ),
                    {"id": processing_case["run"]},
                )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            response = pending.result(timeout=20)
    assert response.status_code == 200
    assert response.json()["action_code"] == "FIXTURE_NODE_SECOND"
    assert name(db_runtime, processing_case) == ("Fresh registered handler", 2)


def test_concurrent_distinct_keys_cannot_repeat_one_source_effect(
    admin, processing_case, db_runtime
):
    barrier = Barrier(2)

    def run(key):
        barrier.wait(timeout=5)
        return admin.post(
            f"/api/processings/{processing_case['run']}/reprocess",
            headers=processing_case["child"],
            json={**processing_case["retry"], "idempotency_key": key},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=20)
            for f in [pool.submit(run, "race-key-a"), pool.submit(run, "race-key-b")]
        ]
    assert sorted(r.status_code for r in results) == [200, 409]
    assert name(db_runtime, processing_case) == ("Reprocessed controlled node", 2)
