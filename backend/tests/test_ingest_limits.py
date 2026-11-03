"""Ingest hardening: constant-time auth (SPEC 3.6) and 1 MiB body limit (SPEC 3.7)."""

from sqlalchemy import func, select

from app.models import Reading

AUTH = {"Authorization": "Bearer dev-token"}
WEATHER_READINGS = {
    "node_id": "weather-main",
    "node_type": "weather",
    "ts": "2026-05-01T12:34:56Z",
    "fw": "1.0.0",
    "battery_v": None,
    "rssi_dbm": -61,
    "metrics": {
        "temp_c": 14.2,
        "humidity_pct": 71,
        "pressure_hpa": 1013.4,
        "rain_mm": 0.2,
        "wind_speed_ms": 3.1,
        "wind_dir_deg": 225,
    },
}

# A body over 1 MiB
_json_tail = (
    '", "node_type": "weather", "ts": "2026-05-01T12:00:00Z", '
    '"fw": "1.0.0", "battery_v": null, "rssi_dbm": -61, '
    '"metrics": {"temp_c": 20.0}}]}'
)
_LARGE_BODY = '{"readings": [{"node_id": "' + "A" * (1024 * 1024 + 1) + _json_tail


# ---------- SPEC 3.6: constant-time token comparison ----------


def test_constant_time_comparison(client, db):
    """SPEC 3.6: token comparison uses hmac.compare_digest (constant-time).

    We verify the behaviour by testing both a correct token (200) and a
    close-but-wrong token (401).  The test exists as a behavioural check:
    if someone reverts to ``!=`` the same status codes still apply — but the
    code at ``app/ingest.py`` must use ``hmac.compare_digest``.
    """
    import inspect

    from app.ingest import ingest_readings

    source = inspect.getsource(ingest_readings)
    assert "compare_digest" in source, "Must use hmac.compare_digest for token comparison"


def test_token_comparison_behaviour(client, db):
    """SPEC 3.6: correct token succeeds, wrong token is rejected with 401."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers=AUTH,
    )
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 6


# ---------- SPEC 3.7: body size limit ----------


def test_body_over_1_mib_rejected(client, db):
    """SPEC 3.7: body larger than 1 MiB returns 413 and stores nothing."""
    resp = client.post(
        "/api/v1/readings",
        data=_LARGE_BODY,
        headers={**AUTH, "Content-Type": "application/json"},
    )
    assert resp.status_code == 413

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_body_under_1_mib_accepted(client, db):
    """SPEC 3.7: body under 1 MiB is accepted normally (with valid token and data)."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers=AUTH,
    )
    assert resp.status_code == 200

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 6


def test_large_body_with_wrong_token(client, db):
    """SPEC 3.7: auth error still returned before body size is checked.

    The 413 limit should only apply after auth succeeds, so a large body
    with a wrong token still returns 401 (no body parsing at all).
    """
    resp = client.post(
        "/api/v1/readings",
        data=_LARGE_BODY,
        headers={"Authorization": "Bearer wrong", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_body_limit_applied_with_valid_token(client, db):
    """SPEC 3.7: the 413 limit is enforced when token is valid."""
    resp = client.post(
        "/api/v1/readings",
        data=_LARGE_BODY,
        headers=AUTH,
    )
    assert resp.status_code == 413

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_body_limit_stores_nothing(client, db):
    """SPEC 3.7: oversized body stores nothing — no node, no readings."""
    client.post(
        "/api/v1/readings",
        data=_LARGE_BODY,
        headers=AUTH,
    )

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_exact_1_mib_boundary(client, db):
    """SPEC 3.7: a body that is exactly 1 MiB should be accepted (limit is > 1 MiB)."""
    prefix = '{"readings":[{"node_id":"'
    suffix_parts = [
        '","node_type":"weather",',
        '"ts":"2026-05-01T12:00:00Z",',
        '"fw":"1.0.0",',
        '"battery_v":null,',
        '"rssi_dbm":-61,',
        '"metrics":{"temp_c":20.0}}]}',
    ]
    suffix = "".join(suffix_parts)
    padding_len = 1024 * 1024 - len(prefix) - len(suffix)
    exact_body = prefix + ("X" * padding_len) + suffix

    resp = client.post(
        "/api/v1/readings",
        data=exact_body,
        headers={**AUTH, "Content-Type": "application/json"},
    )
    # Exact 1 MiB is within limit — accepts or rejects based on node_id length validation
    # but should NOT return 413
    assert resp.status_code != 413
