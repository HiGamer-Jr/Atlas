from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine


def test_database_errors_do_not_disclose_parameters(db_runtime):
    engine = create_database_engine(db_runtime.url)
    try:
        with pytest.raises(DBAPIError) as failure, engine.begin() as conn:
            conn.execute(
                text(
                    "SELECT nonexistent_column FROM (SELECT CAST(:sensitive AS text) AS value) AS sample"
                ),
                {"sensitive": "sentinel-secret"},
            )
        assert "sentinel-secret" not in str(failure.value)
    finally:
        engine.dispose()


def test_runtime_guard_rejects_migration_owner(db_owner):
    from app.db.session import validate_runtime_connection

    with db_owner.connect() as conn, pytest.raises(ValueError, match="runtime"):
        validate_runtime_connection(conn)


def test_runtime_guard_accepts_restricted_role(db_runtime):
    from app.db.session import validate_runtime_connection

    with db_runtime.connect() as conn:
        validate_runtime_connection(conn)


def test_get_db_rolls_back_when_handler_fails(db_runtime):
    from app.db.session import get_db
    from app.main import create_app

    app = create_app(
        Settings(database_url=db_runtime.url.render_as_string(hide_password=False))
    )

    @app.post("/test-rollback")
    def failing(db: Annotated[Session, Depends(get_db)]):
        db.execute(text("INSERT INTO tenants (name) VALUES ('rollback-from-request')"))
        raise RuntimeError("controlled failure")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/test-rollback").status_code == 500
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM tenants WHERE name='rollback-from-request'")
            ).scalar_one()
            == 0
        )


def test_app_factory_keeps_settings_isolated():
    from app.main import create_app

    one = create_app(Settings(app_name="First"))
    two = create_app(Settings(app_name="Second"))
    assert one.title == "First"
    assert two.title == "Second"


def test_migration_settings_never_fall_back_to_runtime(monkeypatch):
    from pydantic import ValidationError

    from app.core.config import MigrationSettings

    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://runtime:sentinel@localhost/production"
    )
    with pytest.raises(ValidationError) as error:
        MigrationSettings()
    assert "sentinel" not in str(error.value)


def test_fresh_application_registers_audit_dependencies():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ("import app.main; from app.audit.models import AuditEvent; "
            "assert AuditEvent.__mapper__._sorted_tables"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
