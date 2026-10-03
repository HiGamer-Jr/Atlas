"""Independent phase10 lock and two-operator acceptance checks."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER
from tests.identity_helpers import login, seed_user
from tests.test_correction_handlers import apply, name, preview
from tests.test_grants import start
from tests.test_phase7_races import wait_for_lock


@pytest.mark.parametrize(
    "cause", ["auth", "parent", "contract", "tenant", "role", "grant"]
)
def test_correction_wait_rechecks_revocation(
    admin, correction_case, scope_ids, db_runtime, cause
):
    case = correction_case
    receipt = preview(admin, case).json()["preview_receipt"]
    table, target, change = {
        "auth": ("auth_sessions", None, "revoked_at=now()"),
        "parent": (
            "access_contexts",
            case["parent"][CONTEXT_HEADER],
            "revoked_at=now()",
        ),
        "contract": ("contracts", scope_ids["contract_a"], "active=false"),
        "tenant": ("tenants", scope_ids["tenant_a"], "active=false"),
        "role": ("contracts", scope_ids["contract_a"], None),
        "grant": (
            "temporary_privileged_grants",
            case["grant"]["id"],
            "status='REVOKED',revoked_at=now(),ended_at=now(),version=version+1",
        ),
    }[cause]
    with db_runtime.connect() as holder:
        tx = holder.begin()
        if cause == "auth":
            target = holder.execute(
                text(
                    "SELECT operator_session_id FROM temporary_privileged_grants WHERE id=:id"
                ),
                {"id": case["grant"]["id"]},
            ).scalar_one()
        holder.execute(
            text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"), {"id": target}
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(apply, admin, case, receipt)
            try:
                wait_for_lock(db_runtime)
                if cause == "role":
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
            assert future.result(timeout=20).status_code in (401, 403, 404)
    assert name(db_runtime, case) == ("Original", 1)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='maintenance.correction.applied'"
                )
            ).scalar_one()
            == 0
        )


def test_two_admins_correct_same_version_only_one_commit(
    admin, correction_case, scope_ids, db_runtime, new_client
):
    seed_user(db_runtime, "second-admin@example.test", "PLATFORM_ADMIN")
    second = new_client()
    login(second, "second-admin@example.test")
    _, response = start(
        second,
        scope_ids,
        grant_type="MAINTENANCE",
        reference="SUP-SECOND",
        scopes=[
            {
                "action_code": "FIXTURE_NODE_RENAME",
                "entity_type": "organization_node",
                "entity_id": str(correction_case["node"]),
            }
        ],
    )
    assert response.status_code == 201
    second_case = {
        **correction_case,
        "child": {CONTEXT_HEADER: response.json()["context_id"]},
    }
    receipts = [
        preview(browser, case).json()["preview_receipt"]
        for browser, case in [(admin, correction_case), (second, second_case)]
    ]
    barrier = Barrier(2)

    def execute(browser, case, receipt):
        barrier.wait(timeout=5)
        return apply(browser, case, receipt)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(execute, browser, case, receipt)
            for browser, case, receipt in [
                (admin, correction_case, receipts[0]),
                (second, second_case, receipts[1]),
            ]
        ]
        results = [future.result(timeout=20) for future in pending]
    assert sorted(result.status_code for result in results) == [200, 409]
    assert name(db_runtime, correction_case) == ("Corrected", 2)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='maintenance.correction.applied'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "mode",
    [
        "read_only_admin",
        "financial",
        "support_stolen",
        "new_session",
        "registered_outside_scope",
    ],
)
def test_direct_apply_and_reprocess_cannot_inherit_maintenance(
    admin, support, processing_case, scope_ids, db_runtime, new_client, app, mode
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry
    from tests.test_reprocessing import retry
    from tests.test_support_sessions import start as start_support

    case = processing_case
    receipt = preview(admin, case).json()["preview_receipt"]
    browser = admin
    if mode == "read_only_admin":
        _, response = start_support(admin, scope_ids)
        assert response.status_code == 201
        case["child"] = {CONTEXT_HEADER: response.json()["context_id"]}
    elif mode == "financial":
        _, response = start(admin, scope_ids)
        assert response.status_code == 201
        case["child"] = {CONTEXT_HEADER: response.json()["context_id"]}
    elif mode == "support_stolen":
        browser = support
    elif mode == "new_session":
        browser = new_client()
        login(browser)
    else:
        action = app.state.maintenance_registry.get("FIXTURE_NODE_RENAME")
        app.state.maintenance_registry = MaintenanceActionRegistry(
            [action, replace(action, action_code="FIXTURE_NODE_OTHER")]
        )
        case["payload"] = {**case["payload"], "action_code": "FIXTURE_NODE_OTHER"}
        # Source known under the second registered action, outside the only granted action.
        with db_runtime.begin() as db:
            db.execute(
                text(
                    "UPDATE processing_runs SET action_code='FIXTURE_NODE_OTHER' WHERE id=:id"
                ),
                {"id": case["run"]},
            )
    assert preview(browser, case).status_code in (401, 403, 404)
    assert apply(browser, case, receipt).status_code in (401, 403, 404)
    assert retry(browser, case).status_code in (401, 403, 404)
    assert name(db_runtime, case) == ("Original", 1)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                {"id": case["run"]},
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action IN ('maintenance.correction.applied','maintenance.processing.succeeded')"
                )
            ).scalar_one()
            == 0
        )
