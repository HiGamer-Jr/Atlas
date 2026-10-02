import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from tests.test_support_sessions import start


def test_support_incremental_upgrade_downgrade_upgrade_and_explicit_runtime_grants(
    db_owner, db_runtime, migration_config
):
    from app.db.models import Base

    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0006")
            assert "support_sessions" not in inspect(conn).get_table_names()
            command.upgrade(migration_config, "0007")
            assert set(Base.metadata.tables["support_sessions"].columns.keys()) == {
                column["name"]
                for column in inspect(conn).get_columns("support_sessions")
            }
        with db_runtime.connect() as conn:
            for verb in ["SELECT", "INSERT", "UPDATE"]:
                assert conn.execute(
                    text(
                        "SELECT has_table_privilege(current_user,'support_sessions',:verb)"
                    ),
                    {"verb": verb},
                ).scalar_one()
            for verb in ["DELETE", "TRUNCATE"]:
                assert not conn.execute(
                    text(
                        "SELECT has_table_privilege(current_user,'support_sessions',:verb)"
                    ),
                    {"verb": verb},
                ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_support_owner_guard_precedes_any_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    good = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0006")
            migration_config.attributes["runtime_role"] = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0007")
            assert "support_sessions" not in inspect(conn).get_table_names()
            migration_config.attributes["runtime_role"] = good
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good


@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_runtime_cannot_destroy_support_sessions(db_runtime, verb):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} support_sessions"))
    assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize(
    "case,state",
    [
        ("mode", "23514"),
        ("target_scope", "23503"),
        ("target_user", "23503"),
        ("operator_session", "23503"),
        ("parent_scope", "23503"),
        ("derived_scope", "23503"),
        ("self_context", "23514"),
        ("terminal", "23514"),
        ("active_duplicate", "23505"),
    ],
)
def test_support_composite_binding_and_mode_constraints(
    support, scope_ids, db_runtime, case, state
):
    from tests.helpers import CONTEXT_HEADER

    parent, response = start(support, scope_ids)
    assert response.status_code == 201
    value = response.json()
    changes = {
        "mode": ("mode='MAINTENANCE'", {}),
        "target_scope": (
            "viewed_membership_id=:other",
            {"other": scope_ids["member_a2"]},
        ),
        "target_user": ("viewed_user_id=:other", {"other": scope_ids["other_user"]}),
        "operator_session": ("operator_id=:other", {"other": scope_ids["admin_user"]}),
        "parent_scope": (
            "parent_context_id=:other",
            {"other": scope_ids["contract_b"]},
        ),
        "derived_scope": ("context_id=:other", {"other": scope_ids["contract_a2"]}),
        "self_context": ("context_id=parent_context_id", {}),
        "terminal": ("status='ENDED'", {}),
    }
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        if case == "active_duplicate":
            conn.execute(
                text(
                    "INSERT INTO access_contexts(session_id,actor_id,tenant_id,contract_id,created_at,expires_at) SELECT operator_session_id,operator_id,tenant_id,contract_id,started_at,expires_at FROM support_sessions WHERE id=:id RETURNING id"
                ),
                {"id": value["id"]},
            )
            conn.execute(
                text(
                    "INSERT INTO support_sessions(operator_id,operator_session_id,operator_role,tenant_id,contract_id,parent_context_id,context_id,viewed_membership_id,viewed_user_id,mode,reason,started_at,expires_at,status) SELECT operator_id,operator_session_id,operator_role,tenant_id,contract_id,parent_context_id,(SELECT id FROM access_contexts WHERE id NOT IN (SELECT context_id FROM support_sessions) AND id<>:parent LIMIT 1),viewed_membership_id,viewed_user_id,mode,reason,started_at,expires_at,status FROM support_sessions WHERE id=:id"
                ),
                {"id": value["id"], "parent": parent[CONTEXT_HEADER]},
            )
        else:
            change, params = changes[case]
            conn.execute(
                text(f"UPDATE support_sessions SET {change} WHERE id=:id"),
                {"id": value["id"], **params},
            )
    assert error.value.orig.sqlstate == state
