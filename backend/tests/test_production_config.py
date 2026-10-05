import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings


@pytest.fixture
def production_config():
    return {
        "environment": "production",
        "database_url": "postgresql+psycopg://runtime:strong-example-secret@localhost/atlas",
        "public_origin": "https://atlas.example",
        "outbox_key": Fernet.generate_key().decode(),
        "email_delivery_enabled": False,
    }


@pytest.mark.parametrize(
    "unsafe",
    [
        {"environment": "prod"},
        {"debug": True},
        {"demo_enabled": True},
        {"session_cookie_secure": False},
        {"public_origin": "https://*.example"},
        {"public_origin": "https://atlas.example:bad"},
        {"database_url": "postgresql+psycopg://runtime:CHANGE_ME@localhost/atlas"},
        {
            "database_url": "postgresql+psycopg://runtime:strong-example-secret@localhost/atlas_test"
        },
        {"outbox_key": None},
        {"email_delivery_enabled": None},
        {"smtp_host": "smtp.example"},
        {"email_delivery_enabled": True},
    ],
)
def test_production_rejects_unsafe_configuration(production_config, unsafe):
    with pytest.raises(ValidationError):
        Settings(**(production_config | unsafe))


def test_production_requires_explicit_origin(production_config, monkeypatch):
    monkeypatch.delenv("PUBLIC_ORIGIN", raising=False)
    production_config.pop("public_origin")
    with pytest.raises(ValidationError):
        Settings(**production_config)


def test_production_accepts_explicit_disabled_delivery(production_config):
    assert (
        Settings(**(production_config | {"email_delivery_enabled": False})).environment
        == "production"
    )


def test_disabled_delivery_never_exposes_smtp_as_available():
    from app.identity.email_transport import SMTPEmailTransport

    settings = Settings(
        email_delivery_enabled=False,
        smtp_host="smtp.example",
        smtp_sender="sender@example.test",
    )
    assert SMTPEmailTransport(settings).available is False


def test_production_smtp_sender_must_be_single_mailbox(production_config):
    with pytest.raises(ValidationError):
        Settings(
            **(
                production_config
                | {
                    "email_delivery_enabled": True,
                    "smtp_host": "smtp.example",
                    "smtp_sender": "invalid",
                }
            )
        )


def test_production_smtp_complete_configuration(production_config):
    settings = Settings(
        **(
            production_config
            | {
                "email_delivery_enabled": True,
                "smtp_host": "smtp.example",
                "smtp_sender": "sender@example.test",
            }
        )
    )
    assert settings.email_delivery_enabled is True


def test_production_settings_and_validation_hide_credentials(production_config):
    import pytest
    from pydantic import ValidationError

    sentinel = "private-password-sentinel"
    configuration = production_config | {
        "database_url": "postgresql+psycopg://runtime:" + sentinel + "@localhost/atlas",
        "smtp_password": sentinel,
    }
    with pytest.raises(ValidationError) as error:
        Settings(**configuration)
    assert sentinel not in str(error.value)
    assert sentinel not in repr(Settings(**production_config))


def test_production_rejects_malformed_database_url(production_config):
    with pytest.raises(ValidationError):
        Settings(**(production_config | {"database_url": "malformed-url"}))
