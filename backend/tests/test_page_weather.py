"""Tests for GET /weather page (T30).

SPEC 10.2: The weather page shows per-node current metrics with label, value,
           unit, compass wind direction, and last-updated time.
           Empty state when no weather nodes exist.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
                (Reading.node_id == node_id) & (Reading.metric == metric) & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()
    return node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def weather_data(db: Session) -> Session:
    """A weather node with current readings including wind direction."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {
            "temp_c": 21.5,
            "humidity_pct": 65.0,
            "pressure_hpa": 1013.4,
            "wind_speed_ms": 5.2,
            "wind_dir_deg": 164,
        },
        battery_v=3.75,
        rssi_dbm=-53,
    )
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_weather_page_loads(client):
    """GET /weather returns 200."""
    resp = client.get("/weather")
    assert resp.status_code == 200


def test_weather_page_content_type(client):
    """GET /weather returns HTML."""
    resp = client.get("/weather")
    assert "text/html" in resp.headers["content-type"]


def test_weather_page_shows_metrics(client, weather_data):
    """Metrics appear with correct values and units."""
    resp = client.get("/weather")
    html = resp.text
    assert "21.5\u00b0C" in html
    assert "65.0%" in html
    assert "1013.4hPa" in html
    assert "5.2m/s" in html
    assert "SSE" in html
    assert "164\u00b0" in html


def test_weather_page_shows_node_id(client, weather_data):
    """The node ID is displayed."""
    resp = client.get("/weather")
    assert "weather-main" in resp.text


def test_weather_page_shows_last_updated(client, weather_data):
    """The last-updated time is displayed."""
    resp = client.get("/weather")
    assert "Updated" in resp.text


def test_weather_page_shows_offline_status(client, db):
    """Old readings (>15 min) show an offline indicator."""
    old_time = _now() - timedelta(minutes=20)
    _make_batch(
        db,
        "weather-old",
        "weather",
        old_time,
        {"temp_c": 18.5, "humidity_pct": 65.0},
        battery_v=3.5,
        rssi_dbm=-70,
    )
    resp = client.get("/weather")
    assert "Offline" in resp.text


def test_weather_page_nav_active(client, weather_data):
    """The 'Weather' nav link is marked as active."""
    resp = client.get("/weather")
    assert 'href="/weather" aria-current="page" class="nav-link active"' in resp.text


def test_weather_page_empty_state(client):
    """An empty state is shown when there are no weather nodes."""
    resp = client.get("/weather")
    assert "No Weather Data" in resp.text
    assert "Waiting for a weather node" in resp.text


def test_weather_page_section_header(client, weather_data):
    """The page has a 'Current Conditions' section header."""
    resp = client.get("/weather")
    assert "Current Conditions" in resp.text
