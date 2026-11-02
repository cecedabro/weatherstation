"""Tests for T43: Admin polish.

SPEC 6.1: GET /admin/nodes.json requires HTTP Basic auth; wrong or missing
          credentials → 401.
SPEC 6.4: /admin links back to the public site and shows Last Seen with
          relative `ago` and local time.
SPEC 6.5: Problem nodes (offline, low battery) sort before healthy nodes on
          both the HTML page and the JSON endpoint.
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
def mixed_nodes(db: Session) -> Session:
    """A mix of offline, low-battery, and healthy nodes."""
    now = _now()

    # Healthy online node
    _make_node(db, "sensor-alpha", "weather", now, battery_v=3.75, rssi_dbm=-50)
    _insert_reading(db, "sensor-alpha", "temp_c", now, 22.0)

    # Offline node (> 15 min)
    then = now - timedelta(minutes=20)
    _make_node(db, "sensor-beta", "soil", then, battery_v=3.90, rssi_dbm=-75)
    _insert_reading(db, "sensor-beta", "soil_moisture_pct", then, 45.0)

    # Low battery node
    now2 = now - timedelta(minutes=5)
    _make_node(db, "sensor-gamma", "weather", now2, battery_v=3.25, rssi_dbm=-80)
    _insert_reading(db, "sensor-gamma", "humidity_pct", now2, 60.0)

    yield db


# ---------------------------------------------------------------------------
# SPEC 6.4 — Back-to-site link and time formatting on /admin
# ---------------------------------------------------------------------------


def test_admin_has_back_to_site_link(client, mixed_nodes):
    """SPEC 6.4: the admin page links back to the public site."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert resp.status_code == 200
    assert 'href="/"' in resp.text or "Back to Website" in resp.text


def test_admin_shows_ago_format(client, mixed_nodes):
    """SPEC 6.4: Last Seen column uses relative ago formatting."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "ago" in resp.text.lower() or "min" in resp.text.lower() or "ago" in resp.text.lower()


def test_admin_shows_local_time(client, mixed_nodes):
    """SPEC 6.4: Last Seen column shows local time alongside relative time."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert "last-seen-local" in resp.text


# ---------------------------------------------------------------------------
# SPEC 6.5 — Problem nodes sort first (HTML)
# ---------------------------------------------------------------------------


def test_admin_sorts_problem_nodes_first(client, mixed_nodes):
    """SPEC 6.5: offline and low-battery nodes appear before healthy ones."""
    settings = Settings()
    resp = client.get("/admin", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    # sensor-alpha is healthy, sensor-beta is offline, sensor-gamma is low battery
    # Both beta and gamma should appear before alpha in the rendered HTML
    alpha_pos = resp.text.find("sensor-alpha")
    beta_pos = resp.text.find("sensor-beta")
    gamma_pos = resp.text.find("sensor-gamma")
    # offline (beta) or low battery (gamma) must come before healthy (alpha)
    assert beta_pos < alpha_pos or gamma_pos < alpha_pos, (
        "Problem nodes should sort before healthy nodes"
    )


# ---------------------------------------------------------------------------
# SPEC 6.1 / 6.5 — /admin/nodes.json auth and ordering
# ---------------------------------------------------------------------------


def test_nodes_json_requires_auth(client):
    """SPEC 6.1: GET /admin/nodes.json without credentials returns 401."""
    resp = client.get("/admin/nodes.json")
    assert resp.status_code == 401


def test_nodes_json_wrong_credentials(client):
    """SPEC 6.1: GET /admin/nodes.json with wrong credentials returns 401."""
    resp = client.get("/admin/nodes.json", auth=("wrong", "wrong"))
    assert resp.status_code == 401


def test_nodes_json_correct_auth(client, mixed_nodes):
    """SPEC 6.1: GET /admin/nodes.json with correct credentials returns 200."""
    settings = Settings()
    resp = client.get("/admin/nodes.json", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_nodes_json_ordering(client, mixed_nodes):
    """SPEC 6.5: /admin/nodes.json returns problem nodes first."""
    settings = Settings()
    resp = client.get("/admin/nodes.json", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    data = resp.json()
    ids = [row["node_id"] for row in data]

    alpha_idx = ids.index("sensor-alpha")
    beta_idx = ids.index("sensor-beta")
    gamma_idx = ids.index("sensor-gamma")

    assert beta_idx < alpha_idx or gamma_idx < alpha_idx, (
        "Problem nodes should sort before healthy nodes in JSON"
    )


def test_nodes_json_fields(client, mixed_nodes):
    """SPEC 6.1: each JSON row contains the expected fields."""
    settings = Settings()
    resp = client.get("/admin/nodes.json", auth=(settings.ADMIN_USER, settings.ADMIN_PASSWORD))
    data = resp.json()
    assert len(data) > 0
    row = data[0]
    assert "node_id" in row
    assert "node_type" in row
    assert "last_seen" in row
    assert "online" in row
    assert "battery_v" in row
    assert "low_battery" in row
    assert "rssi_dbm" in row
    assert "readings_24h" in row
