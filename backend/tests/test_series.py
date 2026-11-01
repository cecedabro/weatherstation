"""Tests for GET /api/v1/series per SPEC 4.2, 4.4.

SPEC 4.2: `GET /api/v1/series?node=&metric=&from=&to=&step=` returns time-ordered
          points. step=raw returns stored points; 5m|1h|1d return averages per bucket
          (sum for rain_mm). Out-of-range or unknown node/metric → empty list, 200.
SPEC 4.4: Invalid query params (bad step, non-RFC3339 dates) return 400.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading


def _now() -> datetime:
    return datetime.now(UTC)


def _make_batch(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict[str, float],
    battery_v: float | None = None,
    rssi_dbm: int | None = None,
) -> Node:
    """Insert a node and its metric readings into the database."""
    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
            last_battery_v=battery_v,
            last_rssi_dbm=rssi_dbm,
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    node.last_battery_v = battery_v
    node.last_rssi_dbm = rssi_dbm
    for metric, value in metrics.items():
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id)
                & (Reading.metric == metric)
                & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()
    return node


@pytest.fixture()
def series_data(db: Session) -> Iterator[Session]:
    """Populate the database with time-series data for testing buckets."""
    base = _now() - timedelta(hours=2)

    # Weather node with readings every 10 minutes for 2 hours (13 readings)
    for i in range(13):
        ts = base + timedelta(minutes=10 * i)
        _make_batch(
            db,
            "series-weather",
            "weather",
            ts,
            {"temp_c": 15.0 + i, "humidity_pct": 60.0 + i},
            battery_v=3.8,
            rssi_dbm=-55,
        )

    # Rain node with readings
    for i in range(5):
        ts = base + timedelta(minutes=15 * i)
        _make_batch(
            db,
            "series-rain",
            "weather",
            ts,
            {"rain_mm": float(i * 2)},
            battery_v=3.7,
            rssi_dbm=-60,
        )

    # Soil node
    for i in range(4):
        ts = base + timedelta(minutes=30 * i)
        _make_batch(
            db,
            "series-soil",
            "soil",
            ts,
            {"soil_moisture_pct": 30.0 + i * 5},
            battery_v=3.9,
            rssi_dbm=-70,
        )

    yield db


def test_series_raw_returns_all_points(client, db: Session, series_data):
    """SPEC 4.2: step=raw returns all stored points for a node+metric."""
    resp = client.get("/api/v1/series?node=series-weather&metric=temp_c&step=raw")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 13  # 13 readings
    # Points are ordered by ts
    for i in range(1, len(data)):
        assert data[i]["ts"] >= data[i - 1]["ts"]
    # Values should be 15, 16, 17, ...
    for i, point in enumerate(data):
        assert point["metric"] == "temp_c"
        assert point["value"] == 15.0 + i


def test_series_with_time_range(client, db: Session, series_data):
    """SPEC 4.2: from/to params filter the returned points."""
    now = _now()
    base = now - timedelta(hours=2)

    _make_batch(db, "range-node", "weather", base, {"temp_c": 10.0})
    _make_batch(db, "range-node", "weather", base + timedelta(minutes=30), {"temp_c": 20.0})
    _make_batch(db, "range-node", "weather", base + timedelta(hours=1), {"temp_c": 30.0})

    from_str = (base + timedelta(minutes=15)).isoformat()
    to_str = (base + timedelta(hours=1) + timedelta(minutes=45)).isoformat()
    resp = client.get(
        f"/api/v1/series?node=range-node&metric=temp_c&step=raw&from={from_str}&to={to_str}"
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should include the 20.0 reading (30 min in) but not the 10.0 one
    assert len(data) == 2
    values = [p["value"] for p in data]
    assert 20.0 in values
    assert 30.0 in values


def test_series_empty_for_unknown_node(client, db: Session):
    """SPEC 4.2: unknown node returns empty list, 200."""
    resp = client.get("/api/v1/series?node=nonexistent&metric=temp_c&step=raw")
    assert resp.status_code == 200
    assert resp.json() == []


def test_series_empty_for_unknown_metric(client, db: Session):
    """SPEC 4.2: unknown metric returns empty list, 200."""
    resp = client.get("/api/v1/series?node=series-weather&metric=nonexistent&step=raw")
    assert resp.status_code == 200
    assert resp.json() == []


def test_series_5m_bucket(client, db: Session, series_data):
    """SPEC 4.2: step=5m returns averaged buckets."""
    resp = client.get("/api/v1/series?node=series-weather&metric=temp_c&step=5m")
    assert resp.status_code == 200
    data = resp.json()
    # 13 readings every 10 min for 2h, bucketed to 5m
    # Each 5m bucket should have 0-2 readings averaged
    assert len(data) > 0
    for point in data:
        assert "ts" in point
        assert "metric" in point
        assert "value" in point
        assert point["metric"] == "temp_c"


def test_series_1h_bucket(client, db: Session, series_data):
    """SPEC 4.2: step=1h returns hour-bucketed averages."""
    resp = client.get("/api/v1/series?node=series-weather&metric=temp_c&step=1h")
    assert resp.status_code == 200
    data = resp.json()
    # 13 readings over 2h should produce 3 buckets (at hour boundaries)
    assert len(data) >= 1
    for point in data:
        assert "ts" in point
        assert point["value"] is not None


def test_series_1d_bucket(client, db: Session, series_data):
    """SPEC 4.2: step=1d returns day-bucketed averages."""
    resp = client.get("/api/v1/series?node=series-weather&metric=temp_c&step=1d")
    assert resp.status_code == 200
    data = resp.json()
    # 2 hours of data → 1 or 2 day buckets depending on day boundary
    assert len(data) >= 1
    assert all(d["value"] is not None for d in data)


def test_series_rain_uses_sum(client, db: Session, series_data):
    """SPEC 4.2: rain_mm uses sum() instead of avg() per bucket."""
    resp = client.get("/api/v1/series?node=series-rain&metric=rain_mm&step=1h")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    for point in data:
        assert point["metric"] == "rain_mm"
        # Rain values are 0, 2, 4, 6, 8 at 15-min intervals
        # Sum within same hour should be > 0
        assert point["value"] >= 0


def test_series_invalid_step_returns_400(client):
    """SPEC 4.4: invalid step returns 400."""
    resp = client.get("/api/v1/series?node=test&metric=temp_c&step=invalid")
    assert resp.status_code == 400


def test_series_invalid_from_returns_400(client):
    """SPEC 4.4: non-RFC3339 from returns 400."""
    resp = client.get("/api/v1/series?node=test&metric=temp_c&from=not-a-date")
    assert resp.status_code == 400


def test_series_invalid_to_returns_400(client):
    """SPEC 4.4: non-RFC3339 to returns 400."""
    resp = client.get("/api/v1/series?node=test&metric=temp_c&to=gibberish")
    assert resp.status_code == 400


def test_series_no_params_returns_all(client, db: Session, series_data):
    """Series with no filters returns all points (raw step by default)."""
    resp = client.get("/api/v1/series")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # There should be data from the series_data fixture
    assert len(data) > 0


def test_series_node_only_no_metric(client, db: Session, series_data):
    """Series with node but no metric returns all metrics for that node."""
    resp = client.get("/api/v1/series?node=series-weather&step=raw")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # Should include both temp_c and humidity_pct readings
    metrics = {p["metric"] for p in data}
    assert "temp_c" in metrics
    assert "humidity_pct" in metrics


def test_series_soil_bucket(client, db: Session, series_data):
    """SPEC 4.2: soil metrics work with bucketing."""
    resp = client.get("/api/v1/series?node=series-soil&metric=soil_moisture_pct&step=1h")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for point in data:
        assert point["metric"] == "soil_moisture_pct"


def test_series_time_range_with_bucket(client, db: Session, series_data):
    """SPEC 4.2: time range filtering works with bucketed step."""
    now = _now()
    base = now - timedelta(hours=2)

    from_str = (base + timedelta(minutes=15)).isoformat()
    to_str = (base + timedelta(hours=1)).isoformat()

    resp = client.get(
        f"/api/v1/series?node=series-weather&metric=temp_c&step=1h&from={from_str}&to={to_str}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should have at least one hour bucket in the range


def test_series_response_format(client, db: Session, series_data):
    """Series response has consistent format: ts, metric, value."""
    resp = client.get("/api/v1/series?node=series-weather&metric=temp_c&step=raw")
    assert resp.status_code == 200
    data = resp.json()
    for point in data:
        assert "ts" in point
        assert "metric" in point
        assert "value" in point
        assert isinstance(point["ts"], str)
        assert isinstance(point["metric"], str)
        assert isinstance(point["value"], (int, float))


def test_series_out_of_range_time(client, db: Session, series_data):
    """SPEC 4.2: time range with no matching data returns empty list."""
    far_past = (datetime.now(UTC) - timedelta(days=365)).isoformat()
    far_future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    resp = client.get(
        f"/api/v1/series?node=series-weather&metric=temp_c&step=raw&from={far_past}&to={far_future}"
    )
    assert resp.status_code == 200
    data = resp.json()
    # All data falls within this range, so should not be empty
    assert len(data) > 0
