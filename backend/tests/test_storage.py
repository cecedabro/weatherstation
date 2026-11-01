"""Storage tests for node and reading models per SPEC 2.1."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import Node, Reading


def test_tables_exist(db):
    """SPEC 2.1: node and reading tables are created by migration."""
    result = db.execute(select(func.count()).select_from(Node)).scalar()
    assert result == 0
    result2 = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert result2 == 0


def test_node_model_create(db):
    """SPEC 2.1: a Node row can be inserted and retrieved by node_id (PK)."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(
        node_id="weather-main",
        node_type="weather",
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.flush()

    fetched = db.get(Node, "weather-main")
    assert fetched is not None
    assert fetched.node_id == "weather-main"
    assert fetched.node_type == "weather"


def test_reading_model_create(db):
    """SPEC 2.1: a Reading row can be inserted and retrieved by id."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(
        node_id="weather-main",
        metric="temp_c",
        ts=now,
        value=21.5,
    )
    db.add(reading)
    db.flush()

    assert reading.id is not None
    fetched = db.get(Reading, reading.id)
    assert fetched is not None
    assert fetched.metric == "temp_c"
    assert float(fetched.value) == 21.5


def test_unique_constraint_prevents_duplicates(db):
    """SPEC 2.3: inserting a duplicate (node_id, metric, ts) raises an error."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(node_id="weather-main", metric="temp_c", ts=now, value=15.0)
    db.add(reading)
    db.flush()

    duplicate = Reading(node_id="weather-main", metric="temp_c", ts=now, value=16.0)
    db.add(duplicate)
    with pytest.raises(Exception):
        db.flush()


def test_upsert_no_duplicate_on_same_key(db):
    """SPEC 2.3: re-inserting a reading with the same (node_id, metric, ts) raises (no dupes)."""
    now = datetime.now(UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(node_id="weather-main", metric="temp_c", ts=now, value=15.0)
    db.add(reading)
    db.flush()

    # Second insert with same key should fail (enforces uniqueness)
    duplicate = Reading(node_id="weather-main", metric="temp_c", ts=now, value=16.0)
    db.add(duplicate)
    with pytest.raises(Exception):
        db.flush()

    # Still only one row
    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 1


def test_node_has_all_columns(db):
    """SPEC 2.1: node table has all required columns."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(
        node_id="soil-bed-1",
        node_type="soil",
        first_seen=now,
        last_seen=now,
        last_battery_v=3.7,
        last_rssi_dbm=-65,
    )
    db.add(node)
    db.flush()

    fetched = db.get(Node, "soil-bed-1")
    assert fetched.last_battery_v is not None
    assert float(fetched.last_battery_v) == 3.7
    assert fetched.last_rssi_dbm == -65


def test_reading_has_all_columns(db):
    """SPEC 2.1: reading table has node_id FK, metric, ts, value columns."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(node_id="weather-main", metric="humidity_pct", ts=now, value=72.3)
    db.add(reading)
    db.flush()

    assert reading.node_id == "weather-main"
    assert reading.metric == "humidity_pct"
    assert reading.ts == now
    assert float(reading.value) == 72.3


def test_multiple_readings_per_node(db):
    """SPEC 2.2: a single batch produces one row per metric."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    metrics = [
        ("temp_c", 21.0),
        ("humidity_pct", 65.0),
        ("pressure_hpa", 1013.0),
    ]
    for metric, value in metrics:
        r = Reading(node_id="weather-main", metric=metric, ts=now, value=value)
        db.add(r)
    db.flush()

    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    assert len(rows) == 3
    assert {r.metric for r in rows} == {"temp_c", "humidity_pct", "pressure_hpa"}


def test_reading_timestamp_utc(db):
    """SPEC 2.1: timestamps are stored as UTC (timezone-aware)."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(node_id="weather-main", metric="temp_c", ts=now, value=20.0)
    db.add(reading)
    db.flush()

    assert reading.ts.tzinfo is not None
    fetched = db.get(Reading, reading.id)
    assert fetched.ts.tzinfo is not None


def test_node_foreign_key_cascade(db):
    """SPEC 2.1: deleting a node cascades to its readings."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="weather-main", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    reading = Reading(node_id="weather-main", metric="temp_c", ts=now, value=20.0)
    db.add(reading)
    db.flush()

    reading_id = reading.id
    db.delete(node)
    db.flush()

    assert db.get(Node, "weather-main") is None
    assert db.get(Reading, reading_id) is None


def test_node_type_stored(db):
    """SPEC 2.1: node_type is stored and retrievable."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    node = Node(node_id="soil-bed-3", node_type="soil", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()

    assert db.get(Node, "soil-bed-3").node_type == "soil"


def test_multiple_nodes(db):
    """SPEC 2.1: multiple distinct nodes can coexist."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for nid, ntype in [("weather-main", "weather"), ("soil-bed-3", "soil")]:
        db.add(Node(node_id=nid, node_type=ntype, first_seen=now, last_seen=now))
    db.flush()

    nodes = db.execute(select(Node)).scalars().all()
    assert len(nodes) == 2
    assert {n.node_id for n in nodes} == {"weather-main", "soil-bed-3"}
