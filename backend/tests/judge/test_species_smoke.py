"""Species glue smoke tests that pass at every step of the loop. Human-owned."""

from datetime import date

from app.models import Sighting, Species

from ._helpers import auth


def test_private(client, db):
    for url in ("/species", "/species/new", "/api/v1/sightings", "/media/sightings/abc.png"):
        assert client.get(url, follow_redirects=False).status_code in (303, 401), url


def test_pages_render(client, db):
    s = Species(name="Slug", verdict="harmful", common=True, kind="other", description="")
    db.add(s)
    db.flush()
    x = Sighting(species_id=s.id, seen_on=date(2026, 6, 1), removed=False, notes="n")
    db.add(x)
    db.flush()
    for url in (
        "/species",
        "/species?tab=catalogue&q=s&verdict=harmful",
        "/species/new",
        f"/species/{s.id}",
        f"/species/{s.id}/edit",
    ):
        assert client.get(url, auth=auth()).status_code == 200, url
    assert client.get("/api/v1/sightings", auth=auth()).status_code == 200
    assert client.get("/species/999", auth=auth()).status_code == 404
    assert client.get("/media/sightings/0123456789abcdef.png", auth=auth()).status_code == 404
    r = client.post(f"/sightings/{x.id}/removed", auth=auth(), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/species/{s.id}"
    assert client.post("/sightings/999/delete", auth=auth()).status_code == 404
    assert (
        client.post(f"/species/{s.id}/delete", auth=auth(), follow_redirects=False).status_code
        == 303
    )


def test_startup_seed_is_safe(monkeypatch):
    from app import species

    monkeypatch.setenv("SEED_CATALOGUE", "1")
    species.startup_seed()  # the stub or the real seed: never raises
    monkeypatch.setenv("SEED_CATALOGUE", "0")
    species.startup_seed()
