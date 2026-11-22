"""Step tests for the Species loop: one group per task (E01–E09). Human-owned.

`make check` skips a group until PLAN.md ticks its task (tests/conftest.py); accept runs it with TASKS=all.
"""

# ruff: noqa: E501

import json
from datetime import date

import pytest

from app import species as m
from app.models import Sighting, Species

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 20


def sp(db, name, verdict="unknown", common=False, latin=None):
    s = Species(
        name=name, verdict=verdict, common=common, kind="plant", latin=latin, description=""
    )
    db.add(s)
    db.flush()
    return s


def seen(db, s, day=date(2026, 6, 1), removed=False):
    x = Sighting(species_id=s.id, seen_on=day, removed=removed, notes="")
    db.add(x)
    db.flush()
    return x


# --- E01
@pytest.mark.task("E01")
def test_e01_verdict_kind():
    got = {
        v: m.verdict_kind(v)
        for v in ("harmful", "invasive", "beneficial", "neutral", "unknown", "odd")
    }
    assert got == {
        "harmful": "bad",
        "invasive": "bad",
        "beneficial": "ok",
        "neutral": "info",
        "unknown": "off",
        "odd": "off",
    }


@pytest.mark.task("E01")
def test_e01_to_remove():
    xs = [Sighting(removed=False), Sighting(removed=True), Sighting(removed=False)]
    assert m.to_remove("invasive", xs) == 2 and m.to_remove("harmful", xs) == 2
    assert m.to_remove("neutral", xs) == 0 and m.to_remove("invasive", []) == 0


# --- E02
GOOD = {
    "name": " Hoverfly ",
    "latin": " Syrphidae ",
    "kind": "insect",
    "verdict": "beneficial",
    "description": "eats aphids",
}


@pytest.mark.task("E02")
def test_e02_validate_species_good():
    values, errors = m.validate_species(GOOD, {"dandelion": 3}, None)
    assert errors == {}
    assert values == {
        "name": "Hoverfly",
        "latin": "Syrphidae",
        "kind": "insect",
        "verdict": "beneficial",
        "description": "eats aphids",
    }
    values, _ = m.validate_species(GOOD | {"latin": "  "}, {}, None)
    assert values["latin"] is None
    assert m.validate_species(GOOD, {"hoverfly": 5}, 5)[1] == {}  # editing itself is fine


@pytest.mark.task("E02")
@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ({"name": " "}, "name"),
        ({"name": "n" * 121}, "name"),
        ({"name": "HOVERFLY"}, "name"),
        ({"latin": "l" * 121}, "latin"),
        ({"kind": "dragon"}, "kind"),
        ({"verdict": "evil"}, "verdict"),
        ({"description": "d" * 4001}, "description"),
    ],
)
def test_e02_validate_species_bad(bad, field):
    values, errors = m.validate_species(GOOD | bad, {"hoverfly": 9}, None if field == "name" else 9)
    assert list(errors) == [field] and errors[field]
    assert set(values) == set(m.SPECIES_FIELDS)


# --- E03
SGOOD = {
    "seen_on": "2026-06-05",
    "count": "4",
    "notes": "under the board",
    "removed": "1",
    "object_id": "7",
}


@pytest.mark.task("E03")
def test_e03_validate_sighting_good():
    values, errors = m.validate_sighting(SGOOD, {7})
    assert errors == {}
    assert values == {
        "seen_on": date(2026, 6, 5),
        "count": 4,
        "notes": "under the board",
        "removed": True,
        "object_id": 7,
    }
    values, errors = m.validate_sighting({"seen_on": "2026-06-05"}, set())
    assert errors == {} and values == {
        "seen_on": date(2026, 6, 5),
        "count": None,
        "notes": "",
        "removed": False,
        "object_id": None,
    }


@pytest.mark.task("E03")
@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ({"seen_on": ""}, "seen_on"),
        ({"seen_on": "June"}, "seen_on"),
        ({"count": "0"}, "count"),
        ({"count": "lots"}, "count"),
        ({"notes": "n" * 2001}, "notes"),
        ({"object_id": "999"}, "object_id"),
    ],
)
def test_e03_validate_sighting_bad(bad, field):
    values, errors = m.validate_sighting(SGOOD | bad, {7})
    assert list(errors) == [field] and errors[field]
    assert set(values) == set(m.SIGHTING_FIELDS)


# --- E04
@pytest.mark.task("E04")
def test_e04_image_ext():
    assert (m.image_ext(JPG), m.image_ext(PNG), m.image_ext(WEBP)) == ("jpg", "png", "webp")
    assert m.image_ext(b"#!/bin/sh\necho hi") is None and m.image_ext(b"") is None
    assert m.image_ext(b"RIFF\x10\x00\x00\x00WAVEfmt ") is None


@pytest.mark.task("E04")
def test_e04_media_name_ok():
    assert m.media_name_ok("0123456789abcdef.png") and m.media_name_ok("a" * 32 + ".webp")
    for bad in (
        "../secret.png",
        "abc.exe",
        "ABCDEF0123456789.png",
        "0123456789abcdef.png.sh",
        "0123456789abcde.png",
        "a" * 65 + ".jpg",
    ):
        assert not m.media_name_ok(bad), bad


# --- E05
@pytest.mark.task("E05")
def test_e05_save_photo(tmp_path):
    name = m.save_photo(PNG, str(tmp_path))
    assert name and m.media_name_ok(name) and name.endswith(".png")
    assert (tmp_path / "sightings" / name).read_bytes() == PNG
    assert m.save_photo(PNG, str(tmp_path)) != name
    assert m.save_photo(b"not an image", str(tmp_path)) is None
    assert m.save_photo(JPG + b"\x00" * m.MAX_PHOTO, str(tmp_path)) is None


# --- E06
@pytest.mark.task("E06")
def test_e06_sighting_stats(db):
    a, b, c = sp(db, "A"), sp(db, "B"), sp(db, "C")
    seen(db, a, date(2026, 5, 1))
    seen(db, a, date(2026, 6, 3))
    seen(db, b, date(2026, 4, 2))
    assert m.sighting_stats(db) == {
        a.id: {"count": 2, "last": date(2026, 6, 3)},
        b.id: {"count": 1, "last": date(2026, 4, 2)},
    }
    assert c.id not in m.sighting_stats(db)


# --- E07
@pytest.mark.task("E07")
def test_e07_find_species(db):
    elder = sp(db, "Ground elder", "invasive", common=True, latin="Aegopodium podagraria")
    sp(db, "hedgehog", "beneficial", common=True)
    bird = sp(db, "Blackbird", "beneficial")
    seen(db, elder)
    seen(db, bird)
    assert [s.name for s in m.find_species(db, "found", None, None)] == [
        "Blackbird",
        "Ground elder",
    ]
    assert [s.name for s in m.find_species(db, "catalogue", None, None)] == [
        "Ground elder",
        "hedgehog",
    ]
    assert [s.name for s in m.find_species(db, "found", "AEGOPOD", None)] == ["Ground elder"]
    assert [s.name for s in m.find_species(db, "found", None, "beneficial")] == ["Blackbird"]


# --- E08
@pytest.mark.task("E08")
def test_e08_seed_catalogue(db, tmp_path):
    f = tmp_path / "cat.json"
    rows = [{"name": "Ground elder", "latin": "Aegopodium", "kind": "plant", "verdict": "invasive", "description": "dig"},
            {"name": "Hedgehog", "latin": None, "kind": "mammal", "verdict": "beneficial", "description": ""}]  # fmt: skip
    f.write_text(json.dumps(rows))
    sp(db, "ground ELDER")  # already there under another case: left alone
    assert m.seed_catalogue(db, f) == 1
    assert m.seed_catalogue(db, f) == 0
    hog = db.query(Species).filter_by(name="Hedgehog").one()
    assert hog.common is True and hog.kind == "mammal" and db.query(Species).count() == 2
    real = json.loads(m.CATALOGUE.read_text())
    have = {"ground elder", "hedgehog"}
    assert m.seed_catalogue(db) == len(
        [r for r in real if r["name"].lower() not in have]
    )  # the real file


# --- E09
@pytest.mark.task("E09")
def test_e09_sighting_json(db):
    s = sp(db, "Ground elder", "invasive")
    x = seen(db, s, date(2026, 6, 1), removed=True)
    x.x, x.y = 2.0, 3.5
    assert m.sighting_json(x, s) == {"id": x.id, "species_id": s.id, "species": "Ground elder", "verdict": "invasive", "seen_on": "2026-06-01",
                                     "x": 2.0, "y": 3.5, "object_id": None, "removed": True}  # fmt: skip
