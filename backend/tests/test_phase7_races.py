from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import monotonic, sleep

import pytest
from sqlalchemy import text

from tests.helpers import select_context
from tests.identity_helpers import login, seed_user
from tests.test_organization_api import create_node


def wait_for_lock(engine):
    deadline = monotonic() + 10
    while monotonic() < deadline:
        with engine.connect() as conn:
            waiting = conn.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename=current_user AND wait_event_type='Lock')"
                )
            ).scalar_one()
        if waiting:
            return
        sleep(0.02)
    raise AssertionError("Request did not wait for dependent lock")


def second_admin(new_client, db_runtime, scope_ids):
    seed_user(db_runtime, "second-admin@example.test", "PLATFORM_ADMIN")
    browser = new_client()
    login(browser, "second-admin@example.test")
    return browser, select_context(browser, scope_ids["contract_a"])


@pytest.mark.parametrize(
    "operation", ["cycle", "node_version", "module_insert", "module_version"]
)
def test_concurrent_contract_mutations_are_serialized(
    admin, new_client, db_runtime, scope_ids, operation
):
    scope = select_context(admin, scope_ids["contract_a"])
    other, other_scope = second_admin(new_client, db_runtime, scope_ids)
    if operation in {"cycle", "node_version"}:
        first = create_node(admin, scope).json()
        second = create_node(admin, scope, "UNIT_B").json()
        path = "/api/organization/nodes/" + first["id"]
        actions = [
            (admin, scope, path, {"expected_version": 1, "parent_id": second["id"]}),
            (
                other,
                other_scope,
                "/api/organization/nodes/" + second["id"]
                if operation == "cycle"
                else path,
                {"expected_version": 1, "parent_id": first["id"]}
                if operation == "cycle"
                else {"expected_version": 1, "name": "Changed"},
            ),
        ]
    else:
        module = None
        version = 0
        if operation == "module_version":
            row = admin.patch(
                "/api/contract/modules/COMEX",
                headers=scope,
                json={
                    "contracted": True,
                    "active": False,
                    "module_id": None,
                    "expected_version": 0,
                },
            ).json()
            module, version = row["id"], 1
        payload = {
            "contracted": True,
            "active": True,
            "module_id": module,
            "expected_version": version,
        }
        actions = [
            (admin, scope, "/api/contract/modules/COMEX", payload),
            (other, other_scope, "/api/contract/modules/COMEX", payload),
        ]
    barrier = Barrier(2)

    def send(action):
        browser, headers, path, payload = action
        barrier.wait(timeout=5)
        return browser.patch(path, headers=headers, json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send, action) for action in actions]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.status_code for result in results) == [200, 409]
    with db_runtime.connect() as conn:
        if operation == "cycle":
            assert (
                conn.execute(
                    text(
                        "SELECT count(*) FROM organization_nodes WHERE parent_id IS NOT NULL"
                    )
                ).scalar_one()
                == 1
            )
        elif operation.startswith("module"):
            assert (
                conn.execute(text("SELECT count(*) FROM contract_modules")).scalar_one()
                == 1
            )
            assert conn.execute(
                text("SELECT version FROM contract_modules")
            ).scalar_one() == (1 if operation == "module_insert" else 2)


@pytest.mark.parametrize(
    "operation", ["create_parent", "patch_node", "module", "unit_scope"]
)
def test_context_expiry_after_dependent_lock_rolls_back(
    admin, new_client, db_runtime, scope_ids, clock, app, operation
):
    app.state.settings.context_seconds = 60
    scope = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, scope).json()
    row = admin.patch(
        "/api/contract/modules/COMEX",
        headers=scope,
        json={
            "contracted": True,
            "active": False,
            "module_id": None,
            "expected_version": 0,
        },
    ).json()
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    with db_runtime.connect() as conn:
        audits = conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as blocker:
            table, key = (
                ("contract_modules", row["id"])
                if operation == "module"
                else ("memberships", scope_ids["member_a"])
                if operation == "unit_scope"
                else ("organization_nodes", node["id"])
            )
            blocker.execute(
                text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"), {"id": key}
            )
            if operation == "create_parent":
                future = pool.submit(
                    create_node, safe, scope, "OFFICE_A", "OFFICE", parent_id=node["id"]
                )
            elif operation == "patch_node":
                future = pool.submit(
                    safe.patch,
                    "/api/organization/nodes/" + node["id"],
                    headers=scope,
                    json={"expected_version": 1, "name": "Changed"},
                )
            elif operation == "module":
                future = pool.submit(
                    safe.patch,
                    "/api/contract/modules/COMEX",
                    headers=scope,
                    json={
                        "contracted": True,
                        "active": True,
                        "module_id": row["id"],
                        "expected_version": 1,
                    },
                )
            else:
                future = pool.submit(
                    safe.put,
                    "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope",
                    headers=scope,
                    json={"node_ids": [node["id"]], "expected_version": 1},
                )
            wait_for_lock(db_runtime)
            clock.advance(seconds=61)
        assert future.result(timeout=10).status_code == 403
    with db_runtime.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
            == audits
        )
        assert (
            conn.execute(text("SELECT count(*) FROM organization_nodes")).scalar_one()
            == 1
        )
        assert (
            conn.execute(text("SELECT version FROM organization_nodes")).scalar_one()
            == 1
        )
        assert (
            conn.execute(text("SELECT active FROM contract_modules")).scalar_one()
            is False
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM membership_unit_scopes")
            ).scalar_one()
            == 0
        )


@pytest.mark.parametrize("operation", ["node", "module", "scope"])
def test_contract_inactivated_while_waiting_denies_mutation(
    admin, new_client, db_runtime, scope_ids, operation
):
    scope = select_context(admin, scope_ids["contract_a"])
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    with db_runtime.connect() as conn:
        audits = conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as blocker:
            blocker.execute(
                text("UPDATE contracts SET active=false WHERE id=:id"),
                {"id": scope_ids["contract_a"]},
            )
            if operation == "node":
                future = pool.submit(create_node, safe, scope)
            elif operation == "module":
                future = pool.submit(
                    safe.patch,
                    "/api/contract/modules/COMEX",
                    headers=scope,
                    json={
                        "contracted": True,
                        "active": True,
                        "module_id": None,
                        "expected_version": 0,
                    },
                )
            else:
                future = pool.submit(
                    safe.put,
                    "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope",
                    headers=scope,
                    json={"node_ids": [], "expected_version": 1},
                )
            wait_for_lock(db_runtime)
        assert future.result(timeout=10).status_code == 403
    with db_runtime.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
            == audits
        )
