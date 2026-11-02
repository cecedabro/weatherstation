"""Tests for GET /api/v1/nodes per SPEC 4.3.

SPEC 4.3: `GET /api/v1/nodes` returns the contract fields (see contract tests),
with `online` true iff `last_seen` is within 15 minutes of now.
"""

from datetime import UTC, datetime, timedelta

from app.models import Node


def _now() -> datetime:
    return datetime.now(UTC)


def test_nodes_empty_list(client):
    """SPEC 4.3: returns an empty list when no nodes exist."""
    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_nodes_online_14_minutes(client, db):
    """SPEC 4.3: online=true when last_seen is 14 minutes ago (within 15 min)."""
    now = _now()
    node = Node(
        node_id="weather-main",
        node_type="weather",
        first_seen=now,
        last_seen=now - timedelta(minutes=14),
    )
    db.add(node)
    db.flush()

    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "weather-main"
    assert data[0]["online"] is True


def test_nodes_offline_16_minutes(client, db):
    """SPEC 4.3: online=false when last_seen is 16 minutes ago (outside 15 min)."""
    now = _now()
    node = Node(
        node_id="weather-main",
        node_type="weather",
        first_seen=now,
        last_seen=now - timedelta(minutes=16),
    )
    db.add(node)
    db.flush()

    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "weather-main"
    assert data[0]["online"] is False


def test_nodes_contract_fields(client, db):
    """SPEC 4.3: each node has the required contract field names."""
    now = _now()
    node = Node(
        node_id="soil-bed-3",
        node_type="soil",
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.flush()

    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    row = data[0]
    # Contract requires: node_id, node_type, last_seen, online
    required = {"node_id", "node_type", "last_seen", "online"}
    assert required.issubset(row), f"Missing fields: {required - set(row)}"
    assert isinstance(row["node_id"], str)
    assert isinstance(row["node_type"], str)
    assert isinstance(row["last_seen"], str)
    assert isinstance(row["online"], bool)


def test_nodes_multiple_with_online_status(client, db):
    """SPEC 4.3: returns all nodes with correct online status per boundary."""
    now = _now()
    # Online node (last seen 10 min ago, within 15 min)
    online_node = Node(
        node_id="weather-main",
        node_type="weather",
        first_seen=now - timedelta(hours=1),
        last_seen=now - timedelta(minutes=10),
    )
    # Offline node (last seen 20 min ago, outside 15 min)
    offline_node = Node(
        node_id="soil-bed-3",
        node_type="soil",
        first_seen=now - timedelta(hours=1),
        last_seen=now - timedelta(minutes=20),
    )
    db.add(online_node)
    db.add(offline_node)
    db.flush()

    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    online = next(e for e in data if e["node_id"] == "weather-main")
    assert online["online"] is True

    offline = next(e for e in data if e["node_id"] == "soil-bed-3")
    assert offline["online"] is False
