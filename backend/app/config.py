"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, all read from env with safe defaults."""

    DATABASE_URL: str = "postgresql+psycopg://weather:weather@localhost:5432/weather"
    INGEST_TOKEN: str = "dev-token"
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = "admin"
