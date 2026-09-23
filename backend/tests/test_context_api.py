from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, select_context
from tests.identity_helpers import login


def test_contract_list_requires_auth(client):
    assert client.get("/api/contracts").status_code == 401


def test_admin_can_create_tenant_and_contract_with_audit(admin, db_runtime):
    tenant = admin.post("/api/tenants", json={"name": "New tenant"})
    assert tenant.status_code == 201
    result = admin.post(
        f"/api/tenants/{tenant.json()['id']}/contracts",
        json={"name": "Contract", "code": "CTR-NEW", "environment": "TEST"},
    )
    assert result.status_code == 201
    with db_runtime.connect() as conn:
        assert set(conn.execute(text("SELECT action FROM audit_events")).scalars()) == {
            "tenant.created",
            "contract.created",
        }


def test_support_cannot_create_tenants_or_contracts(support, scope_ids):
    assert support.post("/api/tenants", json={"name": "Forbidden"}).status_code == 403
    assert (
        support.post(
            f"/api/tenants/{scope_ids['tenant_a']}/contracts",
            json={"name": "Contract", "code": "NO", "environment": "TEST"},
        ).status_code
        == 403
    )


def test_contract_list_internal_metadata_is_minimal(admin, scope_ids):
    rows = admin.get("/api/contracts").json()["items"]
    assert len(rows) == 3
    assert all(
        set(row) == {"id", "tenant_id", "tenant_name", "name", "code", "environment"}
        for row in rows
    )


def test_client_only_lists_active_memberships(member, scope_ids):
    rows = member.get("/api/contracts").json()["items"]
    assert {row["id"] for row in rows} == {
        str(scope_ids["contract_a"]),
        str(scope_ids["contract_a2"]),
    }


def test_search_by_company_code_or_user_is_scoped(admin, member, scope_ids):
    assert (
        len(admin.get("/api/contracts", params={"search": "Aurora"}).json()["items"])
        == 2
    )
    assert (
        len(
            admin.get("/api/contracts", params={"search": "other@example.test"}).json()[
                "items"
            ]
        )
        == 1
    )
    assert (
        member.get("/api/contracts", params={"search": "other@example.test"}).json()[
            "items"
        ]
        == []
    )
    assert (
        admin.get("/api/contracts", params={"search": "' OR 1=1 --"}).json()["items"]
        == []
    )
    assert admin.get("/api/contracts", params={"search": "x" * 129}).status_code == 422
    assert admin.get("/api/contracts", params={"limit": 101}).status_code == 422


def test_context_creation_and_close_are_audited(admin, scope_ids, db_runtime):
    headers = select_context(admin, scope_ids["contract_a"])
    current = admin.get("/api/context", headers=headers)
    assert current.status_code == 200
    assert current.json()["contract_id"] == str(scope_ids["contract_a"])
    assert admin.delete("/api/contexts/" + headers[CONTEXT_HEADER]).status_code == 204
    assert admin.get("/api/context", headers=headers).status_code == 403
    with db_runtime.connect() as conn:
        assert set(conn.execute(text("SELECT action FROM audit_events")).scalars()) == {
            "context.selected",
            "context.closed",
        }


def test_context_requires_explicit_selection(admin, scope_ids):
    assert admin.get("/api/context").status_code == 403
    assert (
        admin.get(
            "/api/context", headers={"X-Atlas-Context": str(scope_ids["contract_a"])}
        ).status_code
        == 403
    )
    assert (
        admin.get(
            "/api/context", headers={CONTEXT_HEADER: str(scope_ids["contract_a"])}
        ).status_code
        == 403
    )


def test_context_is_owned_by_exact_session(admin, new_client, scope_ids):
    other = new_client()
    login(other)
    headers = select_context(admin, scope_ids["contract_a"])
    assert other.get("/api/context", headers=headers).status_code == 403
    assert other.delete("/api/contexts/" + headers[CONTEXT_HEADER]).status_code == 404


def test_context_expiration_before_session_expiry(admin, app, clock, scope_ids):
    app.state.settings.context_seconds = 60
    headers = select_context(admin, scope_ids["contract_a"])
    clock.advance(seconds=61)
    assert admin.get("/api/auth/me").status_code == 200
    assert admin.get("/api/context", headers=headers).status_code == 403


def test_two_contexts_do_not_overwrite_each_other(admin, scope_ids):
    a = select_context(admin, scope_ids["contract_a"])
    b = select_context(admin, scope_ids["contract_b"])
    assert a != b
    assert admin.get("/api/context", headers=a).json()["contract_id"] == str(
        scope_ids["contract_a"]
    )
    assert admin.get("/api/context", headers=b).json()["contract_id"] == str(
        scope_ids["contract_b"]
    )
    assert admin.delete("/api/contexts/" + b[CONTEXT_HEADER]).status_code == 204
    assert admin.get("/api/context", headers=a).status_code == 200


def test_client_cannot_select_unrelated_or_unknown_contract(member, scope_ids):
    known = member.post(
        "/api/contexts", json={"contract_id": str(scope_ids["contract_b"])}
    )
    absent = member.post("/api/contexts", json={"contract_id": str(uuid4())})
    assert known.status_code == absent.status_code == 404
    assert known.json()["code"] == absent.json()["code"]


@pytest.mark.parametrize(
    "payload",
    [
        {"tenant_id": str(uuid4())},
        {"contract_id": str(uuid4()), "actor_id": str(uuid4())},
    ],
)
def test_context_payload_cannot_override_owner_or_tenant(admin, payload):
    assert admin.post("/api/contexts", json=payload).status_code == 422
