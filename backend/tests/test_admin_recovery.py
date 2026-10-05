import subprocess
import sys
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_recovery_request_requires_verified_evidence():
    from app.identity.recover_admin import RecoveryRequest

    with pytest.raises(ValidationError):
        RecoveryRequest(
            environment="TEST",
            user_id=uuid4(),
            technical_operator="infra-42",
            reason="incident",
            reference="INC-42",
            verified_email="admin@example.test",
            confirmation=uuid4(),
            incident_evidence="",
        )


def test_recovery_cli_never_echoes_password_argument():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.identity.recover_admin",
            "--password",
            "secret-sentinel",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "secret-sentinel" not in result.stdout + result.stderr


import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import create_database_engine
from tests.identity_helpers import PASSWORD, seed_user


@pytest.fixture
def recovery_engine(db_runtime):
    url = os.environ.get("HIATLAS_TEST_RECOVERY_DATABASE_URL")
    if not url:
        pytest.fail(
            "Dedicated disposable recovery database URL required", pytrace=False
        )
    engine = create_database_engine(url)
    yield engine
    engine.dispose()


def recovery(engine, target, settings, **overrides):
    from app.identity.recover_admin import RecoveryRequest, recover_admin

    values = {
        "environment": "TEST",
        "user_id": target,
        "technical_operator": "infra-42",
        "reason": "Verified infrastructure incident",
        "reference": "INC-42",
        "verified_email": "admin@example.test",
        "confirmation": target,
        "incident_evidence": "Offline identity and approval verified INC-42",
    }
    values.update(overrides)
    request = RecoveryRequest(**values)
    with Session(engine) as db, db.begin():
        return recover_admin(
            db, request, PASSWORD, settings, recovery_role=engine.url.username
        )


def disabled_admin(db_runtime):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    with db_runtime.begin() as conn:
        conn.execute(text("UPDATE users SET blocked=true WHERE id=:id"), {"id": target})
    return target


def test_runtime_cannot_recover(db_runtime, settings):
    target = disabled_admin(db_runtime)
    with pytest.raises(ApiError) as failure:
        recovery(db_runtime, target, settings)
    assert failure.value.code == "RECOVERY_CREDENTIAL_REQUIRED"


def test_usable_admin_refuses_even_verified_password_lost(
    recovery_engine, db_runtime, settings
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings)
    assert failure.value.code == "RECOVERY_NOT_NECESSARY"


def test_recovery_restores_existing_admin_audits_technical_actor_and_refuses_repeat(
    recovery_engine, db_runtime, settings
):
    target = disabled_admin(db_runtime)
    recovery(recovery_engine, target, settings)
    with db_runtime.connect() as conn:
        user = conn.execute(
            text("SELECT active,blocked,password_hash FROM users WHERE id=:id"),
            {"id": target},
        ).one()
        event = conn.execute(
            text(
                "SELECT actor_id,entity_id,environment,after_state,reason,reference FROM audit_events WHERE action='identity.admin.recovered'"
            )
        ).one()
        assert user.active and not user.blocked
        assert event.actor_id is None and event.entity_id == target
        assert event.environment == "TEST"
        assert event.after_state["technical_operator"] == "infra-42"
        assert PASSWORD not in str(event)
        assert user.password_hash not in str(event)
        assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings)
    assert failure.value.code == "RECOVERY_NOT_NECESSARY"


@pytest.mark.parametrize(
    "kind", ["missing", "external", "support", "email", "confirmation"]
)
def test_invalid_target_refused(recovery_engine, db_runtime, settings, kind):
    target = seed_user(
        db_runtime,
        "admin@example.test",
        None
        if kind == "external"
        else "PLATFORM_SUPPORT"
        if kind == "support"
        else "PLATFORM_ADMIN",
    )
    with db_runtime.begin() as conn:
        conn.execute(text("UPDATE users SET blocked=true"))
    values = (
        {"verified_email": "other@example.test"}
        if kind == "email"
        else {"confirmation": uuid4()}
        if kind == "confirmation"
        else {}
    )
    with pytest.raises(ApiError):
        recovery(
            recovery_engine,
            uuid4() if kind == "missing" else target,
            settings,
            **values,
        )
    with db_runtime.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one() == 0


def test_audit_failure_rolls_back_recovery(
    recovery_engine, db_owner, db_runtime, settings
):
    from sqlalchemy.exc import IntegrityError

    target = disabled_admin(db_runtime)
    with db_runtime.connect() as conn:
        old_hash = conn.execute(
            text("SELECT password_hash FROM users WHERE id=:id"), {"id": target}
        ).scalar_one()
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT test_recovery_fail CHECK (false) NOT VALID"
            )
        )
    try:
        with pytest.raises(IntegrityError):
            recovery(recovery_engine, target, settings)
        with db_runtime.connect() as conn:
            user = conn.execute(
                text("SELECT blocked,password_hash FROM users WHERE id=:id"),
                {"id": target},
            ).one()
            assert user.blocked and user.password_hash == old_hash
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text("ALTER TABLE audit_events DROP CONSTRAINT test_recovery_fail")
            )


def test_concurrent_recovery_exactly_one_success(recovery_engine, db_runtime, settings):
    target = disabled_admin(db_runtime)
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait(timeout=10)
        try:
            recovery(recovery_engine, target, settings)
            return "SUCCESS"
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [
            "RECOVERY_NOT_NECESSARY",
            "SUCCESS",
        ]


def test_recovery_has_no_http_surface(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {path for path in paths if "recover" in path} == {"/api/auth/recovery"}
    assert client.post("/api/platform/admin-recovery", json={}).status_code == 404


def test_recovery_revokes_sessions_and_outstanding_reset(
    recovery_engine, db_runtime, settings, admin, ids
):
    target = ids["admin_user"]
    from datetime import UTC, datetime, timedelta

    from app.identity.models import EmailOutbox, SecurityToken

    token_id = uuid4()
    now = datetime.now(UTC)
    with Session(db_runtime) as db, db.begin():
        db.add(
            SecurityToken(
                id=token_id,
                token_hash="f" * 64,
                purpose="PASSWORD_RESET",
                recipient_user_id=target,
                recipient_email="admin@example.test",
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.flush()
        db.add(
            EmailOutbox(
                token_id=token_id,
                message_type="PASSWORD_RESET",
                recipient="admin@example.test",
                status="QUEUED",
                attempts=0,
                ciphertext="secret-sentinel",
                created_at=now,
            )
        )
        db.execute(text("UPDATE users SET blocked=true WHERE id=:id"), {"id": target})
    recovery(recovery_engine, target, settings)
    assert admin.get("/api/auth/me").status_code == 401
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
        assert (
            conn.execute(
                text("SELECT invalidated_at FROM security_tokens WHERE id=:id"),
                {"id": token_id},
            ).scalar_one()
            is not None
        )
        outbox = conn.execute(
            text("SELECT status,ciphertext FROM email_outbox WHERE token_id=:id"),
            {"id": token_id},
        ).one()
        assert outbox.status == "CANCELLED" and outbox.ciphertext is None


def test_recovery_grants_are_minimal(recovery_engine):
    with recovery_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT has_table_privilege(current_user,'users','INSERT') OR has_table_privilege(current_user,'users','DELETE') OR has_table_privilege(current_user,'users','UPDATE') OR has_table_privilege(current_user,'audit_events','UPDATE') OR has_table_privilege(current_user,'audit_events','DELETE') OR has_table_privilege(current_user,'audit_events','TRUNCATE') OR has_table_privilege(current_user,'audit_events','SELECT') AS unsafe"
            )
        ).one()
        assert not row.unsafe
        assert conn.execute(
            text(
                "SELECT has_column_privilege(current_user,'users','password_hash','UPDATE')"
            )
        ).scalar_one()


def test_recovery_refuses_elevated_recovery_grants(
    recovery_engine, db_owner, db_runtime, settings
):
    target = disabled_admin(db_runtime)
    role = recovery_engine.dialect.identifier_preparer.quote_identifier(
        recovery_engine.url.username
    )
    with db_owner.begin() as conn:
        conn.execute(text(f"GRANT TRUNCATE ON TABLE audit_events TO {role}"))
    try:
        with pytest.raises(ApiError) as failure:
            recovery(recovery_engine, target, settings)
        assert failure.value.code == "RECOVERY_CREDENTIAL_REQUIRED"
    finally:
        with db_owner.begin() as conn:
            conn.execute(text(f"REVOKE TRUNCATE ON TABLE audit_events FROM {role}"))


def test_recovery_revokes_owned_support_grant_and_all_contexts(
    recovery_engine, db_runtime, settings, admin, scope_ids, new_client
):
    from tests.identity_helpers import login
    from tests.test_grants import start as start_grant
    from tests.test_support_sessions import start as start_support

    other_browser = new_client()
    login(other_browser)
    _, grant = start_grant(admin, scope_ids)
    _, support = start_support(other_browser, scope_ids)
    assert grant.status_code == 201 and support.status_code == 201
    target = scope_ids["admin_user"]
    with db_runtime.begin() as conn:
        conn.execute(text("UPDATE users SET blocked=true WHERE id=:id"), {"id": target})
    recovery(recovery_engine, target, settings)
    with db_runtime.connect() as conn:
        for table, column in [
            ("auth_sessions", "user_id"),
            ("access_contexts", "actor_id"),
        ]:
            assert (
                conn.execute(
                    text(
                        f"SELECT count(*) FROM {table} WHERE {column}=:id AND revoked_at IS NULL"
                    ),
                    {"id": target},
                ).scalar_one()
                == 0
            )
        assert (
            conn.execute(
                text("SELECT status FROM support_sessions WHERE id=:id"),
                {"id": support.json()["id"]},
            ).scalar_one()
            == "REVOKED"
        )
        row = conn.execute(
            text(
                "SELECT status,revoked_at,version FROM temporary_privileged_grants WHERE id=:id"
            ),
            {"id": grant.json()["id"]},
        ).one()
        assert (
            row.status == "REVOKED" and row.revoked_at is not None and row.version == 2
        )


@pytest.mark.parametrize(
    "field", ["technical_operator", "reason", "reference", "incident_evidence"]
)
def test_recovery_rejects_control_text(field):
    from app.identity.recover_admin import RecoveryRequest

    values = {
        "environment": "TEST",
        "user_id": uuid4(),
        "technical_operator": "infra-42",
        "reason": "Verified incident",
        "reference": "INC-42",
        "incident_evidence": "Offline identity verified",
        "verified_email": "admin@example.test",
        "confirmation": uuid4(),
    }
    values[field] = "control\ntext"
    with pytest.raises(ValidationError):
        RecoveryRequest(**values)


def test_recovery_audit_requires_bound_technical_actor():
    from app.audit.schemas import RecoveryAuditInput, RecoverySnapshot

    target = uuid4()
    after = RecoverySnapshot(
        user_id=target,
        active=True,
        blocked=False,
        platform_role="PLATFORM_ADMIN",
        technical_operator="infra-42",
        database_role="recovery",
        incident_evidence="Offline verified incident",
    )
    with pytest.raises(ValidationError):
        RecoveryAuditInput(
            environment="TEST",
            entity_type="user",
            entity_id=uuid4(),
            before=after,
            after=after,
            reason="incident",
            reference="INC-42",
        )


def test_recovery_cli_refuses_pipe_without_echoing_password():
    target = str(uuid4())
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.identity.recover_admin",
            "--environment",
            "TEST",
            "--user-id",
            target,
            "--technical-operator",
            "infra-42",
            "--reason",
            "Verified incident",
            "--reference",
            "INC-42",
            "--incident-evidence",
            "Offline verified approval",
            "--verified-email",
            "admin@example.test",
            "--confirm-user-id",
            target,
        ],
        input="secret-sentinel",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "secret-sentinel" not in result.stdout + result.stderr


@pytest.mark.parametrize("state", ["inactive", "assignment_inactive", "no_hash"])
def test_recovery_restores_only_existing_admin_when_none_usable(
    recovery_engine, db_runtime, settings, state
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    with db_runtime.begin() as conn:
        statement = {
            "inactive": "UPDATE users SET active=false WHERE id=:id",
            "assignment_inactive": "UPDATE platform_role_assignments SET active=false WHERE user_id=:id",
            "no_hash": "UPDATE users SET password_hash=NULL WHERE id=:id",
        }[state]
        conn.execute(text(statement), {"id": target})
    assert recovery(recovery_engine, target, settings) == target


def test_other_usable_admin_blocks_recovery(recovery_engine, db_runtime, settings):
    target = disabled_admin(db_runtime)
    seed_user(db_runtime, "otheradmin@example.test", "PLATFORM_ADMIN")
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings)
    assert failure.value.code == "RECOVERY_NOT_NECESSARY"


def test_audit_failure_preserves_existing_session(
    recovery_engine, db_owner, db_runtime, settings, admin, ids
):
    from sqlalchemy.exc import IntegrityError

    target = ids["admin_user"]
    with db_runtime.begin() as conn:
        conn.execute(text("UPDATE users SET blocked=true WHERE id=:id"), {"id": target})
    with db_owner.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT test_recovery_session_fail CHECK (false) NOT VALID"
            )
        )
    try:
        with pytest.raises(IntegrityError):
            recovery(recovery_engine, target, settings)
        with db_runtime.connect() as conn:
            assert (
                conn.execute(
                    text(
                        "SELECT count(*) FROM auth_sessions WHERE user_id=:id AND revoked_at IS NULL"
                    ),
                    {"id": target},
                ).scalar_one()
                == 1
            )
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE audit_events DROP CONSTRAINT test_recovery_session_fail"
                )
            )


def test_sole_admin_lost_credentials_offline_attestation_is_audited(
    recovery_engine, db_runtime, settings
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    recovery(recovery_engine, target, settings, credential_loss_attested=True)
    with db_runtime.connect() as conn:
        state = conn.execute(
            text(
                "SELECT after_state FROM audit_events WHERE action='identity.admin.recovered'"
            )
        ).scalar_one()
        assert state["credential_loss_attested"] is True
        assert state["normal_recovery_unavailable"] is True
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings, credential_loss_attested=True)
    assert failure.value.code == "RECOVERY_INCIDENT_ALREADY_USED"


def test_lost_credentials_refused_if_normal_delivery_available(
    recovery_engine, db_runtime, settings
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    settings.smtp_host = "mail.example.test"
    settings.smtp_sender = "sender@example.test"
    settings.email_delivery_enabled = True
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings, credential_loss_attested=True)
    assert failure.value.code == "RECOVERY_NOT_NECESSARY"


def test_lost_credentials_attestation_never_bypasses_other_usable_admin(
    recovery_engine, db_runtime, settings
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    seed_user(db_runtime, "otheradmin@example.test", "PLATFORM_ADMIN")
    with pytest.raises(ApiError) as failure:
        recovery(recovery_engine, target, settings, credential_loss_attested=True)
    assert failure.value.code == "RECOVERY_NOT_NECESSARY"


def test_attested_same_incident_concurrently_recovers_once(
    recovery_engine, db_runtime, settings
):
    target = seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN")
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait(timeout=10)
        try:
            recovery(recovery_engine, target, settings, credential_loss_attested=True)
            return "SUCCESS"
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [
            "RECOVERY_INCIDENT_ALREADY_USED",
            "SUCCESS",
        ]
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='identity.admin.recovered'"
                )
            ).scalar_one()
            == 1
        )


def test_cli_mismatched_protected_attestation_uuid_never_opens_database(monkeypatch):
    from app.identity import recover_admin as module

    target = str(uuid4())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "recover_admin",
            "--credential-loss",
            "--environment",
            "TEST",
            "--user-id",
            target,
            "--technical-operator",
            "infra-42",
            "--reason",
            "Verified incident",
            "--reference",
            "INC-42",
            "--incident-evidence",
            "Offline verified approval",
            "--verified-email",
            "admin@example.test",
            "--confirm-user-id",
            target,
        ],
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.setenv("RECOVERY_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("RECOVERY_DATABASE_ROLE", "recovery")
    monkeypatch.setattr(module.getpass, "getpass", lambda prompt: str(uuid4()))

    def forbidden_engine(_):
        pytest.fail("Mismatched protected confirmation reached database")

    monkeypatch.setattr(module, "create_database_engine", forbidden_engine)
    assert module.main() == 2
