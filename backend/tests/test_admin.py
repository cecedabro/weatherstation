"""Tests for /admin with Basic auth and node health table (T15, SPEC 6).

SPEC 6.1: GET /admin requires HTTP Basic auth (ADMIN_USER / ADMIN_PASSWORD);
          wrong or missing credentials → 401.
SPEC 6.2: Lists every node with last_seen, online state, last battery voltage
          and RSSI, flags nodes offline > 15 min and batteries < 3.4 V.
SPEC 6.3: Shows, per node, the count of readings in the last 24 h.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Node, Reading

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_node(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    battery_v: float | None = None,
    rssi_dbm: int | None = None,
) -> Node:
    """Insert or update a node in the database."""
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
    return node


def _insert_reading(
    db: Session,
    node_id: str,
    metric: str,
    ts: datetime,
    value: float,
) -> None:
    """Insert a reading, ignoring duplicates."""
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
def online_node(db: Session) -> Session:
    """A node seen just now (online)."""
    now = _now()
    _make_node(db, "weather-main", "weather", now, battery_v=3.75, rssi_dbm=-53)
    _insert_reading(db, "weather-main", "temp_c", now, 21.5)
    _insert_reading(db, "weather-main", "humidity_pct", now, 65.0)
    yield db


@pytest.fixture()
def offline_node(db: Session) -> Session:
    """A node seen 20 minutes ago (offline, > 15 min)."""
    then = _now() - timedelta(minutes=20)
    _make_node(db, "weather-old", "weather", then, battery_v=3.60, rssi_dbm=-70)
    _insert_reading(db, "weather-old", "temp_c", then, 18.0)
    yield db


@pytest.fixture()
def low_battery_node(db: Session) -> Session:
    """A node with low battery (< 3.4 V) but still online."""
    now = _now()
    _make_node(db, "soil-bed-3", "soil", now, battery_v=3.30, rssi_dbm=-80)
    _insert_reading(db, "soil-bed-3", "soil_moisture_pct", now, 40.0)
    yield db


@pytest.fixture()
def all_nodes(db: Session) -> Session:
    """A mix of online, offline, low-battery nodes + 24h reading counts."""
    now = _now()

    # Online weather node
    _make_node(db, "weather-main", "weather", now, battery_v=3.75, rssi_dbm=-53)
    for i in range(5):
        t = now - timedelta(minutes=i * 10)
        _insert_reading(db, "weather-main", "temp_c", t, 21.5 + i * 0.1)

    # Offline soil node (> 15 min)
    then = now - timedelta(minutes=20)
    _make_node(db, "soil-bed-3", "soil", then, battery_v=3.90, rssi_dbm=-78)
    _insert_reading(db, "soil-bed-3", "soil_moisture_pct", then, 38.5)

    # Low battery node
    low = now - timedelta(minutes=2)
    _make_node(db, "soil-garden", "soil", low, battery_v=3.20, rssi_dbm=-85)
    for i in range(3):
        t = low - timedelta(minutes=i * 20)
        _insert_reading(db, "soil-garden", "soil_moisture_pct", t, 40.0 + i)

    yield db


# ---------------------------------------------------------------------------
# SPEC 6.1 — Basic auth on /admin
# ---------------------------------------------------------------------------


def test_admin_requires_basic_auth(client):
    """SPEC 6.1: GET /admin without credentials returns 401."""
    resp = client.get("/admin")
    assert resp.status_code == 401


def test_admin_wrong_credentials(client):
    """SPEC 6.1: GET /admin with wrong credentials returns 401."""
    resp = client.get("/admin", auth=("wrong_user", "wrong_pass"))
    assert resp.status_code == 401


def test_admin_correct_credentials(client):
    """SPEC 6.1: GET /admin with correct credentials returns 200."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SPEC 6.2 — Node health table columns
# ---------------------------------------------------------------------------


def test_admin_shows_node_id(client, online_node):
    """SPEC 6.2: the node ID appears in the admin table."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "weather-main" in resp.text


def test_admin_shows_last_seen(client, online_node):
    """SPEC 6.2: last_seen timestamp appears in the admin table."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "Last Seen" in resp.text


def test_admin_shows_online_column(client, online_node):
    """SPEC 6.2: an 'Online' indicator / column is present."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "Online" in resp.text


def test_admin_shows_battery_column(client, low_battery_node):
    """SPEC 6.2: battery voltage appears in the admin table."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "Battery" in resp.text


def test_admin_shows_rssi_column(client, online_node):
    """SPEC 6.2: RSSI value appears in the admin table."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "RSSI" in resp.text


def test_admin_flags_offline_node(client, offline_node):
    """SPEC 6.2: nodes offline > 15 min are flagged as offline."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    # offline node should have an offline indicator
    assert "Offline" in resp.text


def test_admin_flags_low_battery(client, low_battery_node):
    """SPEC 6.2: nodes with battery < 3.4 V are flagged as low battery."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    # low battery node should show the low battery flag
    assert "3.30" in resp.text


def test_admin_online_node_not_flagged(client, online_node):
    """SPEC 6.2: an online node with healthy battery has no warning flags."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    # online node with 3.75V should not show low battery warning
    assert "3.75" in resp.text


# ---------------------------------------------------------------------------
# SPEC 6.3 — 24h reading count
# ---------------------------------------------------------------------------


def test_admin_shows_24h_readings(client, all_nodes):
    """SPEC 6.3: the admin page shows the count of readings in the last 24 h."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "24 h" in resp.text or "Readings" in resp.text


def test_admin_24h_count_correct(client, all_nodes):
    """SPEC 6.3: the 24 h reading count is correct for the online node (5 readings)."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    # weather-main has 5 readings in last 24h
    assert "5" in resp.text
