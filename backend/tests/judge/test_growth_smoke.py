"""Growth and advisor glue smoke tests that pass at every step of the loop. Human-owned."""

from datetime import date

from app.models import Crop, GardenObject, Planting, Source

from ._helpers import auth


def test_private(client, db):
    for url in ("/growth", "/advisor", "/sources", "/sources/new"):
        assert client.get(url, follow_redirects=False).status_code == 303, url
    assert client.get("/api/v1/growth").status_code == 401


def test_pages_render(client, db):
    c = Crop(name="Carrot", family="Apiaceae", gdd_to_harvest=1200, base_temp_c=4, sun="full")
    db.add_all([c, GardenObject(kind="bed", name="Bed 1", props={"sun_hours": 6})])
    db.flush()
    db.add_all(
        [
            Planting(
                crop="Carrot",
                crop_id=c.id,
                sown_on=date(2026, 4, 1),
                status="growing",
                method="sown",
            ),
            Source(title="Guide", kind="guide", body="Sow carrots.", tags=""),
        ]
    )
    db.flush()
    sid = db.query(Source).one().id
    for url in (
        "/growth",
        f"/growth?crop={c.id}",
        "/advisor",
        "/sources",
        "/sources/new",
        f"/sources/{sid}/edit",
    ):
        assert client.get(url, auth=auth()).status_code == 200, url
    assert client.get("/api/v1/growth", auth=auth()).status_code == 200
    assert client.post("/advisor", data={"question": "carrots?"}, auth=auth()).status_code == 200
    assert client.get("/sources/999/edit", auth=auth()).status_code == 404
    assert (
        client.post(f"/sources/{sid}/delete", auth=auth(), follow_redirects=False).status_code
        == 303
    )
