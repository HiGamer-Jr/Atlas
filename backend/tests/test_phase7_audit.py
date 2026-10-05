from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.audit.schemas import AuditInput, IdentitySnapshot
from tests.helpers import assert_internal_failure, select_context
from tests.test_organization_api import create_node


@pytest.mark.parametrize(
    "action,entity",
    [
        ("organization.node.created", "organization_node"),
        ("organization.node.updated", "organization_node"),
        ("contract.module.updated", "contract_module"),
        ("membership.unit_scope.updated", "membership"),
    ],
)
def test_new_audit_actions_reject_wrong_snapshot_type(action, entity):
    with pytest.raises(ValidationError):
        AuditInput(
            actor_id=uuid4(),
            actor_role="PLATFORM_ADMIN",
            tenant_id=uuid4(),
            contract_id=uuid4(),
            action=action,
            entity_type=entity,
            entity_id=uuid4(),
            after=IdentitySnapshot(user_id=uuid4(), active=True, blocked=False),
        )


def test_admin_audit_projection_support_filters_and_foreign_context(
    admin, support, scope_ids
):
    scope = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, scope).json()
    assert (
        admin.patch(
            "/api/organization/nodes/" + node["id"],
            headers=scope,
            json={"expected_version": 1, "name": "Updated"},
        ).status_code
        == 200
    )
    assert (
        admin.patch(
            "/api/contract/modules/COMEX",
            headers=scope,
            json={
                "contracted": True,
                "active": True,
                "module_id": None,
                "expected_version": 0,
            },
        ).status_code
        == 200
    )
    assert (
        admin.put(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope",
            headers=scope,
            json={"node_ids": [node["id"]], "expected_version": 1},
        ).status_code
        == 200
    )
    events = admin.get("/api/audit", headers=scope)
    assert events.status_code == 200
    rows = [
        row for row in events.json()["items"] if row["action"] != "context.selected"
    ]
    assert {row["action"] for row in rows} == {
        "organization.node.created",
        "organization.node.updated",
        "contract.module.updated",
        "membership.unit_scope.updated",
    }
    for row in rows:
        detail = admin.get("/api/audit/" + row["id"], headers=scope)
        assert detail.status_code == 200 and detail.json()["after"] is not None
        assert detail.json()["reason"] is None and detail.json()["reference"] is None
    supp = select_context(support, scope_ids["contract_a"])
    assert not any(
        row["action"].startswith(("organization.", "membership.unit_scope"))
        for row in support.get("/api/audit", headers=supp).json()["items"]
    )
    for contract in ["contract_a2", "contract_b"]:
        foreign = select_context(admin, scope_ids[contract])
        assert (
            admin.get("/api/audit/" + rows[0]["id"], headers=foreign).status_code == 404
        )


@pytest.mark.parametrize("operation", ["module", "scope"])
def test_module_and_scope_audit_failure_rolls_back(
    admin, scope_ids, db_runtime, monkeypatch, operation
):
    scope = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, scope).json()

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.tenancy.services.append_event", fail)
    if operation == "module":
        response = admin.patch(
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
        response = admin.put(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope",
            headers=scope,
            json={"node_ids": [node["id"]], "expected_version": 1},
        )
    assert_internal_failure(response, "Audit unavailable")
    with db_runtime.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM contract_modules")).scalar_one() == 0
        )
        assert (
            db.execute(text("SELECT count(*) FROM membership_unit_scopes")).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("SELECT version FROM memberships WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            ).scalar_one()
            == 1
        )
