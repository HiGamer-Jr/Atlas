from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import select_context


def new_role(**overrides):
    return {
        "code": "BUYER",
        "name": "Buyer",
        "permissions": ["memberships.read"],
        **overrides,
    }


def assign(browser, headers, ids, role="role_basic", member="member_a", version=1):
    return browser.put(
        f"/api/memberships/{ids[member]}/role",
        headers=headers,
        json={"role_id": str(ids[role]), "expected_version": version},
    )


def test_admin_role_creation_defaults_to_opt_out_and_audits(
    admin, scope_ids, db_runtime
):
    headers = select_context(admin, scope_ids["contract_a"])
    response = admin.post("/api/roles", headers=headers, json=new_role())
    assert response.status_code == 201
    assert response.json()["support_assignable"] is False
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='tenant.role.created'"
                )
            ).scalar_one()
            == 1
        )


def test_admin_can_enable_flag_with_audit(admin, scope_ids, db_runtime):
    headers = select_context(admin, scope_ids["contract_a"])
    result = admin.patch(
        f"/api/roles/{scope_ids['role_opt_out']}",
        headers=headers,
        json={"expected_version": 1, "support_assignable": True},
    )
    assert result.status_code == 200
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,before_state,after_state FROM audit_events WHERE action='tenant.role.updated'"
            )
        ).one()
    assert event.actor_id == scope_ids["admin_user"]
    assert event.before_state["support_assignable"] is False
    assert event.after_state["support_assignable"] is True


@pytest.mark.parametrize("browser", ["support", "member"])
def test_only_platform_admin_can_change_roles(request, browser, scope_ids):
    client = request.getfixturevalue(browser)
    headers = select_context(client, scope_ids["contract_a"])
    assert (
        client.post("/api/roles", headers=headers, json=new_role()).status_code == 403
    )
    assert (
        client.patch(
            f"/api/roles/{scope_ids['role_basic']}",
            headers=headers,
            json={"expected_version": 1, "support_assignable": True},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "role", ["role_opt_out", "role_finance", "role_admin", "role_sensitive_cap"]
)
def test_support_cannot_assign_ineligible_roles(support, scope_ids, role):
    headers = select_context(support, scope_ids["contract_a"])
    assert assign(support, headers, scope_ids, role).status_code == 403


def test_support_assignable_list_and_mutation_agree(support, scope_ids, db_runtime):
    headers = select_context(support, scope_ids["contract_a"])
    response = support.get("/api/roles/assignable", headers=headers)
    assert response.status_code == 200
    rows = response.json()["items"]
    assert {row["id"] for row in rows} == {str(scope_ids["role_basic"])}
    assert assign(support, headers, scope_ids).status_code == 200
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,after_state FROM audit_events WHERE action='membership.role.assigned'"
            )
        ).one()
    assert event.actor_id == scope_ids["support_user"]
    assert event.after_state["version"] == 2


@pytest.mark.parametrize("role", ["role_a2", "role_b"])
def test_valid_foreign_role_id_is_hidden(support, scope_ids, role):
    headers = select_context(support, scope_ids["contract_a"])
    foreign = assign(support, headers, scope_ids, role)
    unknown = support.put(
        f"/api/memberships/{scope_ids['member_a']}/role",
        headers=headers,
        json={"role_id": str(uuid4()), "expected_version": 1},
    )
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["code"] == unknown.json()["code"]


def test_valid_foreign_membership_id_is_hidden(support, scope_ids):
    headers = select_context(support, scope_ids["contract_a"])
    assert assign(support, headers, scope_ids, member="member_b").status_code == 404
    assert assign(support, headers, scope_ids, member="member_a2").status_code == 404


@pytest.mark.parametrize(
    "code", ["PLATFORM_ADMIN", "PLATFORM_SUPPORT", "platform_admin"]
)
def test_internal_codes_are_never_tenant_roles(admin, support, scope_ids, code):
    headers = select_context(admin, scope_ids["contract_a"])
    assert (
        admin.post("/api/roles", headers=headers, json=new_role(code=code)).status_code
        == 422
    )
    supp = select_context(support, scope_ids["contract_a"])
    assert (
        support.put(
            f"/api/memberships/{scope_ids['member_a']}/role",
            headers=supp,
            json={"role_id": code, "expected_version": 1},
        ).status_code
        == 422
    )
    rows = admin.get("/api/roles", headers=headers).json()["items"]
    assert not any(row["code"].startswith("PLATFORM_") for row in rows)


def test_internal_identity_cannot_be_changed_via_tenant_membership(
    admin, support, scope_ids
):
    for browser in (admin, support):
        headers = select_context(browser, scope_ids["contract_a"])
        assert (
            assign(browser, headers, scope_ids, member="member_internal").status_code
            == 403
        )


def test_support_cannot_downgrade_a_sensitive_current_profile(
    support, scope_ids, db_runtime
):
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE memberships SET role_id=:role WHERE id=:id"),
            {"role": scope_ids["role_finance"], "id": scope_ids["member_a"]},
        )
    headers = select_context(support, scope_ids["contract_a"])
    assert assign(support, headers, scope_ids).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        new_role(permissions=["finance.read"], support_assignable=True),
        new_role(classification="ADMINISTRATIVE", support_assignable=True),
        new_role(permissions=["unknown"]),
        new_role(permissions=["operators.manage"]),
        new_role(tenant_id=str(uuid4())),
    ],
)
def test_role_input_rejects_sensitive_opt_in_unknown_and_foreign_scope(
    admin, scope_ids, payload
):
    headers = select_context(admin, scope_ids["contract_a"])
    assert admin.post("/api/roles", headers=headers, json=payload).status_code == 422


def test_renaming_and_removing_sensitive_permissions_cannot_launder_role(
    admin, scope_ids
):
    headers = select_context(admin, scope_ids["contract_a"])
    created = admin.post(
        "/api/roles",
        headers=headers,
        json=new_role(
            code="FINANCE",
            permissions=["finance.read"],
            classification="FINANCIAL_FISCAL",
        ),
    )
    assert created.status_code == 201
    role = created.json()
    updated = admin.patch(
        "/api/roles/" + role["id"],
        headers=headers,
        json={
            "expected_version": 1,
            "name": "Ordinary buyer",
            "permissions": ["memberships.read"],
            "classification": "STANDARD",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["support_eligible"] is False
    assert (
        admin.patch(
            "/api/roles/" + role["id"],
            headers=headers,
            json={"expected_version": 2, "support_assignable": True},
        ).status_code
        == 422
    )


def test_role_changes_revoke_affected_client_contexts(admin, member, scope_ids):
    client_scope = select_context(member, scope_ids["contract_a"])
    headers = select_context(admin, scope_ids["contract_a"])
    assert (
        admin.patch(
            f"/api/roles/{scope_ids['role_basic']}",
            headers=headers,
            json={"expected_version": 1, "permissions": ["roles.read"]},
        ).status_code
        == 200
    )
    assert member.get("/api/context", headers=client_scope).status_code == 403
    new_scope = select_context(member, scope_ids["contract_a"])
    assert (
        member.get(
            f"/api/memberships/{scope_ids['member_a']}", headers=new_scope
        ).status_code
        == 403
    )


def test_assignment_revokes_only_target_contract_context(admin, member, scope_ids):
    a = select_context(member, scope_ids["contract_a"])
    a2 = select_context(member, scope_ids["contract_a2"])
    headers = select_context(admin, scope_ids["contract_a"])
    assert assign(admin, headers, scope_ids, role="role_opt_out").status_code == 200
    assert member.get("/api/context", headers=a).status_code == 403
    assert member.get("/api/context", headers=a2).status_code == 200


def test_assignment_detects_stale_version(support, scope_ids):
    headers = select_context(support, scope_ids["contract_a"])
    assert assign(support, headers, scope_ids).status_code == 200
    assert assign(support, headers, scope_ids).status_code == 409


def test_assignment_rolls_back_when_audit_fails(
    admin, new_client, scope_ids, db_owner, db_runtime
):
    headers = select_context(admin, scope_ids["contract_a"])
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT deny_assignment CHECK(false) NOT VALID"
            )
        )
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    try:
        assert assign(safe, headers, scope_ids, role="role_opt_out").status_code == 500
        with db_runtime.connect() as conn:
            row = conn.execute(
                text("SELECT role_id,version FROM memberships WHERE id=:id"),
                {"id": scope_ids["member_a"]},
            ).one()
        assert row.role_id == scope_ids["role_basic"] and row.version == 1
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT deny_assignment")
            )


def test_flag_is_reread_after_concurrent_commit(support, scope_ids, db_runtime):
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic, sleep

    headers = select_context(support, scope_ids["contract_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text("UPDATE tenant_roles SET support_assignable=false WHERE id=:id"),
                {"id": scope_ids["role_basic"]},
            )
            future = pool.submit(assign, support, headers, scope_ids)
            deadline = monotonic() + 10
            waiting = False
            while monotonic() < deadline:
                with db_runtime.connect() as monitor:
                    waiting = monitor.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename=current_user AND wait_event_type='Lock')"
                        )
                    ).scalar_one()
                if waiting:
                    break
                sleep(0.02)
            assert waiting, "Assignment did not wait for the role being edited"
        assert future.result(timeout=10).status_code == 403


def test_expiry_while_waiting_for_role_prevents_mutation(
    support, scope_ids, db_runtime, clock
):
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic, sleep

    headers = select_context(support, scope_ids["contract_a"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as editor:
            editor.execute(
                text("SELECT id FROM tenant_roles WHERE id=:id FOR UPDATE"),
                {"id": scope_ids["role_basic"]},
            )
            future = pool.submit(assign, support, headers, scope_ids)
            deadline = monotonic() + 10
            waiting = False
            while monotonic() < deadline:
                with db_runtime.connect() as monitor:
                    waiting = monitor.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename=current_user AND wait_event_type='Lock')"
                        )
                    ).scalar_one()
                if waiting:
                    break
                sleep(0.02)
            assert waiting, "Assignment did not wait for the role being edited"
            clock.advance(hours=9)
        assert future.result(timeout=10).status_code == 401
