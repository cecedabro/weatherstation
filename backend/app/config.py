"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings

_DEV_INGEST_TOKEN = "dev-token"
_DEV_ADMIN_PASSWORD = "admin"


class Settings(BaseSettings):
    """Application settings, all read from env with safe defaults."""

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://weather:weather@localhost:5432/weather"
    INGEST_TOKEN: str = _DEV_INGEST_TOKEN
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = _DEV_ADMIN_PASSWORD
    LOG_LEVEL: str = "INFO"
