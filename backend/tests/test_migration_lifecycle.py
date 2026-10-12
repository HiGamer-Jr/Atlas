import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError

from alembic import command

TABLES = {
    "users",
    "platform_role_assignments",
    "tenants",
    "contracts",
    "audit_events",
    "access_events",
}


def test_upgrade_downgrade_upgrade_preserves_runtime_grants(
    db_owner, db_runtime, migration_config
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "base")
            assert not (TABLES & set(inspect(conn).get_table_names()))
            command.upgrade(migration_config, "head")
            assert TABLES <= set(inspect(conn).get_table_names())
        with db_runtime.connect() as conn:
            assert conn.execute(
                text("SELECT has_table_privilege(current_user,'audit_events','INSERT')")
            ).scalar_one()
            assert not conn.execute(
                text("SELECT has_table_privilege(current_user,'audit_events','UPDATE')")
            ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser"])
def test_migration_rejects_unsafe_runtime_role(
    db_owner, db_runtime, migration_config, unsafe
):
    good_role = migration_config.attributes["runtime_role"]
    try:
        with pytest.raises(RuntimeError, match="role"), db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "base")
            bad_role = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
            )
            migration_config.attributes["runtime_role"] = bad_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role
    with db_runtime.connect() as conn:
        assert TABLES <= set(inspect(conn).get_table_names())


def test_incremental_session_migration_rejects_superuser_runtime(
    db_owner, db_runtime, migration_config
):
    good_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0001")
            migration_config.attributes["runtime_role"] = conn.execute(
                text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
            ).scalar_one()
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "head")
            migration_config.attributes["runtime_role"] = good_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_incremental_phase6_migration_rejects_unsafe_runtime_before_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    good_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0004")
            bad_role = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            migration_config.attributes["runtime_role"] = bad_role
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0005")
            assert "description" not in {
                column["name"] for column in inspect(conn).get_columns("tenant_roles")
            }
            migration_config.attributes["runtime_role"] = good_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role


def test_customer_scope_incremental_migration_preserves_restricted_memberships(
    db_owner, db_runtime, migration_config, scope_ids
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0012")
            assert "unit_scope_mode" not in {
                c["name"] for c in inspect(conn).get_columns("memberships")
            }
            command.upgrade(migration_config, "head")
            assert set(
                conn.execute(text("SELECT unit_scope_mode FROM memberships")).scalars()
            ) == {"RESTRICTED"}
            checks = inspect(conn).get_check_constraints("memberships")
            assert any(c["name"] == "ck_membership_unit_scope_mode" for c in checks)
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_purchase_request_migration_rejects_unsafe_runtime_before_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    good_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0013")
            bad_role = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            migration_config.attributes["runtime_role"] = bad_role
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0014")
            assert "purchase_requests" not in inspect(conn).get_table_names()
            migration_config.attributes["runtime_role"] = good_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role


def test_purchase_request_downgrade_refuses_evidence_loss(
    db_owner, db_runtime, migration_config, scope_ids
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            conn.execute(
                text(
                    "INSERT INTO contract_request_policies(tenant_id,contract_id) VALUES (:tenant,:contract)"
                ),
                {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
            )
            with pytest.raises(RuntimeError, match="evidence must be empty"):
                command.downgrade(migration_config, "0013")
            assert "purchase_requests" in inspect(conn).get_table_names()
            conn.execute(text("DELETE FROM contract_request_policies"))
            command.downgrade(migration_config, "0013")
            assert "purchase_requests" not in inspect(conn).get_table_names()
            command.upgrade(migration_config, "head")
        with db_runtime.connect() as conn:
            assert conn.execute(
                text(
                    "SELECT has_table_privilege(current_user,'purchase_request_events','INSERT')"
                )
            ).scalar_one()
            assert not conn.execute(
                text(
                    "SELECT has_table_privilege(current_user,'purchase_request_events','UPDATE')"
                )
            ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)


def test_partner_identity_migration_runtime_permissions(
    db_owner, db_runtime, migration_config
):
    partner_tables = {
        "partner_organizations",
        "partner_memberships",
        "partner_membership_permissions",
    }
    with db_runtime.connect() as conn:
        assert partner_tables <= set(inspect(conn).get_table_names()), (
            "Partner identity migration is missing"
        )
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0015")
            assert not partner_tables & set(inspect(conn).get_table_names())
            command.upgrade(migration_config, "0016")
            assert partner_tables <= set(inspect(conn).get_table_names())
        with db_runtime.connect() as conn:
            for table in sorted(partner_tables):
                for privilege in ("SELECT", "INSERT", "UPDATE"):
                    assert conn.execute(
                        text(
                            "SELECT has_table_privilege(current_user,:table,:privilege)"
                        ),
                        {"table": table, "privilege": privilege},
                    ).scalar_one()
                assert not conn.execute(
                    text("SELECT has_table_privilege(current_user,:table,'DELETE')"),
                    {"table": table},
                ).scalar_one()
            assert not conn.execute(
                text("SELECT has_schema_privilege(current_user,'public','CREATE')")
            ).scalar_one()
        for table in sorted(partner_tables):
            with pytest.raises(ProgrammingError) as error, db_runtime.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN forbidden INTEGER"))
            assert error.value.orig.sqlstate == "42501"
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_partner_identity_migration_rejects_unsafe_runtime_before_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    with db_runtime.connect() as conn:
        assert "partner_organizations" in inspect(conn).get_table_names(), (
            "Partner identity migration is missing"
        )
    good_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0015")
            bad_role = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            migration_config.attributes["runtime_role"] = bad_role
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0016")
            assert "partner_organizations" not in inspect(conn).get_table_names()
            migration_config.attributes["runtime_role"] = good_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role


def test_partner_receipt_migration_roundtrip_constraints_and_privileges(
    db_owner, db_runtime, migration_config
):
    from sqlalchemy import inspect

    from alembic import command

    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0017")
            assert "partner_lifecycle_receipts" not in inspect(conn).get_table_names()
            command.upgrade(migration_config, "0018")
            inspector = inspect(conn)
            assert {
                fk["referred_table"]
                for fk in inspector.get_foreign_keys("partner_lifecycle_receipts")
            } == {"users", "auth_sessions"}
            assert {
                c["name"]
                for c in inspector.get_check_constraints("partner_lifecycle_receipts")
            } == {
                "ck_partner_lifecycle_receipt_digest",
                "ck_partner_lifecycle_receipt_response",
                "ck_partner_lifecycle_receipt_body",
            }
            assert conn.scalar(
                text(
                    "SELECT indnullsnotdistinct FROM pg_index WHERE indexrelid='uq_partner_lifecycle_receipt_key'::regclass"
                )
            )
            assert (
                conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_trigger WHERE tgrelid='partner_lifecycle_receipts'::regclass AND NOT tgisinternal"
                    )
                )
                == 1
            )
        with db_runtime.connect() as conn:
            for privilege in ("SELECT", "INSERT"):
                assert conn.scalar(
                    text(
                        "SELECT has_table_privilege(current_user,'partner_lifecycle_receipts',:privilege)"
                    ),
                    {"privilege": privilege},
                )
            for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
                assert not conn.scalar(
                    text(
                        "SELECT has_table_privilege(current_user,'partner_lifecycle_receipts',:privilege)"
                    ),
                    {"privilege": privilege},
                )
    finally:
        migration_config.attributes.pop("connection", None)


def test_partner_receipt_downgrade_preserves_original_replay(
    admin, db_owner, db_runtime, migration_config
):
    from tests.test_partner_availability import ORG, headers

    key = headers()
    payload = {"name": "Durable external", "category": "OTHER"}
    first = admin.post(ORG, json=payload, headers=key)
    assert first.status_code == 201, first.text
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            before = conn.execute(
                text("SELECT * FROM partner_lifecycle_receipts")
            ).all()
            with pytest.raises(RuntimeError, match="receipt evidence must be empty"):
                command.downgrade(migration_config, "0017")
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version")) == "0018"
            )
            assert (
                conn.execute(text("SELECT * FROM partner_lifecycle_receipts")).all()
                == before
            )
            assert (
                conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_trigger WHERE tgrelid='partner_lifecycle_receipts'::regclass AND NOT tgisinternal"
                    )
                )
                == 1
            )
        replay = admin.post(ORG, json=payload, headers=key)
        assert replay.status_code == first.status_code
        assert replay.json() == first.json()
        with db_runtime.connect() as conn:
            for table in (
                "partner_organizations",
                "partner_lifecycle_receipts",
                "audit_events",
            ):
                assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 1
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("evidence", ["organization", "membership", "permission"])
def test_partner_identity_downgrade_refuses_populated_evidence(
    db_owner, db_runtime, migration_config, auth_users, evidence
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0016")
            org = conn.scalar(
                text(
                    "INSERT INTO partner_organizations(name,category) VALUES ('Durable','OTHER') RETURNING id"
                )
            )
            if evidence != "organization":
                member = conn.scalar(
                    text(
                        "INSERT INTO partner_memberships(organization_id,user_id) VALUES (:org,:user) RETURNING id"
                    ),
                    {"org": org, "user": auth_users["member_user"]},
                )
                if evidence == "permission":
                    conn.execute(
                        text(
                            "INSERT INTO partner_membership_permissions(organization_id,membership_id,code,active) VALUES (:org,:member,'partner.processes.read',false)"
                        ),
                        {"org": org, "member": member},
                    )
            tables = (
                "partner_organizations",
                "partner_memberships",
                "partner_membership_permissions",
            )
            before = {
                table: conn.execute(text(f"SELECT * FROM {table}")).all()
                for table in tables
            }
            expected_table = {
                "organization": "partner_organizations",
                "membership": "partner_memberships",
                "permission": "partner_membership_permissions",
            }[evidence]
            with pytest.raises(
                RuntimeError, match=f"identity evidence must be empty.*{expected_table}"
            ):
                command.downgrade(migration_config, "0015")
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version")) == "0016"
            )
            assert {
                table: conn.execute(text(f"SELECT * FROM {table}")).all()
                for table in tables
            } == before
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("binding", ["partner", "issuer"])
@pytest.mark.parametrize("state", ["pending", "consumed", "invalidated"])
def test_partner_token_downgrade_refuses_binding_history(
    db_owner, db_runtime, migration_config, auth_users, partner_case, binding, state
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0017")
            conn.execute(
                text(
                    "INSERT INTO security_tokens(token_hash,purpose,recipient_user_id,recipient_email,issuer_role,issuer_user_id,partner_membership_id,created_at,expires_at,consumed_at,invalidated_at) VALUES (repeat('a',64),'INVITE',:recipient,'partner@example.test','PLATFORM_ADMIN',:issuer,:member,now(),now()+interval '1 hour',CASE WHEN :state='consumed' THEN now() END,CASE WHEN :state='invalidated' THEN now() END)"
                ),
                {
                    "recipient": partner_case["user"],
                    "issuer": auth_users["admin_user"],
                    "member": partner_case["membership"]
                    if binding == "partner"
                    else None,
                    "state": state,
                },
            )
            before = conn.execute(text("SELECT * FROM security_tokens")).all()
            with pytest.raises(
                RuntimeError, match="invitation binding evidence must be empty"
            ):
                command.downgrade(migration_config, "0016")
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version")) == "0017"
            )
            assert conn.execute(text("SELECT * FROM security_tokens")).all() == before
            assert {"fk_security_partner_membership", "fk_security_issuer_user"} <= {
                fk["name"] for fk in inspect(conn).get_foreign_keys("security_tokens")
            }
            assert "ck_security_invitation_target" in {
                check["name"]
                for check in inspect(conn).get_check_constraints("security_tokens")
            }
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize(
    "revision,target,tables",
    [
        ("0018", "0017", ("partner_lifecycle_receipts",)),
        ("0017", "0016", ("security_tokens",)),
        (
            "0016",
            "0015",
            (
                "partner_organizations",
                "partner_memberships",
                "partner_membership_permissions",
            ),
        ),
    ],
)
def test_partner_downgrade_serializes_writers_before_evidence_check(
    db_owner, db_runtime, migration_config, revision, target, tables
):
    from sqlalchemy import event
    from sqlalchemy.exc import DBAPIError

    checked = set()
    advisory_order = []

    def before_check(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT pg_advisory_xact_lock("):
            advisory_order.append(int(statement.split("(", 1)[1].split(")", 1)[0]))
        if statement.startswith("LOCK TABLE "):
            assert advisory_order == [720260925, 720260922]
            with db_owner.begin() as contender:
                for key in advisory_order:
                    assert not contender.scalar(
                        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
                    )
        if not statement.startswith("SELECT EXISTS(SELECT 1 FROM "):
            return
        table = statement.split("FROM ", 1)[1].split(")", 1)[0].split()[0]
        if table not in tables:
            return
        for protected in tables:
            assert conn.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() "
                    "AND relation=to_regclass(:table) AND mode='AccessExclusiveLock' AND granted)"
                ),
                {"table": protected},
            )
            with pytest.raises(DBAPIError) as blocked, db_owner.begin() as writer:
                writer.execute(text("SET LOCAL lock_timeout='50ms'"))
                writer.execute(text(f"INSERT INTO {protected} DEFAULT VALUES"))
            assert blocked.value.orig.sqlstate == "55P03"
        checked.add(table)

    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, revision)
            event.listen(conn, "before_cursor_execute", before_check)
            try:
                command.downgrade(migration_config, target)
            finally:
                event.remove(conn, "before_cursor_execute", before_check)
            assert checked == set(tables)
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
