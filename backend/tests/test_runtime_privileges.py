import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@pytest.mark.parametrize(
    "table", ["users", "platform_role_assignments", "tenants", "contracts"]
)
@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_runtime_cannot_destroy_business_data(db_runtime, table, verb):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} {table}"))
    assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize("table", ["audit_events", "access_events"])
@pytest.mark.parametrize(
    "statement",
    ["UPDATE {table} SET action='changed'", "DELETE FROM {table}", "TRUNCATE {table}"],
)
def test_runtime_cannot_destroy_audit(db_runtime, table, statement):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(text(statement.format(table=table)))
    assert error.value.orig.sqlstate == "42501"


def test_runtime_cannot_change_schema_or_become_owner(db_runtime, db_owner):
    commands = [
        "CREATE TABLE public.unapproved_table (id integer)",
        'SET ROLE "' + db_owner.url.username + '"',
        "SELECT * FROM alembic_version",
    ]
    for statement in commands:
        with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
            conn.execute(text(statement))
        assert error.value.orig.sqlstate == "42501"


def test_future_technical_tables_receive_no_automatic_grants(db_runtime, db_owner):
    with db_owner.begin() as conn:
        conn.execute(text("CREATE TABLE public.technical_probe (id integer)"))
    try:
        with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
            conn.execute(text("SELECT * FROM technical_probe"))
        assert error.value.orig.sqlstate == "42501"
        # Explicit lifecycle grants for a technical table can allow DELETE,
        # without relaxing any audit or business table.
        runtime = db_owner.dialect.identifier_preparer.quote_identifier(
            db_runtime.url.username
        )
        with db_owner.begin() as conn:
            conn.execute(
                text(
                    f"GRANT SELECT, INSERT, DELETE ON public.technical_probe TO {runtime}"
                )
            )
        with db_runtime.begin() as conn:
            conn.execute(text("INSERT INTO technical_probe VALUES (1)"))
            assert (
                conn.execute(
                    text("DELETE FROM technical_probe RETURNING id")
                ).scalar_one()
                == 1
            )
        with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
            conn.execute(text("TRUNCATE technical_probe"))
        assert error.value.orig.sqlstate == "42501"
    finally:
        with db_owner.begin() as conn:
            conn.execute(text("DROP TABLE public.technical_probe"))
