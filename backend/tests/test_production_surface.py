from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import Settings
from app.main import create_app


def test_liveness_and_headers_are_process_only():
    application = create_app(Settings())
    with TestClient(application) as client:
        response = client.get("/api/health/live", headers={"X-Request-ID": "untrusted"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    UUID(response.headers["X-Request-ID"])
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers
    assert "Access-Control-Allow-Origin" not in response.headers


def test_readiness_failure_is_sanitized():
    application = create_app(Settings())
    application.state.database_engine.dispose()
    application.state.database_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    with TestClient(application) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    UUID(response.headers["X-Request-ID"])


def test_production_startup_rejects_unsafe_runtime_role(db_owner):
    import pytest
    from cryptography.fernet import Fernet

    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://runtime:strong-example-secret@localhost/atlas",
        public_origin="https://atlas.example",
        outbox_key=Fernet.generate_key().decode(),
        email_delivery_enabled=False,
    )
    application = create_app(settings)
    application.state.database_engine.dispose()
    application.state.database_engine = db_owner
    with (
        pytest.raises(RuntimeError, match="Production database prerequisites failed"),
        TestClient(application),
    ):
        pass


def test_readiness_checks_schema_and_runtime_role(client):
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_contains_no_test_recovery_or_secret_fields():
    application = create_app(Settings())
    schema = application.openapi()
    assert all(
        "/test-" not in path and "recover_admin" not in path for path in schema["paths"]
    )
    assert "/api/maintenance/sql" not in schema["paths"]
    schemas = str(schema.get("components", {}).get("schemas", {}))
    assert "password_hash" not in schemas
    assert "session_token" not in schemas


def test_production_startup_refuses_missing_database_prerequisites():
    import pytest
    from cryptography.fernet import Fernet

    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://runtime:strong-example-secret@localhost/atlas",
        public_origin="https://atlas.example",
        outbox_key=Fernet.generate_key().decode(),
        email_delivery_enabled=False,
    )
    application = create_app(settings)
    application.state.database_engine.dispose()
    application.state.database_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    with (
        pytest.raises(RuntimeError, match="Production database prerequisites failed"),
        TestClient(application),
    ):
        pass


def test_internal_failure_preserves_safe_request_identity(caplog, monkeypatch):
    import logging

    # Alembic fileConfig disables existing loggers in the shared test interpreter.
    # The API starts separately in production; restore this harness state locally.
    monkeypatch.setattr(logging.getLogger("app.requests"), "disabled", False)
    caplog.set_level(logging.ERROR, logger="app.requests")
    application = create_app(Settings())
    sentinel = "private-sentinel-for-error-sanitization"

    @application.get("/failure-probe", include_in_schema=False)
    def failing_endpoint():
        raise RuntimeError(sentinel)

    with TestClient(application) as client:
        response = client.get("/failure-probe")
    assert response.status_code == 500
    assert sentinel not in response.text
    assert sentinel not in caplog.text
    assert response.headers["X-Request-ID"] in caplog.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_hsts_only_for_production_https_configuration():
    from cryptography.fernet import Fernet

    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://runtime:strong-example-secret@localhost/atlas",
        public_origin="https://atlas.example",
        outbox_key=Fernet.generate_key().decode(),
        email_delivery_enabled=False,
    )
    application = create_app(settings)
    # A direct request isolates header behavior; lifespan checks are covered separately.
    response = TestClient(application).get("/api/health/live")
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
    application.state.database_engine.dispose()


def test_production_runtime_startup_and_readiness(db_runtime):
    from cryptography.fernet import Fernet
    from sqlalchemy import text

    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://runtime:strong-example-secret@localhost/atlas",
        public_origin="https://atlas.example",
        outbox_key=Fernet.generate_key().decode(),
        email_delivery_enabled=False,
    )
    application = create_app(settings)
    application.state.database_engine.dispose()
    application.state.database_engine = db_runtime
    with TestClient(application) as client:
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert application.debug is False
        assert application.state.email_transport.available is False
        schema = client.get("/openapi.json").json()
        assert all(
            "/test-" not in path and "recover_admin" not in path
            for path in schema["paths"]
        )
        with db_runtime.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
            )


def test_health_probes_ignore_browser_credentials():
    application = create_app(Settings())
    application.state.database_engine.dispose()
    application.state.database_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    with TestClient(application) as client:
        headers = {
            "Cookie": "__Host-hiatlas-session=untrusted",
            "X-HiAtlas-Context": "untrusted",
        }
        live = client.get("/api/health/live", headers=headers)
        ready = client.get("/api/health/ready", headers=headers)
    assert live.status_code == 200
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}


def test_readiness_rejects_incomplete_foundation_schema(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool

    from app.api import router
    from app.db.base import Base

    application = create_app(Settings())
    application.state.database_engine.dispose()
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    application.state.database_engine = engine
    with engine.begin() as connection:
        for name in Base.metadata.tables:
            if name != "processing_runs":
                connection.execute(text(f"CREATE TABLE {name} (id INTEGER)"))
    # The PostgreSQL role query cannot execute in SQLite; isolate schema readiness.
    monkeypatch.setattr(router, "validate_runtime_connection", lambda connection: None)
    with TestClient(application) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_readiness_rejects_tables_missing_required_columns(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool

    from app.api import router
    from app.db.base import Base

    application = create_app(Settings())
    application.state.database_engine.dispose()
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    application.state.database_engine = engine
    with engine.begin() as connection:
        for name in Base.metadata.tables:
            connection.execute(text(f"CREATE TABLE {name} (id INTEGER)"))
    # Isolate the schema guard without consuming the shared PostgreSQL lease.
    monkeypatch.setattr(router, "validate_runtime_connection", lambda connection: None)
    with TestClient(application) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
