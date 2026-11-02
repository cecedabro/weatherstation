"""Tests for GET /partials/current (SPEC 10.10).

SPEC 10.10: The current conditions on `/` refresh every 60 s through HTMX from
            `GET /partials/current` (an HTML fragment) without a full page reload.

The fragment:
  - Must be a plain HTML fragment (no `<html>`, `<head>`, `<body>`, nav, etc.)
  - Must contain the same node IDs, metric values, and section headers as GET /
  - Must return empty-state cards when there is no data
"""

from datetime import UTC, datetime

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
    """A weather node with current readings."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 21.5, "humidity_pct": 65.0, "pressure_hpa": 1013.4},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    yield db


@pytest.fixture()
def soil_data(db: Session) -> Session:
    """A soil node with current readings."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-3",
        "soil",
        now,
        {"soil_moisture_pct": 38.5, "soil_temp_c": 11.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    yield db


@pytest.fixture()
def mixed_data(db: Session) -> Session:
    """Both weather and soil nodes with readings."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 21.5, "humidity_pct": 65.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    _make_batch(
        db,
        "soil-bed-3",
        "soil",
        now,
        {"soil_moisture_pct": 38.5, "soil_temp_c": 11.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    yield db


# ---------------------------------------------------------------------------
# Tests — SPEC 10.10: GET /partials/current returns an HTML fragment
# ---------------------------------------------------------------------------


def test_partial_returns_200(client):
    """SPEC 10.10: /partials/current returns HTTP 200."""
    resp = client.get("/partials/current")
    assert resp.status_code == 200


def test_partial_is_html(client):
    """The partial returns HTML content type."""
    resp = client.get("/partials/current")
    assert "text/html" in resp.headers["content-type"]


def test_partial_no_html_tag(client):
    """SPEC 10.10: the fragment must not contain `<html`."""
    resp = client.get("/partials/current")
    assert "<html" not in resp.text
    assert "<head" not in resp.text
    assert "<body" not in resp.text


def test_partial_no_nav(client):
    """The fragment must not contain navigation markup."""
    resp = client.get("/partials/current")
    assert 'aria-label="Main"' not in resp.text
    assert "<nav" not in resp.text


def test_partial_no_header_footer(client):
    """The fragment must not contain header or footer from base template."""
    resp = client.get("/partials/current")
    assert "<header" not in resp.text
    assert '<footer class="footer">' not in resp.text


# ---------------------------------------------------------------------------
# Tests: node IDs present with data
# ---------------------------------------------------------------------------


def test_partial_shows_weather_node_id(client, weather_data):
    """Weather node ID appears in the fragment."""
    resp = client.get("/partials/current")
    assert "weather-main" in resp.text


def test_partial_shows_soil_node_id(client, soil_data):
    """Soil node ID appears in the fragment."""
    resp = client.get("/partials/current")
    assert "soil-bed-3" in resp.text


def test_partial_shows_both_node_ids(client, mixed_data):
    """Both node IDs appear in the fragment when both data types exist."""
    resp = client.get("/partials/current")
    assert "weather-main" in resp.text
    assert "soil-bed-3" in resp.text


# ---------------------------------------------------------------------------
# Tests: section headers present with data
# ---------------------------------------------------------------------------


def test_partial_has_current_conditions_header(client, weather_data):
    """The Current Conditions header is present in the fragment."""
    resp = client.get("/partials/current")
    assert "Current Conditions" in resp.text


def test_partial_has_soil_header(client, soil_data):
    """The Latest Soil Readings header is present in the fragment."""
    resp = client.get("/partials/current")
    assert "Latest Soil Readings" in resp.text


# ---------------------------------------------------------------------------
# Tests: metric values present with data
# ---------------------------------------------------------------------------


def test_partial_shows_temperature(client, weather_data):
    """Temperature value from weather node is in the fragment."""
    resp = client.get("/partials/current")
    assert "21.5" in resp.text


def test_partial_shows_humidity(client, weather_data):
    """Humidity reading is in the fragment."""
    resp = client.get("/partials/current")
    assert "65.0" in resp.text
    assert "Humidity" in resp.text


def test_partial_shows_soil_moisture(client, soil_data):
    """Soil moisture percentage is in the fragment."""
    resp = client.get("/partials/current")
    assert "Moisture" in resp.text


def test_partial_shows_soil_temperature(client, soil_data):
    """Soil temperature is in the fragment."""
    resp = client.get("/partials/current")
    assert "11.0" in resp.text


# ---------------------------------------------------------------------------
# Tests: empty-state fragment when there is no data
# ---------------------------------------------------------------------------


def test_partial_empty_state_no_data(client):
    """When there is no data, the fragment returns the generic empty state."""
    resp = client.get("/partials/current")
    assert "No Readings Yet" in resp.text
    assert "<html" not in resp.text


def test_partial_empty_state_weather_only(client, weather_data):
    """When only weather data exists, the fragment shows No Soil Data."""
    resp = client.get("/partials/current")
    assert "No Soil Data" in resp.text
    assert "No Weather Data" not in resp.text
    assert "<html" not in resp.text


def test_partial_empty_state_soil_only(client, soil_data):
    """When only soil data exists, the fragment shows No Weather Data."""
    resp = client.get("/partials/current")
    assert "No Weather Data" in resp.text
    assert "No Soil Data" not in resp.text
    assert "<html" not in resp.text


def test_partial_with_data_no_empty_state(client, mixed_data):
    """When both data types exist, no empty-state cards appear."""
    resp = client.get("/partials/current")
    assert "No Readings Yet" not in resp.text
    assert "No Weather Data" not in resp.text
    assert "No Soil Data" not in resp.text


# ---------------------------------------------------------------------------
# Tests: fragment is a superset of what /partials/current should contain
# ---------------------------------------------------------------------------


def test_partial_has_card_sections(client, weather_data):
    """The fragment contains card sections with correct class."""
    resp = client.get("/partials/current")
    assert 'class="card"' in resp.text
    assert 'class="stats-row"' in resp.text
    assert 'class="stat-card"' in resp.text


def test_partial_content_matches_home_current(client, weather_data):
    """The fragment content for weather matches what is on the home page."""
    home_resp = client.get("/")
    partial_resp = client.get("/partials/current")

    # Both should contain the weather node ID and temperature
    assert "weather-main" in home_resp.text
    assert "weather-main" in partial_resp.text
    assert "21.5" in home_resp.text
    assert "21.5" in partial_resp.text
    assert "Current Conditions" in home_resp.text
    assert "Current Conditions" in partial_resp.text
