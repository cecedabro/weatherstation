"""Tests for health endpoint and env config (SPEC 1.2–1.3)."""

import os

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_200():
    """SPEC 1.2: GET /healthz returns HTTP 200 and {"status": "ok"}."""
    client = TestClient(create_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_healthz_no_db_access():
    """SPEC 1.3: /healthz must not touch the database."""
    os.environ["DATABASE_URL"] = "postgresql+psycopg://bad:bad@nowhere:5432/bad"
    try:
        client = TestClient(create_app())
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        del os.environ["DATABASE_URL"]


def test_config_defaults():
    """SPEC 1.3: Settings has safe local defaults."""
    from app.config import Settings

    s = Settings()
    assert s.DATABASE_URL == "postgresql+psycopg://weather:weather@localhost:5432/weather"
    assert s.INGEST_TOKEN == "dev-token"
    assert s.ADMIN_USER == "admin"
    assert s.ADMIN_PASSWORD == "admin"


def test_config_env_overrides():
    """SPEC 1.3: Settings reads env vars over defaults."""
    token = os.environ.get("INGEST_TOKEN")
    user = os.environ.get("ADMIN_USER")
    password = os.environ.get("ADMIN_PASSWORD")

    os.environ["DATABASE_URL"] = "postgresql+psycopg://custom:pass@db:5432/db"
    os.environ["INGEST_TOKEN"] = "real-token"
    os.environ["ADMIN_USER"] = "root"
    os.environ["ADMIN_PASSWORD"] = "secret"

    try:
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.DATABASE_URL == "postgresql+psycopg://custom:pass@db:5432/db"
        assert s.INGEST_TOKEN == "real-token"
        assert s.ADMIN_USER == "root"
        assert s.ADMIN_PASSWORD == "secret"
    finally:
        if token is None:
            os.environ.pop("INGEST_TOKEN", None)
        else:
            os.environ["INGEST_TOKEN"] = token
        if user is None:
            os.environ.pop("ADMIN_USER", None)
        else:
            os.environ["ADMIN_USER"] = user
        if password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = password
        os.environ.pop("DATABASE_URL", None)
