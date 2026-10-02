import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command

TABLES = {"organization_nodes", "contract_modules", "membership_unit_scopes"}


def test_phase7_tables_and_model_columns(db_runtime):
    from app.db.models import Base

    inspector = inspect(db_runtime)
    assert TABLES <= set(inspector.get_table_names())
    for table in TABLES:
        assert set(Base.metadata.tables[table].columns.keys()) == {
            v["name"] for v in inspector.get_columns(table)
        }


@pytest.mark.parametrize("table", sorted(TABLES))
@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_phase7_runtime_never_deletes(db_runtime, table, verb):
    with pytest.raises(DBAPIError) as failure, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} {table}"))
    assert failure.value.orig.sqlstate == "42501"


def test_phase7_incremental_upgrade_downgrade_upgrade(
    db_owner, db_runtime, migration_config
):
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0005")
            assert not TABLES & set(inspect(conn).get_table_names())
            command.upgrade(migration_config, "head")
            assert TABLES <= set(inspect(conn).get_table_names())
        with db_runtime.connect() as conn:
            for table in TABLES:
                for verb in ["SELECT", "INSERT", "UPDATE"]:
                    assert conn.execute(
                        text("SELECT has_table_privilege(current_user,:table,:verb)"),
                        {"table": table, "verb": verb},
                    ).scalar_one()
                for verb in ["DELETE", "TRUNCATE"]:
                    assert not conn.execute(
                        text("SELECT has_table_privilege(current_user,:table,:verb)"),
                        {"table": table, "verb": verb},
                    ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_phase7_guard_precedes_ddl(db_owner, db_runtime, migration_config, unsafe):
    good = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0005")
            bad = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            migration_config.attributes["runtime_role"] = bad
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0006")
            assert not TABLES & set(inspect(conn).get_table_names())
            migration_config.attributes["runtime_role"] = good
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good


@pytest.mark.parametrize(
    "case",
    [
        "project",
        "self",
        "contract",
        "parent",
        "code",
        "module",
        "module_active",
        "scope_member",
        "scope_node",
    ],
)
def test_phase7_database_constraints(db_runtime, scope_ids, case):
    from uuid import uuid4

    node = uuid4()
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code) VALUES(:id,:tenant,:contract,'UNIT','Unit','UNIT_A')"
            ),
            {
                "id": node,
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a"],
            },
        )
    args = {
        "id": uuid4(),
        "tenant": scope_ids["tenant_a"],
        "contract": scope_ids["contract_a"],
        "parent": node,
        "member": scope_ids["member_a"],
    }
    expected = "23514"
    if case == "project":
        sql = "INSERT INTO organization_nodes(tenant_id,contract_id,kind,name,code) VALUES(:tenant,:contract,'PROJECT','Bad','BAD')"
    elif case == "self":
        sql = "UPDATE organization_nodes SET parent_id=id WHERE id=:parent"
    elif case == "contract":
        args["contract"] = scope_ids["contract_b"]
        sql = "INSERT INTO organization_nodes(tenant_id,contract_id,kind,name,code) VALUES(:tenant,:contract,'UNIT','Bad','BAD')"
        expected = "23503"
    elif case == "parent":
        args["contract"] = scope_ids["contract_a2"]
        sql = "INSERT INTO organization_nodes(tenant_id,contract_id,parent_id,kind,name,code) VALUES(:tenant,:contract,:parent,'UNIT','Bad','BAD')"
        expected = "23503"
    elif case == "code":
        sql = "INSERT INTO organization_nodes(tenant_id,contract_id,kind,name,code) VALUES(:tenant,:contract,'UNIT','Bad','UNIT_A')"
        expected = "23505"
    elif case in {"module", "module_active"}:
        sql = (
            "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'UNKNOWN',false,false)"
            if case == "module"
            else "INSERT INTO contract_modules(tenant_id,contract_id,code,contracted,active) VALUES(:tenant,:contract,'FINANCE',false,true)"
        )
    else:
        if case == "scope_member":
            args["member"] = scope_ids["member_a2"]
        else:
            args["contract"] = scope_ids["contract_a2"]
            args["member"] = scope_ids["member_a2"]
        sql = "INSERT INTO membership_unit_scopes(tenant_id,contract_id,membership_id,node_id,active) VALUES(:tenant,:contract,:member,:parent,true)"
        expected = "23503"
    with pytest.raises(IntegrityError) as failure, db_runtime.begin() as conn:
        conn.execute(text(sql), args)
    assert failure.value.orig.sqlstate == expected
