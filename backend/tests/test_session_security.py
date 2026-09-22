import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.identity_helpers import PASSWORD, SESSION_COOKIE, csrf, login


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.test"},
        {"Origin": "null"},
        {},
        {"Origin": "https://testserver", "X-CSRF-Token": "invalid"},
    ],
)
def test_login_requires_matching_csrf_and_origin(client, auth_users, headers):
    csrf(client)
    client.headers.pop("Origin", None)
    client.headers.pop("X-CSRF-Token", None)
    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={"email": "admin@example.test", "password": PASSWORD},
    )
    assert response.status_code == 403
    assert SESSION_COOKIE not in client.cookies


def test_preauth_expires(client, clock, auth_users):
    csrf(client)
    clock.advance(minutes=11)
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": PASSWORD},
        ).status_code
        == 403
    )


def test_idle_expiration_is_observed_next_request(admin, clock):
    clock.advance(minutes=30)
    assert admin.get("/api/auth/me").status_code == 401


def test_absolute_expiration_survives_activity(admin, clock):
    for _ in range(23):
        clock.advance(minutes=20)
        assert admin.get("/api/auth/me").status_code == 200
    clock.advance(minutes=20)
    assert admin.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("change", ["blocked=true", "active=false"])
def test_changed_user_status_is_effective_immediately(
    admin, auth_users, db_runtime, change
):
    with db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE users SET {change} WHERE id=:id"),
            {"id": auth_users["admin_user"]},
        )
    assert admin.get("/api/auth/me").status_code == 401


def test_current_role_is_read_from_database(admin, auth_users, db_runtime):
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE platform_role_assignments SET role='PLATFORM_SUPPORT' WHERE user_id=:id"
            ),
            {"id": auth_users["admin_user"]},
        )
    assert admin.get("/api/auth/me").json()["platform_role"] == "PLATFORM_SUPPORT"


def test_database_has_no_plain_session_or_csrf_tokens(admin, db_runtime):
    with db_runtime.connect() as conn:
        stored = str(
            conn.execute(
                text("SELECT row_to_json(auth_sessions) FROM auth_sessions")
            ).all()
        )
    assert admin.cookies.get(SESSION_COOKIE) not in stored
    assert admin.headers["X-CSRF-Token"] not in stored


def test_logout_requires_csrf(admin):
    admin.headers.pop("X-CSRF-Token")
    assert admin.post("/api/auth/logout").status_code == 403
    assert admin.get("/api/auth/me").status_code == 200


def test_revocation_survives_application_restart(admin, settings):
    from app.main import create_app

    token = admin.cookies.get(SESSION_COOKIE)
    assert admin.post("/api/auth/logout").status_code == 204
    with TestClient(create_app(settings), base_url="https://testserver") as restarted:
        restarted.cookies.set(SESSION_COOKIE, token)
        assert restarted.get("/api/auth/me").status_code == 401


def test_rate_limit_persists_between_app_instances(client, auth_users, settings, clock):
    from app.main import create_app

    csrf(client)
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "admin@example.test", "password": "wrong"},
            ).status_code
            == 401
        )
    with TestClient(create_app(settings), base_url="https://testserver") as restarted:
        csrf(restarted)
        denied = restarted.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": PASSWORD},
        )
        assert denied.status_code == 429
        assert int(denied.headers["retry-after"]) > 0
    clock.advance(minutes=16)
    assert login(client).status_code == 200


def test_untrusted_forwarded_origin_does_not_bypass_rate_limit(client, auth_users, app):
    app.state.settings.auth_source_limit = 2
    csrf(client)
    for index in range(2):
        response = client.post(
            "/api/auth/login",
            headers={"X-Forwarded-For": f"192.0.2.{index}"},
            json={"email": f"absent{index}@example.test", "password": "wrong"},
        )
        assert response.status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            headers={"X-Forwarded-For": "192.0.2.99"},
            json={"email": "admin@example.test", "password": PASSWORD},
        ).status_code
        == 429
    )


def test_concurrent_failures_share_one_identifier_budget(new_client, auth_users, app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    app.state.settings.auth_identifier_limit = 1
    clients = [new_client(), new_client()]
    for browser in clients:
        csrf(browser)
    barrier = Barrier(2)

    def attempt(browser):
        barrier.wait(timeout=10)
        return browser.post(
            "/api/auth/login", json={"email": "admin@example.test", "password": "wrong"}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, clients))
    assert sorted(results) == [401, 429]


def test_consumed_preauth_cannot_be_replayed(client, new_client, auth_users):
    from tests.identity_helpers import CSRF_COOKIE, PREAUTH_COOKIE

    old_csrf = csrf(client)
    old_pre = client.cookies.get(PREAUTH_COOKIE)
    login(client)
    replay = new_client()
    replay.cookies.set(PREAUTH_COOKIE, old_pre)
    replay.cookies.set(CSRF_COOKIE, old_csrf)
    replay.headers.update({"Origin": "https://testserver", "X-CSRF-Token": old_csrf})
    assert (
        replay.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": PASSWORD},
        ).status_code
        == 403
    )


def test_reauthentication_uses_login_failure_budget(admin):
    for _ in range(10):
        assert (
            admin.post(
                "/api/auth/reauthenticate", json={"password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        admin.post("/api/auth/reauthenticate", json={"password": PASSWORD}).status_code
        == 429
    )


def test_revoked_session_cannot_obtain_authenticated_csrf(admin, new_client):
    old = admin.cookies.get(SESSION_COOKIE)
    assert admin.post("/api/auth/logout").status_code == 204
    replay = new_client()
    replay.cookies.set(SESSION_COOKIE, old)
    csrf(replay)
    assert replay.get("/api/auth/me").status_code == 401


def test_authentication_denials_are_audited(client, db_runtime):
    assert client.get("/api/auth/me").status_code == 401
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM access_events WHERE outcome='DENIED' AND reason='SESSION_INVALID'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("table", ["auth_sessions", "auth_preauth", "auth_rate_limits"])
def test_technical_tables_allow_lifecycle_delete_but_not_truncate(db_runtime, table):
    from sqlalchemy.exc import DBAPIError

    with db_runtime.begin() as conn:
        conn.execute(text(f"DELETE FROM {table} WHERE false"))
    with pytest.raises(DBAPIError) as failure, db_runtime.begin() as conn:
        conn.execute(text(f"TRUNCATE {table}"))
    assert failure.value.orig.sqlstate == "42501"


def test_production_rejects_insecure_config():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(environment="production")
    with pytest.raises(ValidationError):
        Settings(public_origin="http://public.example.test")
