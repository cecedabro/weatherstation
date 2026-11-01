"""Tests for current-conditions and latest-soil sections on GET / (T13).

SPEC 5.1: GET / renders an HTML page showing current conditions for each weather
          node and the latest soil readings.
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
# Tests — SPEC 5.1: current conditions and latest soil readings
# ---------------------------------------------------------------------------


def test_current_conditions_section_header(client, weather_data):
    """SPEC 5.1: the 'Current Conditions' section header is rendered."""
    resp = client.get("/")
    assert "Current Conditions" in resp.text


def test_current_conditions_shows_weather_node_id(client, weather_data):
    """SPEC 5.1: weather node ID appears in the current conditions section."""
    resp = client.get("/")
    assert "weather-main" in resp.text


def test_current_conditions_shows_temperature(client, weather_data):
    """SPEC 5.1: temperature value from weather node is displayed."""
    resp = client.get("/")
    assert "21.5" in resp.text


def test_current_conditions_shows_humidity(client, weather_data):
    """SPEC 5.1: humidity reading from weather node is displayed."""
    resp = client.get("/")
    assert "Humidity" in resp.text
    assert "65.0" in resp.text


def test_current_conditions_shows_pressure(client, weather_data):
    """SPEC 5.1: pressure reading from weather node is displayed."""
    resp = client.get("/")
    assert "Pressure" in resp.text
    assert "1013.4" in resp.text


def test_latest_soil_section_header(client, soil_data):
    """SPEC 5.1: the 'Latest Soil Readings' section header is rendered."""
    resp = client.get("/")
    assert "Latest Soil Readings" in resp.text


def test_latest_soil_shows_soil_node_id(client, soil_data):
    """SPEC 5.1: soil node ID appears in the latest soil section."""
    resp = client.get("/")
    assert "soil-bed-3" in resp.text


def test_latest_soil_shows_moisture(client, soil_data):
    """SPEC 5.1: soil moisture percentage is displayed."""
    resp = client.get("/")
    assert "Moisture" in resp.text


def test_latest_soil_shows_temperature(client, soil_data):
    """SPEC 5.1: soil temperature is displayed with value."""
    resp = client.get("/")
    assert "11.0" in resp.text


def test_soil_section_when_no_soil_data(client, weather_data):
    """SPEC 5.1: 'No Soil Data' empty state when soil node has no readings."""
    resp = client.get("/")
    assert "No Soil Data" in resp.text


def test_weather_section_when_no_weather_data(client, soil_data):
    """SPEC 5.1: 'No Weather Data' empty state when weather node has no readings."""
    resp = client.get("/")
    assert "No Weather Data" in resp.text


def test_both_sections_visible_with_mixed_data(client, mixed_data):
    """SPEC 5.1: when both data types exist, both sections are visible."""
    resp = client.get("/")
    assert "Current Conditions" in resp.text
    assert "Latest Soil Readings" in resp.text
    assert "No Readings Yet" not in resp.text


def test_no_global_empty_state_when_data_exists(client, mixed_data):
    """SPEC 5.1: global 'No Readings Yet' is hidden when any data exists."""
    resp = client.get("/")
    assert "No Readings Yet" not in resp.text


def test_multiple_weather_nodes_in_current_conditions(client, db):
    """SPEC 5.1: multiple weather nodes each appear in current conditions."""
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
    assert "21.5" in resp.text
    assert "19.0" in resp.text


def test_multiple_soil_nodes_in_latest_soil(client, db):
    """SPEC 5.1: multiple soil nodes each appear in latest soil section."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-3",
        "soil",
        now,
        {"soil_moisture_pct": 38.5},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    _make_batch(
        db,
        "soil-bed-7",
        "soil",
        now,
        {"soil_moisture_pct": 42.0},
        battery_v=3.88,
        rssi_dbm=-72,
    )
    resp = client.get("/")
    assert "soil-bed-3" in resp.text
    assert "soil-bed-7" in resp.text
    assert "38" in resp.text
    assert "42" in resp.text
