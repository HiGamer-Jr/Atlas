from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)
    app_name: str = "Atlas API"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://atlas:atlas@localhost:5433/atlas", repr=False
    )
    context_seconds: int = Field(default=3600, ge=60, le=28800)
    public_origin: str = "https://localhost:5173"
    trusted_proxy_ips: list[str] = Field(default_factory=list)
    session_idle_seconds: int = Field(default=1800, ge=60, le=1800)
    session_absolute_seconds: int = Field(default=28800, ge=300, le=28800)
    preauth_seconds: int = Field(default=600, ge=60, le=600)
    auth_window_seconds: int = Field(default=900, ge=60)
    auth_identifier_limit: int = Field(default=10, ge=1)
    auth_source_limit: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def validate_security(self):
        origin = urlsplit(self.public_origin)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username
            or origin.password
        ):
            raise ValueError(
                "PUBLIC_ORIGIN must be an explicit HTTPS origin without path"
            )
        if self.environment.lower() == "production":
            try:
                url = make_url(self.database_url)
                if (
                    url.drivername != "postgresql+psycopg"
                    or not url.password
                    or url.password in {"atlas", "password", "postgres"}
                ):
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(
                    "Production requires explicit non-default database credentials"
                ) from None
        return self


class MigrationSettings(BaseSettings):
    """Only the migration process reads owner credentials."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)
    migration_database_url: str = Field(repr=False)
    database_runtime_role: str
