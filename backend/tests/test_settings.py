from importlib import import_module, reload

from app.core.config import Settings


def test_settings_has_atlas_defaults():
    settings = Settings()

    assert settings.app_name == "Atlas API"
    assert settings.api_prefix == "/api"
    assert settings.environment == "development"


def test_fastapi_uses_configured_app_name(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Atlas Test API")

    module = import_module("app.main")
    module = reload(module)

    assert module.app.title == "Atlas Test API"


def test_settings_reads_database_url_from_environment(monkeypatch):
    database_url = "postgresql+psycopg://atlas:test@localhost:5433/atlas"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings()

    assert settings.database_url == database_url
