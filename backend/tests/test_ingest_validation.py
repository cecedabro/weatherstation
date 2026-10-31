"""Ingest validation tests per SPEC 3.2 and SPEC 3.3."""

import copy

from sqlalchemy import func, select

from app.models import Reading

# Reusable valid batches (copies, never mutated)
_BASE_WEATHER = {
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

_BASE_SOIL = {
    "node_id": "soil-bed-3",
    "node_type": "soil",
    "ts": "2026-05-01T12:35:10Z",
    "fw": "1.0.0",
    "battery_v": 3.92,
    "rssi_dbm": -78,
    "metrics": {
        "soil_moisture_pct": 38.5,
        "soil_temp_c": 11.0,
    },
}

AUTH = {"Authorization": "Bearer dev-token"}


# ---------- SPEC 3.2 helpers ----------

def _missing_field(base, field):
    """Return a copy of base with *field* removed."""
    b = copy.deepcopy(base)
    del b[field]
    return b


# ---------- SPEC 3.2: per-item schema rejection ----------

def test_schema_reject_missing_required_field(client, db):
    """SPEC 3.2: batch missing a required field is rejected per-item."""
    bad = _missing_field(_BASE_WEATHER, "fw")
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 1
    assert data["rejected"][0]["index"] == 0
    assert "error" in data["rejected"][0]
    assert data["rejected"][0]["error"].startswith("'fw'")

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_schema_reject_null_timestamp(client, db):
    """SPEC 3.2: batch with null timestamp fails schema validation (string type required)."""
    bad = copy.deepcopy(_BASE_WEATHER)
    bad["ts"] = None
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 1
    assert data["rejected"][0]["index"] == 0
    assert "error" in data["rejected"][0]

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_schema_reject_integer_timestamp(client, db):
    """SPEC 3.2: batch with non-string timestamp fails schema validation."""
    bad = copy.deepcopy(_BASE_WEATHER)
    bad["ts"] = 1234567890
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 1

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


# ---------- SPEC 3.2: mixed valid + invalid ----------

def test_mixed_valid_and_invalid_batches(client, db):
    """SPEC 3.2: valid batch accepted, invalid batch rejected, only valid stored."""
    bad = _missing_field(_BASE_WEATHER, "fw")
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [_BASE_WEATHER, bad, _BASE_SOIL]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 2
    assert len(data["rejected"]) == 1
    assert data["rejected"][0]["index"] == 1

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 8  # 6 weather + 2 soil


def test_all_batches_invalid(client, db):
    """SPEC 3.2: when every batch fails schema, all are rejected and nothing is stored."""
    bad1 = _missing_field(_BASE_WEATHER, "fw")
    bad2 = copy.deepcopy(_BASE_WEATHER)
    bad2["ts"] = None
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad1, bad2]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 2
    indices = {r["index"] for r in data["rejected"]}
    assert indices == {0, 1}

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


# ---------- SPEC 3.3: node_type / metric mismatch ----------

def test_reject_soil_metric_on_weather_node(client, db):
    """SPEC 3.3: a weather node sending soil metrics is rejected."""
    bad = copy.deepcopy(_BASE_WEATHER)
    bad["metrics"]["soil_moisture_pct"] = 45.0
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 1
    assert data["rejected"][0]["index"] == 0
    assert "error" in data["rejected"][0]
    assert "soil_moisture_pct" in data["rejected"][0]["error"]

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_reject_weather_metric_on_soil_node(client, db):
    """SPEC 3.3: a soil node sending weather metrics is rejected."""
    bad = copy.deepcopy(_BASE_SOIL)
    bad["metrics"]["temp_c"] = 20.0
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 0
    assert len(data["rejected"]) == 1

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 0


def test_mixed_valid_and_type_mismatch(client, db):
    """SPEC 3.3: valid soil batch accepted alongside invalid weather-on-soil batch."""
    bad = copy.deepcopy(_BASE_WEATHER)
    bad["metrics"]["soil_moisture_pct"] = 45.0
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [_BASE_SOIL, bad]},
        headers=AUTH,
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["accepted"] == 1
    assert data["rejected"][0]["index"] == 1

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 2  # only soil batch stored
