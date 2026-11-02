"""Tests for GET /soil page (T32).

SPEC 10.3: The soil page lists every soil node as a card with moisture,
           soil temperature, battery, online state, and last seen.
           Moisture below 25 % shows "needs water".
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


def _make_soil_batch(
    db: Session,
    node_id: str,
    ts: datetime,
    moisture: float,
    soil_temp: float,
    battery_v: float | None = None,
    rssi_dbm: int | None = None,
) -> None:
    """Insert a soil node and its metric readings."""
    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type="soil",
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
    db.execute(
        select(Reading).where(
            (Reading.node_id == node_id)
            & (Reading.metric == "soil_moisture_pct")
            & (Reading.ts == ts)
        )
    ).scalar_one_or_none()
    reading = db.execute(
        select(Reading).where(
            (Reading.node_id == node_id)
            & (Reading.metric == "soil_moisture_pct")
            & (Reading.ts == ts)
        )
    ).scalar_one_or_none()
    if reading is None:
        reading = Reading(node_id=node_id, metric="soil_moisture_pct", ts=ts, value=moisture)
        db.add(reading)
    reading2 = db.execute(
        select(Reading).where(
            (Reading.node_id == node_id) & (Reading.metric == "soil_temp_c") & (Reading.ts == ts)
        )
    ).scalar_one_or_none()
    if reading2 is None:
        reading2 = Reading(node_id=node_id, metric="soil_temp_c", ts=ts, value=soil_temp)
        db.add(reading2)
    db.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def soil_data(db: Session) -> Session:
    """A soil node with typical readings."""
    now = _now()
    _make_soil_batch(
        db,
        "soil-bed-1",
        now,
        moisture=42.0,
        soil_temp=18.5,
        battery_v=3.6,
        rssi_dbm=-62,
    )
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_soil_page_loads(client):
    """GET /soil returns 200."""
    resp = client.get("/soil")
    assert resp.status_code == 200


def test_soil_page_content_type(client):
    """GET /soil returns HTML."""
    resp = client.get("/soil")
    assert "text/html" in resp.headers["content-type"]


def test_soil_page_shows_node_id(client, soil_data):
    """The node ID is displayed."""
    resp = client.get("/soil")
    assert "soil-bed-1" in resp.text


def test_soil_page_shows_moisture(client, soil_data):
    """Soil moisture value appears."""
    resp = client.get("/soil")
    assert "42%" in resp.text


def test_soil_page_shows_soil_temperature(client, soil_data):
    """Soil temperature appears with degree symbol and °C."""
    resp = client.get("/soil")
    assert "18.5\u00b0C" in resp.text


def test_soil_page_shows_battery(client, soil_data):
    """Battery voltage appears with V suffix."""
    resp = client.get("/soil")
    assert "3.60V" in resp.text


def test_soil_page_nav_active(client, soil_data):
    """The 'Soil' nav link is marked as active."""
    resp = client.get("/soil")
    assert 'href="/soil" aria-current="page" class="nav-link active"' in resp.text


def test_soil_page_shows_needs_water_badge_below_25(client, db):
    """Moisture at 24.9 % shows the 'needs water' badge."""
    now = _now()
    _make_soil_batch(
        db,
        "soil-bed-low",
        now,
        moisture=24.9,
        soil_temp=16.0,
        battery_v=3.5,
    )
    resp = client.get("/soil")
    assert "Needs Water" in resp.text


def test_soil_page_no_badge_at_25(client, db):
    """Moisture at 25.0 % does NOT show the 'needs water' badge."""
    now = _now()
    _make_soil_batch(
        db,
        "soil-bed-ok",
        now,
        moisture=25.0,
        soil_temp=17.0,
        battery_v=3.5,
    )
    resp = client.get("/soil")
    assert "Needs Water" not in resp.text


def test_soil_page_offline_16_min(client, db):
    """A node last seen 16 minutes ago is shown as offline."""
    old_time = _now() - timedelta(minutes=16)
    _make_soil_batch(
        db,
        "soil-bed-old",
        old_time,
        moisture=50.0,
        soil_temp=15.0,
        battery_v=3.4,
    )
    resp = client.get("/soil")
    assert "Offline" in resp.text


def test_soil_page_empty_state(client):
    """An empty state is shown when there are no soil nodes."""
    resp = client.get("/soil")
    assert "No Soil Data" in resp.text
    assert "Waiting for a soil node" in resp.text


def test_soil_page_shows_online_status(client, soil_data):
    """A fresh node shows 'Online' status."""
    resp = client.get("/soil")
    assert "Online" in resp.text


def test_soil_page_links_to_detail(client, soil_data):
    """Each soil card links to /soil/<node_id>."""
    resp = client.get("/soil")
    assert 'href="/soil/soil-bed-1"' in resp.text
