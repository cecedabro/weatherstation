"""Seed log glue smoke tests that pass at every step of the loop. Human-owned."""

from datetime import date

from app.models import Crop, GardenObject, Planting

from ._helpers import auth


def test_private(client, db):
    for url in ("/seeds", "/seeds/new", "/crops"):
        assert client.get(url, follow_redirects=False).status_code == 303, url
    assert client.get("/api/v1/plantings").status_code == 401


def test_pages_render(client, db):
    b = GardenObject(kind="bed", name="Bed 1", props={})
    db.add_all([b, Crop(name="Carrot", family="Apiaceae", days_to_harvest=80, sow_months="3-7")])
    db.flush()
    db.add(
        Planting(
            crop="Carrot", sown_on=date(2026, 4, 1), status="sown", method="sown", object_id=b.id
        )
    )
    db.flush()
    pid = db.query(Planting).one().id
    for url in (
        "/seeds",
        "/seeds?show=done&year=2026",
        "/seeds?show=all",
        "/seeds/new",
        "/seeds/new?crop=Carrot",
        f"/seeds/{pid}/edit",
        "/crops",
    ):
        assert client.get(url, auth=auth()).status_code == 200, url
    assert client.get("/api/v1/plantings?show=active", auth=auth()).status_code == 200
    assert client.get("/seeds/999/edit", auth=auth()).status_code == 404
    for act in ("advance", "failed"):
        assert (
            client.post(f"/seeds/{pid}/{act}", auth=auth(), follow_redirects=False).status_code
            == 303
        )
    assert client.post("/seeds/999/advance", auth=auth()).status_code == 404
    assert (
        client.post(f"/seeds/{pid}/delete", auth=auth(), follow_redirects=False).status_code == 303
    )
