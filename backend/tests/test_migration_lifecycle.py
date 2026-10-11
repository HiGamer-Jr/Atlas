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
