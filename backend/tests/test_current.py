"""Tests for GET /api/v1/current per SPEC 4.1.

SPEC 4.1: `GET /api/v1/current` returns the latest reading per node.
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
def sample_data(db: Session) -> Iterator[Session]:
    """Populate the database with multiple nodes and readings."""
    now = _now()
    older = now - timedelta(minutes=10)

    # Weather node with multiple readings (only latest should be returned)
    _make_batch(
        db,
        "weather-main",
        "weather",
        older,
        {"temp_c": 15.0, "humidity_pct": 70.0, "pressure_hpa": 1010.0},
        battery_v=3.8,
        rssi_dbm=-55,
    )
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 21.5, "humidity_pct": 65.0, "pressure_hpa": 1013.4},
        battery_v=3.75,
        rssi_dbm=-53,
    )

    # Soil node with a single reading
    _make_batch(
        db,
        "soil-bed-3",
        "soil",
        now,
        {"soil_moisture_pct": 38.5, "soil_temp_c": 11.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )

    # Node with no readings at all
    no_readings_node = Node(
        node_id="weather-spare",
        node_type="weather",
        first_seen=now - timedelta(hours=1),
        last_seen=now - timedelta(hours=1),
    )
    db.add(no_readings_node)
    db.flush()

    yield db


def test_current_empty_list(client, db: Session):
    """SPEC 4.1: returns an empty list when no data exists."""
    resp = client.get("/api/v1/current")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


def test_current_returns_latest_per_node(client, db: Session, sample_data):
    """SPEC 4.1: returns the latest reading per node, not historical ones."""
    resp = client.get("/api/v1/current")
    assert resp.status_code == 200
    data = resp.json()

    # Find the weather-main entry
    weather = next((e for e in data if e["node_id"] == "weather-main"), None)
    assert weather is not None
    # Latest temp_c should be 21.5 (not 15.0 from older reading)
    assert weather["metrics"]["temp_c"] == 21.5
    assert weather["metrics"]["humidity_pct"] == 65.0
    assert weather["metrics"]["pressure_hpa"] == 1013.4


def test_current_multiple_nodes(client, db: Session, sample_data):
    """SPEC 4.1: returns one entry per node (weather + soil)."""
    resp = client.get("/api/v1/current")
    assert resp.status_code == 200
    data = resp.json()
    node_ids = {e["node_id"] for e in data}
    assert "weather-main" in node_ids
    assert "soil-bed-3" in node_ids


def test_current_soil_metrics(client, db: Session, sample_data):
    """SPEC 4.1: soil node returns its metrics correctly."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    soil = next((e for e in data if e["node_id"] == "soil-bed-3"), None)
    assert soil is not None
    assert soil["metrics"]["soil_moisture_pct"] == 38.5
    assert soil["metrics"]["soil_temp_c"] == 11.0


def test_current_node_without_readings(client, db: Session, sample_data):
    """SPEC 4.1: a node with no readings still appears (with empty metrics)."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    spare = next((e for e in data if e["node_id"] == "weather-spare"), None)
    assert spare is not None
    assert spare["metrics"] == {}
    assert spare["node_type"] == "weather"


def test_current_response_fields(client, db: Session, sample_data):
    """SPEC 4.1: each entry has the required fields."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    required_fields = {"node_id", "node_type", "last_seen", "battery_v", "rssi_dbm", "metrics"}
    for entry in data:
        assert required_fields.issubset(entry), f"Missing fields: {required_fields - set(entry)}"
        assert isinstance(entry["metrics"], dict)
        assert isinstance(entry["node_id"], str)
        assert isinstance(entry["node_type"], str)


def test_current_returns_updated_values_on_upsert(client, db: Session):
    """SPEC 4.1 + SPEC 2.3: after upsert, only the updated value is returned."""
    now = _now()
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    # Insert first reading
    r1 = Reading(node_id="weather-main", metric="temp_c", ts=now, value=15.0)
    db.add(r1)
    db.flush()

    # Ingest the first batch to register auth token is not needed for direct db queries
    # but the endpoint reads from db directly
    resp = client.get("/api/v1/current")
    data = resp.json()
    weather = next((e for e in data if e["node_id"] == "weather-main"), None)
    assert weather is not None
    assert weather["metrics"]["temp_c"] == 15.0

    # Now update the reading (simulating upsert via new batch)
    newer = now + timedelta(minutes=1)
    node.last_seen = newer
    r2 = Reading(node_id="weather-main", metric="temp_c", ts=newer, value=22.0)
    db.add(r2)
    db.flush()

    resp = client.get("/api/v1/current")
    data = resp.json()
    weather = next((e for e in data if e["node_id"] == "weather-main"), None)
    assert weather is not None
    assert weather["metrics"]["temp_c"] == 22.0


def test_current_battery_and_rssi(client, db: Session, sample_data):
    """SPEC 4.1: battery_v and rssi_dbm are included in the response."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    weather = next((e for e in data if e["node_id"] == "weather-main"), None)
    assert weather is not None
    assert weather["battery_v"] == 3.75
    assert weather["rssi_dbm"] == -53


def test_current_node_ordering(client, db: Session, sample_data):
    """SPEC 4.1: nodes appear in the result (order is not specified but should be deterministic)."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    assert len(data) == 3  # weather-main, soil-bed-3, weather-spare


def test_current_empty_metrics_node(client, db: Session):
    """SPEC 4.1: node with no readings returns empty metrics dict."""
    now = _now()
    node = Node(node_id="empty-node", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    resp = client.get("/api/v1/current")
    data = resp.json()
    empty = next((e for e in data if e["node_id"] == "empty-node"), None)
    assert empty is not None
    assert empty["metrics"] == {}


def test_current_only_node_id_entries(client, db: Session, sample_data):
    """SPEC 4.1: exactly one entry per unique node_id."""
    resp = client.get("/api/v1/current")
    data = resp.json()
    node_ids = [e["node_id"] for e in data]
    # Each node_id should appear exactly once
    assert len(node_ids) == len(set(node_ids))
