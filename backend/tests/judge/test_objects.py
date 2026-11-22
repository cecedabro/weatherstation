"""Acceptance tests for the garden map data API (SPEC §12, roadmap loop G). Human-owned."""

import pytest

from app.models import Task

from ._helpers import add_node, add_readings, auth, hours_ago

pytestmark = pytest.mark.task("G11")  # the whole feature; G11 makes it pass


def test_create_read_update_delete(client, db):
    add_node(db, "soil-1", "soil")
    body = {
        "kind": "bed",
        "name": "Bed 1",
        "x": 2,
        "y": 3,
        "w": 1.2,
        "d": 4,
        "props": {"soil": "loam", "raised": True},
    }
    r = client.post("/api/v1/objects", json=body, auth=auth())
    assert r.status_code == 201, r.text
    o = r.json()
    assert (o["kind"], o["name"], o["x"], o["w"], o["h"]) == ("bed", "Bed 1", 2.0, 1.2, 0.2)
    assert o["props"] == {"soil": "loam", "raised": True}

    r = client.patch(
        f"/api/v1/objects/{o['id']}",
        json={"x": 2.5, "rotation": 370, "props": {"sun_hours": 6}},
        auth=auth(),
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["x"], p["y"], p["rotation"], p["name"]) == (2.5, 3.0, 10.0, "Bed 1")
    assert p["props"] == {"sun_hours": 6.0}  # props are replaced as a whole

    assert client.get(f"/api/v1/objects/{o['id']}", auth=auth()).json() == p
    assert [x["id"] for x in client.get("/api/v1/objects?kind=bed", auth=auth()).json()] == [
        o["id"]
    ]
    assert client.get("/api/v1/objects?kind=tree", auth=auth()).json() == []

    r = client.post(
        "/api/v1/objects",
        json={"kind": "sensor", "name": "Probe", "x": 1, "y": 1, "node_id": "soil-1"},
        auth=auth(),
    )
    assert r.status_code == 201 and r.json()["node_id"] == "soil-1"
    assert len(client.get("/api/v1/objects", auth=auth()).json()) == 2

    assert client.delete(f"/api/v1/objects/{o['id']}", auth=auth()).status_code == 204
    assert client.get(f"/api/v1/objects/{o['id']}", auth=auth()).status_code == 404


def test_errors(client, db):
    r = client.post(
        "/api/v1/objects",
        json={"kind": "castle", "name": "", "w": 0, "props": {"x": 1}},
        auth=auth(),
    )
    assert r.status_code == 400
    assert r.json() == {
        "errors": {
            "kind": "unknown kind",
            "name": "1 to 80 characters",
            "w": "must be more than 0 and at most 100",
            "props.x": "unknown property",
        }
    }
    oid = client.post(
        "/api/v1/objects", json={"kind": "tree", "name": "Apple"}, auth=auth()
    ).json()["id"]
    r = client.patch(
        f"/api/v1/objects/{oid}", json={"props": {"crown": 99}, "node_id": "ghost"}, auth=auth()
    )
    assert r.status_code == 400
    assert r.json()["errors"] == {
        "props.crown": "must be a number from 0 to 30",
        "node_id": "unknown node",
    }
    assert client.patch("/api/v1/objects/999", json={"x": 1}, auth=auth()).status_code == 404
    assert client.post("/api/v1/objects", json=[1], auth=auth()).json() == {
        "errors": {"_": "send a JSON object"}
    }


def test_soil_and_pins(client, db):
    add_node(db, "soil-1", "soil")
    add_node(db, "soil-2", "soil")
    add_readings(db, "soil-1", "soil_moisture_pct", [(hours_ago(1), 20.0)])
    add_readings(db, "soil-2", "soil_moisture_pct", [(hours_ago(1), 60.0)])
    assert client.get("/api/v1/garden/soil", auth=auth()).json()["rows"] == []
    for nid, x in (("soil-1", 0.5), ("soil-2", 9.5)):
        client.post(
            "/api/v1/objects",
            json={"kind": "sensor", "name": nid, "x": x, "y": 0.5, "node_id": nid},
            auth=auth(),
        )
    s = client.get("/api/v1/garden/soil?cell=1", auth=auth()).json()
    assert (s["width"], s["depth"], s["cell"]) == (10.0, 20.0, 1.0)
    assert len(s["rows"]) == 20 and len(s["rows"][0]) == 10
    assert s["rows"][0][0] == 20.0 and s["rows"][0][9] == 60.0
    assert 20.0 < s["rows"][0][4] < s["rows"][0][5] < 60.0

    shed = client.post(
        "/api/v1/objects", json={"kind": "house", "name": "Shed", "x": 8, "y": 9}, auth=auth()
    ).json()
    db.add(
        Task(
            title="Paint shed",
            status="open",
            urgency="critical",
            category="repair",
            object_id=shed["id"],
        )
    )
    db.flush()
    assert client.get("/api/v1/garden/pins", auth=auth()).json() == [
        {
            "type": "task",
            "id": db.query(Task).one().id,
            "label": "Paint shed",
            "x": 8.0,
            "y": 9.0,
            "level": "bad",
        }
    ]
