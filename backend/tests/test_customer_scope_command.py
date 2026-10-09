import pytest
from sqlalchemy import text

from tests.helpers import assert_internal_failure, select_context
from tests.test_organization_api import create_node


@pytest.mark.parametrize("nodes", [None, []])
def test_all_to_restricted_does_not_restore_history(admin, scope_ids, nodes):
    headers = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, headers).json()["id"]
    path = f"/api/memberships/{scope_ids['member_a']}/unit-scope"
    assert (
        admin.put(
            path, headers=headers, json={"node_ids": [node], "expected_version": 1}
        ).status_code
        == 200
    )
    result = admin.put(
        path, headers=headers, json={"mode": "ALL", "expected_version": 2}
    )
    assert result.status_code == 200
    assert result.json()["mode"] == "ALL"
    assert result.json()["node_ids"] == []
    payload = {"mode": "RESTRICTED", "expected_version": 3}
    if nodes is not None:
        payload["node_ids"] = nodes
    result = admin.put(path, headers=headers, json=payload)
    assert result.status_code == 200
    assert result.json()["node_ids"] == []
    result = admin.put(
        path,
        headers=headers,
        json={"mode": "RESTRICTED", "node_ids": [node], "expected_version": 4},
    )
    assert result.status_code == 200
    assert result.json()["node_ids"] == [node]


def test_scope_conflict_and_audit_failure_roll_back_everything(
    admin, member, scope_ids, db_runtime, monkeypatch
):
    headers = select_context(admin, scope_ids["contract_a"])
    path = f"/api/memberships/{scope_ids['member_a']}/unit-scope"
    node = create_node(admin, headers).json()["id"]
    assert (
        admin.put(
            path, headers=headers, json={"node_ids": [node], "expected_version": 1}
        ).status_code
        == 200
    )
    customer_headers = select_context(member, scope_ids["contract_a"])
    before = admin.get(path, headers=headers).json()
    assert before["mode"] == "RESTRICTED"
    assert (
        admin.put(
            path, headers=headers, json={"mode": "ALL", "expected_version": 999}
        ).status_code
        == 409
    )
    with db_runtime.connect() as conn:
        contexts = conn.execute(
            text("SELECT id, revoked_at FROM access_contexts ORDER BY id")
        ).all()
        audits = conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.tenancy.services.append_event", fail)
    result = admin.put(
        path, headers=headers, json={"mode": "ALL", "expected_version": 2}
    )
    assert_internal_failure(result, "Audit unavailable")
    assert admin.get(path, headers=headers).json() == before
    assert member.get("/api/context", headers=customer_headers).status_code == 200
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT id, revoked_at FROM access_contexts ORDER BY id")
            ).all()
            == contexts
        )
        assert (
            conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
            == audits
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "UNKNOWN", "node_ids": [], "expected_version": 1},
        {"expected_version": 1},
        {
            "mode": "ALL",
            "node_ids": ["00000000-0000-0000-0000-000000000001"],
            "expected_version": 1,
        },
    ],
)
def test_invalid_policy_is_rejected(admin, scope_ids, payload):
    headers = select_context(admin, scope_ids["contract_a"])
    path = f"/api/memberships/{scope_ids['member_a']}/unit-scope"
    assert admin.put(path, headers=headers, json=payload).status_code == 422


def test_atomic_mode_change_audit_contains_explicit_policy(
    admin, scope_ids, db_runtime
):
    headers = select_context(admin, scope_ids["contract_a"])
    path = f"/api/memberships/{scope_ids['member_a']}/unit-scope"
    result = admin.put(
        path, headers=headers, json={"mode": "ALL", "expected_version": 1}
    )
    assert result.status_code == 200
    with db_runtime.connect() as conn:
        before, after = conn.execute(
            text(
                "SELECT before_state,after_state FROM audit_events WHERE action='membership.unit_scope.updated' AND entity_id=:m"
            ),
            {"m": scope_ids["member_a"]},
        ).one()
    assert before == {"mode": "RESTRICTED", "node_ids": [], "version": 1}
    assert after == {"mode": "ALL", "node_ids": [], "version": 2}
