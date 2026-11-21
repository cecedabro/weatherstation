"""Acceptance tests for Species and sightings (SPEC §15). Human-owned."""

import io
import json
import re
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.accept  # loop E; removed after review

from app.config import Settings
from app.models import GardenObject, Sighting, Species

from ._helpers import auth

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def media(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    return tmp_path


def sp(db, name, verdict="unknown", common=False, kind="plant", latin=None):
    s = Species(name=name, verdict=verdict, common=common, kind=kind, latin=latin, description="")
    db.add(s)
    db.flush()
    return s.id


def seen(db, species_id, day=date(2026, 6, 1), removed=False, notes=""):
    x = Sighting(species_id=species_id, seen_on=day, removed=removed, notes=notes)
    db.add(x)
    db.flush()
    return x.id


def get(client, url, **params):
    return client.get(url, params=params, auth=auth())


def post(client, url, data=None, files=None):
    return client.post(url, data=data or {}, files=files, auth=auth(), follow_redirects=False)


def test_private(client, db):
    for url in ("/species", "/species/new", "/api/v1/sightings", "/media/sightings/abc.png"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (303, 401), url


# --- 15.1 / 15.2 list
def test_found_and_catalogue_tabs(client, db):
    weed = sp(db, "Ground elder", "invasive", common=True)
    sp(db, "Hedgehog", "beneficial", common=True, kind="mammal")
    seen(db, weed, date(2026, 5, 1))
    seen(db, weed, date(2026, 6, 2), removed=True)
    seen(db, weed, date(2026, 6, 3))
    t = get(client, "/species").text
    assert "Ground elder" in t and "Hedgehog" not in t
    assert "chip-bad" in t
    assert re.search(r"2 to remove", t)
    assert "3 June 2026" in t or "3 Jun 2026" in t or "2026-06-03" in t
    c = get(client, "/species", tab="catalogue").text
    assert "Hedgehog" in c and "Ground elder" in c and "chip-ok" in c


def test_search_and_filter(client, db):
    a = sp(db, "Ground elder", "invasive", latin="Aegopodium podagraria")
    b = sp(db, "Seven-spot ladybird", "beneficial", kind="insect")
    seen(db, a)
    seen(db, b)
    t = get(client, "/species", q="aegopodium").text
    assert "Ground elder" in t and "ladybird" not in t
    t = get(client, "/species", verdict="beneficial").text
    assert "ladybird" in t and "Ground elder" not in t


def test_empty(client, db):
    t = get(client, "/species").text
    assert 'class="empty"' in t and 'href="/species/new"' in t


# --- 15.3 detail
def test_detail(client, db):
    obj = GardenObject(kind="bed", name="Bed 3", x=0, y=0, w=1, d=1, h=0.2, props={})
    db.add(obj)
    db.flush()
    sid = sp(db, "Creeping thistle", "harmful")
    db.add(Sighting(species_id=sid, seen_on=date(2026, 5, 1), notes="older note", object_id=obj.id))
    db.add(Sighting(species_id=sid, seen_on=date(2026, 7, 1), notes="newer note", removed=True))
    db.flush()
    t = get(client, f"/species/{sid}").text
    assert t.index("newer note") < t.index("older note")
    assert "Bed 3" in t
    assert f'action="/species/{sid}/sightings"' in t and 'enctype="multipart/form-data"' in t
    assert get(client, "/species/999").status_code == 404


# --- 15.4 create / edit / delete
def test_create_and_unique(client, db):
    r = post(
        client,
        "/species",
        {
            "name": "Hoverfly",
            "latin": "Syrphidae",
            "kind": "insect",
            "verdict": "beneficial",
            "description": "Eats aphids",
        },
    )
    assert r.status_code == 303
    sid = db.query(Species).filter_by(name="Hoverfly").one().id
    assert r.headers["location"] == f"/species/{sid}"
    r = post(
        client,
        "/species",
        {"name": "hoverfly", "kind": "insect", "verdict": "neutral", "description": ""},
    )
    assert r.status_code == 400 and 'class="field-error"' in r.text


@pytest.mark.parametrize(
    "bad",
    [
        {"name": " "},
        {"name": "n" * 121},
        {"kind": "dragon"},
        {"verdict": "evil"},
        {"latin": "l" * 121},
        {"description": "d" * 4001},
    ],
)
def test_species_validation(client, db, bad):
    data = {"name": "Valid", "latin": "", "kind": "plant", "verdict": "unknown", "description": ""}
    data.update(bad)
    assert post(client, "/species", data).status_code == 400
    assert db.query(Species).count() == 0


def test_edit_and_delete(client, db):
    sid = sp(db, "Dandelion", "neutral")
    seen(db, sid)
    assert f'action="/species/{sid}"' in get(client, f"/species/{sid}/edit").text
    assert (
        post(
            client,
            f"/species/{sid}",
            {
                "name": "Dandelion",
                "latin": "Taraxacum",
                "kind": "plant",
                "verdict": "harmful",
                "description": "",
            },
        ).status_code
        == 303
    )
    db.expire_all()
    assert db.get(Species, sid).verdict == "harmful"
    assert post(client, f"/species/{sid}/delete").status_code == 303
    db.expire_all()
    assert db.get(Species, sid) is None and db.query(Sighting).count() == 0


# --- 15.5 sightings with photos
def test_add_sighting_with_photo(client, db, media):
    sid = sp(db, "Spanish slug", "harmful")
    r = post(
        client,
        f"/species/{sid}/sightings",
        {
            "seen_on": "2026-06-05",
            "count": "4",
            "notes": "under the board",
            "removed": "1",
            "object_id": "",
        },
        files={"photo": ("anything.txt", io.BytesIO(PNG), "application/octet-stream")},
    )
    assert r.status_code == 303 and r.headers["location"] == f"/species/{sid}"
    x = db.query(Sighting).one()
    assert (x.count, x.removed, x.seen_on) == (4, True, date(2026, 6, 5))
    assert re.fullmatch(r"[0-9a-f]{16,}\.png", x.photo)
    assert (media / "sightings" / x.photo).read_bytes() == PNG
    img = get(client, f"/media/sightings/{x.photo}")
    assert img.status_code == 200 and img.content == PNG
    assert x.photo in get(client, f"/species/{sid}").text


@pytest.mark.parametrize(
    "bad", [{"seen_on": ""}, {"seen_on": "June"}, {"count": "0"}, {"object_id": "999"}]
)
def test_sighting_validation(client, db, bad):
    sid = sp(db, "Spanish slug", "harmful")
    data = {"seen_on": "2026-06-05", "count": "", "notes": "", "object_id": ""}
    data.update(bad)
    assert post(client, f"/species/{sid}/sightings", data).status_code == 400
    assert db.query(Sighting).count() == 0


def test_photo_must_be_an_image(client, db):
    sid = sp(db, "Spanish slug", "harmful")
    r = post(
        client,
        f"/species/{sid}/sightings",
        {"seen_on": "2026-06-05"},
        files={"photo": ("slug.png", io.BytesIO(b"#!/bin/sh\necho hi"), "image/png")},
    )
    assert r.status_code == 400 and db.query(Sighting).count() == 0


@pytest.mark.parametrize("name", ["../secret.png", "abc.exe", "ABCDEF.png", "x.png.sh"])
def test_media_names(client, db, name):
    assert get(client, f"/media/sightings/{name}").status_code == 404


# --- 15.6 toggle / delete sighting
def test_toggle_and_delete_sighting(client, db):
    sid = sp(db, "Couch grass", "invasive")
    x = seen(db, sid)
    assert post(client, f"/sightings/{x}/removed").headers["location"] == f"/species/{sid}"
    db.expire_all()
    assert db.get(Sighting, x).removed is True
    post(client, f"/sightings/{x}/removed")
    db.expire_all()
    assert db.get(Sighting, x).removed is False
    assert post(client, f"/sightings/{x}/delete").status_code == 303
    db.expire_all()
    assert db.get(Sighting, x) is None
    assert post(client, "/sightings/999/removed").status_code == 404


# --- 15.7 catalogue seed, 15.8 API
def test_seed_catalogue_idempotent(db):
    from app.species import seed_catalogue

    data = json.loads(
        (Path(__file__).resolve().parents[2] / "app" / "data" / "common_species.json").read_text()
    )
    sp(db, data[0]["name"], "unknown")  # already there: left alone
    seed_catalogue(db)
    seed_catalogue(db)
    assert db.query(Species).count() == len(data)
    assert db.query(Species).filter_by(common=True).count() == len(data) - 1


def test_api(client, db):
    a = sp(db, "Ground elder", "invasive")
    seen(db, a, date(2026, 5, 1))
    seen(db, a, date(2026, 6, 1), removed=True)
    rows = get(client, "/api/v1/sightings").json()
    assert [r["seen_on"] for r in rows] == ["2026-06-01", "2026-05-01"]
    assert set(rows[0]) == {
        "id",
        "species_id",
        "species",
        "verdict",
        "seen_on",
        "x",
        "y",
        "object_id",
        "removed",
    }
    assert rows[0]["species"] == "Ground elder" and rows[0]["removed"] is True


def test_media_dir_setting_used(media):
    assert str(media) == Settings().MEDIA_DIR
