"""Disposable PostgreSQL operations proof. Never accepts production URLs."""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from tests.database_harness import (
    attest_test_connection,
    open_test_engines,
)


def pgtool(name, *args, owner=False):
    env = os.environ.copy()
    if owner:
        from sqlalchemy.engine import make_url

        url = make_url(env["TEST_DATABASE_OWNER_URL"])
        env["PGUSER"], env["PGPASSWORD"] = url.username, url.password
    result = subprocess.run(
        [name, *args], env=env, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(
            f"{name} failed; diagnostic withheld to prevent credential exposure"
        )


def invalidate_restore(restored, database, root, uid, tid, cid, sid, password=None):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.orm import Session

    from app.db.models import (
        AccessContext,
        AuthPreauth,
        EmailOutbox,
        Membership,
        SecurityToken,
        SupportSession,
        TemporaryPrivilegedGrant,
        TenantRole,
        User,
    )

    now = datetime.now(UTC)
    with Session(restored) as db, db.begin():
        target = User(
            id=uuid4(),
            email_normalized="restore-viewed@example.test",
            display_name="Synthetic viewed member",
        )
        db.add(target)
        db.flush()
        role = TenantRole(
            id=uuid4(),
            tenant_id=tid,
            contract_id=cid,
            code="RESTORE_PROOF",
            name="Synthetic restore role",
        )
        db.add(role)
        db.flush()
        member = Membership(
            id=uuid4(),
            user_id=target.id,
            tenant_id=tid,
            contract_id=cid,
            role_id=role.id,
        )
        db.add(member)
        db.flush()
        contexts = [
            AccessContext(
                id=uuid4(),
                session_id=sid,
                actor_id=uid,
                tenant_id=tid,
                contract_id=cid,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
            for _ in range(3)
        ]
        db.add_all(contexts)
        db.flush()
        db.add(
            SupportSession(
                id=uuid4(),
                operator_id=uid,
                operator_session_id=sid,
                operator_role="PLATFORM_ADMIN",
                tenant_id=tid,
                contract_id=cid,
                parent_context_id=contexts[0].id,
                context_id=contexts[1].id,
                viewed_membership_id=member.id,
                viewed_user_id=target.id,
                mode="READ_ONLY",
                reason="Synthetic restore proof",
                started_at=now,
                expires_at=now + timedelta(minutes=20),
                status="ACTIVE",
            )
        )
        db.add(
            TemporaryPrivilegedGrant(
                id=uuid4(),
                operator_id=uid,
                operator_session_id=sid,
                operator_role="PLATFORM_ADMIN",
                tenant_id=tid,
                contract_id=cid,
                parent_context_id=contexts[0].id,
                context_id=contexts[2].id,
                grant_type="FINANCIAL_FISCAL",
                reason="Synthetic restore proof",
                started_at=now,
                expires_at=now + timedelta(minutes=20),
                status="ACTIVE",
            )
        )
        db.add(
            AuthPreauth(
                token_hash="1" * 64,
                csrf_hash="2" * 64,
                expires_at=now + timedelta(minutes=10),
            )
        )
        token = SecurityToken(
            id=uuid4(),
            token_hash="3" * 64,
            purpose="PASSWORD_RESET",
            recipient_user_id=uid,
            recipient_email="backup-proof@example.test",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        db.add(token)
        db.flush()
        db.add(
            EmailOutbox(
                id=uuid4(),
                token_id=token.id,
                message_type="PASSWORD_RESET",
                recipient="backup-proof@example.test",
                status="QUEUED",
                attempts=0,
                ciphertext="synthetic-unusable-ciphertext",
                created_at=now,
            )
        )
    policy = (
        Path(__file__).resolve().parents[1] / "database" / "post-restore-invalidate.sql"
    )
    with restored.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_events ADD CONSTRAINT phase11_restore_audit_failure CHECK (action <> 'identity.restore.invalidated')"
            )
        )
    try:
        pgtool(
            "psql.exe",
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            "expected_database=" + database,
            "-v",
            "technical_operator=Phase11 operator",
            "-v",
            "incident_reference=PHASE11-ROLLBACK",
            "-d",
            database,
            "-f",
            str(policy),
            owner=True,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Audit failure did not fail policy")
    with restored.begin() as conn:
        assert conn.execute(
            text("SELECT count(*)=1 FROM auth_sessions WHERE revoked_at IS NULL")
        ).scalar_one()
        assert conn.execute(
            text("SELECT count(*)=1 FROM support_sessions WHERE status='ACTIVE'")
        ).scalar_one()
        assert conn.execute(
            text(
                "SELECT count(*)=1 FROM temporary_privileged_grants WHERE status='ACTIVE'"
            )
        ).scalar_one()
        assert conn.execute(text("SELECT count(*)=1 FROM auth_preauth")).scalar_one()
        assert conn.execute(
            text("SELECT count(*)=1 FROM security_tokens WHERE invalidated_at IS NULL")
        ).scalar_one()
        assert conn.execute(
            text(
                "SELECT count(*)=1 FROM email_outbox WHERE ciphertext IS NOT NULL AND status='QUEUED'"
            )
        ).scalar_one()
        conn.execute(
            text(
                "ALTER TABLE audit_events DROP CONSTRAINT phase11_restore_audit_failure"
            )
        )
    pgtool(
        "psql.exe",
        "-v",
        "ON_ERROR_STOP=1",
        "-v",
        "expected_database=" + database,
        "-v",
        "technical_operator=Phase11 synthetic operator",
        "-v",
        "incident_reference=PHASE11-RESTORE-PROOF",
        "-d",
        database,
        "-f",
        str(policy),
        owner=True,
    )
    with restored.connect() as conn:
        for sql in [
            "SELECT count(*)=0 FROM auth_sessions WHERE revoked_at IS NULL",
            "SELECT count(*)=0 FROM access_contexts WHERE revoked_at IS NULL",
            "SELECT count(*)=0 FROM support_sessions WHERE status='ACTIVE'",
            "SELECT count(*)=0 FROM temporary_privileged_grants WHERE status='ACTIVE'",
            "SELECT count(*)=0 FROM auth_preauth",
            "SELECT count(*)=0 FROM security_tokens WHERE consumed_at IS NULL AND invalidated_at IS NULL",
            "SELECT count(*)=0 FROM email_outbox WHERE status IN ('QUEUED','DISPATCHING') OR ciphertext IS NOT NULL",
            "SELECT count(*)=1 FROM audit_events WHERE action='identity.restore.invalidated'",
            "SELECT count(*)=1 FROM contracts WHERE code='PHASE11_SYNTHETIC'",
            "SELECT count(*)=1 FROM audit_events WHERE action='phase11.synthetic.backup'",
        ]:
            assert conn.execute(text(sql)).scalar_one(), (
                "Postrestore policy proof failed"
            )

    if password:
        from fastapi.testclient import TestClient

        from app.core.config import Settings
        from app.main import create_app
        from tests.identity_helpers import csrf, login

        settings = Settings(
            database_url=restored.url.set(
                username="phase11_runtime",
                password=__import__("sqlalchemy")
                .engine.make_url(os.environ["TEST_DATABASE_RUNTIME_URL"])
                .password,
            ).render_as_string(hide_password=False),
            environment="test",
            public_origin="https://testserver",
        )
        with TestClient(create_app(settings), base_url="https://testserver") as client:
            client.cookies.set("__Host-hiatlas-session", "synthetic_session")
            assert client.get("/api/auth/me").status_code == 401
            client.cookies.clear()
            login(client, email="backup-proof@example.test", password=password)
            assert client.get("/api/auth/me").status_code == 200
            csrf(client)
            assert client.post("/api/auth/logout").status_code == 204


def schema_snapshot(conn):
    queries = [
        "SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
        "SELECT c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname",
        "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
        "SELECT c.relname,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','S') ORDER BY c.relname",
        "SELECT c.relname,a.attname,a.attacl::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
    ]
    return [[list(row) for row in conn.execute(text(sql))] for sql in queries]


def run():
    owner, runtime = open_test_engines()
    report = {}
    config = Config("alembic.ini")
    config.attributes["runtime_role"] = runtime.url.username
    config.attributes["recovery_role"] = os.environ["RECOVERY_DATABASE_ROLE"]
    with owner.begin() as conn:
        for table in inspect(conn).get_table_names():
            if table != "alembic_version":
                quoted = conn.dialect.identifier_preparer.quote(table)
                assert (
                    conn.execute(text("SELECT count(*) FROM " + quoted)).scalar_one()
                    == 0
                )
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
        command.upgrade(config, "0008")
        command.upgrade(config, "0009")
        report["full_0001_0009"] = "PASS"
        command.upgrade(config, "0010")
        report["incremental_0009_0010"] = "PASS"
        incremental_schema = schema_snapshot(conn)
        command.downgrade(config, "0009")
        command.upgrade(config, "0010")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        report["down_up_full_head"] = "PASS"
        assert schema_snapshot(conn) == incremental_schema, (
            "Fresh/incremental physical catalog mismatch"
        )
        report[
            "fresh_incremental_tables_columns_constraints_indexes_table_column_acls_equivalence"
        ] = "PASS"
    config.attributes.pop("connection")
    with runtime.connect() as conn:
        checks = {
            "runtime_no_schema_create": "NOT has_schema_privilege(current_user,'public','CREATE')",
            "runtime_no_database_create": "NOT has_database_privilege(current_user,current_database(),'CREATE')",
            "runtime_no_event_update": "NOT has_table_privilege(current_user,'audit_events','UPDATE')",
            "runtime_no_event_delete": "NOT has_table_privilege(current_user,'audit_events','DELETE')",
            "runtime_no_event_truncate": "NOT has_table_privilege(current_user,'audit_events','TRUNCATE')",
            "runtime_no_business_delete": "NOT has_table_privilege(current_user,'users','DELETE')",
            "runtime_no_migration_select": "NOT has_table_privilege(current_user,'alembic_version','SELECT')",
            "runtime_event_insert": "has_table_privilege(current_user,'audit_events','INSERT')",
            "runtime_technical_delete": "has_table_privilege(current_user,'auth_sessions','DELETE')",
        }
        for name, sql in checks.items():
            assert conn.execute(text("SELECT " + sql)).scalar_one(), name
            report[name] = "PASS"
        for sql in [
            "CREATE TABLE forbidden_phase11(id int)",
            "DELETE FROM users",
            "UPDATE audit_events SET action=action",
            "TRUNCATE audit_events",
            "SELECT * FROM alembic_version",
        ]:
            transaction = conn.begin_nested()
            try:
                conn.execute(text(sql))
            except DBAPIError as exc:
                assert getattr(exc.orig, "sqlstate", None) == "42501"
                transaction.rollback()
            else:
                transaction.rollback()
                raise AssertionError("Forbidden runtime statement succeeded")
        report["actual_runtime_permission_denials"] = "PASS"
    uid, tid, cid, aid, sid, oid = [uuid4() for _ in range(6)]
    password = secrets.token_urlsafe(32)
    from app.identity.passwords import hash_password

    password_hash = hash_password(password)
    with owner.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users(id,email_normalized,display_name,password_hash) VALUES(:id,'backup-proof@example.test','Synthetic backup proof',:hash)"
            ),
            {"id": uid, "hash": password_hash},
        )
        conn.execute(
            text("INSERT INTO tenants(id,name) VALUES(:id,'Synthetic phase11 tenant')"),
            {"id": tid},
        )
        conn.execute(
            text(
                "INSERT INTO contracts(id,tenant_id,code,name,environment) VALUES(:id,:tid,'PHASE11_SYNTHETIC','Synthetic phase11 contract','TEST')"
            ),
            {"id": cid, "tid": tid},
        )
        conn.execute(
            text(
                "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code,version) VALUES(:id,:tid,:cid,'COMPANY','Synthetic restore company','RESTORE_COMPANY',7)"
            ),
            {"id": oid, "tid": tid, "cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO auth_sessions(id,user_id,token_hash,csrf_hash,created_at,last_seen_at,expires_at) VALUES(:id,:uid,:token,:csrf,now(),now(),now()+interval '1 hour')"
            ),
            {
                "id": sid,
                "uid": uid,
                "token": hashlib.sha256(b"synthetic_session").hexdigest(),
                "csrf": hashlib.sha256(b"synthetic_csrf").hexdigest(),
            },
        )
        conn.execute(
            text(
                "INSERT INTO audit_events(id,actor_id,actor_role,tenant_id,contract_id,environment,action,outcome,request_id) VALUES(:id,:uid,'PLATFORM_ADMIN',:tid,:cid,'TEST','phase11.synthetic.backup','SUCCESS',:request)"
            ),
            {"id": aid, "uid": uid, "tid": tid, "cid": cid, "request": uuid4()},
        )
    root = Path(os.environ["PHASE11_TEMP"])
    dump = root / "synthetic.dump"
    pgtool(
        "pg_dump.exe",
        "-Fc",
        "--file",
        str(dump),
        "--dbname",
        owner.url.database,
        owner=True,
    )
    restored_name = "hiatlas_phase11_restore_" + uuid4().hex[:8] + "_test"
    admin = create_engine(
        owner.url.set(
            username=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            database="postgres",
        ),
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
    )
    with admin.connect() as conn:
        assert not conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:name"),
            {"name": restored_name},
        ).scalar()
        conn.execute(text(f"CREATE DATABASE {restored_name} OWNER phase11_owner"))
        conn.execute(
            text(f"COMMENT ON DATABASE {restored_name} IS 'hiatlas-disposable-test-db'")
        )
        conn.execute(text(f"REVOKE ALL ON DATABASE {restored_name} FROM PUBLIC"))
        conn.execute(
            text(
                f"GRANT CONNECT ON DATABASE {restored_name} TO phase11_runtime,phase11_recovery"
            )
        )
    pgtool(
        "pg_restore.exe",
        "--exit-on-error",
        "--dbname",
        restored_name,
        str(dump),
        owner=True,
    )
    restored_url = owner.url.set(database=restored_name)
    restored = create_engine(restored_url, hide_parameters=True)
    with restored.connect() as conn:
        attest_test_connection(conn, restored_url)
        assert (
            conn.execute(
                text("SELECT name FROM contracts WHERE id=:id AND tenant_id=:tid"),
                {"id": cid, "tid": tid},
            ).scalar_one()
            == "Synthetic phase11 contract"
        )
        assert (
            conn.execute(
                text("SELECT action FROM audit_events WHERE id=:id AND actor_id=:uid"),
                {"id": aid, "uid": uid},
            ).scalar_one()
            == "phase11.synthetic.backup"
        )
        assert conn.execute(
            text("SELECT revoked_at IS NULL FROM auth_sessions WHERE id=:id"),
            {"id": sid},
        ).scalar_one()
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0010"
        )
        assert conn.execute(
            text(
                "SELECT NOT has_table_privilege('phase11_runtime','audit_events','UPDATE')"
            )
        ).scalar_one()
        assert conn.execute(
            text(
                "SELECT code,version FROM organization_nodes WHERE id=:id AND tenant_id=:tid AND contract_id=:cid"
            ),
            {"id": oid, "tid": tid, "cid": cid},
        ).one() == ("RESTORE_COMPANY", 7)
        report["backup_restore_organization_scope_id_code_version"] = "PASS"
        report["backup_restore_new_database_integrity_and_grants"] = "PASS"
    invalidate_restore(restored, restored_name, root, uid, tid, cid, sid, password)
    report["offline_postrestore_technical_invalidation"] = "PASS"
    report["postrestore_oldsession_denied_newlogin_logout"] = "PASS"
    report["postrestore_audit_failure_atomic_rollback"] = "PASS"
    report["archive_sha256"] = hashlib.sha256(dump.read_bytes()).hexdigest()
    report["restored_database"] = restored_name
    report["source_database"] = owner.url.database
    (root / "operations-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    with owner.begin() as conn:
        names = [
            conn.dialect.identifier_preparer.quote(name)
            for name in inspect(conn).get_table_names()
            if name != "alembic_version"
        ]
        conn.execute(text("TRUNCATE " + ", ".join(names) + " CASCADE"))
    owner.dispose()
    runtime.dispose()
    restored.dispose()
    admin.dispose()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 -- redact all secret-bearing diagnostics
        print(f"Operational proof FAILED: {type(exc).__name__}; details withheld")
        raise SystemExit(1) from None
