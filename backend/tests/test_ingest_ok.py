"""Happy path tests for POST /api/v1/readings per SPEC 3.1."""

import json
import pathlib

from sqlalchemy import func, select

from app.models import Node, Reading

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_WEATHER = json.loads((_ROOT / "contract" / "samples" / "weather_valid.json").read_text())
_SOIL = json.loads((_ROOT / "contract" / "samples" / "soil_valid.json").read_text())


def test_single_weather_batch_accepted(client, db):
    """SPEC 3.1: a single weather batch is accepted and stored."""
    client.post(
        "/api/v1/readings",
        json={"readings": [_WEATHER]},
        headers={"Authorization": "Bearer dev-token"},
    )

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 6

    node = db.get(Node, "weather-main")
    assert node is not None
    assert node.node_type == "weather"


def test_single_soil_batch_accepted(client, db):
    """SPEC 3.1: a single soil batch is accepted and stored."""
    client.post(
        "/api/v1/readings",
        json={"readings": [_SOIL]},
        headers={"Authorization": "Bearer dev-token"},
    )

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 2

    node = db.get(Node, "soil-bed-3")
    assert node is not None
    assert node.node_type == "soil"


def test_multiple_batches_accepted(client, db):
    """SPEC 3.1: multiple valid batches in one request are all accepted."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [_WEATHER, _SOIL]},
        headers={"Authorization": "Bearer dev-token"},
    )
    data = resp.json()

    assert resp.status_code == 200
    assert data["accepted"] == 2
    assert data["rejected"] == []

    count = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert count == 8


def test_response_format(client):
    """SPEC 3.1: response has accepted count and empty rejected list."""
    resp = client.post(
        "/api/v1/readings",
        json={"readings": [_WEATHER]},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "accepted" in data
    assert "rejected" in data
    assert isinstance(data["accepted"], int)
    assert isinstance(data["rejected"], list)
    assert data["accepted"] == 1
    assert data["rejected"] == []


def test_reading_values_stored_correctly(client, db):
    """SPEC 3.1: metric values are stored correctly after ingestion."""
    client.post(
        "/api/v1/readings",
        json={"readings": [_WEATHER]},
        headers={"Authorization": "Bearer dev-token"},
    )

    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    temps = [r for r in rows if r.metric == "temp_c"]
    assert len(temps) == 1
    assert float(temps[0].value) == 14.2

    humid = [r for r in rows if r.metric == "humidity_pct"]
    assert len(humid) == 1
    assert float(humid[0].value) == 71.0


def test_node_registry_updated_on_ingest(client, db):
    """SPEC 3.1: the node registry is updated with last_seen, battery, rssi."""
    client.post(
        "/api/v1/readings",
        json={"readings": [_WEATHER]},
        headers={"Authorization": "Bearer dev-token"},
    )

    node = db.get(Node, "weather-main")
    assert node is not None
    assert node.last_battery_v is None
    assert node.last_rssi_dbm == -61
