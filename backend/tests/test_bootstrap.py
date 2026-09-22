from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.identity_helpers import PASSWORD, seed_user


def bootstrap(engine, email="first@example.test"):
    from app.identity.bootstrap import bootstrap_admin

    with Session(engine) as db, db.begin():
        return bootstrap_admin(db, email, PASSWORD)


def test_bootstrap_creates_hashed_admin_and_audit(db_runtime, capsys):
    user_id = bootstrap(db_runtime)
    with db_runtime.connect() as conn:
        user = conn.execute(
            text("SELECT password_hash FROM users WHERE id=:id"), {"id": user_id}
        ).scalar_one()
        assert user.startswith("$argon2id$")
        assert PASSWORD not in user
        assert (
            conn.execute(
                text("SELECT role FROM platform_role_assignments WHERE user_id=:id"),
                {"id": user_id},
            ).scalar_one()
            == "PLATFORM_ADMIN"
        )
        event = conn.execute(
            text(
                "SELECT actor_id,after_state FROM audit_events WHERE action='identity.bootstrap'"
            )
        ).one()
    assert event.actor_id == user_id
    assert event.after_state["platform_role"] == "PLATFORM_ADMIN"
    captured = capsys.readouterr()
    assert PASSWORD not in captured.out + captured.err
    assert user not in captured.out + captured.err


def test_second_bootstrap_never_creates_another_admin(db_runtime):
    from app.core.errors import ApiError

    bootstrap(db_runtime)
    with pytest.raises(ApiError) as failure:
        bootstrap(db_runtime, "second@example.test")
    assert failure.value.status == 409
    with db_runtime.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 1


def test_bootstrap_cannot_reopen_after_operator_is_disabled(db_runtime):
    from app.core.errors import ApiError

    bootstrap(db_runtime)
    with db_runtime.begin() as conn:
        conn.execute(text("UPDATE users SET active=false"))
        conn.execute(
            text("UPDATE platform_role_assignments SET role='PLATFORM_SUPPORT'")
        )
    with pytest.raises(ApiError):
        bootstrap(db_runtime, "replacement@example.test")


def test_bootstrap_cannot_take_over_existing_identity(db_runtime):
    from app.core.errors import ApiError

    seed_user(db_runtime, "first@example.test")
    with pytest.raises(ApiError):
        bootstrap(db_runtime)
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM platform_role_assignments")
            ).scalar_one()
            == 0
        )


def test_concurrent_bootstrap_creates_exactly_one_admin(db_runtime):
    from app.core.errors import ApiError

    barrier = Barrier(2)

    def attempt(email):
        barrier.wait(timeout=10)
        try:
            bootstrap(db_runtime, email)
            return "created"
        except ApiError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["one@example.test", "two@example.test"]))
    assert outcomes.count("created") == 1
    assert outcomes.count(409) == 1
    with db_runtime.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one() == 1


def test_bootstrap_audit_failure_rolls_back_identity(db_owner, db_runtime):
    from sqlalchemy.exc import IntegrityError

    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT test_deny_bootstrap CHECK (false) NOT VALID"
            )
        )
    try:
        with pytest.raises(IntegrityError):
            bootstrap(db_runtime)
        with db_runtime.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT test_deny_bootstrap")
            )


def test_bootstrap_has_no_http_endpoint(client):
    assert (
        client.post(
            "/api/bootstrap", json={"email": "x@example.test", "password": PASSWORD}
        ).status_code
        == 404
    )


def test_cli_does_not_accept_password_argument_or_pipe():
    import subprocess
    import sys

    response = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.identity.bootstrap",
            "--email",
            "x@example.test",
            "--password",
            "sentinel-password",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode != 0
    assert "sentinel-password" not in response.stdout + response.stderr
    piped = subprocess.run(
        [sys.executable, "-m", "app.identity.bootstrap", "--email", "x@example.test"],
        input=PASSWORD,
        capture_output=True,
        text=True,
        check=False,
    )
    assert piped.returncode != 0
    assert PASSWORD not in piped.stdout + piped.stderr
