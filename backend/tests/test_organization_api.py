from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import assert_internal_failure, select_context


def create_node(client, headers, code="UNIT_A", kind="UNIT", **kwargs):
    return client.post(
        "/api/organization/nodes",
        headers=headers,
        json={"kind": kind, "name": code, "code": code, **kwargs},
    )


def test_catalogue_and_worksite_are_real(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    response = admin.get("/api/organization/node-types", headers=scope)
    assert response.status_code == 200
    assert {v["kind"] for v in response.json()["items"]} == {
        "COMPANY",
        "BRANCH",
        "UNIT",
        "STORE",
        "DISTRIBUTION_CENTER",
        "WAREHOUSE",
        "OFFICE",
        "WORKSITE",
    }
    row = create_node(admin, scope, " site_a ", "WORKSITE")
    assert row.status_code == 201
    assert row.json()["code"] == "SITE_A"
    assert row.json()["depth"] == 0
    assert row.json()["parent_name"] is None
    assert row.json()["version"] == 1
    assert row.json()["created_at"] and row.json()["updated_at"]


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "PROJECT"},
        {"name": " "},
        {"code": "bad code"},
        {"url": "https://invalid.test"},
    ],
)
def test_invalid_physical_nodes(admin, scope_ids, payload):
    scope = select_context(admin, scope_ids["contract_a"])
    response = admin.post(
        "/api/organization/nodes",
        headers=scope,
        json={"kind": "UNIT", "name": "Unit", "code": "UNIT_A", **payload},
    )
    assert response.status_code == 422


def test_support_and_member_have_no_structure_access(support, member, scope_ids):
    for client in [support, member]:
        scope = select_context(client, scope_ids["contract_a"])
        assert client.get("/api/organization/nodes", headers=scope).status_code == 403
        assert create_node(client, scope).status_code == 403


def test_foreign_nodes_are_hidden_before_filters_and_parent_checks(admin, scope_ids):
    scopes = {
        key: select_context(admin, scope_ids[key])
        for key in ["contract_a", "contract_a2", "contract_b"]
    }
    foreign = [
        create_node(admin, scopes[key], key.upper()).json()["id"]
        for key in ["contract_a2", "contract_b"]
    ]
    headers = scopes["contract_a"]
    assert (
        admin.get(
            "/api/organization/nodes?search=CONTRACT&limit=1", headers=headers
        ).json()["total"]
        == 0
    )
    for node in foreign:
        assert (
            admin.get("/api/organization/nodes/" + node, headers=headers).status_code
            == 404
        )
        assert create_node(admin, headers, parent_id=node).status_code == 404
        assert (
            admin.patch(
                "/api/organization/nodes/" + node,
                headers=headers,
                json={"expected_version": 1, "name": "Changed"},
            ).status_code
            == 404
        )


def test_tree_matrix_cycle_code_version_and_lifecycle(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    root = create_node(admin, scope).json()
    child = create_node(admin, scope, "UNIT_B", parent_id=root["id"]).json()
    leaf = create_node(admin, scope, "OFFICE_A", "OFFICE", parent_id=child["id"]).json()
    assert leaf["depth"] == 2 and leaf["parent_code"] == "UNIT_B"
    path = "/api/organization/nodes/" + root["id"]
    assert admin.get(path, headers=scope).json()["active_child_count"] == 1
    for mutation in [
        {"parent_id": child["id"]},
        {"parent_id": root["id"]},
        {"active": False},
    ]:
        assert (
            admin.patch(
                path, headers=scope, json={"expected_version": 1, **mutation}
            ).status_code
            == 409
        )
    assert (
        admin.patch(
            path, headers=scope, json={"expected_version": 1, "code": "OTHER"}
        ).status_code
        == 422
    )
    assert (
        create_node(
            admin, scope, "COMPANY_A", "COMPANY", parent_id=root["id"]
        ).status_code
        == 422
    )
    assert create_node(admin, scope, "UNIT_C", parent_id=leaf["id"]).status_code == 422
    options = admin.get(
        "/api/organization/nodes?parent_for_kind=UNIT&exclude_descendants_of="
        + root["id"],
        headers=scope,
    )
    assert options.json()["items"] == []
    patched = admin.patch(
        "/api/organization/nodes/" + leaf["id"],
        headers=scope,
        json={"expected_version": 1, "active": False},
    )
    assert patched.status_code == 200 and patched.json()["version"] == 2
    assert (
        admin.patch(
            "/api/organization/nodes/" + leaf["id"],
            headers=scope,
            json={"expected_version": 1, "name": "stale"},
        ).status_code
        == 409
    )
    assert (
        admin.patch(
            "/api/organization/nodes/" + child["id"],
            headers=scope,
            json={"expected_version": 1, "active": False},
        ).status_code
        == 200
    )
    assert (
        admin.patch(
            "/api/organization/nodes/" + leaf["id"],
            headers=scope,
            json={"expected_version": 2, "active": True},
        ).status_code
        == 409
    )
    assert (
        create_node(
            admin, scope, "OFFICE_B", "OFFICE", parent_id=child["id"]
        ).status_code
        == 409
    )
    assert create_node(admin, scope).status_code == 409


def test_unit_scope_minimum_api_and_dependencies(admin, support, scope_ids, db_runtime):
    scope = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, scope).json()
    path = "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope"
    initial = admin.get(path, headers=scope)
    assert initial.status_code == 200 and initial.json()["node_ids"] == []
    assert (
        admin.put(
            path, headers=scope, json={"node_ids": [node["id"]], "expected_version": 1}
        ).status_code
        == 200
    )
    assert (
        admin.get("/api/organization/nodes/" + node["id"], headers=scope).json()[
            "scope_membership_count"
        ]
        == 1
    )
    assert (
        admin.patch(
            "/api/organization/nodes/" + node["id"],
            headers=scope,
            json={"expected_version": 1, "active": False},
        ).status_code
        == 409
    )
    assert (
        admin.put(
            path, headers=scope, json={"node_ids": [], "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        admin.put(
            path, headers=scope, json={"node_ids": [], "expected_version": 2}
        ).status_code
        == 200
    )
    assert (
        admin.put(
            path,
            headers=scope,
            json={"node_ids": [str(uuid4())], "expected_version": 3},
        ).status_code
        == 404
    )
    supp = select_context(support, scope_ids["contract_a"])
    assert support.get(path, headers=supp).status_code == 403
    assert (
        support.put(
            path, headers=supp, json={"node_ids": [], "expected_version": 3}
        ).status_code
        == 403
    )
    for key in ["member_a2", "member_b"]:
        assert (
            admin.get(
                "/api/memberships/" + str(scope_ids[key]) + "/unit-scope", headers=scope
            ).status_code
            == 404
        )
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM membership_unit_scopes WHERE active=false")
            ).scalar_one()
            == 1
        )


def test_organization_audit_is_atomic_and_typed(
    admin, scope_ids, db_runtime, monkeypatch
):
    scope = select_context(admin, scope_ids["contract_a"])
    from app.audit import service

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(service, "append_event", fail)
    # tenancy.services owns imported append_event
    monkeypatch.setattr("app.tenancy.services.append_event", fail)
    response = create_node(admin, scope)
    assert_internal_failure(response, "Audit unavailable")
    with db_runtime.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM organization_nodes")).scalar_one()
            == 0
        )


@pytest.mark.parametrize("code", ["cd-cwb", "LOJA-BAURU", "WS-OBRA-001"])
def test_stable_organization_code_accepts_approved_hyphens(admin, scope_ids, code):
    scope = select_context(admin, scope_ids["contract_a"])
    result = create_node(admin, scope, code)
    assert result.status_code == 201
    assert result.json()["code"] == code.upper()


def test_hierarchy_is_preorder_before_pagination(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    root = create_node(admin, scope, "ZZ_ROOT", "COMPANY").json()
    child = create_node(admin, scope, "AA_CHILD", "UNIT", parent_id=root["id"]).json()
    leaf = create_node(admin, scope, "AA_LEAF", "OFFICE", parent_id=child["id"]).json()
    assert [
        row["id"]
        for row in admin.get("/api/organization/nodes", headers=scope).json()["items"]
    ] == [root["id"], child["id"], leaf["id"]]
    page = admin.get("/api/organization/nodes?limit=1&offset=1", headers=scope).json()
    assert page["total"] == 3 and page["items"][0]["id"] == child["id"]


def test_physical_containment_matrix_is_enforced_on_create(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    kinds = ["COMPANY", "BRANCH", "UNIT", "STORE", "DISTRIBUTION_CENTER", "WAREHOUSE", "OFFICE", "WORKSITE"]
    expected = {
        "COMPANY": set(kinds) - {"COMPANY"},
        "BRANCH": {"UNIT", "STORE", "DISTRIBUTION_CENTER", "WAREHOUSE", "OFFICE", "WORKSITE"},
        "UNIT": {"UNIT", "STORE", "DISTRIBUTION_CENTER", "WAREHOUSE", "OFFICE", "WORKSITE"},
        "STORE": {"WAREHOUSE", "OFFICE"}, "DISTRIBUTION_CENTER": {"WAREHOUSE", "OFFICE"},
        "WAREHOUSE": {"OFFICE"}, "WORKSITE": {"OFFICE"}, "OFFICE": set(),
    }
    roots = {kind: create_node(admin, scope, kind + "_ROOT", kind).json() for kind in kinds}
    for parent in kinds:
        for kind in kinds:
            response = create_node(admin, scope, parent + "_" + kind, kind, parent_id=roots[parent]["id"])
            assert response.status_code == (201 if kind in expected[parent] else 422), (parent, kind)


def test_unit_scope_foreign_inactive_duplicates_and_boundaries(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    inactive = create_node(admin, scope, active=False).json()
    path = "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope"
    assert admin.put(path, headers=scope, json={"node_ids": [inactive["id"]], "expected_version": 1}).status_code == 409
    assert admin.put(path, headers=scope, json={"node_ids": [inactive["id"], inactive["id"]], "expected_version": 1}).status_code == 422
    assert admin.put(path, headers=scope, json={"node_ids": [str(uuid4()) for _ in range(101)], "expected_version": 1}).status_code == 422
    for contract in ["contract_a2", "contract_b"]:
        foreign = select_context(admin, scope_ids[contract])
        node = create_node(admin, foreign).json()
        assert admin.put(path, headers=scope, json={"node_ids": [node["id"]], "expected_version": 1}).status_code == 404
    assert admin.get(path, headers=scope).json()["version"] == 1


def test_full_accepted_node_name_can_be_searched(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    name = "Unidade " + "a" * 192
    node = create_node(admin, scope, name=name).json()
    response = admin.get("/api/organization/nodes", headers=scope, params={"search": name})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == node["id"]
