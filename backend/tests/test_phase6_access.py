from uuid import uuid4

import pytest
from sqlalchemy import text

from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from tests.helpers import select_context


def test_phase6_capabilities_are_explicit_internal_grants():
    required = {
        "users.create",
        "users.invite",
        "users.status",
        "users.password_reset",
        "audit.read",
        "logs.access.read",
    }
    for role in ("PLATFORM_ADMIN", "PLATFORM_SUPPORT"):
        assert required <= INTERNAL_GRANTS[role]
    assert all(not CATALOG[code].tenant_role for code in required)


def test_role_description_count_catalogue_and_support_projection(
    admin, support, scope_ids
):
    scope = select_context(admin, scope_ids["contract_a"])
    response = admin.post(
        "/api/roles",
        headers=scope,
        json={
            "code": "BUYER",
            "name": "Buyer",
            "description": "Purchasing access",
            "permissions": ["memberships.read"],
        },
    )
    assert response.status_code == 201
    assert response.json()["description"] == "Purchasing access"
    assert response.json()["member_count"] == 0
    catalogue = admin.get("/api/capabilities", headers=scope)
    assert catalogue.status_code == 200
    assert {row["code"] for row in catalogue.json()["items"]} == {
        code for code, cap in CATALOG.items() if cap.tenant_role
    }
    supp = select_context(support, scope_ids["contract_a"])
    assert support.get("/api/capabilities", headers=supp).status_code == 403
    rows = support.get("/api/roles", headers=supp).json()
    assert rows["total"] == 1
    assert rows["items"][0]["id"] == str(scope_ids["role_basic"])
    assert rows["items"][0]["member_count"] == 1


def test_scoped_member_detail_filters_pagination_and_actions(admin, support, scope_ids):
    scope = select_context(support, scope_ids["contract_a"])
    response = support.get("/api/memberships?limit=1&offset=0", headers=scope)
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (1, 1, 0)
    item = body["items"][0]
    assert item["id"] == str(scope_ids["member_a"])
    assert item["role_name"] == "role_basic"
    assert item["last_access_at"] is None
    assert item["invitation_status"] is None
    assert {"reset_password", "inactivate", "block", "assign_role"} <= set(
        item["allowed_actions"]
    )
    assert support.get("/api/memberships?offset=1", headers=scope).json()["items"] == []
    assert (
        support.get(
            "/api/memberships?role_id=" + str(scope_ids["role_b"]), headers=scope
        ).json()["total"]
        == 0
    )
    assert (
        support.get("/api/memberships?search=other", headers=scope).json()["total"] == 0
    )
    detail = support.get("/api/memberships/" + item["id"], headers=scope)
    assert detail.json() == item
    for foreign in ("member_a2", "member_b"):
        assert (
            support.get(
                "/api/memberships/" + str(scope_ids[foreign]), headers=scope
            ).status_code
            == 404
        )


def test_support_sensitive_member_is_hidden_and_direct_reset_denied(
    support, scope_ids, db_runtime, mail
):
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE memberships SET role_id=:role WHERE id=:id"),
            {"role": scope_ids["role_finance"], "id": scope_ids["member_a"]},
        )
    scope = select_context(support, scope_ids["contract_a"])
    assert support.get("/api/memberships", headers=scope).json()["items"] == []
    assert (
        support.get(
            "/api/memberships/" + str(scope_ids["member_a"]), headers=scope
        ).status_code
        == 404
    )
    assert (
        support.post(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/reset-password",
            headers=scope,
        ).status_code
        == 403
    )


def test_blocked_member_reset_is_unavailable_and_mutations_return_full_view(
    admin, scope_ids, mail
):
    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    response = admin.patch(
        path + "/status", headers=scope, json={"expected_version": 1, "blocked": True}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "member@example.test"
    assert "reset_password" not in response.json()["allowed_actions"]
    assert admin.post(path + "/reset-password", headers=scope).status_code == 409
    assert (
        admin.patch(
            path + "/status",
            headers=scope,
            json={"expected_version": 1, "active": False},
        ).status_code
        == 409
    )


def seed_audit(db_runtime, ids):
    values = []
    with db_runtime.begin() as db:
        for contract, tenant, action, entity, entity_id in [
            (
                "contract_a",
                "tenant_a",
                "membership.status.changed",
                "membership",
                ids["member_a"],
            ),
            (
                "contract_a2",
                "tenant_a",
                "membership.status.changed",
                "membership",
                ids["member_a2"],
            ),
            (
                "contract_b",
                "tenant_b",
                "membership.status.changed",
                "membership",
                ids["member_b"],
            ),
            ("contract_a", "tenant_a", "finance.invoice.changed", "invoice", uuid4()),
        ]:
            event_id = uuid4()
            db.execute(
                text(
                    'INSERT INTO audit_events(id,actor_id,actor_role,tenant_id,contract_id,action,outcome,entity_type,entity_id,request_id,before_state,after_state,reason,reference) VALUES(:id,:actor,\'PLATFORM_ADMIN\',:tenant,:contract,:action,\'SUCCESS\',:entity,:entity_id,:request,\'{"password_hash":"private","amount": 900}\', \'{"active": true,"blocked": false,"invitation_pending": false,"version": 2,"token":"private"}\', \'private reason\',\'private reference\')'
                ),
                {
                    "id": event_id,
                    "actor": ids["admin_user"],
                    "tenant": ids[tenant],
                    "contract": ids[contract],
                    "action": action,
                    "entity": entity,
                    "entity_id": entity_id,
                    "request": uuid4(),
                },
            )
            values.append(event_id)
    return values


def test_audit_context_allowlist_cursor_and_financial_redaction(
    admin, support, scope_ids, db_runtime
):
    events = seed_audit(db_runtime, scope_ids)
    supp = select_context(support, scope_ids["contract_a"])
    result = support.get("/api/audit?limit=1", headers=supp)
    assert result.status_code == 200
    rows = result.json()["items"]
    assert len(rows) == 1 and rows[0]["id"] == str(events[0])
    assert set(rows[0]) == {
        "id",
        "occurred_at",
        "actor_id",
        "actor_name",
        "action",
        "outcome",
        "entity_type",
        "entity_id",
        "reference",
        "request_id",
    }
    assert rows[0]["reference"] is None
    assert support.get("/api/audit/" + str(events[0]), headers=supp).status_code == 403
    scope = select_context(admin, scope_ids["contract_a"])
    result = admin.get("/api/audit?limit=1", headers=scope)
    assert result.status_code == 200 and result.json()["next_cursor"]
    cursor = result.json()["next_cursor"]
    next_rows = admin.get("/api/audit?cursor=" + cursor, headers=scope).json()["items"]
    assert str(events[0]) in {row["id"] for row in next_rows}
    assert result.json()["items"][0]["id"] not in {row["id"] for row in next_rows}
    foreign = select_context(admin, scope_ids["contract_a2"])
    assert admin.get("/api/audit?cursor=" + cursor, headers=foreign).status_code == 422
    assert admin.get("/api/audit?limit=101", headers=scope).status_code == 422
    for event_id in events[1:3]:
        assert (
            admin.get("/api/audit/" + str(event_id), headers=scope).status_code == 404
        )
    detail = admin.get("/api/audit/" + str(events[0]), headers=scope).json()
    assert detail["before"] is None and detail["after"] is None
    assert detail["reason"] is None
    financial = admin.get("/api/audit/" + str(events[3]), headers=scope).json()
    assert financial["before"] is None and financial["after"] is None
    assert financial["reason"] is None


def test_access_history_only_membership_context_evidence(
    support, scope_ids, db_runtime
):
    events = seed_audit(db_runtime, scope_ids)
    scope = select_context(support, scope_ids["contract_a"])
    response = support.get(
        "/api/memberships/" + str(scope_ids["member_a"]) + "/access-history",
        headers=scope,
    )
    assert response.status_code == 200
    assert response.json()["last_access_at"] is None
    assert [row["id"] for row in response.json()["items"]] == [str(events[0])]
    for key in ("member_a2", "member_b"):
        assert (
            support.get(
                "/api/memberships/" + str(scope_ids[key]) + "/access-history",
                headers=scope,
            ).status_code
            == 404
        )


def wait_for_lock(engine):
    from time import monotonic, sleep

    deadline = monotonic() + 10
    while monotonic() < deadline:
        with engine.connect() as monitor:
            if monitor.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename=current_user AND wait_event_type='Lock')"
                )
            ).scalar_one():
                return
        sleep(0.02)
    pytest.fail("Command did not reach the held database lock")


@pytest.mark.parametrize("operation", ["status", "reset", "invite"])
def test_context_expiry_while_membership_waits_prevents_command(
    admin, scope_ids, db_runtime, mail, clock, operation
):
    from concurrent.futures import ThreadPoolExecutor

    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text("SELECT id FROM memberships WHERE id=:id FOR UPDATE"),
                {"id": scope_ids["member_a"]},
            )
            if operation == "status":
                future = pool.submit(
                    admin.patch,
                    path + "/status",
                    headers=scope,
                    json={"expected_version": 1, "blocked": True},
                )
            else:
                future = pool.submit(
                    admin.post,
                    path
                    + "/"
                    + ("reset-password" if operation == "reset" else "invite"),
                    headers=scope,
                )
            wait_for_lock(db_runtime)
            clock.advance(hours=9)
        assert future.result(timeout=10).status_code == 401
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT version FROM memberships WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            ).scalar_one()
            == 1
        )
        assert (
            db.execute(text("SELECT count(*) FROM security_tokens")).scalar_one() == 0
        )


@pytest.mark.parametrize("operation", ["status", "role"])
def test_concurrent_member_edit_rechecks_version(
    admin, scope_ids, db_runtime, operation
):
    from concurrent.futures import ThreadPoolExecutor

    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text("UPDATE memberships SET version=version+1 WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            )
            if operation == "status":
                future = pool.submit(
                    admin.patch,
                    path + "/status",
                    headers=scope,
                    json={"expected_version": 1, "blocked": True},
                )
            else:
                future = pool.submit(
                    admin.put,
                    path + "/role",
                    headers=scope,
                    json={
                        "expected_version": 1,
                        "role_id": str(scope_ids["role_opt_out"]),
                    },
                )
            wait_for_lock(db_runtime)
        assert future.result(timeout=10).status_code == 409


@pytest.mark.parametrize("operation", ["reset-password", "invite"])
def test_block_commits_before_issuance_prevents_email(
    admin, scope_ids, db_runtime, mail, operation
):
    from concurrent.futures import ThreadPoolExecutor

    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text(
                    "UPDATE memberships SET blocked=true,invitation_pending=:pending,version=version+1 WHERE id=:id"
                ),
                {"id": scope_ids["member_a"], "pending": operation == "invite"},
            )
            future = pool.submit(admin.post, path + "/" + operation, headers=scope)
            wait_for_lock(db_runtime)
        assert future.result(timeout=10).status_code == 409
    with db_runtime.connect() as db:
        assert db.execute(text("SELECT count(*) FROM email_outbox")).scalar_one() == 0


@pytest.mark.parametrize(
    "change",
    [
        "support_assignable=false",
        "classification='SENSITIVE'",
        "sensitivity_locked=true",
    ],
)
def test_role_becomes_ineligible_before_support_assignment(
    support, scope_ids, db_runtime, change
):
    from concurrent.futures import ThreadPoolExecutor

    scope = select_context(support, scope_ids["contract_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text("UPDATE tenant_roles SET " + change + " WHERE id=:id"),
                {"id": scope_ids["role_basic"]},
            )
            future = pool.submit(
                support.put,
                "/api/memberships/" + str(scope_ids["member_a"]) + "/role",
                headers=scope,
                json={"expected_version": 1, "role_id": str(scope_ids["role_basic"])},
            )
            wait_for_lock(db_runtime)
        assert future.result(timeout=10).status_code == 403


def test_membership_status_audit_failure_is_atomic(
    admin, new_client, scope_ids, db_owner, db_runtime
):
    scope = select_context(admin, scope_ids["contract_a"])
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    with db_owner.begin() as db:
        db.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT phase6_deny_audit CHECK(false) NOT VALID"
            )
        )
    try:
        response = safe.patch(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/status",
            headers=scope,
            json={"expected_version": 1, "blocked": True},
        )
        assert response.status_code == 500
        with db_runtime.connect() as db:
            row = db.execute(
                text("SELECT version,blocked FROM memberships WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            ).one()
            assert row.version == 1 and not row.blocked
    finally:
        with db_owner.begin() as db:
            db.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT phase6_deny_audit")
            )


def test_block_cancels_already_queued_contextual_reset(
    admin, scope_ids, db_runtime, mail
):
    scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    assert admin.post(path + "/reset-password", headers=scope).status_code == 202
    assert (
        admin.patch(
            path + "/status",
            headers=scope,
            json={"expected_version": 1, "blocked": True},
        ).status_code
        == 200
    )
    with db_runtime.connect() as db:
        assert db.execute(
            text("SELECT invalidated_at IS NOT NULL FROM security_tokens")
        ).scalar_one()
        row = db.execute(
            text("SELECT status,ciphertext IS NULL AS cleared FROM email_outbox")
        ).one()
        assert row.status == "CANCELLED" and row.cleared
    assert mail[1].deliver_batch(10).sent == 0


@pytest.mark.parametrize("change", ["active=false", "blocked=true"])
def test_inactive_or_blocked_member_cannot_reset(
    support, scope_ids, db_runtime, mail, change
):
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE memberships SET " + change + " WHERE id=:id"),
            {"id": scope_ids["member_a"]},
        )
    scope = select_context(support, scope_ids["contract_a"])
    assert (
        support.post(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/reset-password",
            headers=scope,
        ).status_code
        == 409
    )
    assert mail[1].deliver_batch(10).sent == 0


def test_access_audit_filters_are_scoped_and_validate_ranges(
    admin, scope_ids, db_runtime
):
    seed_audit(db_runtime, scope_ids)
    scope = select_context(admin, scope_ids["contract_a"])
    assert (
        len(
            admin.get(
                "/api/audit?action=membership.status.changed&outcome=SUCCESS",
                headers=scope,
            ).json()["items"]
        )
        == 1
    )
    assert (
        admin.get(
            "/api/audit?action=membership.status.changed&outcome=DENIED", headers=scope
        ).json()["items"]
        == []
    )
    assert (
        admin.get("/api/audit?from_at=2099-01-01T00:00:00Z", headers=scope).json()[
            "items"
        ]
        == []
    )
    assert (
        admin.get("/api/audit?to_at=2000-01-01T00:00:00Z", headers=scope).json()[
            "items"
        ]
        == []
    )
    assert (
        admin.get(
            "/api/audit?from_at=2099-01-01T00:00:00Z&to_at=2000-01-01T00:00:00Z",
            headers=scope,
        ).status_code
        == 422
    )
    assert (
        admin.get("/api/audit?from_at=2000-01-01T00:00:00", headers=scope).status_code
        == 422
    )
    assert admin.get("/api/audit?cursor=invalid", headers=scope).status_code == 422


def test_context_selection_proves_only_selected_member_access(
    member, support, scope_ids
):
    select_context(member, scope_ids["contract_a2"])
    scope = select_context(support, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    assert support.get(path, headers=scope).json()["last_access_at"] is None
    select_context(member, scope_ids["contract_a"])
    detail = support.get(path, headers=scope).json()
    history = support.get(path + "/access-history", headers=scope).json()
    assert detail["last_access_at"] is not None
    assert history["last_access_at"] == detail["last_access_at"]
    assert [row["action"] for row in history["items"]] == ["context.selected"]
    assert history["items"][0]["actor_id"] == str(scope_ids["member_user"])


def test_operator_reset_consumption_keeps_contextual_history(
    admin, support, client, scope_ids, mail
):
    from tests.identity_helpers import csrf
    from tests.test_access_tokens import NEW_PASSWORD, token_from

    admin_scope = select_context(admin, scope_ids["contract_a"])
    path = "/api/memberships/" + str(scope_ids["member_a"])
    assert admin.post(path + "/reset-password", headers=admin_scope).status_code == 202
    assert mail[1].deliver_batch(10).sent == 1
    raw = token_from(mail[0])
    csrf(client)
    response = client.post(
        "/api/auth/reset-password", json={"token": raw, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204
    supp = select_context(support, scope_ids["contract_a"])
    history = support.get(path + "/access-history", headers=supp).json()["items"]
    assert {row["action"] for row in history} == {
        "access.reset.requested",
        "access.reset.consumed",
        "access.sessions.revoked",
    }
    foreign = select_context(support, scope_ids["contract_a2"])
    assert (
        support.get(
            "/api/memberships/" + str(scope_ids["member_a2"]) + "/access-history",
            headers=foreign,
        ).json()["items"]
        == []
    )


def test_scoped_support_reset_rechecks_current_role_before_delivery(
    support, scope_ids, db_runtime, mail
):
    scope = select_context(support, scope_ids["contract_a"])
    assert (
        support.post(
            "/api/memberships/" + str(scope_ids["member_a"]) + "/reset-password",
            headers=scope,
        ).status_code
        == 202
    )
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE memberships SET role_id=:role WHERE id=:id"),
            {"role": scope_ids["role_finance"], "id": scope_ids["member_a"]},
        )
    result = mail[1].deliver_batch(10)
    assert result.sent == 0 and result.cancelled == 1


def test_support_audit_hides_sensitive_actor_identity(support, scope_ids, db_runtime):
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE memberships SET role_id=:role WHERE id=:id"),
            {"role": scope_ids["role_finance"], "id": scope_ids["member_a"]},
        )
        db.execute(
            text(
                "INSERT INTO audit_events(actor_id,tenant_id,contract_id,action,outcome,entity_type,entity_id,request_id) VALUES(:actor,:tenant,:contract,'tenant.role.updated','SUCCESS','tenant_role',:role,:request)"
            ),
            {
                "actor": scope_ids["member_user"],
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a"],
                "role": scope_ids["role_basic"],
                "request": uuid4(),
            },
        )
    scope = select_context(support, scope_ids["contract_a"])
    rows = support.get("/api/audit?action=tenant.role.updated", headers=scope).json()[
        "items"
    ]
    assert len(rows) == 1
    assert rows[0]["actor_id"] is None and rows[0]["actor_name"] is None


@pytest.mark.parametrize("operation", ["create_invite", "patch_role"])
def test_context_expiry_after_final_dependent_lock_rolls_back(
    admin, scope_ids, db_runtime, mail, clock, operation
):
    from concurrent.futures import ThreadPoolExecutor

    scope = select_context(admin, scope_ids["contract_a"])
    if operation == "patch_role":
        with db_runtime.begin() as db:
            db.execute(
                text("UPDATE memberships SET invitation_pending=true WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            )
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as blocker:
            if operation == "create_invite":
                blocker.execute(
                    text("SELECT id FROM tenant_roles WHERE id=:id FOR UPDATE"),
                    {"id": scope_ids["role_basic"]},
                )
                future = pool.submit(
                    admin.post,
                    "/api/memberships",
                    headers=scope,
                    json={
                        "email": "new-phase6@example.test",
                        "display_name": "Scoped user",
                        "role_id": str(scope_ids["role_basic"]),
                    },
                )
            else:
                blocker.execute(
                    text("SELECT id FROM memberships WHERE id=:id FOR UPDATE"),
                    {"id": scope_ids["member_a"]},
                )
                future = pool.submit(
                    admin.patch,
                    "/api/roles/" + str(scope_ids["role_basic"]),
                    headers=scope,
                    json={"expected_version": 1, "support_assignable": False},
                )
            wait_for_lock(db_runtime)
            clock.advance(hours=9)
        assert future.result(timeout=10).status_code == 401
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT version FROM tenant_roles WHERE id=:id"),
                {"id": scope_ids["role_basic"]},
            ).scalar_one()
            == 1
        )
        assert db.execute(text("SELECT count(*) FROM email_outbox")).scalar_one() == 0
