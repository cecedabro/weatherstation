"""Tests for production settings (SPEC 1.4).

SPEC 1.4: With APP_ENV=production, the app refuses to start when
INGEST_TOKEN or ADMIN_PASSWORD still has its development default.

APP_ENV defaults to development. LOG_LEVEL defaults to INFO.
"""

import logging
import os

import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _clear_env():
    """Unset APP_ENV and LOG_LEVEL so Settings gets defaults."""
    original = {
        "APP_ENV": os.environ.pop("APP_ENV", None),
        "LOG_LEVEL": os.environ.pop("LOG_LEVEL", None),
        "INGEST_TOKEN": os.environ.get("INGEST_TOKEN"),
        "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
    }
    yield
    # Restore
    for key, val in original.items():
        if val is not None:
            os.environ[key] = val
        elif key in os.environ:
            del os.environ[key]


def _make_settings(**overrides) -> Settings:
    """Build Settings with explicit env var overrides."""
    env = {}
    for k, v in overrides.items():
        env[k] = str(v)
    return Settings(_env_file=None, _env_file_encoding=None, **overrides)


def test_settings_app_env_defaults_to_development():
    """APP_ENV defaults to 'development'."""
    s = _make_settings()
    assert s.APP_ENV == "development"


def test_settings_log_level_defaults_to_info():
    """LOG_LEVEL defaults to 'INFO'."""
    s = _make_settings()
    assert s.LOG_LEVEL == "INFO"


def test_settings_can_set_production_env():
    """APP_ENV can be set to 'production'."""
    s = _make_settings(APP_ENV="production")
    assert s.APP_ENV == "production"


def test_settings_can_set_log_level():
    """LOG_LEVEL can be overridden."""
    s = _make_settings(LOG_LEVEL="DEBUG")
    assert s.LOG_LEVEL == "DEBUG"


def test_create_app_development_does_not_raise():
    """SPEC 1.4: development mode works even with default tokens."""
    # Default settings: APP_ENV=development, default INGEST_TOKEN, default ADMIN_PASSWORD
    app = create_app()
    assert app is not None


def test_create_app_production_default_ingest_token_raises():
    """SPEC 1.4: production + default INGEST_TOKEN → RuntimeError."""
    old = os.environ.get("APP_ENV")
    try:
        os.environ["APP_ENV"] = "production"
        with pytest.raises(RuntimeError) as exc_info:
            create_app()
        assert "INGEST_TOKEN" in str(exc_info.value)
        assert "development default" in str(exc_info.value)
    finally:
        if old is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old


def test_create_app_production_default_admin_password_raises():
    """SPEC 1.4: production + default ADMIN_PASSWORD → RuntimeError."""
    old_app_env = os.environ.get("APP_ENV")
    old_token = os.environ.get("INGEST_TOKEN")
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["INGEST_TOKEN"] = "a-safe-token"
        with pytest.raises(RuntimeError) as exc_info:
            create_app()
        assert "ADMIN_PASSWORD" in str(exc_info.value)
        assert "development default" in str(exc_info.value)
    finally:
        if old_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old_app_env
        if old_token is None:
            os.environ.pop("INGEST_TOKEN", None)
        else:
            os.environ["INGEST_TOKEN"] = old_token


def test_create_app_production_with_all_secrets_set():
    """SPEC 1.4: production with non-default secrets works."""
    old = {}
    for key in ("APP_ENV", "INGEST_TOKEN", "ADMIN_PASSWORD"):
        old[key] = os.environ.get(key)
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["INGEST_TOKEN"] = "production-token-abc"
        os.environ["ADMIN_PASSWORD"] = "strong-admin-password"
        app = create_app()
        assert app is not None
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_create_app_production_ingest_token_check_first():
    """The error references INGEST_TOKEN when both are default."""
    old_app_env = os.environ.get("APP_ENV")
    try:
        os.environ["APP_ENV"] = "production"
        with pytest.raises(RuntimeError) as exc_info:
            create_app()
        assert "INGEST_TOKEN" in str(exc_info.value)
    finally:
        if old_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old_app_env


def test_logging_configured_with_correct_level():
    """LOG_LEVEL is applied to the root logger."""
    old = os.environ.get("LOG_LEVEL")
    try:
        os.environ["LOG_LEVEL"] = "DEBUG"
        create_app()
        root = logging.getLogger()
        assert root.level == logging.DEBUG
    finally:
        if old is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = old
