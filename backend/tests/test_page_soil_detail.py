"""Tests for GET /soil/{node_id} page (T33).

SPEC 10.4: The soil detail page shows current values (moisture, soil temperature,
battery) and moisture + soil-temperature charts with a day/week/month selector.
An unknown or non-soil node returns the styled HTML 404 page.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading
from app.web import _SELECTORS

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
    for metric, value in [("soil_moisture_pct", moisture), ("soil_temp_c", soil_temp)]:
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id) & (Reading.metric == metric) & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def soil_detail_data(db: Session) -> Session:
    """A soil node with typical readings for detail page tests."""
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


@pytest.fixture()
def soil_detail_low_moisture(db: Session) -> Session:
    """A soil node with low moisture (< 25%) for badge testing."""
    now = _now()
    _make_soil_batch(
        db,
        "soil-bed-dry",
        now,
        moisture=18.0,
        soil_temp=15.2,
        battery_v=3.4,
    )
    yield db


@pytest.fixture()
def weather_only_data(db: Session) -> None:
    """A weather node (no soil nodes) for 404 testing."""
    now = _now()
    node = db.execute(select(Node).where(Node.node_id == "weather-main")).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id="weather-main",
            node_type="weather",
            first_seen=now,
            last_seen=now,
        )
        db.add(node)
        db.flush()
    node.last_seen = now
    for metric, value in [("temp_c", 21.5), ("humidity_pct", 65.0)]:
        reading = Reading(node_id="weather-main", metric=metric, ts=now, value=value)
        db.add(reading)
    db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_soil_detail_page_loads(client, soil_detail_data):
    """GET /soil/soil-bed-1 returns 200."""
    resp = client.get("/soil/soil-bed-1")
    assert resp.status_code == 200


def test_soil_detail_page_content_type(client, soil_detail_data):
    """GET /soil/soil-bed-1 returns HTML."""
    resp = client.get("/soil/soil-bed-1")
    assert "text/html" in resp.headers["content-type"]


def test_soil_detail_page_shows_node_id(client, soil_detail_data):
    """The node ID is displayed in the page heading."""
    resp = client.get("/soil/soil-bed-1")
    assert "soil-bed-1" in resp.text


def test_soil_detail_page_shows_moisture(client, soil_detail_data):
    """Soil moisture value appears with correct formatting."""
    resp = client.get("/soil/soil-bed-1")
    assert "42%" in resp.text
    assert "Moisture" in resp.text


def test_soil_detail_page_shows_soil_temperature(client, soil_detail_data):
    """Soil temperature appears with correct formatting."""
    resp = client.get("/soil/soil-bed-1")
    assert "18.5\u00b0C" in resp.text
    assert "Soil Temperature" in resp.text


def test_soil_detail_page_shows_battery(client, soil_detail_data):
    """Battery voltage appears with correct formatting."""
    resp = client.get("/soil/soil-bed-1")
    assert "3.60V" in resp.text
    assert "Battery" in resp.text


def test_soil_detail_page_nav_active(client, soil_detail_data):
    """The 'Soil' nav link is marked as active."""
    resp = client.get("/soil/soil-bed-1")
    assert 'href="/soil" aria-current="page" class="nav-link active"' in resp.text


def test_soil_detail_page_shows_online_status(client, soil_detail_data):
    """A fresh node shows 'Online' badge."""
    resp = client.get("/soil/soil-bed-1")
    assert "Online" in resp.text


def test_soil_detail_page_needs_water_badge(client, soil_detail_low_moisture):
    """Moisture below 25% shows 'Needs Water' badge."""
    resp = client.get("/soil/soil-bed-dry")
    assert "Needs Water" in resp.text


def test_soil_detail_page_offline_16_min(client, db):
    """A node last seen 16 minutes ago shows offline status."""
    old_time = _now() - timedelta(minutes=16)
    _make_soil_batch(
        db,
        "soil-bed-old",
        old_time,
        moisture=50.0,
        soil_temp=14.0,
        battery_v=3.3,
    )
    resp = client.get("/soil/soil-bed-old")
    assert "Offline" in resp.text


def test_soil_detail_chart_section_exists(client, soil_detail_data):
    """The chart section is present on the soil detail page."""
    resp = client.get("/soil/soil-bed-1")
    assert 'id="chart-section"' in resp.text
    assert "History" in resp.text


def test_soil_detail_chart_containers(client, soil_detail_data):
    """Soil moisture and soil temp chart containers are rendered."""
    resp = client.get("/soil/soil-bed-1")
    assert 'data-metric="soil_moisture_pct"' in resp.text
    assert 'data-metric="soil_temp_c"' in resp.text


def test_soil_detail_chart_node_attribute(client, soil_detail_data):
    """Chart containers carry the correct data-node attribute."""
    resp = client.get("/soil/soil-bed-1")
    assert 'data-node="soil-bed-1"' in resp.text


def test_soil_detail_chart_has_data_chart_attr(client, soil_detail_data):
    """All chart containers have the data-chart attribute."""
    resp = client.get("/soil/soil-bed-1")
    assert "data-chart" in resp.text


def test_soil_detail_chart_selector_present(client, soil_detail_data):
    """Chart selector buttons are rendered with correct labels."""
    resp = client.get("/soil/soil-bed-1")
    text = resp.text
    for sel in _SELECTORS:
        assert sel["label"] in text
    assert 'class="btn-glossy chart-btn"' in text


def test_soil_detail_chart_selector_query_params(client, soil_detail_data):
    """Selector links carry from/to/step query parameters."""
    resp = client.get("/soil/soil-bed-1")
    text = resp.text
    import re

    hrefs = re.findall(r'href="/api/v1/series\?([^"]+)"', text)
    assert len(hrefs) >= 3
    for href in hrefs[:3]:
        from urllib.parse import parse_qs

        params = parse_qs(href)
        assert "from" in params
        assert "to" in params
        assert "step" in params


def test_soil_detail_404_unknown_node(client, soil_detail_data):
    """An unknown node_id returns 404."""
    resp = client.get("/soil/nonexistent-node")
    assert resp.status_code == 404


def test_soil_detail_404_weather_node(client, weather_only_data):
    """A weather node_id returns 404 on the soil detail page."""
    resp = client.get("/soil/weather-main")
    assert resp.status_code == 404


def test_soil_detail_404_is_html(client, soil_detail_data):
    """The 404 response for soil detail is HTML."""
    resp = client.get("/soil/nonexistent-node")
    assert "text/html" in resp.headers["content-type"]


def test_soil_detail_404_has_nav(client, soil_detail_data):
    """The 404 page contains the shared navigation."""
    resp = client.get("/soil/nonexistent-node")
    assert '<nav aria-label="Main"' in resp.text


def test_soil_detail_404_has_friendly_message(client, soil_detail_data):
    """The 404 page contains a friendly message."""
    resp = client.get("/soil/nonexistent-node")
    assert "Page Not Found" in resp.text


def test_soil_detail_chart_selectors_context(client, soil_detail_data):
    """24h, 7d, 30d selector buttons appear on the page."""
    resp = client.get("/soil/soil-bed-1")
    assert "24h" in resp.text
    assert "7d" in resp.text
    assert "30d" in resp.text


def test_soil_detail_page_extends_base(client, soil_detail_data):
    """The soil detail page extends base.html (has header/footer)."""
    resp = client.get("/soil/soil-bed-1")
    assert 'class="header"' in resp.text
    assert 'class="footer"' in resp.text
    assert "<main" in resp.text


def test_soil_detail_empty_metrics_no_charts(client, db):
    """When a soil node has no metrics, no chart containers are rendered."""
    now = _now()
    node = Node(
        node_id="soil-empty",
        node_type="soil",
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.flush()
    resp = client.get("/soil/soil-empty")
    assert resp.status_code == 200
    assert "data-chart" not in resp.text


def test_soil_detail_single_metric(client, db):
    """When a soil node has only one metric, only one chart container is rendered."""
    now = _now()
    node = Node(
        node_id="soil-partial",
        node_type="soil",
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.flush()
    reading = Reading(node_id="soil-partial", metric="soil_moisture_pct", ts=now, value=35.0)
    db.add(reading)
    db.flush()
    resp = client.get("/soil/soil-partial")
    assert 'data-metric="soil_moisture_pct"' in resp.text
    assert 'data-metric="soil_temp_c"' not in resp.text


def test_soil_detail_chart_js_barPath_exists() -> None:
    """chart.js defines barPath for rain_mm-style rendering (existing contract)."""
    static_dir = Path(__file__).resolve().parent.parent / "app" / "static"
    with open(static_dir / "chart.js") as f:
        source = f.read()
    assert "function barPath" in source
