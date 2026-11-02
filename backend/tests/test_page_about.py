"""Tests for GET /about page (T38).

SPEC 10.8: `GET /about` renders an HTML page showing the station description,
            data path diagram, units table, and a registry of known nodes.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_about_page_loads(client):
    """GET /about renders an HTML page with HTTP 200."""
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_about_empty_state_without_nodes(client):
    """SPEC 10.8: page shows 'No sensor nodes registered yet' when no nodes."""
    resp = client.get("/about")
    body = resp.text
    assert "No sensor nodes registered yet" in body


def test_about_shows_station_description(client):
    """SPEC 10.8: station description is present."""
    resp = client.get("/about")
    body = resp.text
    assert "Garden Weather Station" in body
    assert "volkstuin" in body


def test_about_shows_data_path(client):
    """SPEC 10.8: data path diagram elements are rendered."""
    resp = client.get("/about")
    body = resp.text
    assert "ESP32 Nodes" in body
    assert "Raspberry Pi" in body
    assert "Backend (k3s)" in body
    assert "Website" in body


def test_about_shows_units_table(client):
    """SPEC 10.8: units table contains expected units."""
    resp = client.get("/about")
    body = resp.text
    assert "°C" in body
    assert "hPa" in body
    assert "mm" in body
    assert "m/s" in body
    assert "dBm" in body


def test_about_node_table_headers(db: Session, client):
    """SPEC 10.8: node registry table has correct headers."""
    db.add(Node(node_id="x", node_type="y", first_seen=_now(), last_seen=_now()))
    db.flush()
    resp = client.get("/about")
    body = resp.text
    assert "Node ID" in body
    assert "Type" in body
    assert "First Seen" in body
    assert "Last Seen" in body
    assert "Status" in body


def test_about_shows_online_node(db: Session, client):
    """SPEC 10.8: recent node shows Online badge."""
    node = Node(
        node_id="sensor-garden-1",
        node_type="weather",
        first_seen=_now(),
        last_seen=_now(),
    )
    db.add(node)
    db.flush()

    resp = client.get("/about")
    body = resp.text
    assert "sensor-garden-1" in body
    assert "Online" in body


def test_about_shows_offline_node(db: Session, client):
    """SPEC 10.8: node older than 15 min shows Offline badge."""
    old_time = _now() - timedelta(minutes=20)
    node = Node(
        node_id="sensor-garden-2",
        node_type="wind",
        first_seen=old_time,
        last_seen=old_time,
    )
    db.add(node)
    db.flush()

    resp = client.get("/about")
    body = resp.text
    assert "sensor-garden-2" in body
    assert "Offline" in body


def test_about_shows_multiple_nodes(db: Session, client):
    """SPEC 10.8: multiple nodes each appear in the table."""
    now = _now()
    n1 = Node(node_id="node-a", node_type="weather", first_seen=now, last_seen=now)
    n2 = Node(node_id="node-b", node_type="soil", first_seen=now, last_seen=now)
    db.add_all([n1, n2])
    db.flush()

    resp = client.get("/about")
    body = resp.text
    assert "node-a" in body
    assert "node-b" in body
