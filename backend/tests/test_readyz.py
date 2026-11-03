"""Tests for /readyz endpoint (SPEC 1.5).

SPEC 1.5: GET /readyz returns 200 {"status": "ready"} when the database
answers a trivial query, and 503 {"status": "unavailable"} when it does not.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_readyz_returns_200_when_db_ok(client) -> None:
    """SPEC 1.5: GET /readyz returns HTTP 200 and {"status": "ready"}."""
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_readyz_returns_503_when_db_unavailable() -> None:
    """SPEC 1.5: GET /readyz returns 503 {"status": "unavailable"} on db error.

    Mock the database engine's connect method to raise an exception,
    simulating an unreachable database.
    """
    app = create_app()
    connect_error = Exception("database connection refused")

    with patch("app.db.engine") as mock_engine:
        mock_engine.connect.return_value.__enter__ = lambda self: (_ for _ in ()).throw(
            connect_error
        )
        mock_engine.connect.return_value.__exit__ = lambda self, *a: None

        client = TestClient(app)
        resp = client.get("/readyz")
        assert resp.status_code == 503
        assert resp.json() == {"status": "unavailable"}
