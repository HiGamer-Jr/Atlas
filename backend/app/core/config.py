from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)
    app_name: str = "Atlas API"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://atlas:atlas@localhost:5433/atlas", repr=False
    )


class MigrationSettings(BaseSettings):
    """Only the migration process reads owner credentials."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)
    migration_database_url: str = Field(repr=False)
    database_runtime_role: str
