"""Garden map data glue smoke tests that pass at every step of the loop. Human-owned."""

from app.models import GardenObject

from ._helpers import auth


def test_private(client, db):
    for url in (
        "/api/v1/objects",
        "/api/v1/objects/kinds",
        "/api/v1/garden/soil",
        "/api/v1/garden/pins",
    ):
        assert client.get(url).status_code == 401, url
    assert client.post("/api/v1/objects", json={}).status_code == 401
    assert client.delete("/api/v1/objects/1").status_code == 401


def test_routes_answer(client, db):
    db.add(GardenObject(kind="bed", name="Bed", props={}))
    db.flush()
    oid = db.query(GardenObject).one().id
    for url in (
        "/api/v1/objects",
        "/api/v1/objects?kind=bed",
        f"/api/v1/objects/{oid}",
        "/api/v1/garden/pins",
        "/api/v1/garden/soil?cell=1",
    ):
        assert client.get(url, auth=auth()).status_code == 200, url
    kinds = client.get("/api/v1/objects/kinds", auth=auth()).json()
    assert "bed" in kinds["kinds"] and kinds["props"]["bed"]["soil"][0] == "choice"
    assert client.get("/api/v1/objects/999", auth=auth()).status_code == 404
    assert client.get("/api/v1/garden/soil?cell=0", auth=auth()).status_code == 422
    assert client.post("/api/v1/objects", data={"kind": "bed"}, auth=auth()).status_code == 415
    r = client.post(
        "/api/v1/objects",
        content=b"{nope",
        headers={"content-type": "application/json"},
        auth=auth(),
    )
    assert r.status_code == 400
    assert client.delete("/api/v1/objects/999", auth=auth()).status_code == 404
    assert client.delete(f"/api/v1/objects/{oid}", auth=auth()).status_code == 204
