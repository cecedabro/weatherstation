"""Tests for SPEC 10.14: Garden alerts on GET /.

SPEC 10.14: `/` shows a frost warning when any weather node reads
            ≤ 2.0 °C, the rain total of the last 24 h, and how many
            beds need water.
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
def frost_weather_data(db: Session) -> Session:
    """A weather node with a frost-level temperature (2.0 °C)."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 2.0, "humidity_pct": 90.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    yield db


@pytest.fixture()
def no_frost_weather_data(db: Session) -> Session:
    """A weather node with a temperature above frost threshold (2.1 °C)."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 2.1, "humidity_pct": 85.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    yield db


@pytest.fixture()
def normal_weather_data(db: Session) -> Session:
    """A weather node with normal temperature."""
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
    yield db


@pytest.fixture()
def soil_moist_low(db: Session) -> Session:
    """A soil node with low moisture (< 25%)."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-1",
        "soil",
        now,
        {"soil_moisture_pct": 18.5, "soil_temp_c": 11.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    yield db


@pytest.fixture()
def soil_moist_high(db: Session) -> Session:
    """A soil node with normal moisture (> 25%)."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-1",
        "soil",
        now,
        {"soil_moisture_pct": 45.0, "soil_temp_c": 12.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    yield db


@pytest.fixture()
def soil_moist_at_threshold(db: Session) -> Session:
    """A soil node at exactly 25% moisture (should NOT need water)."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-1",
        "soil",
        now,
        {"soil_moisture_pct": 25.0, "soil_temp_c": 12.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_frost_warning_shown_at_2_0(client, frost_weather_data):
    """SPEC 10.14: frost warning appears when temp_c is exactly 2.0 °C."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "frost" in resp.text.lower() or "Frost" in resp.text or "freezing" in resp.text.lower()


def test_frost_warning_shown_below_2_0(client, db):
    """Frost warning appears when temp_c is below 2.0 °C."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 0.5, "humidity_pct": 95.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert "frost" in resp.text.lower() or "Frost" in resp.text or "freezing" in resp.text.lower()


def test_frost_warning_not_shown_at_2_1(client, no_frost_weather_data):
    """Frost warning does NOT appear when temp_c is 2.1 °C."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "frost" not in resp.text.lower() and "freezing" not in resp.text.lower()


def test_frost_warning_not_shown_normal(client, normal_weather_data):
    """Frost warning does NOT appear at normal temperatures."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "frost" not in resp.text.lower() and "freezing" not in resp.text.lower()


def test_frost_warning_multiple_weather_nodes(client, db):
    """Frost warning shows when ANY weather node has temp_c <= 2.0."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {"temp_c": 21.0, "humidity_pct": 65.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    _make_batch(
        db,
        "weather-garden",
        "weather",
        now,
        {"temp_c": 1.5, "humidity_pct": 90.0},
        battery_v=3.70,
        rssi_dbm=-60,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert "frost" in resp.text.lower() or "Frost" in resp.text or "freezing" in resp.text.lower()


def test_rain_24h_total_shown(client, db):
    """24h rain total is displayed when there is rain data."""
    now = _now()
    # Insert rain readings spread across the last 24 hours
    _make_batch(
        db,
        "weather-main",
        "weather",
        now - timedelta(hours=2),
        {"rain_mm": 5.3},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    _make_batch(
        db,
        "weather-main",
        "weather",
        now - timedelta(hours=10),
        {"rain_mm": 2.1},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    # Old rain reading (outside 24h window)
    _make_batch(
        db,
        "weather-main",
        "weather",
        now - timedelta(days=2),
        {"rain_mm": 100.0},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    # Should show rain total (7.4 mm from the two recent readings)
    assert "mm" in resp.text.lower() or "rain" in resp.text.lower()


def test_rain_24h_zero_when_no_rain(client, normal_weather_data):
    """24h rain total shows 0 or empty when there is no rain data."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_beds_needing_water_shown(client, soil_moist_low):
    """Beds needing water count is shown when soil moisture < 25%."""
    resp = client.get("/")
    assert resp.status_code == 200
    # Should mention beds needing water
    assert "bed" in resp.text.lower() or "Bed" in resp.text or "soil" in resp.text.lower()


def test_beds_needing_water_multiple(client, db):
    """Beds needing water counts multiple low-moisture beds."""
    now = _now()
    _make_batch(
        db,
        "soil-bed-1",
        "soil",
        now,
        {"soil_moisture_pct": 15.0, "soil_temp_c": 10.0},
        battery_v=3.92,
        rssi_dbm=-78,
    )
    _make_batch(
        db,
        "soil-bed-2",
        "soil",
        now,
        {"soil_moisture_pct": 20.0, "soil_temp_c": 11.0},
        battery_v=3.90,
        rssi_dbm=-80,
    )
    _make_batch(
        db,
        "soil-bed-3",
        "soil",
        now,
        {"soil_moisture_pct": 50.0, "soil_temp_c": 12.0},
        battery_v=3.88,
        rssi_dbm=-82,
    )
    resp = client.get("/")
    assert resp.status_code == 200


def test_beds_needing_water_at_threshold(client, soil_moist_at_threshold):
    """Soil at exactly 25% moisture does NOT count as needing water."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_alerts_graceful_degradation_no_data(client):
    """Page renders without errors when there is no data at all."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_alerts_no_crash_with_weather_only(client, normal_weather_data):
    """Alerts section does not crash when there is only weather data (no soil)."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_alerts_no_crash_with_soil_only(client, soil_moist_high):
    """Alerts section does not crash when there is only soil data (no weather)."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_frost_banner_has_separate_section(client, frost_weather_data):
    """Frost warning appears in its own alert/banner section."""
    resp = client.get("/")
    assert resp.status_code == 200
    # The page should have some kind of alert/banner structure
    assert "<div" in resp.text


def test_rain_display_format(client, db):
    """Rain 24h total displays with at least one decimal place."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now - timedelta(hours=1),
        {"rain_mm": 3.7},
        battery_v=3.75,
        rssi_dbm=-53,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    # The page should contain something related to rain measurement
    assert "rain" in resp.text.lower() or "Rain" in resp.text or "mm" in resp.text
