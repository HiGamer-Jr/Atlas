import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command


def test_processing_physical_table_is_migrated(migrated, db_owner):
    assert "processing_runs" in inspect(db_owner).get_table_names()


@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_runtime_cannot_destroy_processing_runs(db_runtime, verb):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as db:
        db.execute(text(f"{verb} processing_runs"))
    assert error.value.orig.sqlstate == "42501"


def test_processing_upgrade_downgrade_upgrade(db_owner, db_runtime, migration_config):
    try:
        with db_owner.begin() as db:
            migration_config.attributes["connection"] = db
            command.downgrade(migration_config, "0008")
            assert "processing_runs" not in inspect(db).get_table_names()
            command.upgrade(migration_config, "head")
            assert "processing_runs" in inspect(db).get_table_names()
        with db_runtime.connect() as db:
            assert db.execute(
                text(
                    "SELECT has_table_privilege(current_user,'processing_runs','SELECT,INSERT,UPDATE')"
                )
            ).scalar_one()
    finally:
        migration_config.attributes.pop("connection", None)
