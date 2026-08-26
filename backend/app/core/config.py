from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Atlas API"
    api_prefix: str = "/api"
    environment: str = "development"
