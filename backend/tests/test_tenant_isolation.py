from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, select_context


@pytest.mark.parametrize("contract", ["contract_a2", "contract_b"])
def test_other_contract_valid_membership_id_is_hidden(admin, scope_ids, contract):
    headers = select_context(admin, scope_ids[contract])
    foreign = admin.get(f"/api/memberships/{scope_ids['member_a']}", headers=headers)
    absent = admin.get(f"/api/memberships/{uuid4()}", headers=headers)
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json()["code"] == absent.json()["code"]


def test_membership_read_requires_selected_context(admin, scope_ids):
    assert admin.get(f"/api/memberships/{scope_ids['member_a']}").status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE contracts SET active=false WHERE id=:id",
        "UPDATE tenants SET active=false WHERE id=(SELECT tenant_id FROM contracts WHERE id=:id)",
    ],
)
def test_inactive_contract_or_tenant_revokes_context_immediately(
    admin, scope_ids, db_runtime, change
):
    headers = select_context(admin, scope_ids["contract_a"])
    with db_runtime.begin() as conn:
        conn.execute(text(change), {"id": scope_ids["contract_a"]})
    assert admin.get("/api/context", headers=headers).status_code == 403


@pytest.mark.parametrize("change", ["active=false", "blocked=true"])
def test_membership_status_revalidated_on_every_request(
    member, scope_ids, db_runtime, change
):
    headers = select_context(member, scope_ids["contract_a"])
    with db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE memberships SET {change} WHERE id=:id"),
            {"id": scope_ids["member_a"]},
        )
    assert member.get("/api/context", headers=headers).status_code == 403


def test_role_deactivation_revalidated(member, scope_ids, db_runtime):
    headers = select_context(member, scope_ids["contract_a"])
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE tenant_roles SET active=false WHERE id=:id"),
            {"id": scope_ids["role_basic"]},
        )
    assert member.get("/api/context", headers=headers).status_code == 403


def test_permission_change_is_effective_on_existing_context(
    member, scope_ids, db_owner
):
    headers = select_context(member, scope_ids["contract_a"])
    url = f"/api/memberships/{scope_ids['member_a']}"
    assert member.get(url, headers=headers).status_code == 200
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM tenant_role_permissions WHERE role_id=:id AND capability='memberships.read'"
            ),
            {"id": scope_ids["role_basic"]},
        )
    assert member.get(url, headers=headers).status_code == 403


def test_revoked_context_rejected(admin, scope_ids, db_runtime):
    headers = select_context(admin, scope_ids["contract_a"])
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE access_contexts SET revoked_at=now() WHERE id=:id"),
            {"id": headers[CONTEXT_HEADER]},
        )
    assert admin.get("/api/context", headers=headers).status_code == 403


def test_session_revocation_invalidates_all_its_contexts(admin, scope_ids):
    headers = select_context(admin, scope_ids["contract_a"])
    assert admin.post("/api/auth/logout").status_code == 204
    assert admin.get("/api/context", headers=headers).status_code == 401


def test_context_mutations_require_csrf(admin, scope_ids):
    admin.headers.pop("X-CSRF-Token")
    assert (
        admin.post(
            "/api/contexts", json={"contract_id": str(scope_ids["contract_a"])}
        ).status_code
        == 403
    )


def test_context_creation_rolls_back_if_audit_fails(
    admin, new_client, scope_ids, db_owner, db_runtime
):
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT deny_context_audit CHECK(false) NOT VALID"
            )
        )
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    try:
        assert (
            safe.post(
                "/api/contexts", json={"contract_id": str(scope_ids["contract_a"])}
            ).status_code
            == 500
        )
        with db_runtime.connect() as conn:
            assert (
                conn.execute(text("SELECT count(*) FROM access_contexts")).scalar_one()
                == 0
            )
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT deny_context_audit")
            )


@pytest.mark.parametrize("role", ["role_a2", "role_b"])
def test_database_rejects_cross_contract_role_reference(db_runtime, scope_ids, role):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError) as failure, db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE memberships SET role_id=:role WHERE id=:id"),
            {"role": scope_ids[role], "id": scope_ids["member_a"]},
        )
    assert failure.value.orig.sqlstate == "23503"


def test_database_rejects_context_actor_from_another_session(
    admin, support, scope_ids, db_runtime
):
    headers = select_context(admin, scope_ids["contract_a"])
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError) as failure, db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE access_contexts SET actor_id=:actor WHERE id=:id"),
            {"actor": scope_ids["support_user"], "id": headers[CONTEXT_HEADER]},
        )
    assert failure.value.orig.sqlstate == "23503"


@pytest.mark.parametrize(
    "table", ["tenant_roles", "tenant_role_permissions", "memberships"]
)
@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_new_business_tables_remain_protected(db_runtime, table, verb):
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as failure, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} {table}"))
    assert failure.value.orig.sqlstate == "42501"


@pytest.mark.parametrize("operation,expected", [("read", 403), ("close", 404)])
def test_context_removed_while_request_waits_fails_closed(
    admin, new_client, scope_ids, db_runtime, operation, expected
):
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic, sleep

    headers = select_context(admin, scope_ids["contract_a"])
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as cleanup:
            cleanup.execute(
                text("SELECT id FROM contracts WHERE id=:id FOR UPDATE"),
                {"id": scope_ids["contract_a"]},
            )
            cleanup.execute(
                text("DELETE FROM access_contexts WHERE id=:id"),
                {"id": headers[CONTEXT_HEADER]},
            )
            future = (
                pool.submit(safe.get, "/api/context", headers=headers)
                if operation == "read"
                else pool.submit(
                    safe.delete,
                    f"/api/contexts/{headers[CONTEXT_HEADER]}",
                    headers=headers,
                )
            )
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
            assert waiting
        assert future.result(timeout=10).status_code == expected


@pytest.mark.parametrize("operation", ["select", "contract", "close"])
def test_session_expiry_during_scope_lock_prevents_mutation(
    admin, new_client, scope_ids, db_runtime, clock, operation
):
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic, sleep

    context = select_context(admin, scope_ids["contract_a"])
    safe = new_client(raise_server_exceptions=False)
    safe.cookies.update(admin.cookies)
    safe.headers.update(admin.headers)
    with db_runtime.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db_runtime.begin() as blocker:
            blocker.execute(
                text("SELECT id FROM tenants WHERE id=:id FOR UPDATE"),
                {"id": scope_ids["tenant_a"]},
            )
            if operation == "select":
                future = pool.submit(
                    safe.post,
                    "/api/contexts",
                    json={"contract_id": str(scope_ids["contract_a"])},
                )
            elif operation == "contract":
                future = pool.submit(
                    safe.post,
                    f"/api/tenants/{scope_ids['tenant_a']}/contracts",
                    json={"name": "Expired", "code": "EXPIRED", "environment": "TEST"},
                )
            else:
                future = pool.submit(
                    safe.delete, f"/api/contexts/{context[CONTEXT_HEADER]}"
                )
            deadline = monotonic() + 10
            waiting = False
            while monotonic() < deadline:
                with db_runtime.connect() as monitor:
                    waiting = monitor.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() AND usename=current_user "
                            "AND wait_event_type='Lock')"
                        )
                    ).scalar_one()
                if waiting:
                    break
                sleep(0.02)
            assert waiting, "Request did not wait for tenant lock"
            clock.advance(hours=9)
        assert future.result(timeout=10).status_code == 401
    with db_runtime.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
            == before
        )
        assert (
            conn.execute(
                text("SELECT revoked_at FROM access_contexts WHERE id=:id"),
                {"id": context[CONTEXT_HEADER]},
            ).scalar_one()
            is None
        )
