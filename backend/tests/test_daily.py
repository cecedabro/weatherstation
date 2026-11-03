"""Tests for GET /api/v1/daily per SPEC 10.6.

SPEC 10.6: `GET /api/v1/daily?node=&days=` returns one row per UTC day with
date, temp_min, temp_max, temp_avg, rain_total, humidity_avg.
days is 1-366 (default 30), otherwise 400.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading


def _now() -> datetime:
    return datetime.now(UTC)


def _insert_node_and_readings(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict[str, float],
) -> None:
    """Insert a node (if new) and metric readings at a specific timestamp."""
    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
            last_battery_v=3.8,
            last_rssi_dbm=-55,
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    for metric, value in metrics.items():
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id) & (Reading.metric == metric) & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()


def _daily_fixture(db: Session):
    """Insert fixed test data spanning two days.

    Day offset 2 (3 days before now): temp 15.0 & 18.0, humidity 55.0, rain 2.0
    Day offset 1 (yesterday):      temp 20.0 & 24.0, humidity 60.0 & 70.0, rain 5.5
    """
    now = _now()
    node_id = "weather-daily"

    # Day offset 2 -- two readings on this UTC day
    ts_d2 = now - timedelta(days=2, hours=2)  # 22 hours before now, same UTC day
    _insert_node_and_readings(
        db,
        node_id,
        "weather",
        ts_d2,
        {
            "temp_c": 15.0,
            "humidity_pct": 55.0,
            "rain_mm": 2.0,
        },
    )
    _insert_node_and_readings(
        db,
        node_id,
        "weather",
        ts_d2 + timedelta(hours=4),
        {
            "temp_c": 18.0,
        },
    )

    # Day offset 1 -- two readings on this UTC day
    ts_d1 = now - timedelta(days=1, hours=2)  # 22 hours before now, same UTC day
    _insert_node_and_readings(
        db,
        node_id,
        "weather",
        ts_d1,
        {
            "temp_c": 20.0,
            "humidity_pct": 60.0,
        },
    )
    _insert_node_and_readings(
        db,
        node_id,
        "weather",
        ts_d1 + timedelta(hours=8),
        {
            "temp_c": 24.0,
            "humidity_pct": 70.0,
            "rain_mm": 5.5,
        },
    )

    return now


def test_daily_returns_two_days_with_computed_values(client, db):
    """SPEC 10.6: two days of data returns correct per-day aggregation."""
    now = _daily_fixture(db)

    resp = client.get("/api/v1/daily?node=weather-daily&days=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2, f"Expected 2 days, got {len(data)}: {data}"

    # Oldest day first: day offset 2
    d2 = (now - timedelta(days=2)).date()
    assert data[0]["date"] == str(d2)
    assert data[0]["temp_min"] == 15.0
    assert data[0]["temp_max"] == 18.0
    assert data[0]["temp_avg"] == 16.5  # (15.0 + 18.0) / 2
    assert data[0]["rain_total"] == 2.0
    assert data[0]["humidity_avg"] == 55.0

    # Newer day: day offset 1
    d1 = (now - timedelta(days=1)).date()
    assert data[1]["date"] == str(d1)
    assert data[1]["temp_min"] == 20.0
    assert data[1]["temp_max"] == 24.0
    assert data[1]["temp_avg"] == 22.0  # (20.0 + 24.0) / 2
    assert data[1]["rain_total"] == 5.5
    assert data[1]["humidity_avg"] == 65.0  # (60.0 + 70.0) / 2


def test_daily_unknown_node_returns_empty(client, db):
    """Unknown node returns an empty list, not an error."""
    resp = client.get("/api/v1/daily?node=nonexistent&days=30")
    assert resp.status_code == 200
    assert resp.json() == []


def test_daily_days_zero_returns_400(client):
    """SPEC 10.6: days=0 is out of range, returns 400."""
    resp = client.get("/api/v1/daily?days=0")
    assert resp.status_code == 400


def test_daily_days_400_returns_400(client):
    """SPEC 10.6: days=400 is out of range, returns 400."""
    resp = client.get("/api/v1/daily?days=400")
    assert resp.status_code == 400


def test_daily_days_366_ok(client, db):
    """SPEC 10.6: days=366 is the upper bound, returns 200."""
    resp = client.get("/api/v1/daily?days=366")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_daily_days_1_ok(client, db):
    """SPEC 10.6: days=1 is the lower bound, returns 200."""
    resp = client.get("/api/v1/daily?days=1")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_daily_default_days_is_30(client, db):
    """Default days=30 works and returns aggregation."""
    _daily_fixture(db)
    resp = client.get("/api/v1/daily?node=weather-daily")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2  # at least our two test days
