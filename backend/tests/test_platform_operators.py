from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.identity_helpers import PASSWORD, login, seed_user


def role_payload(user_id, role="PLATFORM_ADMIN", password=PASSWORD):
    return {
        "role": role,
        "password": password,
        "confirmation": {"target_user_id": str(user_id), "target_role": role},
    }


@pytest.mark.parametrize("state", [{"active": False}, {"blocked": True}])
def test_cannot_disable_last_admin(last_admin, ids, state):
    response = last_admin.post(
        f"/api/platform/operators/{ids['last_admin_user']}/status", json=state
    )
    assert response.status_code == 409


def test_cannot_demote_last_admin(last_admin, ids):
    target = ids["last_admin_user"]
    response = last_admin.post(
        f"/api/platform/operators/{target}/role",
        json=role_payload(target, "PLATFORM_SUPPORT"),
    )
    assert response.status_code == 409


def test_support_cannot_promote_itself(support, ids):
    target = ids["support_user"]
    assert (
        support.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        ).status_code
        == 403
    )


def test_support_cannot_manage_another_operator(support, ids):
    assert (
        support.post(
            f"/api/platform/operators/{ids['admin_user']}/status",
            json={"active": False},
        ).status_code
        == 403
    )


def test_member_cannot_manage_operators(new_client, auth_users):
    member = new_client()
    login(member, "member@example.test")
    target = auth_users["support_user"]
    assert (
        member.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        ).status_code
        == 403
    )


def test_promotion_requires_target_bound_confirmation(admin, ids):
    target = ids["support_user"]
    payload = role_payload(target)
    payload["confirmation"]["target_user_id"] = str(uuid4())
    assert (
        admin.post(f"/api/platform/operators/{target}/role", json=payload).status_code
        == 422
    )
    payload = role_payload(target)
    payload["confirmation"]["target_role"] = "PLATFORM_SUPPORT"
    assert (
        admin.post(f"/api/platform/operators/{target}/role", json=payload).status_code
        == 422
    )


def test_promotion_requires_correct_password(admin, ids):
    target = ids["support_user"]
    assert (
        admin.post(
            f"/api/platform/operators/{target}/role",
            json=role_payload(target, password="wrong"),
        ).status_code
        == 401
    )


def test_promotion_audits_server_snapshots_and_revokes_target(
    admin, support, ids, db_runtime
):
    target = ids["support_user"]
    response = admin.post(
        f"/api/platform/operators/{target}/role", json=role_payload(target)
    )
    assert response.status_code == 200
    assert response.json()["platform_role"] == "PLATFORM_ADMIN"
    assert support.get("/api/auth/me").status_code == 401
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,before_state,after_state FROM audit_events WHERE action='platform.role.changed'"
            )
        ).one()
    assert event.actor_id == ids["admin_user"]
    assert event.before_state["platform_role"] == "PLATFORM_SUPPORT"
    assert event.after_state["platform_role"] == "PLATFORM_ADMIN"
    assert PASSWORD not in str(event)
    assert "password_hash" not in str(event)


def test_admin_can_assign_internal_role_to_existing_identity(admin, ids):
    target = ids["member_user"]
    response = admin.post(
        f"/api/platform/operators/{target}/role",
        json=role_payload(target, "PLATFORM_SUPPORT"),
    )
    assert response.status_code == 200
    assert response.json()["platform_role"] == "PLATFORM_SUPPORT"


def test_status_cannot_change_tenant_only_identity(admin, ids):
    assert (
        admin.post(
            f"/api/platform/operators/{ids['member_user']}/status",
            json={"blocked": True},
        ).status_code
        == 404
    )


def test_status_requires_recent_authentication(admin, ids, clock):
    clock.advance(minutes=6)
    target = ids["support_user"]
    assert (
        admin.post(
            f"/api/platform/operators/{target}/status", json={"blocked": True}
        ).status_code
        == 403
    )
    assert (
        admin.post("/api/auth/reauthenticate", json={"password": PASSWORD}).status_code
        == 204
    )
    assert (
        admin.post(
            f"/api/platform/operators/{target}/status", json={"blocked": True}
        ).status_code
        == 200
    )


def test_role_password_is_fresh_reauthentication(admin, ids, clock):
    clock.advance(minutes=6)
    target = ids["support_user"]
    assert (
        admin.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        ).status_code
        == 200
    )


def test_status_revokes_all_sessions_and_records_audit(admin, support, ids, db_runtime):
    target = ids["support_user"]
    assert (
        admin.post(
            f"/api/platform/operators/{target}/status",
            json={"active": False, "blocked": True},
        ).status_code
        == 200
    )
    assert support.get("/api/auth/me").status_code == 401
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM auth_sessions WHERE user_id=:id AND revoked_at IS NULL"
                ),
                {"id": target},
            ).scalar_one()
            == 0
        )
        event = conn.execute(
            text(
                "SELECT before_state,after_state FROM audit_events WHERE action='platform.operator.status.changed'"
            )
        ).one()
    assert event.before_state["active"] is True
    assert event.after_state["active"] is False
    assert event.after_state["blocked"] is True


def test_operators_require_csrf(admin, ids):
    admin.headers.pop("X-CSRF-Token")
    assert (
        admin.post(
            f"/api/platform/operators/{ids['support_user']}/status",
            json={"active": False},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "payload", [{}, {"active": "false"}, {"active": True, "tenant_id": str(uuid4())}]
)
def test_status_input_is_explicit_and_closed(admin, ids, payload):
    assert (
        admin.post(
            f"/api/platform/operators/{ids['support_user']}/status", json=payload
        ).status_code
        == 422
    )


def test_role_endpoint_does_not_create_identity(admin):
    target = uuid4()
    assert (
        admin.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        ).status_code
        == 404
    )


def test_two_admins_cannot_disable_themselves_concurrently(
    admin, new_client, auth_users, db_runtime
):
    second_id = seed_user(db_runtime, "second@example.test", "PLATFORM_ADMIN")
    second = new_client()
    login(second, "second@example.test")
    barrier = Barrier(2)

    def disable(pair):
        browser, target = pair
        barrier.wait(timeout=10)
        return browser.post(
            f"/api/platform/operators/{target}/status", json={"active": False}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(disable, [(admin, auth_users["admin_user"]), (second, second_id)])
        )
    assert sorted(results) == [200, 409]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM users u JOIN platform_role_assignments r ON r.user_id=u.id WHERE u.active AND NOT u.blocked AND r.active AND r.role='PLATFORM_ADMIN'"
                )
            ).scalar_one()
            == 1
        )


def test_operator_change_rolls_back_when_audit_fails(
    admin, ids, db_owner, db_runtime, new_client
):
    target = ids["support_user"]
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT test_deny_audit CHECK (false) NOT VALID"
            )
        )
    try:
        safe = new_client(raise_server_exceptions=False)
        safe.cookies.update(admin.cookies)
        safe.headers.update(admin.headers)
        response = safe.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        )
        assert response.status_code == 500
        assert PASSWORD not in response.text
        with db_runtime.connect() as conn:
            assert (
                conn.execute(
                    text(
                        "SELECT role FROM platform_role_assignments WHERE user_id=:id"
                    ),
                    {"id": target},
                ).scalar_one()
                == "PLATFORM_SUPPORT"
            )
            assert (
                conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
                == 0
            )
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT test_deny_audit")
            )


def test_operator_denial_records_authenticated_actor(support, ids, db_runtime):
    assert (
        support.post(
            f"/api/platform/operators/{ids['admin_user']}/status",
            json={"active": False},
        ).status_code
        == 403
    )
    with db_runtime.connect() as conn:
        event = conn.execute(
            text(
                "SELECT actor_id,actor_role FROM access_events WHERE action='auth.request.denied' AND reason='PLATFORM_ADMIN_REQUIRED'"
            )
        ).one()
    assert event.actor_id == ids["support_user"]
    assert event.actor_role == "PLATFORM_SUPPORT"


def test_operator_password_attempts_share_login_limit(admin, ids):
    target = ids["support_user"]
    for _ in range(10):
        assert (
            admin.post(
                f"/api/platform/operators/{target}/role",
                json=role_payload(target, password="wrong"),
            ).status_code
            == 401
        )
    assert (
        admin.post(
            f"/api/platform/operators/{target}/role", json=role_payload(target)
        ).status_code
        == 429
    )
