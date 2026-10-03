from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, select_context
from tests.test_grants import start
from tests.test_phase7_races import wait_for_lock


def test_two_grants_same_parent_only_one_effect_and_audit(admin, scope_ids, db_runtime):
    parent = select_context(admin, scope_ids["contract_a"])
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=5)
        return start(admin, scope_ids, parent)[1]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create), pool.submit(create)]
        results = [f.result(timeout=20) for f in futures]
    assert sorted(r.status_code for r in results) == [201, 409]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM temporary_privileged_grants WHERE status='ACTIVE'"
                )
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.started'"
                )
            ).scalar_one()
            == 1
        )


def test_two_ends_same_grant_terminal_is_idempotent(admin, scope_ids, db_runtime):
    parent, response = start(admin, scope_ids)
    row = response.json()
    barrier = Barrier(2)

    def end():
        barrier.wait(timeout=5)
        return admin.post(
            f"/api/grants/{row['id']}/end", headers=parent, json={"expected_version": 1}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(end), pool.submit(end)]
        results = [f.result(timeout=20) for f in futures]
    assert [r.status_code for r in results] == [200, 200]
    assert all(
        r.json()["version"] == 2 and r.json()["status"] == "ENDED" for r in results
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.ended'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "cause", ["expiry", "auth", "parent", "contract", "tenant", "role"]
)
def test_waiting_read_rechecks_all_bound_states(
    admin, scope_ids, db_runtime, clock, cause
):
    parent, response = start(admin, scope_ids)
    row = response.json()
    table, target, change = {
        "expiry": ("temporary_privileged_grants", row["id"], None),
        "auth": ("auth_sessions", None, "revoked_at=now()"),
        "parent": ("access_contexts", parent[CONTEXT_HEADER], "revoked_at=now()"),
        "contract": ("contracts", scope_ids["contract_a"], "active=false"),
        "tenant": ("tenants", scope_ids["tenant_a"], "active=false"),
        # Contract lock lets role mutation commit before the fresh role check.
        "role": ("contracts", scope_ids["contract_a"], None),
    }[cause]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        if cause == "auth":
            target = holder.execute(
                text(
                    "SELECT operator_session_id FROM temporary_privileged_grants WHERE id=:id"
                ),
                {"id": row["id"]},
            ).scalar_one()
        holder.execute(
            text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"), {"id": target}
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                admin.get,
                "/api/grants/context",
                headers={CONTEXT_HEADER: row["context_id"]},
            )
            try:
                wait_for_lock(db_runtime)
                if cause == "expiry":
                    clock.advance(seconds=1801)
                elif cause == "role":
                    holder.execute(
                        text(
                            "UPDATE platform_role_assignments SET active=false WHERE user_id=:id"
                        ),
                        {"id": scope_ids["admin_user"]},
                    )
                else:
                    holder.execute(
                        text(f"UPDATE {table} SET {change} WHERE id=:id"),
                        {"id": target},
                    )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            assert future.result(timeout=20).status_code in {401, 403}
    expected = "EXPIRED" if cause == "expiry" else "REVOKED"
    with db_runtime.connect() as conn:
        assert conn.execute(
            text("SELECT status,version FROM temporary_privileged_grants WHERE id=:id"),
            {"id": row["id"]},
        ).one() == (expected, 2)
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE entity_id=:id AND action IN ('privileged_grant.expired','privileged_grant.revoked')"
                ),
                {"id": row["id"]},
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("cause", ["contract", "parent", "role", "reauth"])
def test_waiting_start_revalidates_authorization_after_lock(
    admin, scope_ids, db_runtime, clock, cause
):
    parent = select_context(admin, scope_ids["contract_a"])
    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT id FROM contracts WHERE id=:id FOR UPDATE"),
            {"id": scope_ids["contract_a"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(start, admin, scope_ids, parent)
            try:
                wait_for_lock(db_runtime)
                if cause == "contract":
                    holder.execute(
                        text("UPDATE contracts SET active=false WHERE id=:id"),
                        {"id": scope_ids["contract_a"]},
                    )
                elif cause == "parent":
                    holder.execute(
                        text(
                            "UPDATE access_contexts SET revoked_at=now() WHERE id=:id"
                        ),
                        {"id": parent[CONTEXT_HEADER]},
                    )
                elif cause == "role":
                    holder.execute(
                        text(
                            "UPDATE platform_role_assignments SET role='PLATFORM_SUPPORT' WHERE user_id=:id"
                        ),
                        {"id": scope_ids["admin_user"]},
                    )
                else:
                    clock.advance(seconds=301)
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            result = future.result(timeout=20)[1]
    assert result.status_code in {401, 403}
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM temporary_privileged_grants")
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.started'"
                )
            ).scalar_one()
            == 0
        )


@pytest.mark.parametrize("control", ["end", "logout"])
def test_terminal_control_concurrent_read_cannot_resurrect_grant(
    admin, scope_ids, db_runtime, control
):
    parent, response = start(admin, scope_ids)
    row = response.json()
    child = {CONTEXT_HEADER: row["context_id"]}
    barrier = Barrier(2)

    def run(kind):
        barrier.wait(timeout=5)
        if kind == "read":
            return admin.get("/api/grants/context", headers=child)
        if control == "logout":
            return admin.post("/api/auth/logout", headers=child)
        return admin.post(
            f"/api/grants/{row['id']}/end", headers=parent, json={"expected_version": 1}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        action = pool.submit(run, "control")
        reading = pool.submit(run, "read")
        assert action.result(timeout=20).status_code == (
            204 if control == "logout" else 200
        )
        assert reading.result(timeout=20).status_code in {200, 401, 403}
    with db_runtime.connect() as conn:
        assert conn.execute(
            text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
            {"id": row["id"]},
        ).scalar_one() == ("REVOKED" if control == "logout" else "ENDED")
