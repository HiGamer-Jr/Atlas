from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, select_context
from tests.identity_helpers import SESSION_COOKIE, login


def start(browser, ids, parent=None, **payload):
    parent = parent or select_context(browser, ids["contract_a"])
    response = browser.post(
        "/api/support-sessions",
        headers=parent,
        json={
            "membership_id": str(ids["member_a"]),
            "reason": "Investigação de acesso",
            **payload,
        },
    )
    return parent, response


@pytest.mark.parametrize("browser", ["admin", "support"])
def test_start_preserves_real_actor_cookie_and_exact_scope(
    request, browser, scope_ids, db_runtime, clock
):
    client = request.getfixturevalue(browser)
    cookie = client.cookies.get(SESSION_COOKIE)
    parent, response = start(
        client, scope_ids, reason="  Cafe\u0301 acesso  ", reference="  INC-42  "
    )
    assert response.status_code == 201
    value = response.json()
    assert value["parent_context_id"] == parent[CONTEXT_HEADER]
    assert value["context_id"] != parent[CONTEXT_HEADER]
    assert value["operator"]["user_id"] == str(scope_ids[browser + "_user"])
    assert value["viewed"]["membership_id"] == str(scope_ids["member_a"])
    assert value["viewed"]["user_id"] == str(scope_ids["member_user"])
    assert value["mode"] == "READ_ONLY"
    assert value["status"] == "ACTIVE"
    assert (value["reason"], value["reference"]) == ("Café acesso", "INC-42")
    assert datetime.fromisoformat(value["expires_at"]) == clock.now + timedelta(
        seconds=1800
    )
    assert client.cookies.get(SESSION_COOKIE) == cookie
    assert "set-cookie" not in response.headers
    assert set(value["operator"]) == {"user_id", "display_name", "platform_role"}
    assert set(value["viewed"]) == {
        "membership_id",
        "user_id",
        "display_name",
        "role_id",
        "role_name",
    }
    with db_runtime.connect() as conn:
        audit = conn.execute(
            text(
                "SELECT actor_id, actor_role, support_session_id, reason, reference, after_state FROM audit_events WHERE action='support.session.started'"
            )
        ).one()
        assert str(audit[0]) == value["operator"]["user_id"]
        assert audit[1] == value["operator"]["platform_role"]
        assert str(audit[2]) == value["id"]
        assert audit[3:5] == ("Café acesso", "INC-42")
        assert audit[5]["viewed_membership_id"] == str(scope_ids["member_a"])
    assert (
        client.get("/api/context", headers=parent).json()["support_session_id"]
        == value["id"]
    )


def test_ordinary_user_cannot_start(member, scope_ids):
    _, response = start(member, scope_ids)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "target", ["member_a2", "member_b", "member_internal", "absent"]
)
def test_start_rejects_foreign_and_internal_targets_neutrally(
    support, scope_ids, target
):
    _, response = start(
        support,
        scope_ids,
        membership_id=str(uuid4() if target == "absent" else scope_ids[target]),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "payload",
    [
        {"reason": ""},
        {"reason": "ab"},
        {"reason": "x" * 1001},
        {"reason": "bad\nreason"},
        {"reason": "bad\x00reason"},
        {"reference": "x" * 101},
        {"reference": "bad\tref"},
        {"mode": "MAINTENANCE"},
        {"operator_id": str(uuid4())},
    ],
)
def test_start_validates_bounded_plain_text_and_read_only_mode(
    support, scope_ids, payload
):
    _, response = start(support, scope_ids, **payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "table,key,change",
    [
        ("memberships", "member_a", "active=false"),
        ("memberships", "member_a", "blocked=true"),
        ("memberships", "member_a", "invitation_pending=true"),
        ("users", "member_user", "active=false"),
        ("users", "member_user", "blocked=true"),
        ("tenant_roles", "role_basic", "active=false"),
    ],
)
def test_live_target_ineligibility_blocks_start_and_action_projection(
    support, scope_ids, db_runtime, table, key, change
):
    parent = select_context(support, scope_ids["contract_a"])
    with db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET {change} WHERE id=:id"), {"id": scope_ids[key]}
        )
    detail = support.get(
        "/api/memberships/" + str(scope_ids["member_a"]), headers=parent
    )
    assert "start_support" not in detail.json()["allowed_actions"]
    _, response = start(support, scope_ids, parent)
    assert response.status_code == 404


def test_start_action_and_explicit_internal_capabilities(support, scope_ids):
    parent = select_context(support, scope_ids["contract_a"])
    context = support.get("/api/context", headers=parent).json()
    assert {
        "support.session.start",
        "support.session.read",
        "support.session.end",
        "support.history.read",
    } <= set(context["capabilities"])
    detail = support.get(
        "/api/memberships/" + str(scope_ids["member_a"]), headers=parent
    )
    assert "start_support" in detail.json()["allowed_actions"]


def test_workspace_has_no_management_finance_or_fictitious_business_grants(
    support, scope_ids, db_runtime
):
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'COMEX',true,true),(:tenant,:contract,'FINANCE',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    child = {CONTEXT_HEADER: value["context_id"]}
    workspace = support.get(
        "/api/support-sessions/" + value["id"] + "/workspace", headers=child
    )
    assert workspace.status_code == 200
    assert workspace.json()["effective_access"] == {
        "read_only": True,
        "capabilities": [],
    }
    assert {row["code"] for row in workspace.json()["modules"]} == {
        "PROCUREMENT",
        "COMEX",
        "INVENTORY",
        "PROJECTS",
        "DATAHUB",
    }
    assert all(
        row["operational_available"] is False for row in workspace.json()["modules"]
    )
    assert (
        next(row for row in workspace.json()["modules"] if row["code"] == "COMEX")[
            "enabled"
        ]
        is True
    )
    for headers in [child, parent, {}]:
        for path in [
            "/api/memberships",
            "/api/roles",
            "/api/audit",
            "/api/contract/modules",
            "/api/contracts",
        ]:
            assert support.get(path, headers=headers).status_code == 403
    assert support.get("/api/auth/me", headers=child).json()["user_id"] == str(
        scope_ids["support_user"]
    )
    assert support.get("/api/auth/csrf", headers=child).status_code == 200


def test_support_blocks_every_existing_mutation_before_payload_or_controller(
    admin, app, scope_ids
):
    parent, response = start(admin, scope_ids)
    assert response.status_code == 201
    value = response.json()
    for path, operations in app.openapi()["paths"].items():
        methods = {method.upper() for method in operations}
        if (
            not path.startswith("/api/")
            or path.startswith("/api/support-sessions")
            or path == "/api/auth/logout"
        ):
            continue
        path = (
            path.replace("{member_id}", str(scope_ids["member_a"]))
            .replace("{user_id}", str(scope_ids["support_user"]))
            .replace("{role_id}", str(scope_ids["role_basic"]))
            .replace("{tenant_id}", str(scope_ids["tenant_a"]))
            .replace("{context_id}", parent[CONTEXT_HEADER])
            .replace("{node_id}", str(uuid4()))
            .replace("{code}", "COMEX")
        )
        for verb in methods & {"POST", "PATCH", "PUT", "DELETE"}:
            for headers in (parent, {CONTEXT_HEADER: value["context_id"]}, {}):
                assert (
                    admin.request(verb, path, headers=headers, json={}).status_code
                    == 403
                ), (verb, path)


def test_new_unmarked_no_database_get_fails_closed(admin, app, scope_ids):
    @app.get("/api/future-side-effect")
    def future():
        return {"unsafe": True}

    parent, response = start(admin, scope_ids)
    assert response.status_code == 201
    for headers in [parent, {CONTEXT_HEADER: response.json()["context_id"]}, {}]:
        assert admin.get("/api/future-side-effect", headers=headers).status_code == 403


def test_exact_http_session_and_context_binding(support, new_client, scope_ids):
    unrelated = select_context(support, scope_ids["contract_a"])
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    path = "/api/support-sessions/" + value["id"]
    assert support.get(path, headers=unrelated).status_code == 403
    assert support.post(path + "/end", headers=unrelated).status_code == 403
    other = new_client()
    login(other, "support@example.test")
    for headers in [parent, {CONTEXT_HEADER: value["context_id"]}]:
        assert other.get(path, headers=headers).status_code == 403
        assert other.post(path + "/end", headers=headers).status_code == 403
    assert support.get(path, headers=parent).status_code == 200


def test_independent_parent_flows_and_idempotent_end(support, scope_ids, db_runtime):
    first = select_context(support, scope_ids["contract_a"])
    second = select_context(support, scope_ids["contract_a2"])
    _, a = start(support, scope_ids, first)
    assert a.status_code == 201
    _, b = start(support, scope_ids, second, membership_id=str(scope_ids["member_a2"]))
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    assert (
        support.post(
            "/api/support-sessions/" + a.json()["id"] + "/end", headers=first
        ).status_code
        == 204
    )
    assert (
        support.post(
            "/api/support-sessions/" + a.json()["id"] + "/end", headers=first
        ).status_code
        == 204
    )
    assert support.get("/api/memberships", headers=first).status_code == 200
    assert (
        support.get(
            "/api/support-sessions/" + b.json()["id"], headers=second
        ).status_code
        == 200
    )
    history = support.get("/api/support-sessions?limit=1&offset=0", headers=first)
    assert history.status_code == 200
    assert (
        history.json()["total"],
        history.json()["limit"],
        history.json()["offset"],
    ) == (1, 1, 0)
    assert "context_id" not in history.json()["items"][0]
    assert "parent_context_id" not in history.json()["items"][0]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='support.session.ended'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "cause",
    ["ttl", "parent", "membership", "global", "role", "contract", "tenant", "auth"],
)
def test_observed_expiry_or_revoke_persists_terminal_audit_on_rejection(
    support, scope_ids, clock, db_runtime, cause
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    if cause == "ttl":
        clock.advance(seconds=1801)
    else:
        changes = {
            "parent": ("access_contexts", parent[CONTEXT_HEADER], "revoked_at=now()"),
            "membership": ("memberships", scope_ids["member_a"], "blocked=true"),
            "global": ("users", scope_ids["member_user"], "blocked=true"),
            "role": ("tenant_roles", scope_ids["role_basic"], "active=false"),
            "contract": ("contracts", scope_ids["contract_a"], "active=false"),
            "tenant": ("tenants", scope_ids["tenant_a"], "active=false"),
            "auth": ("auth_sessions", None, "revoked_at=now()"),
        }
        table, key, change = changes[cause]
        with db_runtime.begin() as conn:
            if cause == "auth":
                conn.execute(
                    text("UPDATE auth_sessions SET revoked_at=now() WHERE user_id=:id"),
                    {"id": scope_ids["support_user"]},
                )
            else:
                conn.execute(
                    text(f"UPDATE {table} SET {change} WHERE id=:id"), {"id": key}
                )
    assert support.get(
        "/api/support-sessions/" + value["id"], headers=parent
    ).status_code in {401, 403}
    with db_runtime.connect() as conn:
        row = conn.execute(
            text("SELECT status, ended_at FROM support_sessions WHERE id=:id"),
            {"id": value["id"]},
        ).one()
        assert row[0] == ("EXPIRED" if cause == "ttl" else "REVOKED")
        assert row[1] is not None
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE support_session_id=:id AND action IN ('support.session.expired','support.session.revoked')"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


def test_logout_terminalizes_support_in_same_transaction(
    support, scope_ids, db_runtime
):
    _, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    assert (
        support.post(
            "/api/auth/logout", headers={CONTEXT_HEADER: value["context_id"]}
        ).status_code
        == 204
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM support_sessions WHERE id=:id"),
                {"id": value["id"]},
            ).scalar_one()
            == "REVOKED"
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='support.session.revoked' AND support_session_id=:id"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


def test_support_reads_do_not_renew_operator_idle_lifetime(
    support, scope_ids, clock, db_runtime
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    with db_runtime.connect() as conn:
        seen = conn.execute(
            text("SELECT last_seen_at FROM auth_sessions WHERE user_id=:id"),
            {"id": scope_ids["support_user"]},
        ).scalar_one()
    clock.advance(seconds=20)
    assert (
        support.get(
            "/api/support-sessions/" + response.json()["id"], headers=parent
        ).status_code
        == 200
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT last_seen_at FROM auth_sessions WHERE user_id=:id"),
                {"id": scope_ids["support_user"]},
            ).scalar_one()
            == seen
        )


@pytest.mark.parametrize(
    "header",
    [
        "missing",
        "malformed",
        "unknown",
        "expired",
        "revoked",
        "contract_inactive",
        "foreign_session",
    ],
)
def test_invalid_independent_context_cannot_bypass_contextless_management(
    admin, new_client, scope_ids, db_runtime, header
):
    unrelated = select_context(admin, scope_ids["contract_b"])
    parent, response = start(admin, scope_ids)
    assert response.status_code == 201
    if header == "missing":
        headers = {}
    elif header == "malformed":
        headers = {CONTEXT_HEADER: "bad-id"}
    elif header == "unknown":
        headers = {CONTEXT_HEADER: str(uuid4())}
    elif header == "foreign_session":
        other = new_client()
        login(other)
        headers = select_context(other, scope_ids["contract_b"])
    else:
        headers = unrelated
        with db_runtime.begin() as conn:
            if header == "contract_inactive":
                conn.execute(
                    text("UPDATE contracts SET active=false WHERE id=:id"),
                    {"id": scope_ids["contract_b"]},
                )
            else:
                change = (
                    "created_at=created_at-interval '2 seconds', expires_at=created_at-interval '1 second'"
                    if header == "expired"
                    else "revoked_at=now()"
                )
                conn.execute(
                    text(f"UPDATE access_contexts SET {change} WHERE id=:id"),
                    {"id": unrelated[CONTEXT_HEADER]},
                )
    assert (
        admin.post(
            "/api/tenants", headers=headers, json={"name": "Bypass attempt"}
        ).status_code
        == 403
    )
    assert (
        admin.get(
            "/api/support-sessions/" + response.json()["id"], headers=parent
        ).status_code
        == 200
    )


@pytest.mark.parametrize("operation", ["start", "end", "expiry", "logout"])
def test_audit_failure_rolls_back_support_transition(
    support, new_client, scope_ids, db_runtime, monkeypatch, clock, operation
):
    from app.support import services

    support = new_client(raise_server_exceptions=False)
    login(support, "support@example.test")

    parent = select_context(support, scope_ids["contract_a"])
    value = None
    if operation != "start":
        _, response = start(support, scope_ids, parent)
        assert response.status_code == 201
        value = response.json()

    def broken(*args, **kwargs):
        raise RuntimeError("Audit sink unavailable")

    monkeypatch.setattr(services, "append_event", broken)
    if operation == "start":
        _, response = start(support, scope_ids, parent)
    elif operation == "end":
        response = support.post(
            "/api/support-sessions/" + value["id"] + "/end", headers=parent
        )
    elif operation == "expiry":
        clock.advance(seconds=1801)
        response = support.get("/api/support-sessions/" + value["id"], headers=parent)
    else:
        response = support.post("/api/auth/logout", headers=parent)
    assert response.status_code == 500
    with db_runtime.connect() as conn:
        rows = conn.execute(text("SELECT status, ended_at FROM support_sessions")).all()
        assert rows == ([] if operation == "start" else [("ACTIVE", None)])
        if value:
            assert (
                conn.execute(
                    text("SELECT revoked_at FROM access_contexts WHERE id=:id"),
                    {"id": value["context_id"]},
                ).scalar_one()
                is None
            )


@pytest.mark.parametrize(
    "cause,seconds",
    [("configured", 60), ("parent", 120), ("idle", 60), ("absolute", 300)],
)
def test_support_lifetime_is_bounded_by_live_dependencies(
    support, scope_ids, app, clock, db_runtime, cause, seconds
):
    if cause == "configured":
        app.state.settings.support_session_seconds = seconds
    if cause == "parent":
        app.state.settings.context_seconds = seconds
    if cause == "idle":
        app.state.settings.session_idle_seconds = seconds
    if cause == "absolute":
        with db_runtime.begin() as conn:
            conn.execute(
                text("UPDATE auth_sessions SET expires_at=:expires WHERE user_id=:id"),
                {
                    "id": scope_ids["support_user"],
                    "expires": clock.now + timedelta(seconds=seconds),
                },
            )
    _, response = start(support, scope_ids)
    assert response.status_code == 201
    assert datetime.fromisoformat(
        response.json()["expires_at"]
    ) == clock.now + timedelta(seconds=seconds)


def test_effective_access_intersects_closed_read_limit_target_permission_and_live_module(
    support, scope_ids, db_runtime, monkeypatch
):
    from types import MappingProxyType
    from uuid import UUID

    from sqlalchemy.orm import Session

    from app.identity.schemas import Principal
    from app.organization import modules
    from app.platform.capabilities import CATALOG
    from app.platform.policy import effective_capabilities
    from app.platform.types import Capability
    from app.support import services
    from app.support.models import SupportSession
    from app.tenancy.schemas import AccessScope

    _, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    monkeypatch.setattr(
        services,
        "SUPPORT_READ_LIMITS",
        frozenset({"roles.read", "finance.read", "roles.manage"}),
    )
    monkeypatch.setattr(
        services,
        "CATALOG",
        MappingProxyType(
            {
                **CATALOG,
                "roles.read": Capability(
                    "roles.read",
                    "operational",
                    tenant_enabled=True,
                    read_only_safe=True,
                    mutates_business_state=False,
                    module_code="COMEX",
                ),
            }
        ),
    )
    monkeypatch.setattr(modules, "OPERATIONAL_MODULES", frozenset({"COMEX", "FINANCE"}))
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'COMEX',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )

    def effective():
        with Session(db_runtime) as db, db.begin():
            db.info.update(
                clock=support.app.state.clock, settings=support.app.state.settings
            )
            row = db.get(SupportSession, UUID(value["id"]))
            return effective_capabilities(
                db,
                Principal(row.operator_id, row.operator_session_id, "PLATFORM_ADMIN"),
                AccessScope(
                    row.context_id,
                    row.tenant_id,
                    row.contract_id,
                    row.operator_session_id,
                    row.operator_id,
                ),
            )

    assert effective() == {"roles.read"}
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_role_permissions SET active=false WHERE role_id=:id AND capability='roles.read'"
            ),
            {"id": scope_ids["role_basic"]},
        )
    assert effective() == set()
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_role_permissions SET active=true WHERE role_id=:id AND capability='roles.read'"
            ),
            {"id": scope_ids["role_basic"]},
        )
        conn.execute(
            text("UPDATE contract_modules SET active=false WHERE code='COMEX'")
        )
    assert effective() == set()


def test_operator_role_change_revokes_bound_support_and_preserves_original_audit_role(
    support, scope_ids, db_runtime
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE platform_role_assignments SET role='PLATFORM_ADMIN' WHERE user_id=:id"
            ),
            {"id": scope_ids["support_user"]},
        )
    assert (
        support.get("/api/support-sessions/" + value["id"], headers=parent).status_code
        == 403
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM support_sessions WHERE id=:id"),
                {"id": value["id"]},
            ).scalar_one()
            == "REVOKED"
        )
        assert (
            conn.execute(
                text(
                    "SELECT actor_role FROM audit_events WHERE support_session_id=:id AND action='support.session.revoked'"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == "PLATFORM_SUPPORT"
        )


def test_csrf_control_cannot_fall_back_to_preauth_after_support_deadline(
    support, scope_ids, db_runtime, clock, app
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    cookie = support.cookies.get(SESSION_COOKIE)
    count = 0

    def boundary_clock():
        nonlocal count
        count += 1
        # Two support gate checks and csrf metadata clock remain valid;
        # authenticate crosses the idle/support deadline in the endpoint.
        return clock.now if count <= 3 else clock.now + timedelta(seconds=1801)

    app.state.clock = boundary_clock
    response = support.get("/api/auth/csrf", headers=parent)
    assert response.status_code in {401, 403}
    assert "set-cookie" not in response.headers
    assert support.cookies.get(SESSION_COOKIE) == cookie
    with db_runtime.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM auth_preauth")).scalar_one() == 0
        assert (
            conn.execute(
                text("SELECT status FROM support_sessions WHERE id=:id"),
                {"id": value["id"]},
            ).scalar_one()
            == "EXPIRED"
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE support_session_id=:id AND action='support.session.expired'"
                ),
                {"id": value["id"]},
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("scope", ["parent", "child", "contextless"])
def test_support_business_denial_has_bound_real_actor_and_scope(
    support, scope_ids, db_runtime, scope
):
    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    headers = (
        parent
        if scope == "parent"
        else {CONTEXT_HEADER: value["context_id"]}
        if scope == "child"
        else {}
    )
    response = support.patch(
        "/api/memberships/" + str(scope_ids["member_a"]) + "/status",
        headers=headers,
        json={"active": False, "expected_version": 1},
    )
    assert response.status_code == 403
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,actor_role,tenant_id,contract_id,environment,support_session_id,reason FROM access_events WHERE request_id=:id AND action='support.session.denied'"
            ),
            {"id": response.headers["x-request-id"]},
        ).one()
        assert tuple(str(v) if v is not None else None for v in event) == (
            str(scope_ids["support_user"]),
            "PLATFORM_SUPPORT",
            str(scope_ids["tenant_a"]),
            str(scope_ids["contract_a"]),
            "TEST",
            value["id"],
            "SUPPORT_READ_ONLY",
        )


def test_foreign_support_header_denial_does_not_attribute_foreign_actor(
    support, new_client, scope_ids, db_runtime
):
    _, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    other = new_client()
    login(other)
    response = other.patch(
        "/api/memberships/" + str(scope_ids["member_a"]) + "/status",
        headers={CONTEXT_HEADER: value["context_id"]},
        json={"active": False, "expected_version": 1},
    )
    assert response.status_code == 403
    with db_runtime.connect() as conn:
        events = conn.execute(
            text(
                "SELECT actor_id,support_session_id FROM access_events WHERE request_id=:id"
            ),
            {"id": response.headers["x-request-id"]},
        ).all()
        assert events == [(None, None)]


def test_active_parent_capabilities_ignore_ended_history_with_equal_start_timestamp(
    support, scope_ids, db_runtime
):
    parent, first = start(support, scope_ids)
    assert first.status_code == 201
    assert support.post(
        f"/api/support-sessions/{first.json()['id']}/end", headers=parent
    ).status_code == 204
    # Force the ended row to win the historical id tie-break without changing
    # the fixed-clock timestamp. A live parent must still remain suspended.
    with db_runtime.begin() as connection:
        connection.execute(
            text("UPDATE support_sessions SET id=:high WHERE id=:old"),
            {"high": "ffffffff-ffff-ffff-ffff-ffffffffffff", "old": first.json()["id"]},
        )
    _, second = start(support, scope_ids, parent=parent)
    assert second.status_code == 201
    assert second.json()["started_at"] == first.json()["started_at"]
    response = support.get("/api/context", headers=parent)
    assert response.status_code == 200
    assert response.json()["support_session_id"] == second.json()["id"]
    assert response.json()["capabilities"] == []
