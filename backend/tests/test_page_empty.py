"""Tests for home page empty states per SPEC 5.3 (T22).

SPEC 5.3: The site degrades gracefully when there is no data yet (no error page;
          a friendly "no readings yet" state).

The empty-state behaviour:
  - No data at all          → single "No Readings Yet" card only
  - Weather data only       → "No Soil Data" (not "No Weather Data")
  - Soil data only          → "No Weather Data" (not "No Soil Data")
  - Both weather and soil   → no empty-state cards at all
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
def weather_only(db: Session) -> Session:
    """A weather node with current readings, no soil data."""
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
def soil_only(db: Session) -> Session:
    """A soil node with current readings, no weather data."""
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


# ---------------------------------------------------------------------------
# Tests: no data at all
# ---------------------------------------------------------------------------


def test_no_data_only_readings_yet(client) -> None:
    """When there is no data at all, only "No Readings Yet" appears.

    The individual "No Weather Data" and "No Soil Data" messages must NOT
    appear because there is nothing to partially display.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No Readings Yet" in resp.text
    assert "No Weather Data" not in resp.text
    assert "No Soil Data" not in resp.text


def test_no_data_has_friendly_message(client) -> None:
    """SPEC 5.3: the empty state is friendly, not an error page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "weather station is setting up" in resp.text.lower()
    assert "error" not in resp.text.lower()


# ---------------------------------------------------------------------------
# Tests: weather data only
# ---------------------------------------------------------------------------


def test_weather_only_shows_soil_empty(client, weather_only) -> None:
    """When only weather data exists, "No Soil Data" is shown."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No Soil Data" in resp.text
    assert "soil-bed" not in resp.text.lower()  # no soil node content


def test_weather_only_no_weather_empty(client, weather_only) -> None:
    """When only weather data exists, "No Weather Data" must NOT appear."""
    resp = client.get("/")
    assert "No Weather Data" not in resp.text
    # Weather data should be visible
    assert "weather-main" in resp.text
    assert "Current Conditions" in resp.text


def test_weather_only_no_generic_empty(client, weather_only) -> None:
    """When some data exists, the generic "No Readings Yet" must NOT appear."""
    resp = client.get("/")
    assert "No Readings Yet" not in resp.text


# ---------------------------------------------------------------------------
# Tests: soil data only
# ---------------------------------------------------------------------------


def test_soil_only_shows_weather_empty(client, soil_only) -> None:
    """When only soil data exists, "No Weather Data" is shown."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No Weather Data" in resp.text
    assert "weather-main" not in resp.text


def test_soil_only_no_soil_empty(client, soil_only) -> None:
    """When only soil data exists, "No Soil Data" must NOT appear."""
    resp = client.get("/")
    assert "No Soil Data" not in resp.text
    # Soil data should be visible
    assert "soil-bed-3" in resp.text


def test_soil_only_no_generic_empty(client, soil_only) -> None:
    """When some data exists, the generic "No Readings Yet" must NOT appear."""
    resp = client.get("/")
    assert "No Readings Yet" not in resp.text


# ---------------------------------------------------------------------------
# Tests: both weather and soil
# ---------------------------------------------------------------------------


@pytest.fixture()
def both_data(db: Session) -> Session:
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


def test_both_data_no_empty_states(client, both_data) -> None:
    """When both weather and soil data exist, no empty-state cards appear."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No Readings Yet" not in resp.text
    assert "No Weather Data" not in resp.text
    assert "No Soil Data" not in resp.text
    # Both data sections must be visible
    assert "weather-main" in resp.text
    assert "soil-bed-3" in resp.text
    assert "Current Conditions" in resp.text
    assert "Latest Soil Readings" in resp.text


def test_empty_state_count(client, weather_only) -> None:
    """When only one type of data exists, exactly one empty-state card is shown."""
    resp = client.get("/")
    empty_states = resp.text.count('class="empty-state"')
    assert empty_states == 1, (
        f"Expected exactly 1 empty-state card, got {empty_states}: "
        f"{resp.text[resp.text.find('empty-state') - 50 : resp.text.find('empty-state') + 200]}"
    )


def test_empty_state_count_no_data(client) -> None:
    """When no data exists, exactly one empty-state card ("No Readings Yet") is shown."""
    resp = client.get("/")
    empty_states = resp.text.count('class="empty-state"')
    assert empty_states == 1, (
        f"Expected exactly 1 empty-state card when no data, got {empty_states}"
    )
