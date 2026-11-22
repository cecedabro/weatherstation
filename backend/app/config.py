"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings

_DEV_INGEST_TOKEN = "dev-token"
_DEV_ADMIN_PASSWORD = "admin"
_DEV_SESSION_SECRET = "dev-session-secret"


class Settings(BaseSettings):
    """Application settings, all read from env with safe defaults."""

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://weather:weather@localhost:5432/weather"
    INGEST_TOKEN: str = _DEV_INGEST_TOKEN
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = _DEV_ADMIN_PASSWORD
    LOG_LEVEL: str = "INFO"
    SESSION_SECRET: str = _DEV_SESSION_SECRET
    SESSION_DAYS: int = 30
    # Local LLM through the agent gateway (OpenAI-compatible /v1). Empty = advisor off.
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "coder"
    # Where uploaded photos go (species finds). Must be writable; a volume in production.
    # Add the common-species catalogue (app/data/common_species.json) on startup. Tests turn it off.
    SEED_CATALOGUE: bool = True
    MEDIA_DIR: str = "/tmp/garden-media"  # nosec B108: only writable path in the read-only image
