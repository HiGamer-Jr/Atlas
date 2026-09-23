from uuid import uuid4

from sqlalchemy import text

from tests.identity_helpers import seed_user

CONTEXT_HEADER = "X-HiAtlas-Context"


def select_context(client, contract_id):
    response = client.post("/api/contexts", json={"contract_id": str(contract_id)})
    assert response.status_code == 201, response.text
    return {CONTEXT_HEADER: response.json()["id"]}


def seed_scope(engine, users):
    ids = {
        name: uuid4()
        for name in (
            "tenant_a",
            "tenant_b",
            "contract_a",
            "contract_a2",
            "contract_b",
            "role_basic",
            "role_opt_out",
            "role_finance",
            "role_admin",
            "role_sensitive_cap",
            "role_a2",
            "role_b",
            "member_a",
            "member_a2",
            "member_b",
            "member_internal",
        )
    }
    other_user = seed_user(engine, "other@example.test")
    with engine.begin() as conn:
        for key, name in [("tenant_a", "Aurora"), ("tenant_b", "Beta")]:
            conn.execute(
                text("INSERT INTO tenants (id,name) VALUES (:id,:name)"),
                {"id": ids[key], "name": name},
            )
        for key, tenant, code in [
            ("contract_a", "tenant_a", "CTR-A"),
            ("contract_a2", "tenant_a", "CTR-A2"),
            ("contract_b", "tenant_b", "CTR-B"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO contracts (id,tenant_id,code,name,environment) VALUES (:id,:tenant,:code,:code,'TEST')"
                ),
                {"id": ids[key], "tenant": ids[tenant], "code": code},
            )
        definitions = [
            (
                "role_basic",
                "tenant_a",
                "contract_a",
                "STANDARD",
                True,
                ["memberships.read", "roles.read"],
            ),
            (
                "role_opt_out",
                "tenant_a",
                "contract_a",
                "STANDARD",
                False,
                ["memberships.read"],
            ),
            (
                "role_finance",
                "tenant_a",
                "contract_a",
                "FINANCIAL_FISCAL",
                True,
                ["finance.read"],
            ),
            (
                "role_admin",
                "tenant_a",
                "contract_a",
                "ADMINISTRATIVE",
                True,
                ["roles.manage"],
            ),
            (
                "role_sensitive_cap",
                "tenant_a",
                "contract_a",
                "STANDARD",
                True,
                ["finance.read"],
            ),
            (
                "role_a2",
                "tenant_a",
                "contract_a2",
                "STANDARD",
                True,
                ["memberships.read"],
            ),
            (
                "role_b",
                "tenant_b",
                "contract_b",
                "STANDARD",
                True,
                ["memberships.read"],
            ),
        ]
        for (
            key,
            tenant,
            contract,
            classification,
            assignable,
            permissions,
        ) in definitions:
            conn.execute(
                text(
                    "INSERT INTO tenant_roles (id,tenant_id,contract_id,code,name,classification,support_assignable) VALUES (:id,:tenant,:contract,:code,:name,:classification,:flag)"
                ),
                {
                    "id": ids[key],
                    "tenant": ids[tenant],
                    "contract": ids[contract],
                    "code": key.upper(),
                    "name": key,
                    "classification": classification,
                    "flag": assignable,
                },
            )
            for capability in permissions:
                conn.execute(
                    text(
                        "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:tenant,:contract,:role,:cap)"
                    ),
                    {
                        "tenant": ids[tenant],
                        "contract": ids[contract],
                        "role": ids[key],
                        "cap": capability,
                    },
                )
        for key, user, tenant, contract, role in [
            ("member_a", users["member_user"], "tenant_a", "contract_a", "role_basic"),
            ("member_a2", users["member_user"], "tenant_a", "contract_a2", "role_a2"),
            ("member_b", other_user, "tenant_b", "contract_b", "role_b"),
            (
                "member_internal",
                users["support_user"],
                "tenant_a",
                "contract_a",
                "role_basic",
            ),
        ]:
            conn.execute(
                text(
                    "INSERT INTO memberships (id,user_id,tenant_id,contract_id,role_id) VALUES (:id,:user,:tenant,:contract,:role)"
                ),
                {
                    "id": ids[key],
                    "user": user,
                    "tenant": ids[tenant],
                    "contract": ids[contract],
                    "role": ids[role],
                },
            )
    return {**users, **ids, "other_user": other_user}
