from uuid import uuid4

from sqlalchemy import text

from tests.helpers import select_context


def test_closed_catalogue_defaults_are_readonly(admin, support, scope_ids, db_runtime):
    for client in [admin, support]:
        scope = select_context(client, scope_ids["contract_a"])
        response = client.get("/api/contract/modules", headers=scope)
        assert response.status_code == 200
        rows = response.json()["items"]
        assert {row["code"] for row in rows} == {
            "PROCUREMENT",
            "COMEX",
            "INVENTORY",
            "FINANCE",
            "PROJECTS",
            "DATAHUB",
        }
        assert all(
            row["id"] is None
            and row["version"] == 0
            and not row["enabled"]
            and not row["operational_available"]
            for row in rows
        )
        if client is support:
            assert all(row["allowed_actions"] == [] for row in rows)
    with db_runtime.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM contract_modules")).scalar_one() == 0
        )


def test_module_contract_active_versions_and_foreign_ids(admin, support, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/contract/modules/FINANCE"
    payload = {
        "contracted": True,
        "active": True,
        "expected_version": 0,
        "module_id": None,
    }
    response = admin.patch(path, headers=scope, json=payload)
    assert response.status_code == 200
    row = response.json()
    assert row["enabled"] and row["version"] == 1 and not row["operational_available"]
    assert admin.patch(path, headers=scope, json=payload).status_code == 409
    assert (
        admin.patch(
            path,
            headers=scope,
            json={**payload, "module_id": str(uuid4()), "expected_version": 1},
        ).status_code
        == 404
    )
    assert (
        admin.patch(
            path,
            headers=scope,
            json={
                **payload,
                "contracted": False,
                "module_id": row["id"],
                "expected_version": 1,
            },
        ).status_code
        == 422
    )
    payload.update(module_id=row["id"], expected_version=1, active=False)
    inactive = admin.patch(path, headers=scope, json=payload)
    assert (
        inactive.status_code == 200
        and inactive.json()["contracted"]
        and not inactive.json()["enabled"]
    )
    for contract in ["contract_a2", "contract_b"]:
        foreign = select_context(admin, scope_ids[contract])
        assert admin.patch(path, headers=foreign, json=payload).status_code == 404
    supp = select_context(support, scope_ids["contract_a"])
    assert support.patch(path, headers=supp, json=payload).status_code == 403
    assert (
        admin.patch(
            "/api/contract/modules/UNKNOWN", headers=scope, json=payload
        ).status_code
        == 422
    )


def test_generic_extensions_have_no_routes(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    for path in ["feature-flags", "contract/parameters", "integrations"]:
        assert (
            admin.post(
                "/api/" + path, headers=scope, json={"name": "anything"}
            ).status_code
            == 404
        )


def test_comex_has_requested_commercial_label(admin, scope_ids):
    scope = select_context(admin, scope_ids["contract_a"])
    rows = admin.get("/api/contract/modules", headers=scope).json()["items"]
    assert (
        next(row for row in rows if row["code"] == "COMEX")["label"]
        == "Compras Internacionais / COMEX"
    )
