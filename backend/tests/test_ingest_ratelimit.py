"""Rate limiting for POST /api/v1/readings — SPEC 3.8.

Tests verify:
- RateLimiter class exists with injectable clock
- get_limiter() / reset_rate_limiter() are exported
- 60 requests/minute window is enforced
- 429 response with Retry-After header
- Client isolation (per-IP sliding window)
- Rate-limited requests are NOT stored in the database
"""


from sqlalchemy import func, select

from app.ingest import RateLimiter, get_limiter, reset_rate_limiter
from app.models import Reading

AUTH = {"Authorization": "Bearer dev-token"}


def _build_readings(request_index: int) -> list[dict]:
    """Build 6 readings with unique timestamps per request so upserts create new rows."""
    return [
        {
            "node_id": f"weather-{i}",
            "node_type": "weather",
            "ts": f"2026-05-01T12:{request_index:02d}:{i:02d}Z",
            "fw": "1.0.0",
            "battery_v": None,
            "rssi_dbm": -61,
            "metrics": {
                "temp_c": 14.2 + i + request_index,
                "humidity_pct": 71,
                "pressure_hpa": 1013.4,
                "rain_mm": 0.2,
                "wind_speed_ms": 3.1,
                "wind_dir_deg": 225,
            },
        }
        for i in range(6)
    ]


# ---------- RateLimiter class ----------


def test_rate_limiter_exists():
    """SPEC 3.8: RateLimiter class exists and is importable from app.ingest."""
    assert RateLimiter is not None
    limiter = RateLimiter()
    assert hasattr(limiter, "is_allowed")


def test_rate_limiter_allows_within_limit():
    """RateLimiter.is_allowed returns True when under the per-minute limit."""
    limiter = RateLimiter()
    now = [0.0]
    limiter._now = lambda: now[0]

    for _ in range(60):
        assert limiter.is_allowed("client-a") is True


def test_rate_limiter_blocks_after_limit():
    """RateLimiter.is_allowed returns False when limit is exceeded."""
    limiter = RateLimiter()
    now = [0.0]
    limiter._now = lambda: now[0]

    for _ in range(60):
        assert limiter.is_allowed("client-a") is True

    assert limiter.is_allowed("client-a") is False


def test_rate_limiter_injectable_clock():
    """RateLimiter._now can be set to a function for deterministic tests."""
    limiter = RateLimiter()
    now = [0.0]
    limiter._now = lambda: now[0]

    for _ in range(60):
        limiter.is_allowed("client-a")

    assert limiter.is_allowed("client-a") is False

    # Advance past the window
    now[0] = 61.0
    assert limiter.is_allowed("client-a") is True


def test_rate_limiter_client_isolation():
    """Different client keys are tracked separately."""
    limiter = RateLimiter()
    now = [0.0]
    limiter._now = lambda: now[0]

    for _ in range(60):
        limiter.is_allowed("client-a")

    # client-a should be blocked
    assert limiter.is_allowed("client-a") is False
    # client-b should still be allowed
    assert limiter.is_allowed("client-b") is True


# ---------- Module-level exports ----------


def test_get_limiter_returns_singleton():
    """SPEC 3.8: get_limiter() returns the global RateLimiter instance."""
    limiter1 = get_limiter()
    limiter2 = get_limiter()
    assert limiter1 is limiter2


def test_reset_rate_limiter_clears_state():
    """SPEC 3.8: reset_rate_limiter() clears all client tracking."""
    limiter = get_limiter()
    limiter._now = lambda: 0.0

    # Fill up the limiter
    for _ in range(60):
        limiter.is_allowed("client-x")
    assert limiter.is_allowed("client-x") is False

    # Reset should clear everything
    reset_rate_limiter()
    assert limiter.is_allowed("client-x") is True


# ---------- Endpoint integration ----------


def test_endpoint_rate_limit_enforced(client, db):
    """SPEC 3.8: more than 60 requests per minute from one client returns 429."""
    reset_rate_limiter()

    # Send 60 requests
    for i in range(60):
        resp = client.post(
            "/api/v1/readings",
            json={"readings": _build_readings(i)},
            headers={**AUTH, "CF-Connecting-IP": "10.0.0.1"},
        )
        assert resp.status_code == 200, (
            f"Request {i + 1} failed with {resp.status_code}: {resp.text}"
        )

    # 61st request should be rate limited
    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(60)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.1"},
    )
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]


def test_endpoint_429_has_retry_after_header(client, db):
    """SPEC 3.8: rate-limited response includes a Retry-After header."""
    reset_rate_limiter()

    for i in range(60):
        client.post(
            "/api/v1/readings",
            json={"readings": _build_readings(i)},
            headers={**AUTH, "CF-Connecting-IP": "10.0.0.2"},
        )

    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(60)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.2"},
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"


def test_endpoint_rate_limited_requests_not_stored(client, db):
    """SPEC 3.8: rate-limited requests are NOT stored in the database."""
    reset_rate_limiter()

    # Send 60 requests (should all be stored)
    for i in range(60):
        client.post(
            "/api/v1/readings",
            json={"readings": _build_readings(i)},
            headers={**AUTH, "CF-Connecting-IP": "10.0.0.3"},
        )

    # 61st request should be rejected and NOT stored
    client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(60)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.3"},
    )

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 2160


def test_endpoint_different_clients_independent(client, db):
    """SPEC 3.8: different client IPs have independent rate limits."""
    reset_rate_limiter()

    # Fill up client-a
    for i in range(60):
        client.post(
            "/api/v1/readings",
            json={"readings": _build_readings(i)},
            headers={**AUTH, "CF-Connecting-IP": "10.0.0.10"},
        )

    # client-a should be blocked
    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(60)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.10"},
    )
    assert resp.status_code == 429

    # client-b should still work
    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(0)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.11"},
    )
    assert resp.status_code == 200


def test_endpoint_without_cf_header_uses_client_host(client, db):
    """SPEC 3.8: when CF-Connecting-IP is absent, request.client.host is used."""
    reset_rate_limiter()

    # First request without CF-Connecting-IP uses the test client host
    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(0)},
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_endpoint_rate_limit_429_stores_nothing(client, db):
    """SPEC 3.8: a 429 response stores zero rows (the rejected batch is discarded)."""
    reset_rate_limiter()

    # Fill up exactly at the limit
    for i in range(60):
        client.post(
            "/api/v1/readings",
            json={"readings": _build_readings(i)},
            headers={**AUTH, "CF-Connecting-IP": "10.0.0.20"},
        )

    # Send one more that will be rejected
    resp = client.post(
        "/api/v1/readings",
        json={"readings": _build_readings(60)},
        headers={**AUTH, "CF-Connecting-IP": "10.0.0.20"},
    )
    assert resp.status_code == 429

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 2160
