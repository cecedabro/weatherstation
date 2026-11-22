"""Step tests for the seed log loop: one group per task (P01–P10). Human-owned.

`make check` skips a group while PLAN.md lists its task as open (tests/conftest.py); accept runs it with TASKS=all.
"""

# ruff: noqa: E501

import json
from datetime import date

import pytest

from app import seeds as m
from app.models import Crop, GardenObject, Planting


def bed(db, name="Bed 1", kind="bed"):
    o = GardenObject(kind=kind, name=name, props={})
    db.add(o)
    db.flush()
    return o


def crop(db, name="Carrot", family="Apiaceae", days=80, sow="3-7"):
    c = Crop(name=name, family=family, days_to_harvest=days, sow_months=sow)
    db.add(c)
    db.flush()
    return c


def plant(
    db, name="Carrot", sown=date(2026, 4, 1), status="sown", object_id=None, crop_id=None, **kw
):
    p = Planting(
        crop=name,
        sown_on=sown,
        status=status,
        method="sown",
        object_id=object_id,
        crop_id=crop_id,
        **kw,
    )
    db.add(p)
    db.flush()
    return p


# -- P01 parse_months, sowable
@pytest.mark.task("P01")
@pytest.mark.parametrize(
    "text, want",
    [
        (None, set()),
        ("", set()),
        ("5", {5}),
        ("3-5", {3, 4, 5}),
        ("3-5, 9", {3, 4, 5, 9}),
        ("11-2", {11, 12, 1, 2}),
        ("10-11,2-3", {10, 11, 2, 3}),
        ("x, 4, 13, 0-2, 6-", {4}),
        (" , 7 ,", {7}),
    ],
)
def test_p01_parse_months(text, want):
    assert m.parse_months(text) == want


@pytest.mark.task("P01")
def test_p01_sowable():
    c = Crop(name="Garlic", sow_months="10-11,2-3")
    assert m.sowable(c, 10) and m.sowable(c, 2)
    assert not m.sowable(c, 6)
    assert not m.sowable(Crop(name="X", sow_months=None), 5)


# -- P02 expected_harvest, harvest_text
@pytest.mark.task("P02")
def test_p02_expected_harvest():
    assert m.expected_harvest(date(2026, 4, 1), 80) == date(2026, 6, 20)
    assert m.expected_harvest(date(2026, 12, 20), 30) == date(2027, 1, 19)
    assert m.expected_harvest(date(2026, 4, 1), None) is None


@pytest.mark.task("P02")
@pytest.mark.parametrize(
    "expected, status, want",
    [
        (date(2026, 6, 10), "growing", "ready in 9 days"),
        (date(2026, 6, 2), "growing", "ready tomorrow"),
        (date(2026, 6, 1), "growing", "ready today"),
        (date(2026, 5, 31), "harvesting", "ready since yesterday"),
        (date(2026, 5, 20), "growing", "ready since 12 days"),
        (None, "growing", ""),
        (date(2026, 6, 10), "done", "harvested"),
        (None, "done", "harvested"),
        (date(2026, 6, 10), "failed", "failed"),
    ],
)
def test_p02_harvest_text(expected, status, want):
    assert m.harvest_text(expected, date(2026, 6, 1), status) == want


# -- P03 validate_planting
GOOD = {
    "crop": " Carrot ",
    "variety": "Nantes",
    "object_id": "7",
    "method": "sown",
    "status": "sown",
    "sown_on": "2026-04-01",
    "count": "",
    "notes": "row 2",
}


@pytest.mark.task("P03")
def test_p03_good():
    values, errors = m.validate_planting(GOOD, {"carrot": 3}, {7})
    assert errors == {}
    assert values == {
        "crop": "Carrot",
        "crop_id": 3,
        "variety": "Nantes",
        "object_id": 7,
        "method": "sown",
        "status": "sown",
        "sown_on": date(2026, 4, 1),
        "count": None,
        "notes": "row 2",
    }
    values, errors = m.validate_planting(
        GOOD | {"crop": "Kohlrabi", "variety": " ", "object_id": "", "count": "12"},
        {"carrot": 3},
        {7},
    )
    assert errors == {}
    assert (values["crop_id"], values["variety"], values["object_id"], values["count"]) == (
        None,
        None,
        None,
        12,
    )


@pytest.mark.task("P03")
@pytest.mark.parametrize(
    "change, field, msg",
    [
        ({"crop": "  "}, "crop", "Which crop?"),
        ({"crop": "x" * 81}, "crop", "At most 80 characters"),
        ({"variety": "y" * 81}, "variety", "At most 80 characters"),
        ({"method": "thrown"}, "method", "Pick a method"),
        ({"status": "dead"}, "status", "Pick a status"),
        ({"sown_on": ""}, "sown_on", "When was it sown or planted?"),
        ({"sown_on": "1 April"}, "sown_on", "Use a date (YYYY-MM-DD)"),
        ({"count": "0"}, "count", "A whole number, 1 or more"),
        ({"count": "many"}, "count", "A whole number, 1 or more"),
        ({"object_id": "99"}, "object_id", "Pick a bed from the list"),
        ({"object_id": "abc"}, "object_id", "Pick a bed from the list"),
        ({"notes": "n" * 2001}, "notes", "At most 2000 characters"),
    ],
)
def test_p03_bad(change, field, msg):
    values, errors = m.validate_planting(GOOD | change, {"carrot": 3}, {7})
    assert errors == {field: msg}
    assert set(values) == set(m.FORM_FIELDS) | {"crop_id"}


@pytest.mark.task("P03")
def test_p03_keeps_raw_text():
    values, _ = m.validate_planting(
        GOOD | {"sown_on": "1 April", "count": "many", "object_id": "99"}, {}, {7}
    )
    assert (values["sown_on"], values["count"], values["object_id"]) == ("1 April", "many", None)


# -- P04 next_status, timeline
@pytest.mark.task("P04")
def test_p04_next_status():
    assert m.next_status("planned") == "sown"
    assert m.next_status("flowering") == "harvesting"
    assert m.next_status("harvesting") == "done"
    assert m.next_status("done") is None
    assert m.next_status("failed") is None
    assert m.next_status("nonsense") is None


@pytest.mark.task("P04")
def test_p04_timeline():
    assert m.timeline("planned")[0] == ("planned", "current")
    t = m.timeline("growing")
    assert [s for s, _ in t] == list(m.PATH)
    assert [st for _, st in t] == ["done", "done", "done", "current", "todo", "todo", "todo"]
    assert m.timeline("done")[-1] == ("done", "current")
    f = m.timeline("failed")
    assert f[-1] == ("failed", "current") and len(f) == len(m.PATH) + 1
    assert all(st == "todo" for _, st in f[:-1])


# -- P05 rotation_warning
@pytest.mark.task("P05")
def test_p05_rotation_warning(db):
    b1, b2 = bed(db, "Bed 1"), bed(db, "Bed 2")
    carrot = crop(db, "Carrot", "Apiaceae")
    parsnip = crop(db, "Parsnip", "Apiaceae")
    pea = crop(db, "Pea", "Fabaceae")
    plant(db, "Carrot", date(2024, 4, 1), object_id=b1.id, crop_id=carrot.id)
    plant(db, "Parsnip", date(2025, 3, 20), object_id=b1.id, crop_id=parsnip.id)
    plant(db, "Pea", date(2025, 4, 1), object_id=b2.id, crop_id=pea.id)
    plant(db, "Carrot", date(2022, 4, 1), object_id=b2.id, crop_id=carrot.id)  # 4 years before 2026
    now = plant(db, "Carrot", date(2026, 4, 1), object_id=b1.id, crop_id=carrot.id)

    assert (
        m.rotation_warning(db, b1.id, "Apiaceae", 2026, now.id)
        == "Apiaceae grew here in 2025 (Parsnip)"
    )
    assert m.rotation_warning(db, b1.id, "apiaceae", 2025) == "apiaceae grew here in 2024 (Carrot)"
    assert m.rotation_warning(db, b2.id, "Apiaceae", 2026) is None  # 2022 is more than 3 years back
    assert m.rotation_warning(db, b2.id, "Fabaceae", 2025) is None  # same year doesn't count
    assert m.rotation_warning(db, b1.id, "Fabaceae", 2026) is None
    assert m.rotation_warning(db, None, "Apiaceae", 2026) is None
    assert m.rotation_warning(db, b1.id, None, 2026) is None


# -- P06 find_plantings
@pytest.mark.task("P06")
def test_p06_find_plantings(db):
    a = plant(db, "A", date(2026, 4, 1), "growing")
    b = plant(db, "B", date(2026, 5, 1), "done")
    c = plant(db, "C", date(2025, 6, 1), "failed")
    d = plant(db, "D", date(2026, 5, 1), "planned")
    e = plant(db, "E", date(2025, 3, 1), "sown")
    ids = lambda rows: [p.id for p in rows]  # noqa: E731
    assert ids(m.find_plantings(db, "all", None)) == [d.id, b.id, a.id, c.id, e.id]
    assert ids(m.find_plantings(db, "active", None)) == [d.id, a.id, e.id]
    assert ids(m.find_plantings(db, "done", None)) == [b.id, c.id]
    assert ids(m.find_plantings(db, "all", 2025)) == [c.id, e.id]
    assert ids(m.find_plantings(db, "active", 2026)) == [d.id, a.id]
    assert m.find_plantings(db, "all", 2020) == []


# -- P07 group_by_bed
@pytest.mark.task("P07")
def test_p07_group_by_bed():
    ps = [
        Planting(id=i, crop=f"c{i}", object_id=o)
        for i, o in ((1, 2), (2, None), (3, 1), (4, 2), (5, 99))
    ]
    groups = m.group_by_bed(ps, {1: "bed b", 2: "Bed A"})
    assert [(name, [p.id for p in rows]) for name, rows in groups] == [
        ("Bed A", [1, 4]),
        ("bed b", [3]),
        ("Not placed", [2, 5]),
    ]
    assert m.group_by_bed([], {1: "x"}) == []
    assert [n for n, _ in m.group_by_bed(ps[:1], {2: "Zz"})] == ["Zz"]


# -- P08 planting_json
@pytest.mark.task("P08")
def test_p08_planting_json(db):
    b = bed(db)
    p = plant(
        db,
        "Carrot",
        date(2026, 4, 1),
        "done",
        object_id=b.id,
        variety="Nantes",
        count=40,
        expected_harvest=date(2026, 6, 20),
        harvested_on=date(2026, 6, 25),
        x=1.5,
        y=2.0,
        notes="n",
    )
    j = m.planting_json(p)
    assert j == {
        "id": p.id,
        "crop": "Carrot",
        "crop_id": None,
        "variety": "Nantes",
        "object_id": b.id,
        "method": "sown",
        "status": "done",
        "sown_on": "2026-04-01",
        "expected_harvest": "2026-06-20",
        "harvested_on": "2026-06-25",
        "count": 40,
        "x": 1.5,
        "y": 2.0,
        "notes": "n",
    }
    assert m.planting_json(plant(db, "Pea"))["expected_harvest"] is None


# -- P09 seed_crops
@pytest.mark.task("P09")
def test_p09_seed_crops(db, tmp_path):
    f = tmp_path / "crops.json"
    f.write_text(
        json.dumps(
            [
                {"name": "Carrot", "family": "Apiaceae", "days_to_harvest": 80},
                {"name": "Pea", "family": "Fabaceae"},
            ]
        )
    )
    crop(db, "carrot", "Apiaceae")
    assert m.seed_crops(db, f) == 1
    assert m.seed_crops(db, f) == 0
    names = sorted(c.name for c in db.query(Crop).all())
    assert names == ["Pea", "carrot"]
    assert db.query(Crop).filter_by(name="Pea").one().family == "Fabaceae"


@pytest.mark.task("P09")
def test_p09_real_catalogue(db):
    n = m.seed_crops(db)
    assert n >= 25
    assert db.query(Crop).count() == n
    assert m.seed_crops(db) == 0


# -- P10 apply_form, set_status
@pytest.mark.task("P10")
def test_p10_apply_form():
    p = Planting()
    values = {
        "crop": "Carrot",
        "crop_id": 3,
        "variety": None,
        "object_id": 7,
        "method": "sown",
        "status": "growing",
        "sown_on": date(2026, 4, 1),
        "count": 12,
        "notes": "x",
    }
    m.apply_form(p, values, 80)
    assert (
        p.crop,
        p.crop_id,
        p.variety,
        p.object_id,
        p.method,
        p.status,
        p.sown_on,
        p.count,
        p.notes,
    ) == ("Carrot", 3, None, 7, "sown", "growing", date(2026, 4, 1), 12, "x")
    assert p.expected_harvest == date(2026, 6, 20)
    m.apply_form(p, values, None)
    assert p.expected_harvest is None


@pytest.mark.task("P10")
def test_p10_set_status():
    p = Planting(status="harvesting")
    m.set_status(p, "done", date(2026, 7, 1))
    assert (p.status, p.harvested_on) == ("done", date(2026, 7, 1))
    m.set_status(p, "done", date(2026, 7, 9))
    assert p.harvested_on == date(2026, 7, 1)  # keeps the first harvest date
    m.set_status(p, "harvesting", date(2026, 7, 9))
    assert (p.status, p.harvested_on) == ("harvesting", None)
    m.set_status(p, "failed", date(2026, 7, 9))
    assert (p.status, p.harvested_on) == ("failed", None)
