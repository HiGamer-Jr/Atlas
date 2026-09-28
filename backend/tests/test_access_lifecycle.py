from app.core.config import Settings
from app.identity import passwords


def test_phase05_policy_is_central_and_allows_long_passwords():
    assert hasattr(passwords, "validate_password"), "central password policy missing"
    settings = Settings()
    passwords.validate_password("a" * 256, settings)


def test_access_lifecycle_models_exist():
    from app.identity import models

    assert hasattr(models, "SecurityToken"), "persistent token missing"
    assert hasattr(models, "EmailOutbox"), "persistent outbox missing"


def test_access_lifecycle_routes_registered():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/auth/recovery" in paths
