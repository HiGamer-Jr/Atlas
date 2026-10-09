from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from sqlalchemy import text

from tests.helpers import select_context
from tests.test_organization_api import create_node

URL = "/api/context/operational-scope"


def policy(admin, ids, mode="RESTRICTED", nodes=(), version=1):
    headers = select_context(admin, ids["contract_a"])
    result = admin.put(
        f"/api/memberships/{ids['member_a']}/unit-scope",
        headers=headers,
        json={"mode": mode, "node_ids": list(nodes), "expected_version": version},
    )
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize(
    "mode,count", [("ALL", 3), ("RESTRICTED", 0), ("RESTRICTED", 1), ("RESTRICTED", 2)]
)
def test_self_scope_exact_and_no_admin_permission(
    admin, member, scope_ids, mode, count
):
    admin_scope = select_context(admin, scope_ids["contract_a"])
    root = create_node(admin, admin_scope, "ROOT").json()
    nodes = [
        root,
        create_node(admin, admin_scope, "CHILD", parent_id=root["id"]).json(),
        create_node(admin, admin_scope, "OTHER").json(),
    ]
    desired = [n["id"] for n in nodes[:count]] if mode == "RESTRICTED" else []
    policy(admin, scope_ids, mode, desired)
    headers = select_context(member, scope_ids["contract_a"])
    result = member.get(URL, headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["schema_version"] == 1
    assert body["context_id"] == headers["X-HiAtlas-Context"]
    assert body["customer_scope"]["role"]["code"] == "ROLE_BASIC"
    scope = body["customer_scope"]
    assert scope["unit_scope"]["mode"] == mode
    assert {n["id"] for n in scope["organization_nodes"]} == {
        n["id"] for n in nodes[:count]
    }
    visible = {n["id"] for n in scope["organization_nodes"]}
    assert {
        n["parent_id"] for n in scope["organization_nodes"] if n["parent_id"]
    } <= visible
    assert result.headers["cache-control"] == "no-store"


def test_restricted_child_hides_unauthorized_parent_and_foreign_metadata(
    admin, member, scope_ids
):
    headers = select_context(admin, scope_ids["contract_a"])
    root = create_node(admin, headers, "PRIVATE_PARENT").json()
    child = create_node(admin, headers, "CHILD", parent_id=root["id"]).json()
    for contract in ("contract_a2", "contract_b"):
        foreign_headers = select_context(admin, scope_ids[contract])
        create_node(admin, foreign_headers, "FOREIGN_NODE")
    policy(admin, scope_ids, nodes=[child["id"]])
    headers = select_context(member, scope_ids["contract_a"])
    response = member.get(
        URL,
        headers=headers,
        params={
            "tenant_id": str(scope_ids["tenant_b"]),
            "contract_id": str(scope_ids["contract_b"]),
        },
    )
    assert response.status_code == 200
    nodes = response.json()["customer_scope"]["organization_nodes"]
    assert len(nodes) == 1 and nodes[0]["parent_id"] is None
    assert "PRIVATE_PARENT" not in response.text and "FOREIGN_NODE" not in response.text
    assert str(scope_ids["contract_b"]) not in response.text
    assert member.post(
        "/api/contexts", json={"contract_id": str(scope_ids["contract_b"])}
    ).status_code in (403, 404)


@pytest.mark.parametrize(
    "table,key,change",
    [
        ("memberships", "member_a", "active=false"),
        ("memberships", "member_a", "blocked=true"),
        ("tenant_roles", "role_basic", "active=false"),
        ("contracts", "contract_a", "active=false"),
    ],
)
def test_next_request_revalidates_context(
    member, scope_ids, db_runtime, table, key, change
):
    headers = select_context(member, scope_ids["contract_a"])
    assert member.get(URL, headers=headers).status_code == 200
    with db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET {change} WHERE id=:id"), {"id": scope_ids[key]}
        )
    assert member.get(URL, headers=headers).status_code == 403


@pytest.mark.parametrize("target", ["node", "ancestor", "grant"])
def test_next_request_revalidates_nodes_and_grants(
    admin, member, scope_ids, db_runtime, target
):
    headers = select_context(admin, scope_ids["contract_a"])
    root = create_node(admin, headers, "ROOT").json()
    child = create_node(admin, headers, "CHILD", parent_id=root["id"]).json()
    policy(admin, scope_ids, nodes=[child["id"]])
    headers = select_context(member, scope_ids["contract_a"])
    assert (
        len(
            member.get(URL, headers=headers).json()["customer_scope"][
                "organization_nodes"
            ]
        )
        == 1
    )
    with db_runtime.begin() as conn:
        if target == "grant":
            conn.execute(
                text(
                    "UPDATE membership_unit_scopes SET active=false WHERE membership_id=:id"
                ),
                {"id": scope_ids["member_a"]},
            )
        else:
            conn.execute(
                text("UPDATE organization_nodes SET active=false WHERE id=:id"),
                {"id": UUID(child["id"] if target == "node" else root["id"])},
            )
    assert (
        member.get(URL, headers=headers).json()["customer_scope"]["organization_nodes"]
        == []
    )


@pytest.mark.parametrize("active", [True, False])
def test_contracted_module_and_descriptive_capabilities(
    admin, member, scope_ids, db_runtime, settings, active
):
    settings.datahub_enabled = True
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules (tenant_id,contract_id,code,contracted,active) VALUES (:t,:c,'DATAHUB',true,:a)"
            ),
            {"t": scope_ids["tenant_a"], "c": scope_ids["contract_a"], "a": active},
        )
        conn.execute(
            text(
                "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:t,:c,:r,'datahub.read')"
            ),
            {
                "t": scope_ids["tenant_a"],
                "c": scope_ids["contract_a"],
                "r": scope_ids["role_basic"],
            },
        )
    headers = select_context(member, scope_ids["contract_a"])
    scope = member.get(URL, headers=headers).json()["customer_scope"]
    assert scope["modules"][0]["contracted"] is True
    assert scope["modules"][0]["active"] is active
    assert scope["modules"][0]["operational_available"] is active
    assert ("datahub.read" in scope["capabilities"]) is active
    # A formerly valid UX summary is never accepted as operation authorization.
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE contract_modules SET active=false, contracted=false WHERE contract_id=:c"
            ),
            {"c": scope_ids["contract_a"]},
        )
    response = member.get(
        "/api/datahub/templates",
        headers=headers,
        params={"module": "DATAHUB", "capabilities": "datahub.read"},
    )
    assert response.status_code == 403
    current = member.get(URL, headers=headers).json()["customer_scope"]
    assert current["modules"] == [] and "datahub.read" not in current["capabilities"]


@pytest.mark.parametrize("who", ["admin", "support"])
def test_internal_operator_has_no_fabricated_tenant_role(request, who, scope_ids):
    client = request.getfixturevalue(who)
    headers = select_context(client, scope_ids["contract_a"])
    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["actor_kind"] == "INTERNAL"
    assert response.json()["customer_scope"] is None


def test_two_contexts_and_session_binding(member, admin, scope_ids):
    a = select_context(member, scope_ids["contract_a"])
    b = select_context(member, scope_ids["contract_a2"])
    assert member.get(URL, headers=a).json()["contract"]["id"] == str(
        scope_ids["contract_a"]
    )
    assert member.get(URL, headers=b).json()["contract"]["id"] == str(
        scope_ids["contract_a2"]
    )
    assert admin.get(URL, headers=a).status_code == 403
    member.delete("/api/contexts/" + a["X-HiAtlas-Context"])
    assert member.get(URL, headers=a).status_code == 403
    assert member.get(URL, headers=b).status_code == 200


@pytest.mark.parametrize("count", [1000, 1001])
def test_complete_graph_limit(admin, member, scope_ids, db_runtime, count):
    policy(admin, scope_ids, "ALL")
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organization_nodes (tenant_id,contract_id,kind,name,code) SELECT :t,:c,'UNIT','Unit ' || n,'NODE_' || n FROM generate_series(1,:n) n"
            ),
            {"t": scope_ids["tenant_a"], "c": scope_ids["contract_a"], "n": count},
        )
    headers = select_context(member, scope_ids["contract_a"])
    response = member.get(URL, headers=headers)
    if count == 1000:
        assert response.status_code == 200
        assert len(response.json()["customer_scope"]["organization_nodes"]) == 1000
    else:
        assert response.status_code == 503
        assert response.json()["code"] == "OPERATIONAL_SCOPE_TOO_LARGE"
        assert "customer_scope" not in response.json()


def test_scope_concurrent_versions_have_only_one_winner(admin, scope_ids):
    headers = select_context(admin, scope_ids["contract_a"])
    path = f"/api/memberships/{scope_ids['member_a']}/unit-scope"

    def write(mode):
        return admin.put(
            path, headers=headers, json={"mode": mode, "expected_version": 1}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["ALL", "RESTRICTED"]))
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(r.json() for r in results if r.status_code == 200)
    assert admin.get(path, headers=headers).json() == winner


def test_cycle_fails_closed_without_partial_nodes(admin, member, scope_ids, db_runtime):
    headers = select_context(admin, scope_ids["contract_a"])
    a = create_node(admin, headers, "A").json()["id"]
    b = create_node(admin, headers, "B", parent_id=a).json()["id"]
    policy(admin, scope_ids, "ALL")
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE organization_nodes SET parent_id=:b WHERE id=:a"),
            {"a": UUID(a), "b": UUID(b)},
        )
    headers = select_context(member, scope_ids["contract_a"])
    response = member.get(URL, headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "OPERATIONAL_SCOPE_INVALID"
    assert "customer_scope" not in response.json()


def test_small_restricted_scope_in_oversized_contract_is_not_truncated(
    admin, member, scope_ids, db_runtime
):
    headers = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, headers).json()["id"]
    policy(admin, scope_ids, nodes=[node])
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organization_nodes (tenant_id,contract_id,kind,name,code,active) SELECT :t,:c,'UNIT','Inactive','INACTIVE_' || n,false FROM generate_series(1,1000) n"
            ),
            {"t": scope_ids["tenant_a"], "c": scope_ids["contract_a"]},
        )
    headers = select_context(member, scope_ids["contract_a"])
    response = member.get(URL, headers=headers)
    assert response.status_code == 503
    assert "customer_scope" not in response.json()


def test_inactive_nonoperational_contracted_module_remains_visible(
    member, scope_ids, db_runtime
):
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules (tenant_id,contract_id,code,contracted,active) VALUES (:t,:c,'PROCUREMENT',true,false),(:t,:c,'PROJECTS',true,true)"
            ),
            {"t": scope_ids["tenant_a"], "c": scope_ids["contract_a"]},
        )
    headers = select_context(member, scope_ids["contract_a"])
    modules = member.get(URL, headers=headers).json()["customer_scope"]["modules"]
    assert len(modules) == 2
    assert all(not m["operational_available"] for m in modules)
    assert {m["code"] for m in modules if m["active"]} == {"PROJECTS"}


def test_backend_feature_disable_closes_effective_datahub_availability(
    member, scope_ids, db_runtime, settings
):
    settings.datahub_enabled = False
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules (tenant_id,contract_id,code,contracted,active) VALUES (:t,:c,'DATAHUB',true,true)"
            ),
            {"t": scope_ids["tenant_a"], "c": scope_ids["contract_a"]},
        )
        conn.execute(
            text(
                "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:t,:c,:r,'datahub.read')"
            ),
            {
                "t": scope_ids["tenant_a"],
                "c": scope_ids["contract_a"],
                "r": scope_ids["role_basic"],
            },
        )
    headers = select_context(member, scope_ids["contract_a"])
    customer = member.get(URL, headers=headers).json()["customer_scope"]
    assert customer["modules"][0]["active"] is True
    assert customer["modules"][0]["operational_available"] is False
    assert "datahub.read" not in customer["capabilities"]
