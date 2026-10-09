import pytest
from sqlalchemy import inspect, text

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
