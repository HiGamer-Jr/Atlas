from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)
    app_name: str = "Atlas API"
    api_prefix: str = "/api"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    demo_enabled: bool = False
    email_delivery_enabled: bool | None = None
    database_url: str = Field(
        default="postgresql+psycopg://atlas:atlas@localhost:5433/atlas", repr=False
    )
    grant_seconds: int = Field(default=1800, ge=60, le=1800)
    support_session_seconds: int = Field(default=1800, ge=60, le=1800)
    context_seconds: int = Field(default=3600, ge=60, le=28800)
    public_origin: str = "https://localhost:5173"
    trusted_proxy_ips: list[str] = Field(default_factory=list)
    session_idle_seconds: int = Field(default=1800, ge=60, le=1800)
    session_absolute_seconds: int = Field(default=28800, ge=300, le=28800)
    preauth_seconds: int = Field(default=600, ge=60, le=600)
    auth_window_seconds: int = Field(default=900, ge=60)
    auth_identifier_limit: int = Field(default=10, ge=1)
    auth_source_limit: int = Field(default=100, ge=1)

    invite_seconds: int = Field(default=86400, ge=60)
    password_reset_seconds: int = Field(default=1800, ge=60)
    password_min_length: int = Field(default=12, ge=8)
    password_max_length: int = Field(default=1024, ge=64, le=1024)
    reauthentication_seconds: int = Field(default=300, ge=30, le=900)
    outbox_key: SecretStr | None = Field(default=None, repr=False)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = Field(default=None, repr=False)
    smtp_sender: str | None = None
    smtp_timeout_seconds: int = Field(default=15, ge=1, le=60)
    email_max_attempts: int = Field(default=5, ge=1, le=10)
    email_retry_seconds: int = Field(default=60, ge=1, le=3600)
    email_retry_max_seconds: int = Field(default=3600, ge=1, le=86400)
    email_lease_seconds: int = Field(default=120, ge=90, le=3600)
    recovery_response_floor_seconds: float = Field(default=0.25, ge=0.1, le=2)
    access_request_limit: int = Field(default=5, ge=1)
    access_source_limit: int = Field(default=100, ge=1)
    access_window_seconds: int = Field(default=900, ge=60)

    @model_validator(mode="after")
    def validate_security(self):
        if self.password_max_length < self.password_min_length:
            raise ValueError("Password length configuration is invalid")
        if self.outbox_key:
            from cryptography.fernet import Fernet

            try:
                Fernet(self.outbox_key.get_secret_value().encode())
            except (ValueError, TypeError):
                raise ValueError("OUTBOX_KEY must be a valid encryption key") from None
        try:
            origin = urlsplit(self.public_origin)
            _ = origin.port
        except ValueError:
            raise ValueError("PUBLIC_ORIGIN must be a valid HTTPS origin") from None
        if (
            origin.scheme != "https"
            or not origin.hostname
            or "*" in origin.netloc
            or any(c.isspace() for c in self.public_origin)
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username
            or origin.password
        ):
            raise ValueError(
                "PUBLIC_ORIGIN must be an explicit HTTPS origin without path"
            )
        if self.environment == "production":
            if self.debug or self.demo_enabled:
                raise ValueError("Production forbids debug and demo mode")
            if not {"database_url", "public_origin"} <= self.model_fields_set:
                raise ValueError(
                    "Production requires explicit DATABASE_URL and PUBLIC_ORIGIN"
                )
            if not self.outbox_key:
                raise ValueError("Production requires OUTBOX_KEY")
            if self.email_delivery_enabled is None:
                raise ValueError("Production requires explicit EMAIL_DELIVERY_ENABLED")
            smtp = (
                self.smtp_host,
                self.smtp_sender,
                self.smtp_username,
                self.smtp_password,
            )
            if self.email_delivery_enabled:
                if (
                    not self.smtp_host
                    or not self.smtp_sender
                    or bool(self.smtp_username) != bool(self.smtp_password)
                ):
                    raise ValueError("Production requires complete SMTP configuration")
                from app.identity.mailboxes import single_mailbox

                try:
                    single_mailbox(self.smtp_sender)
                except ValueError:
                    raise ValueError(
                        "Production requires a valid SMTP sender"
                    ) from None
            elif any(smtp):
                raise ValueError("Disabled delivery requires absent SMTP configuration")
            try:
                url = make_url(self.database_url)
                if (
                    url.drivername != "postgresql+psycopg"
                    or not url.password
                    or url.password.lower()
                    in {
                        "atlas",
                        "password",
                        "postgres",
                        "change_me",
                        "changeme",
                        "secret",
                    }
                    or not url.database
                    or "test" in url.database.lower()
                    or url.username
                    in {
                        "postgres",
                        "atlas",
                        "hiatlas_owner",
                        "hiatlas_test_owner",
                        "hiatlas_test_runtime",
                    }
                ):
                    raise ValueError
            except (ValueError, TypeError, ArgumentError):
                raise ValueError(
                    "Production requires explicit non-default database credentials"
                ) from None
        return self


class MigrationSettings(BaseSettings):
    """Only the migration process reads owner credentials."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)
    migration_database_url: str = Field(repr=False)
    database_runtime_role: str
