from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.helpers import CONTEXT_HEADER, select_context
from tests.identity_helpers import SESSION_COOKIE, login


def start(browser, ids, parent=None, **payload):
    parent = parent or select_context(browser, ids["contract_a"])
    response = browser.post(
        "/api/grants",
        headers=parent,
        json={
            "grant_type": "FINANCIAL_FISCAL",
            "reason": "Investigação financeira contextual",
            **payload,
        },
    )
    return parent, response


def test_admin_grant_exact_bindings_cookie_actor_audit(
    admin, scope_ids, db_runtime, clock
):
    cookie = admin.cookies.get(SESSION_COOKIE)
    parent, response = start(
        admin, scope_ids, reason="  Cafe\u0301 financeiro  ", reference="  INC-42  "
    )
    assert response.status_code == 201
    row = response.json()
    assert row["operator"]["user_id"] == str(scope_ids["admin_user"])
    assert row["operator"]["platform_role"] == "PLATFORM_ADMIN"
    assert row["parent_context_id"] == parent[CONTEXT_HEADER]
    assert row["context_id"] != parent[CONTEXT_HEADER]
    assert row["status"] == "ACTIVE" and row["version"] == 1
    assert row["reason"] == "Café financeiro" and row["reference"] == "INC-42"
    assert datetime.fromisoformat(row["expires_at"]) == clock.now + timedelta(
        seconds=1800
    )
    assert (
        admin.cookies.get(SESSION_COOKIE) == cookie
        and "set-cookie" not in response.headers
    )
    assert not any(
        key in row
        for key in (
            "password",
            "password_hash",
            "token",
            "auth_session_id",
            "operator_session_id",
        )
    )
    child = {CONTEXT_HEADER: row["context_id"]}
    restored = admin.get("/api/grants/context", headers=child).json()
    assert restored["id"] == row["id"]
    assert datetime.fromisoformat(restored["expires_at"]) == datetime.fromisoformat(
        row["expires_at"]
    )
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,actor_role,tenant_id,contract_id,entity_id,after_state FROM audit_events WHERE action='privileged_grant.started'"
            )
        ).one()
        assert str(event.actor_id) == row["operator"]["user_id"]
        assert str(event.entity_id) == row["id"]
        assert event.actor_role == "PLATFORM_ADMIN"
        assert event.after_state["grant_type"] == "FINANCIAL_FISCAL"
        assert event.after_state["scopes"] == []


@pytest.mark.parametrize("browser", ["support", "member"])
def test_only_admin_can_create(request, browser, scope_ids):
    client = request.getfixturevalue(browser)
    _, response = start(client, scope_ids)
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/grants", "/api/grants/maintenance-actions"])
def test_support_cannot_query_grants(support, scope_ids, path):
    parent = select_context(support, scope_ids["contract_a"])
    assert support.get(path, headers=parent).status_code == 403


@pytest.mark.parametrize("age", [300, 301, 900])
def test_old_reauth_denied_then_real_reauth_allows(admin, scope_ids, clock, age):
    parent = select_context(admin, scope_ids["contract_a"])
    clock.advance(seconds=age)
    _, response = start(admin, scope_ids, parent)
    assert response.status_code == 403 and response.json()["code"] == "REAUTH_REQUIRED"
    from tests.identity_helpers import PASSWORD

    assert (
        admin.post("/api/auth/reauthenticate", json={"password": PASSWORD}).status_code
        == 204
    )
    assert start(admin, scope_ids, parent)[1].status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"grant_type": "WRITE"},
        {"grant_type": "FINANCE"},
        {"reason": ""},
        {"reason": "ab"},
        {"reason": "x" * 1001},
        {"reason": "bad\nreason"},
        {"reason": "bad\u200breason"},
        {"reference": "x" * 101},
        {"reference": "bad\tref"},
        {"operator_id": str(uuid4())},
        {"scopes": [{"action_code": "SQL", "entity_type": "organization_node"}]},
        {"grant_type": "MAINTENANCE"},
        {"grant_type": "MAINTENANCE", "reference": "INC-1"},
        {
            "grant_type": "MAINTENANCE",
            "scopes": [{"action_code": "TEST", "entity_type": "organization_node"}],
        },
    ],
)
def test_closed_input_and_bounded_reason(admin, scope_ids, payload):
    assert start(admin, scope_ids, **payload)[1].status_code == 422


def test_maintenance_production_registry_is_empty_no_fake_handler(admin, scope_ids):
    parent = select_context(admin, scope_ids["contract_a"])
    assert admin.get("/api/grants/maintenance-actions", headers=parent).json() == {
        "items": []
    }
    response = start(
        admin,
        scope_ids,
        parent,
        grant_type="MAINTENANCE",
        reference="INC-1",
        scopes=[{"action_code": "UNREGISTERED", "entity_type": "organization_node"}],
    )[1]
    assert response.status_code == 403
    assert response.json()["code"] == "MAINTENANCE_ACTION_UNAVAILABLE"


@pytest.mark.parametrize(
    "path",
    [
        "/api/memberships",
        "/api/roles",
        "/api/audit",
        "/api/organization/nodes",
        "/api/contract/modules",
        "/api/health",
    ],
)
def test_derived_context_fails_closed_even_unmarked_get(admin, scope_ids, path):
    parent, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    assert admin.get(path, headers=child).status_code == 403
    assert admin.get("/api/context", headers=parent).status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/contexts"),
        ("patch", "/api/memberships/00000000-0000-0000-0000-000000000001/status"),
        ("put", "/api/memberships/00000000-0000-0000-0000-000000000001/role"),
        ("delete", "/api/contexts/00000000-0000-0000-0000-000000000001"),
        ("post", "/api/support-sessions"),
        ("post", "/api/grants"),
    ],
)
def test_derived_context_cannot_write_generic_or_start_support(
    admin, scope_ids, method, path
):
    _, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    result = (
        getattr(admin, method)(path, headers=child, json={})
        if method != "delete"
        else admin.delete(path, headers=child)
    )
    assert result.status_code == 403


def test_effective_access_is_only_exception_normal_context_stays_normal(
    admin, scope_ids
):
    independent = select_context(admin, scope_ids["contract_a"])
    parent, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    effective = admin.get("/api/context", headers=child).json()
    assert set(effective["capabilities"]) == {"finance.read", "fiscal.read"}
    for normal in (parent, independent):
        caps = admin.get("/api/context", headers=normal).json()["capabilities"]
        assert "finance.read" not in caps and "fiscal.read" not in caps
        assert "users.create" in caps
        assert admin.get("/api/grants", headers=normal).status_code == 200


@pytest.mark.parametrize("contract", ["contract_a2", "contract_b"])
def test_grant_history_and_controls_cannot_cross_contract(admin, scope_ids, contract):
    other = select_context(admin, scope_ids[contract])
    _, response = start(admin, scope_ids)
    row = response.json()
    assert admin.get("/api/grants", headers=other).json()["total"] == 0
    assert (
        admin.post(
            f"/api/grants/{row['id']}/end", headers=other, json={"expected_version": 1}
        ).status_code
        == 403
    )
    assert admin.get("/api/grants/context", headers=other).status_code == 403


def test_exact_http_session_support_stolen_context_new_login_rejected(
    admin, support, new_client, scope_ids
):
    _, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    other = new_client()
    login(other)
    for browser in (other, support):
        assert browser.get("/api/grants/context", headers=child).status_code == 403
        assert (
            browser.post(
                f"/api/grants/{response.json()['id']}/end",
                headers=child,
                json={"expected_version": 1},
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "table,key,change",
    [
        ("users", "admin_user", "active=false"),
        ("users", "admin_user", "blocked=true"),
        ("contracts", "contract_a", "active=false"),
        ("tenants", "tenant_a", "active=false"),
    ],
)
def test_live_ineligibility_revokes_before_read_with_audit(
    admin, scope_ids, db_runtime, table, key, change
):
    _, response = start(admin, scope_ids)
    row = response.json()
    child = {CONTEXT_HEADER: row["context_id"]}
    with db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET {change} WHERE id=:id"), {"id": scope_ids[key]}
        )
    assert admin.get("/api/grants/context", headers=child).status_code == 403
    with db_runtime.connect() as conn:
        status = conn.execute(
            text("SELECT status,version FROM temporary_privileged_grants WHERE id=:id"),
            {"id": row["id"]},
        ).one()
        assert status == ("REVOKED", 2)
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.revoked'"
                )
            ).scalar_one()
            == 1
        )


def test_expiry_fixed_no_reload_extension_audit_once(
    admin, scope_ids, clock, db_runtime
):
    _, response = start(admin, scope_ids)
    row = response.json()
    child = {CONTEXT_HEADER: row["context_id"]}
    clock.advance(seconds=100)
    assert datetime.fromisoformat(
        admin.get("/api/grants/context", headers=child).json()["expires_at"]
    ) == datetime.fromisoformat(row["expires_at"])
    clock.advance(seconds=1700)
    for _ in range(2):
        assert admin.get("/api/grants/context", headers=child).status_code == 403
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
                {"id": row["id"]},
            ).scalar_one()
            == "EXPIRED"
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.expired'"
                )
            ).scalar_one()
            == 1
        )


def test_parent_context_revocation_revokes_child(admin, scope_ids, db_runtime):
    parent, response = start(admin, scope_ids)
    row = response.json()
    assert (
        admin.delete(
            "/api/contexts/" + parent[CONTEXT_HEADER], headers=parent
        ).status_code
        == 204
    )
    assert (
        admin.get(
            "/api/grants/context", headers={CONTEXT_HEADER: row["context_id"]}
        ).status_code
        == 403
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
                {"id": row["id"]},
            ).scalar_one()
            == "REVOKED"
        )


def test_logout_revokes_grant_same_transaction(admin, scope_ids, db_runtime):
    _, response = start(admin, scope_ids)
    row = response.json()
    assert (
        admin.post(
            "/api/auth/logout", headers={CONTEXT_HEADER: row["context_id"]}
        ).status_code
        == 204
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
                {"id": row["id"]},
            ).scalar_one()
            == "REVOKED"
        )


def test_role_change_revokes_grant_without_return_to_support(
    admin, scope_ids, db_runtime
):
    _, response = start(admin, scope_ids)
    row = response.json()
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE platform_role_assignments SET role='PLATFORM_SUPPORT' WHERE user_id=:id"
            ),
            {"id": scope_ids["admin_user"]},
        )
    assert (
        admin.get(
            "/api/grants/context", headers={CONTEXT_HEADER: row["context_id"]}
        ).status_code
        == 403
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
                {"id": row["id"]},
            ).scalar_one()
            == "REVOKED"
        )


def test_end_version_conflict_and_idempotent_terminal(admin, scope_ids, db_runtime):
    parent, response = start(admin, scope_ids)
    row = response.json()
    path = f"/api/grants/{row['id']}/end"
    assert (
        admin.post(path, headers=parent, json={"expected_version": 99}).status_code
        == 409
    )
    end = admin.post(path, headers=parent, json={"expected_version": 1})
    assert (
        end.status_code == 200
        and end.json()["status"] == "ENDED"
        and end.json()["version"] == 2
    )
    again = admin.post(path, headers=parent, json={"expected_version": 1})
    assert again.status_code == 200 and again.json() == end.json()
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='privileged_grant.ended'"
                )
            ).scalar_one()
            == 1
        )


def test_start_audit_failure_rolls_back_grant_and_child(
    admin, scope_ids, db_runtime, monkeypatch
):
    from app.grants import services

    parent = select_context(admin, scope_ids["contract_a"])

    def broken(*args, **kwargs):
        raise RuntimeError("Controlled audit failure")

    monkeypatch.setattr(services, "append_event", broken)
    # The TestClient factory does not expose this as a mutable setting; service is exercised transactionally.
    with Session(db_runtime) as db:
        from app.grants.models import TemporaryPrivilegedGrant

        assert db.query(TemporaryPrivilegedGrant).count() == 0
    try:
        response = start(admin, scope_ids, parent)[1]
        assert response.status_code == 500
    except RuntimeError as error:
        assert str(error) == "Controlled audit failure"
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM temporary_privileged_grants")
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(text("SELECT count(*) FROM access_contexts")).scalar_one() == 1
        )


def test_support_read_only_cannot_elevate_to_any_grant(admin, scope_ids):
    parent = select_context(admin, scope_ids["contract_a"])
    support = admin.post(
        "/api/support-sessions",
        headers=parent,
        json={
            "membership_id": str(scope_ids["member_a"]),
            "reason": "Diagnóstico de menu",
        },
    )
    assert support.status_code == 201
    for context in (parent, {CONTEXT_HEADER: support.json()["context_id"]}):
        assert start(admin, scope_ids, context)[1].status_code == 403


@pytest.mark.parametrize(
    "capability,path",
    [
        ("grants.read", "/api/grants"),
        ("maintenance.authorize", "/api/grants/maintenance-actions"),
    ],
)
def test_control_requires_its_exact_capability(
    admin, scope_ids, monkeypatch, capability, path
):
    from app.grants import services

    parent = select_context(admin, scope_ids["contract_a"])
    current = services.INTERNAL_GRANTS
    monkeypatch.setattr(
        services,
        "INTERNAL_GRANTS",
        {**current, "PLATFORM_ADMIN": current["PLATFORM_ADMIN"] - {capability}},
    )
    assert admin.get(path, headers=parent).status_code == 403


def test_end_requires_specific_control_capability(admin, scope_ids, monkeypatch):
    from app.grants import services

    parent, response = start(admin, scope_ids)
    current = services.INTERNAL_GRANTS
    monkeypatch.setattr(
        services,
        "INTERNAL_GRANTS",
        {**current, "PLATFORM_ADMIN": current["PLATFORM_ADMIN"] - {"grants.end"}},
    )
    assert (
        admin.post(
            f"/api/grants/{response.json()['id']}/end",
            headers=parent,
            json={"expected_version": 1},
        ).status_code
        == 403
    )


def test_expired_previous_grant_does_not_block_new_request_forever(
    admin, scope_ids, clock, settings, db_runtime
):
    settings.grant_seconds = 60
    parent, response = start(admin, scope_ids)
    assert response.status_code == 201
    clock.advance(seconds=61)
    from tests.identity_helpers import PASSWORD

    assert (
        admin.post("/api/auth/reauthenticate", json={"password": PASSWORD}).status_code
        == 204
    )
    new = start(admin, scope_ids, parent)[1]
    assert new.status_code == 201
    assert new.json()["id"] != response.json()["id"]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM temporary_privileged_grants WHERE id=:id"),
                {"id": response.json()["id"]},
            ).scalar_one()
            == "EXPIRED"
        )


def test_maintenance_scope_entity_type_is_closed():
    from pydantic import ValidationError

    from app.grants.schemas import MaintenanceScope

    with pytest.raises(ValidationError):
        MaintenanceScope(action_code="TEST", entity_type="arbitrary_table")


def test_end_audit_failure_rolls_back_status_context_and_version(
    admin, scope_ids, db_runtime, monkeypatch
):
    from app.grants import services

    parent, response = start(admin, scope_ids)
    row = response.json()

    def broken(*args, **kwargs):
        raise RuntimeError("Controlled audit failure")

    monkeypatch.setattr(services, "append_event", broken)
    with pytest.raises(RuntimeError, match="Controlled audit failure"):
        admin.post(
            f"/api/grants/{row['id']}/end", headers=parent, json={"expected_version": 1}
        )
    with db_runtime.connect() as conn:
        assert conn.execute(
            text("SELECT status,version FROM temporary_privileged_grants WHERE id=:id"),
            {"id": row["id"]},
        ).one() == ("ACTIVE", 1)
        assert (
            conn.execute(
                text("SELECT revoked_at FROM access_contexts WHERE id=:id"),
                {"id": row["context_id"]},
            ).scalar_one()
            is None
        )


def test_declared_financial_get_revalidates_after_entity_resolver_wait(
    admin, scope_ids, app, clock, settings, db_runtime, monkeypatch
):
    from app.grants.gate import privileged_read
    from app.organization import modules

    settings.grant_seconds = 60
    monkeypatch.setattr(modules, "OPERATIONAL_MODULES", frozenset({"FINANCE"}))
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'FINANCE',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )

    def resolve_entity(db, scope, path):
        clock.advance(seconds=61)
        return True

    @app.get("/api/fixture-financial-read")
    @privileged_read("finance.read", "FINANCE", resolve_entity)
    def controlled_no_database_dependency():
        return {"fixture": "authorized"}

    _, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    assert admin.get("/api/fixture-financial-read", headers=child).status_code == 403


@pytest.mark.parametrize(
    "contracted,active,operational",
    [(False, False, True), (True, False, True), (True, True, False)],
)
def test_financial_grant_still_requires_every_module_condition(
    admin, scope_ids, app, db_runtime, monkeypatch, contracted, active, operational
):
    from app.grants.gate import privileged_read
    from app.organization import modules

    monkeypatch.setattr(
        modules,
        "OPERATIONAL_MODULES",
        frozenset({"FINANCE"}) if operational else frozenset(),
    )
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'FINANCE',:contracted,:active)"
            ),
            {
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a"],
                "contracted": contracted,
                "active": active,
            },
        )

    @app.get("/api/fixture-financial-read")
    @privileged_read("finance.read", "FINANCE", lambda db, scope, path: True)
    def controlled_no_database_dependency():
        return {"fixture": "authorized"}

    _, response = start(admin, scope_ids)
    result = admin.get(
        "/api/fixture-financial-read",
        headers={CONTEXT_HEADER: response.json()["context_id"]},
    )
    assert result.status_code == 403 and result.json()["code"] == "MODULE_UNAVAILABLE"


def test_declared_financial_read_requires_capability_and_current_grant(
    admin, scope_ids, app, db_runtime, monkeypatch
):
    from app.grants import services
    from app.grants.gate import privileged_read
    from app.organization import modules

    monkeypatch.setattr(modules, "OPERATIONAL_MODULES", frozenset({"FINANCE"}))
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'FINANCE',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )

    @app.get("/api/fixture-financial-read")
    @privileged_read("finance.read", "FINANCE", lambda db, scope, path: True)
    def controlled_no_database_dependency():
        return {"fixture": "authorized"}

    parent, response = start(admin, scope_ids)
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    assert admin.get("/api/fixture-financial-read", headers=child).status_code == 200
    monkeypatch.setattr(services, "FINANCIAL_CAPABILITIES", frozenset())
    result = admin.get("/api/fixture-financial-read", headers=child)
    assert result.status_code == 403 and result.json()["code"] == "CAPABILITY_DENIED"
    # Test-only decorated route is gate-protected for financial normal contexts too.
    assert admin.get("/api/fixture-financial-read", headers=parent).status_code == 403
    assert admin.get("/api/fixture-financial-read").status_code == 403
    assert (
        "finance.read"
        not in admin.get("/api/context", headers=parent).json()["capabilities"]
    )


def register_controlled_action(app, db_runtime, scope_ids, *, handler=None):
    from sqlalchemy import select

    from app.grants.registry import MaintenanceAction, MaintenanceActionRegistry
    from app.organization.models import OrganizationNode

    node_id = uuid4()
    foreign_id = uuid4()
    with db_runtime.begin() as conn:
        for node, contract in [
            (node_id, scope_ids["contract_a"]),
            (foreign_id, scope_ids["contract_a2"]),
        ]:
            conn.execute(
                text(
                    "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code) VALUES(:id,:tenant,:contract,'WORKSITE','Canteiro controlado','WS-CONTROLLED')"
                ),
                {"id": node, "tenant": scope_ids["tenant_a"], "contract": contract},
            )

    def resolve(db, scope, target):
        return (
            target is None
            or db.scalar(
                select(OrganizationNode.id).where(
                    OrganizationNode.id == target,
                    OrganizationNode.tenant_id == scope.tenant_id,
                    OrganizationNode.contract_id == scope.contract_id,
                    OrganizationNode.active.is_(True),
                )
            )
            is not None
        )

    action = MaintenanceAction(
        "CONTROLLED_ACTION",
        "Ação controlada",
        "organization_node",
        "maintenance.authorize",
        "PROCUREMENT",
        resolve,
        lambda *args: True,
        handler,
    )
    app.state.maintenance_registry = MaintenanceActionRegistry([action])
    return node_id, foreign_id


def test_registered_maintenance_typed_scope_and_no_handler_fails_explicitly(
    admin, scope_ids, app, db_runtime
):
    from app.grants import services
    from app.grants.models import TemporaryPrivilegedGrant
    from app.identity.schemas import Principal
    from app.tenancy.schemas import AccessScope

    node, _ = register_controlled_action(app, db_runtime, scope_ids)
    _, response = start(
        admin,
        scope_ids,
        grant_type="MAINTENANCE",
        reference="INC-42",
        scopes=[
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": str(node),
            }
        ],
    )
    assert response.status_code == 201
    row = response.json()
    with Session(db_runtime) as db, db.begin():
        db.info.update(settings=app.state.settings, clock=app.state.clock)
        persisted = db.get(TemporaryPrivilegedGrant, UUID(row["id"]))
        principal = Principal(
            persisted.operator_id, persisted.operator_session_id, "PLATFORM_ADMIN"
        )
        scope = AccessScope(
            persisted.context_id,
            persisted.tenant_id,
            persisted.contract_id,
            persisted.operator_session_id,
            persisted.operator_id,
        )
        from types import SimpleNamespace

        request = SimpleNamespace(app=app)
        from app.core.errors import ApiError

        with pytest.raises(ApiError) as error:
            services.require_maintenance(
                db,
                request,
                principal,
                scope,
                "CONTROLLED_ACTION",
                "organization_node",
                node,
            )
        assert error.value.code == "MAINTENANCE_HANDLER_UNAVAILABLE"


def test_registered_scope_foreign_entity_and_duplicate_action_are_rejected(
    admin, scope_ids, app, db_runtime
):
    node, foreign = register_controlled_action(app, db_runtime, scope_ids)
    parent = select_context(admin, scope_ids["contract_a"])
    response = start(
        admin,
        scope_ids,
        parent,
        grant_type="MAINTENANCE",
        reference="INC-42",
        scopes=[
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": str(foreign),
            }
        ],
    )[1]
    assert response.status_code == 404
    response = start(
        admin,
        scope_ids,
        parent,
        grant_type="MAINTENANCE",
        reference="INC-42",
        scopes=[
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": str(node),
            },
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": None,
            },
        ],
    )[1]
    assert response.status_code == 422


@pytest.mark.parametrize("limit", ["parent", "auth", "idle"])
def test_grant_lifetime_never_exceeds_parent_or_exact_auth_session(
    admin, scope_ids, settings, clock, db_runtime, limit
):
    settings.context_seconds = 60 if limit == "parent" else 3600
    parent = select_context(admin, scope_ids["contract_a"])
    seconds = 60 if limit == "parent" else 120 if limit == "auth" else 100
    if limit != "parent":
        with db_runtime.begin() as conn:
            conn.execute(
                text("UPDATE auth_sessions SET expires_at=:expiry WHERE user_id=:id")
                if limit == "auth"
                else text(
                    "UPDATE auth_sessions SET last_seen_at=:seen WHERE user_id=:id"
                ),
                {
                    "id": scope_ids["admin_user"],
                    "expiry": clock.now + timedelta(seconds=120),
                    "seen": clock.now - timedelta(seconds=1700),
                },
            )
    row = start(admin, scope_ids, parent)[1].json()
    assert datetime.fromisoformat(row["expires_at"]) == clock.now + timedelta(
        seconds=seconds
    )


def test_privileged_denial_has_real_operator_scope_and_no_rejected_payload(
    admin, scope_ids, db_runtime
):
    _, response = start(admin, scope_ids)
    row = response.json()
    denied = admin.post(
        "/api/grants",
        headers={CONTEXT_HEADER: row["context_id"]},
        json={"password": "rejected-private-fixture"},
    )
    assert denied.status_code == 403
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,actor_role,tenant_id,contract_id,entity_id,reason FROM access_events WHERE action='privileged_grant.denied' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert str(event.actor_id) == row["operator"]["user_id"]
        assert event.actor_role == "PLATFORM_ADMIN"
        assert (
            str(event.tenant_id) == row["tenant_id"]
            and str(event.contract_id) == row["contract_id"]
        )
        assert str(event.entity_id) == row["id"]
        assert event.reason == "GRANT_CONTEXT_INVALID"
        assert "rejected-private-fixture" not in str(event)


def test_expired_csrf_does_not_fallback_to_preauth_or_clear_cookie(
    admin, scope_ids, settings, clock
):
    settings.grant_seconds = 60
    _, response = start(admin, scope_ids)
    cookie = admin.cookies.get(SESSION_COOKIE)
    clock.advance(seconds=61)
    result = admin.get(
        "/api/auth/csrf", headers={CONTEXT_HEADER: response.json()["context_id"]}
    )
    assert result.status_code == 403 and "set-cookie" not in result.headers
    assert admin.cookies.get(SESSION_COOKIE) == cookie


@pytest.mark.parametrize("operational", [False, True])
def test_controlled_maintenance_policy_requires_module_and_never_executes_handler(
    admin, scope_ids, app, db_runtime, monkeypatch, operational
):
    from types import SimpleNamespace

    from app.core.errors import ApiError
    from app.grants import services
    from app.grants.models import TemporaryPrivilegedGrant
    from app.identity.schemas import Principal
    from app.organization import modules
    from app.tenancy.schemas import AccessScope

    calls = []
    node, _ = register_controlled_action(
        app, db_runtime, scope_ids, handler=lambda: calls.append("executed")
    )
    monkeypatch.setattr(
        modules,
        "OPERATIONAL_MODULES",
        frozenset({"PROCUREMENT"}) if operational else frozenset(),
    )
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'PROCUREMENT',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )
    parent, response = start(
        admin,
        scope_ids,
        grant_type="MAINTENANCE",
        reference="INC-42",
        scopes=[
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": str(node),
            }
        ],
    )
    assert response.status_code == 201
    with Session(db_runtime) as db, db.begin():
        db.info.update(settings=app.state.settings, clock=app.state.clock)
        row = db.get(TemporaryPrivilegedGrant, UUID(response.json()["id"]))
        principal = Principal(
            row.operator_id, row.operator_session_id, "PLATFORM_ADMIN"
        )
        scope = AccessScope(
            row.context_id,
            row.tenant_id,
            row.contract_id,
            row.operator_session_id,
            row.operator_id,
        )
        request = SimpleNamespace(app=app)
        if operational:
            action = services.require_maintenance(
                db,
                request,
                principal,
                scope,
                "CONTROLLED_ACTION",
                "organization_node",
                node,
            )
            assert action.action_code == "CONTROLLED_ACTION"
        else:
            with pytest.raises(ApiError) as error:
                services.require_maintenance(
                    db,
                    request,
                    principal,
                    scope,
                    "CONTROLLED_ACTION",
                    "organization_node",
                    node,
                )
            assert error.value.code == "MODULE_UNAVAILABLE"
        foreign_scope = AccessScope(
            row.context_id,
            row.tenant_id,
            scope_ids["contract_a2"],
            row.operator_session_id,
            row.operator_id,
        )
        with pytest.raises(ApiError):
            services.require_maintenance(
                db,
                request,
                principal,
                foreign_scope,
                "CONTROLLED_ACTION",
                "organization_node",
                node,
            )
    assert calls == []
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    assert (
        admin.post("/api/organization/nodes", headers=child, json={}).status_code == 403
    )
    assert admin.get("/api/context", headers=parent).status_code == 200
