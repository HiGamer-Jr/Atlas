import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from tests.helpers import CONTEXT_HEADER, select_context
from tests.test_grants import register_controlled_action, start


def test_grant_incremental_upgrade_downgrade_upgrade_and_minimal_grants(
    db_owner, db_runtime, migration_config
):
    from app.db.models import Base

    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0007")
            assert "temporary_privileged_grants" not in inspect(conn).get_table_names()
            command.upgrade(migration_config, "0008")
            for table in ("temporary_privileged_grants", "maintenance_grant_scopes"):
                assert set(Base.metadata.tables[table].columns.keys()) == {
                    col["name"] for col in inspect(conn).get_columns(table)
                }
        with db_runtime.connect() as conn:
            for table in ("temporary_privileged_grants", "maintenance_grant_scopes"):
                for verb in ("SELECT", "INSERT", "UPDATE"):
                    assert conn.execute(
                        text("SELECT has_table_privilege(current_user,:table,:verb)"),
                        {"table": table, "verb": verb},
                    ).scalar_one()
                for verb in ("DELETE", "TRUNCATE"):
                    assert not conn.execute(
                        text("SELECT has_table_privilege(current_user,:table,:verb)"),
                        {"table": table, "verb": verb},
                    ).scalar_one()
            assert conn.execute(
                text(
                    "SELECT NOT rolsuper AND rolname <> (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE relname='temporary_privileged_grants') FROM pg_roles WHERE rolname=current_user"
                )
            ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize(
    "table", ["temporary_privileged_grants", "maintenance_grant_scopes"]
)
@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_runtime_cannot_destroy_grant_tables(db_runtime, table, verb):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} {table}"))
    assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize(
    "case,state",
    [
        ("operator_role", "23514"),
        ("grant_type", "23514"),
        ("status", "23514"),
        ("terminal", "23514"),
        ("revoked", "23514"),
        ("expires", "23514"),
        ("version", "23514"),
        ("self_parent", "23514"),
        ("operator_session", "23503"),
        ("parent_context", "23503"),
        ("child_context", "23503"),
        ("tenant_contract", "23503"),
        ("active_duplicate", "23505"),
    ],
)
def test_physical_grant_types_lifecycle_and_exact_binding_constraints(
    admin, scope_ids, db_runtime, case, state
):
    other = select_context(admin, scope_ids["contract_a2"])
    _parent, response = start(admin, scope_ids)
    row = response.json()
    changes = {
        "operator_role": "operator_role='PLATFORM_SUPPORT'",
        "grant_type": "grant_type='WRITE'",
        "status": "status='UNKNOWN'",
        "terminal": "status='ENDED'",
        "revoked": "revoked_at=now()",
        "expires": "expires_at=started_at",
        "version": "version=0",
        "self_parent": "parent_context_id=context_id",
        "operator_session": "operator_id=:foreign_user",
        "parent_context": "parent_context_id=:foreign_context",
        "child_context": "context_id=:foreign_context",
        "tenant_contract": "tenant_id=:foreign_tenant",
    }
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        if case == "active_duplicate":
            conn.execute(
                text("""
                INSERT INTO temporary_privileged_grants(
                    operator_id,operator_session_id,operator_role,tenant_id,contract_id,
                    parent_context_id,context_id,grant_type,status,reason,started_at,expires_at)
                SELECT operator_id,operator_session_id,operator_role,tenant_id,contract_id,
                    parent_context_id,context_id,grant_type,status,reason,started_at,expires_at
                FROM temporary_privileged_grants WHERE id=:id
            """),
                {"id": row["id"]},
            )
        else:
            conn.execute(
                text(
                    f"UPDATE temporary_privileged_grants SET {changes[case]} WHERE id=:id"
                ),
                {
                    "id": row["id"],
                    "foreign_user": scope_ids["support_user"],
                    "foreign_context": other[CONTEXT_HEADER],
                    "foreign_tenant": scope_ids["tenant_b"],
                },
            )
    assert error.value.orig.sqlstate == state


def test_physical_maintenance_scope_foreign_entity_and_grant_contract_rejected(
    admin, scope_ids, app, db_runtime
):
    node, foreign = register_controlled_action(app, db_runtime, scope_ids)
    _, response = start(
        admin,
        scope_ids,
        grant_type="MAINTENANCE",
        reference="INC-1",
        scopes=[
            {
                "action_code": "CONTROLLED_ACTION",
                "entity_type": "organization_node",
                "entity_id": str(node),
            }
        ],
    )
    assert response.status_code == 201
    for change in ("entity_id=:foreign", "contract_id=:foreign_contract"):
        with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE maintenance_grant_scopes SET {change} WHERE grant_id=:id"
                ),
                {
                    "id": response.json()["id"],
                    "foreign": foreign,
                    "foreign_contract": scope_ids["contract_a2"],
                },
            )
        assert error.value.orig.sqlstate == "23503"


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_grant_migration_owner_guard_precedes_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    good = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0007")
            migration_config.attributes["runtime_role"] = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            with pytest.raises(RuntimeError, match="roles"):
                command.upgrade(migration_config, "0008")
            assert "temporary_privileged_grants" not in inspect(conn).get_table_names()
            migration_config.attributes["runtime_role"] = good
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good
