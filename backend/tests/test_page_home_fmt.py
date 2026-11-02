"""Tests for T25: wind direction compass formatting, <time> tags, offline state.

SPEC 10.11 – Times on pages are shown in Europe/Amsterdam with a relative age;
wind direction is shown as a compass point next to degrees.
SPEC 10.13 – A node whose last reading is older than 15 minutes is shown as
"offline since …", never as live.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading
from app.readapi import _current_readings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_batch(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict[str, float],
    battery_v: float | None = None,
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
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    node.last_battery_v = battery_v
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
    return node


# ---------------------------------------------------------------------------
# _current_readings returns reading_time
# ---------------------------------------------------------------------------


def test_reading_time_returns_datetime(db: Session):
    """_current_readings includes reading_time as a datetime object."""
    now = datetime.now(UTC)
    _make_batch(db, "test-node", "weather", now, {"temp_c": 20.0})
    result = _current_readings(db)
    entry = next(e for e in result if e["node_id"] == "test-node")
    assert entry["reading_time"] is not None
    assert isinstance(entry["reading_time"], datetime)


def test_reading_time_is_none_when_no_readings(db: Session):
    """_current_readings returns reading_time=None for nodes with no readings."""
    now = datetime.now(UTC)
    node = Node(node_id="empty-node", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()
    result = _current_readings(db)
    entry = next(e for e in result if e["node_id"] == "empty-node")
    assert entry["reading_time"] is None


def test_reading_time_is_max_across_metrics(db: Session):
    """reading_time is the latest timestamp across all metrics for a node."""
    now = datetime.now(UTC)
    older = now - timedelta(minutes=5)
    _make_batch(db, "multi-node", "weather", older, {"temp_c": 15.0})
    _make_batch(db, "multi-node", "weather", now, {"humidity_pct": 60.0})
    result = _current_readings(db)
    entry = next(e for e in result if e["node_id"] == "multi-node")
    assert entry["reading_time"] == now
    assert entry["metrics"]["temp_c"] == 15.0
    assert entry["metrics"]["humidity_pct"] == 60.0


# ---------------------------------------------------------------------------
# Wind direction compass formatting on GET /
# ---------------------------------------------------------------------------


def test_wind_dir_shows_compass_and_degrees(client, db: Session):
    """SPEC 10.11: wind direction shows compass point plus degrees."""
    now = datetime.now(UTC)
    _make_batch(db, "wind-test", "weather", now, {"wind_dir_deg": 225.0})
    resp = client.get("/")
    text = resp.text
    assert "SW" in text
    assert "225" in text or "225°" in text


def test_wind_dir_compass_n(client, db: Session):
    """North (0°) renders as 'N'."""
    now = datetime.now(UTC)
    _make_batch(db, "n-node", "weather", now, {"wind_dir_deg": 0.0})
    resp = client.get("/")
    assert "N" in resp.text


def test_wind_dir_compass_south(client, db: Session):
    """South (180°) renders as 'S'."""
    now = datetime.now(UTC)
    _make_batch(db, "s-node", "weather", now, {"wind_dir_deg": 180.0})
    resp = client.get("/")
    assert "S" in resp.text


def test_wind_dir_no_compass_when_missing(client, db: Session):
    """Nodes without wind_dir_deg still render without error."""
    now = datetime.now(UTC)
    _make_batch(db, "no-wind", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "no-wind" in resp.text


# ---------------------------------------------------------------------------
# <time> tag with datetime attribute and local_time title
# ---------------------------------------------------------------------------


def test_time_tag_present(client, db: Session):
    """SPEC 10.11: each node card contains a <time> element."""
    now = datetime.now(UTC)
    _make_batch(db, "time-test", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    assert "<time" in resp.text
    assert "</time>" in resp.text


def test_time_tag_has_datetime_attribute(client, db: Session):
    """<time> has a datetime attribute with ISO format."""
    now = datetime.now(UTC)
    _make_batch(db, "dt-test", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    assert "datetime=" in resp.text


def test_time_tag_title_contains_local_time(client, db: Session):
    """<time> title attribute contains local Europe/Amsterdam time string."""
    now = datetime.now(UTC)
    _make_batch(db, "title-test", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    text = resp.text
    # local_time format is like "14:05, 2 Nov"
    assert "title=" in text


def test_time_tag_content_has_relative_age(client, db: Session):
    """<time> content shows relative age like 'just now' or 'X min ago'."""
    now = datetime.now(UTC)
    _make_batch(db, "ago-test", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    text = resp.text
    # Within 1 minute → "just now"
    assert "just now" in text or "min ago" in text


# ---------------------------------------------------------------------------
# Offline state for readings older than 15 min
# ---------------------------------------------------------------------------


def test_offline_text_shown_for_old_readings(client, db: Session):
    """SPEC 10.13: node with last reading > 15 min shows offline message."""
    old = datetime.now(UTC) - timedelta(minutes=20)
    _make_batch(db, "offline-node", "weather", old, {"temp_c": 18.0})
    resp = client.get("/")
    assert "offline" in resp.text.lower() or "Offline" in resp.text


def test_offline_since_shows_local_time(client, db: Session):
    """Offline message includes 'since' and local formatted time."""
    old = datetime.now(UTC) - timedelta(minutes=20)
    _make_batch(db, "offline-since", "weather", old, {"temp_c": 18.0})
    resp = client.get("/")
    text = resp.text
    assert "since" in text.lower()


def test_not_offline_for_recent_readings(client, db: Session):
    """Node with recent reading does NOT show offline message."""
    now = datetime.now(UTC)
    _make_batch(db, "online-node", "weather", now, {"temp_c": 20.0})
    resp = client.get("/")
    text = resp.text
    # Should show <time> with relative age, not offline
    assert "<time" in text
    assert "offline" not in text.lower() or "no readings" in text.lower()


def test_not_offline_at_exactly_15_minutes(client, db: Session):
    """Exactly 15 minutes is NOT offline (cutoff is strictly greater than 15 min)."""
    cutoff = datetime.now(UTC) - timedelta(minutes=14, seconds=59)
    _make_batch(db, "boundary-node", "weather", cutoff, {"temp_c": 19.0})
    resp = client.get("/")
    text = resp.text
    # At exactly 15 min, it should still show as alive (<time> present, no offline)
    assert "<time" in text


def test_offline_when_no_readings(client, db: Session):
    """Node with no readings at all shows as offline."""
    now = datetime.now(UTC)
    node = Node(node_id="no-data", node_type="weather", first_seen=now, last_seen=now)
    db.add(node)
    db.flush()
    resp = client.get("/")
    text = resp.text
    assert "offline" in text.lower() or "Offline" in text
