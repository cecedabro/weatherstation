"""Ingest auth and malformed envelope tests per SPEC 3.4–3.5."""

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


# ---------- SPEC 3.4: bearer token authentication ----------

def test_missing_authorization_header(client, db):
    """SPEC 3.4: missing Authorization header returns 401."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
    )
    assert resp.status_code == 401

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_empty_authorization_header(client, db):
    """SPEC 3.4: empty Authorization header returns 401."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_wrong_bearer_token(client, db):
    """SPEC 3.4: wrong bearer token returns 401."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_valid_token_succeeds(client, db):
    """SPEC 3.4: valid bearer token allows ingestion."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["rejected"] == []

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 6


def test_auth_checked_before_body_validation(client, db):
    """SPEC 3.4: auth failure returns 401 even with a malformed body."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [WEATHER_READINGS]},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


# ---------- SPEC 3.5: malformed envelope ----------

def test_non_json_body(client, db):
    """SPEC 3.5: non-JSON body returns 400."""
    resp = client.post(
        "/api/v1/readings",
        data="not json at all",
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_no_readings_key(client, db):
    """SPEC 3.5: JSON body without 'readings' key returns 400."""
    resp = client.post(
        "/api/v1/readings",
        json={"nodes": ["weather-main"]},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_readings_not_an_array(client, db):
    """SPEC 3.5: 'readings' key present but not an array returns 400."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": "not-an-array"},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_empty_readings_array(client, db):
    """SPEC 3.5: empty readings array is accepted (no batches to process)."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": []},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 0
    assert data["rejected"] == []

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_malformed_body_does_not_store(client, db):
    """SPEC 3.5: malformed envelope does not store any data."""
    resp = client.post(
        "/api/v1/readings",
        data="bad data",
        headers=AUTH,
    )
    assert resp.status_code == 400

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0
