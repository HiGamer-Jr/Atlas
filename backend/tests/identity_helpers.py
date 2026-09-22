from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from sqlalchemy import text

PASSWORD = "test-only-password-2026"
TEST_HASH = PasswordHasher().hash(PASSWORD)
SESSION_COOKIE = "__Host-hiatlas-session"
CSRF_COOKIE = "__Host-hiatlas-csrf"
PREAUTH_COOKIE = "__Host-hiatlas-preauth"


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


def seed_user(engine, email, role=None):
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id,email_normalized,display_name,password_hash) "
                "VALUES (:id,:email,'Test operator',:hash)"
            ),
            {"id": user_id, "email": email, "hash": TEST_HASH},
        )
        if role:
            conn.execute(
                text(
                    "INSERT INTO platform_role_assignments (user_id,role) VALUES (:id,:role)"
                ),
                {"id": user_id, "role": role},
            )
    return user_id


def csrf(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["token"]
    client.headers["Origin"] = "https://testserver"
    return response.json()["token"]


def login(client, email="admin@example.test", password=PASSWORD):
    csrf(client)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    csrf(client)
    return response
