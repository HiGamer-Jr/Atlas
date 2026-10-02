from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, select_context
from tests.identity_helpers import login, seed_user
from tests.test_phase7_races import wait_for_lock
from tests.test_support_sessions import start


def test_two_simultaneous_ends_are_idempotent_and_audited_once(
    support, scope_ids, db_runtime
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    barrier = Barrier(2)

    def end():
        barrier.wait(timeout=5)
        return support.post(
            "/api/support-sessions/" + value["id"] + "/end", headers=parent
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=15) for f in [pool.submit(end), pool.submit(end)]]
    assert [r.status_code for r in results] == [204, 204]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='support.session.ended' AND support_session_id=:id"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "cause", ["expiry", "membership", "global", "context", "contract", "role", "auth"]
)
def test_waiting_support_read_rechecks_dependencies_and_persists_atomic_terminal(
    support, scope_ids, db_runtime, clock, cause
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    settings = {
        "expiry": ("support_sessions", value["id"], None),
        "membership": ("memberships", scope_ids["member_a"], "blocked=true"),
        "global": ("users", scope_ids["member_user"], "blocked=true"),
        "context": ("access_contexts", parent[CONTEXT_HEADER], "revoked_at=now()"),
        "contract": ("contracts", scope_ids["contract_a"], "active=false"),
        "role": ("tenant_roles", scope_ids["role_basic"], "active=false"),
        "auth": ("auth_sessions", None, "revoked_at=now()"),
    }
    table, target, change = settings[cause]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        if cause == "auth":
            target = holder.execute(
                text("SELECT id FROM auth_sessions WHERE user_id=:id"),
                {"id": scope_ids["support_user"]},
            ).scalar_one()
        holder.execute(
            text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"), {"id": target}
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                support.get, "/api/support-sessions/" + value["id"], headers=parent
            )
            try:
                wait_for_lock(db_runtime)
                if cause == "expiry":
                    clock.advance(seconds=1801)
                else:
                    holder.execute(
                        text(f"UPDATE {table} SET {change} WHERE id=:id"),
                        {"id": target},
                    )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            result = future.result(timeout=15)
    assert result.status_code in {401, 403}
    with db_runtime.connect() as conn:
        assert conn.execute(
            text("SELECT status FROM support_sessions WHERE id=:id"),
            {"id": value["id"]},
        ).scalar_one() == ("EXPIRED" if cause == "expiry" else "REVOKED")
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE support_session_id=:id AND action IN ('support.session.expired','support.session.revoked')"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


def test_simultaneous_logout_and_read_cannot_resurrect_support(
    support, scope_ids, db_runtime
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    barrier = Barrier(2)

    def run(verb, path):
        barrier.wait(timeout=5)
        return support.request(verb, path, headers=parent)

    with ThreadPoolExecutor(max_workers=2) as pool:
        logout = pool.submit(run, "POST", "/api/auth/logout")
        read = pool.submit(run, "GET", "/api/support-sessions/" + value["id"])
        assert logout.result(timeout=15).status_code == 204
        assert read.result(timeout=15).status_code in {200, 401, 403}
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM support_sessions WHERE id=:id"),
                {"id": value["id"]},
            ).scalar_one()
            == "REVOKED"
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='support.session.revoked' AND support_session_id=:id"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


def test_operator_management_exclusive_lock_has_no_shared_upgrade_deadlock(
    admin, new_client, scope_ids, db_runtime
):
    seed_user(db_runtime, "second-admin@example.test", "PLATFORM_ADMIN")
    other = new_client()
    login(other, "second-admin@example.test")
    # Both independent normal contexts share their own active support flow.
    independent_a = select_context(admin, scope_ids["contract_b"])
    independent_b = select_context(other, scope_ids["contract_b"])
    _, a = start(admin, scope_ids)
    _, b = start(other, scope_ids)
    assert a.status_code == b.status_code == 201
    barrier = Barrier(2)

    def change(client, context):
        barrier.wait(timeout=5)
        return client.post(
            "/api/platform/operators/" + str(scope_ids["support_user"]) + "/status",
            headers=context,
            json={"active": True, "blocked": False},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(change, admin, independent_a),
            pool.submit(change, other, independent_b),
        ]
        results = [future.result(timeout=15) for future in futures]
    assert [result.status_code for result in results] == [200, 200]


@pytest.mark.parametrize("cause", ["expiry", "membership", "context"])
def test_start_waiting_on_target_lock_cannot_use_cached_authorization(
    support, scope_ids, db_runtime, clock, cause
):
    parent = select_context(support, scope_ids["contract_a"])
    with db_runtime.connect() as holder:
        tx = holder.begin()
        table = "access_contexts" if cause == "context" else "memberships"
        target = parent[CONTEXT_HEADER] if cause == "context" else scope_ids["member_a"]
        holder.execute(
            text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"), {"id": target}
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(start, support, scope_ids, parent)
            try:
                wait_for_lock(db_runtime)
                if cause == "expiry":
                    clock.advance(seconds=1801)
                elif cause == "membership":
                    holder.execute(
                        text("UPDATE memberships SET blocked=true WHERE id=:id"),
                        {"id": scope_ids["member_a"]},
                    )
                else:
                    holder.execute(
                        text(
                            "UPDATE access_contexts SET revoked_at=now() WHERE id=:id"
                        ),
                        {"id": parent[CONTEXT_HEADER]},
                    )
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            _, response = future.result(timeout=15)
    assert response.status_code in {401, 403, 404}
    with db_runtime.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM support_sessions")).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='support.session.started'"
                )
            ).scalar_one()
            == 0
        )
