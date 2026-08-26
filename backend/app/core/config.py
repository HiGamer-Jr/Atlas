from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Atlas API"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5433/atlas"
