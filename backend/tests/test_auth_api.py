import pytest
from sqlalchemy import text

from tests.identity_helpers import PASSWORD, SESSION_COOKIE, csrf, login


def test_unauthenticated_request_is_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert set(response.json()) == {"code", "message", "request_id"}


def test_csrf_issues_secure_preauth_without_session(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    assert len(response.json()["token"]) >= 32
    assert SESSION_COOKIE not in client.cookies
    for cookie in response.headers.get_list("set-cookie"):
        assert (
            "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
        )
        assert "Path=/" in cookie and "Domain=" not in cookie
    assert response.headers["cache-control"] == "no-store"


def test_login_returns_server_role_and_safe_projection(client, auth_users):
    response = login(client)
    assert response.json()["platform_role"] == "PLATFORM_ADMIN"
    assert response.json()["user_id"] == str(auth_users["admin_user"])
    assert (
        not {"password", "password_hash", "token", "token_hash"}
        & response.json().keys()
    )
    assert client.get("/api/auth/me").json() == response.json()


def test_support_and_member_roles_are_not_interchangeable(new_client, auth_users):
    support, member = new_client(), new_client()
    assert (
        login(support, "support@example.test").json()["platform_role"]
        == "PLATFORM_SUPPORT"
    )
    assert login(member, "member@example.test").json()["platform_role"] is None


def test_client_cannot_choose_platform_role(client):
    csrf(client)
    response = client.post(
        "/api/auth/login",
        json={
            "email": "member@example.test",
            "password": PASSWORD,
            "platform_role": "PLATFORM_ADMIN",
        },
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text


def test_logout_revokes_session(admin, new_client):
    stolen = admin.cookies.get(SESSION_COOKIE)
    assert admin.post("/api/auth/logout").status_code == 204
    assert admin.get("/api/auth/me").status_code == 401
    replay = new_client()
    replay.cookies.set(SESSION_COOKIE, stolen)
    assert replay.get("/api/auth/me").status_code == 401


def test_unknown_user_and_wrong_password_have_generic_response(
    client, auth_users, db_runtime
):
    csrf(client)
    wrong = client.post(
        "/api/auth/login",
        json={"email": "admin@example.test", "password": "wrong-secret"},
    )
    absent = client.post(
        "/api/auth/login",
        json={"email": "absent@example.test", "password": "wrong-secret"},
    )
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json()["code"] == absent.json()["code"]
    assert wrong.json()["message"] == absent.json()["message"]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM access_events WHERE action='auth.login' AND outcome='FAILURE'"
                )
            ).scalar_one()
            == 2
        )
        assert "wrong-secret" not in str(
            conn.execute(
                text("SELECT row_to_json(access_events) FROM access_events")
            ).all()
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a", "password": "sensitive-value", "role": "admin"},
        {"email": [], "password": {"secret": "sensitive-value"}},
    ],
)
def test_validation_never_echoes_credentials(client, payload):
    csrf(client)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 422
    assert "sensitive-value" not in response.text


def test_login_rotation_invalidates_old_session(admin, new_client):
    old = admin.cookies.get(SESSION_COOKIE)
    login(admin)
    assert admin.cookies.get(SESSION_COOKIE) != old
    replay = new_client()
    replay.cookies.set(SESSION_COOKIE, old)
    assert replay.get("/api/auth/me").status_code == 401


def test_reauthentication_requires_password_and_csrf(admin):
    assert (
        admin.post("/api/auth/reauthenticate", json={"password": "wrong"}).status_code
        == 401
    )
    assert (
        admin.post("/api/auth/reauthenticate", json={"password": PASSWORD}).status_code
        == 204
    )


def test_login_email_normalization(client, auth_users):
    assert login(client, " ADMIN@EXAMPLE.TEST ").status_code == 200
