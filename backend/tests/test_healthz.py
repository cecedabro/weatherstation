"""Tests for the skeleton app."""

from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    """SPEC 1.2: GET /healthz returns HTTP 200 and {"status": "ok"}."""
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
