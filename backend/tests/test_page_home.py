"""Tests for GET / home page (T12).

SPEC 5.1: `GET /` renders an HTML page showing current conditions for each weather
          node and the latest soil readings.
SPEC 5.3: The site degrades gracefully when there is no data yet (no error page;
          a friendly "no readings yet" state).
SPEC 5.4: Pages are responsive and usable on a phone screen (360px wide)
          without horizontal scrolling.
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
# Tests
# ---------------------------------------------------------------------------


def test_home_renders(client):
    """GET / renders an HTML page with HTTP 200."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_home_empty_state_without_data(client):
    """SPEC 5.3: page shows 'No Readings Yet' when there is no data."""
    resp = client.get("/")
    assert "No Readings Yet" in resp.text
    assert "weather station is setting up" in resp.text.lower()


def test_home_shows_weather_with_data(client, weather_data):
    """SPEC 5.1: weather node readings appear on the home page."""
    resp = client.get("/")
    assert "weather-main" in resp.text
    assert "Current Conditions" in resp.text


def test_home_shows_soil_with_data(client, soil_data):
    """SPEC 5.1: soil node readings appear on the home page."""
    resp = client.get("/")
    assert "soil-bed-3" in resp.text


def test_home_shows_soil_temperature(client, soil_data):
    """SPEC 5.1: soil temperature is displayed."""
    resp = client.get("/")
    assert "11.0" in resp.text


def test_home_shows_soil_moisture(client, soil_data):
    """SPEC 5.1: soil moisture percentage is displayed."""
    resp = client.get("/")
    assert "Moisture" in resp.text


def test_home_shows_weather_temperature(client, weather_data):
    """SPEC 5.1: weather temperature is displayed."""
    resp = client.get("/")
    assert "21.5" in resp.text


def test_home_shows_humidity(client, weather_data):
    """SPEC 5.1: humidity reading is displayed."""
    resp = client.get("/")
    assert "Humidity" in resp.text


def test_home_hides_soil_empty_with_data(client, soil_data):
    """SPEC 5.1: when soil data exists, soil node is shown (not hidden)."""
    resp = client.get("/")
    assert "soil-bed-3" in resp.text


def test_home_hides_weather_empty_with_data(client, weather_data):
    """When weather data exists, the weather section is shown (not hidden)."""
    resp = client.get("/")
    assert "weather-main" in resp.text
    assert "Current Conditions" in resp.text


def test_home_multiple_weather_nodes(client, db):
    """Multiple weather nodes each get their own card."""
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
        "weather-garden",
        "weather",
        now,
        {"temp_c": 19.0, "humidity_pct": 70.0},
        battery_v=3.80,
        rssi_dbm=-60,
    )
    resp = client.get("/")
    assert "weather-main" in resp.text
    assert "weather-garden" in resp.text


def test_home_weather_empty_when_no_weather(client, soil_data):
    """When only soil data exists, weather empty state is shown."""
    resp = client.get("/")
    assert "No Weather Data" in resp.text


def test_home_soil_empty_when_no_soil(client, weather_data):
    """When only weather data exists, soil empty state is shown."""
    resp = client.get("/")
    assert "No Soil Data" in resp.text


def test_home_has_semantic_structure(client, weather_data):
    """The page uses semantic HTML elements."""
    resp = client.get("/")
    assert "<header" in resp.text
    assert "<main" in resp.text
    assert "<footer" in resp.text
    assert '<section class="card">' in resp.text


def test_home_has_viewport_meta(client):
    """SPEC 5.4: page includes viewport meta tag."""
    resp = client.get("/")
    assert '<meta name="viewport"' in resp.text
    assert "width=device-width" in resp.text


def test_home_still_has_base_structure_with_data(client, weather_data):
    """Even with data, the page retains base template structure."""
    resp = client.get("/")
    assert '<html lang="en"' in resp.text
    assert '<header class="header">' in resp.text
    assert '<footer class="footer">' in resp.text
    assert "/static/style.css" in resp.text


def test_home_no_readings_still_has_bubbles(client):
    """Even in empty state, bubble decorations are present."""
    resp = client.get("/")
    assert resp.text.count('class="bubble"') == 4


def test_home_with_both_data_shows_both_sections(client, mixed_data):
    """When both weather and soil data exist, both sections are visible."""
    resp = client.get("/")
    assert "Current Conditions" in resp.text
    assert "Latest Soil Readings" in resp.text
    assert "No Readings Yet" not in resp.text


def test_home_pressure_shown(client, weather_data):
    """SPEC 5.1: pressure reading is displayed."""
    resp = client.get("/")
    assert "1013.4" in resp.text
    assert "Pressure" in resp.text


def test_home_responsive_structure(client):
    """SPEC 5.4: page renders valid HTML structure for responsive design."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Should have a container element for responsive layout
    assert '<main class="container">' in resp.text


def test_home_stats_row_present(client, weather_data):
    """Weather cards use stats-row grid for metric display."""
    resp = client.get("/")
    assert 'class="stats-row"' in resp.text


def test_home_stat_cards_present(client, weather_data):
    """Each weather metric is displayed in a stat-card."""
    resp = client.get("/")
    assert 'class="stat-card"' in resp.text
