"""Step tests for the garden map data loop: one group per task (G01–G10). Human-owned.

`make check` skips a group until PLAN.md ticks its task (tests/conftest.py); accept runs it with TASKS=all.
"""

# ruff: noqa: E501

from datetime import date

import pytest

from app import objects as m
from app.models import GardenObject, Sighting, Species, Task

from ._helpers import add_node, add_readings, hours_ago


def obj(db, kind="bed", name="Bed", x=1.0, y=2.0, node_id=None, **kw):
    o = GardenObject(
        kind=kind, name=name, x=x, y=y, node_id=node_id, props=kw.pop("props", {}), **kw
    )
    db.add(o)
    db.flush()
    return o


# -- G01 clean_prop
@pytest.mark.task("G01")
@pytest.mark.parametrize(
    "spec, value, want",
    [
        (("choice", ("clay", "sand")), "sand", "sand"),
        (("bool",), True, True),
        (("bool",), False, False),
        (("bool",), "on", True),
        (("bool",), "0", False),
        (("number", 0, 16), 6, 6.0),
        (("number", 0, 16), 16.0, 16.0),
        (("date",), "2026-03-01", "2026-03-01"),
        (("text", 10), "  oak  ", "oak"),
        (("color",), "#A1B2C3", "#a1b2c3"),
        (("number", 0, 16), None, None),
        (("text", 10), "", None),
    ],
)
def test_g01_clean_prop_good(spec, value, want):
    assert m.clean_prop(spec, value) == (want, None)


@pytest.mark.task("G01")
@pytest.mark.parametrize(
    "spec, value, err",
    [
        (("choice", ("clay", "sand")), "mud", "must be one of clay, sand"),
        (("bool",), "maybe", "must be yes or no"),
        (("number", 0, 16), 17, "must be a number from 0 to 16"),
        (("number", 0, 16), "6", "must be a number from 0 to 16"),
        (("number", 0, 16), True, "must be a number from 0 to 16"),
        (("date",), "1 March", "must be a date (YYYY-MM-DD)"),
        (("date",), 20260301, "must be a date (YYYY-MM-DD)"),
        (("text", 3), "four", "at most 3 characters"),
        (("color",), "red", "must be a colour like #a1b2c3"),
    ],
)
def test_g01_clean_prop_bad(spec, value, err):
    assert m.clean_prop(spec, value) == (None, err)


# -- G02 validate_props
@pytest.mark.task("G02")
def test_g02_validate_props_good():
    props, errors = m.validate_props(
        "bed", {"soil": "loam", "raised": "on", "sun_hours": 7, "soil_x": None}
    )
    assert errors == {"props.soil_x": "unknown property"}
    assert props == {"soil": "loam", "raised": True, "sun_hours": 7.0}


@pytest.mark.task("G02")
def test_g02_validate_props_cleared_and_bad():
    props, errors = m.validate_props("bed", {"soil": "", "sun_hours": 30})
    assert props == {}
    assert errors == {"props.sun_hours": "must be a number from 0 to 16"}
    assert m.validate_props("path", {}) == ({}, {})
    assert m.validate_props("bed", ["soil"]) == ({}, {"props": "must be an object"})
    assert m.validate_props("nope", {"a": 1}) == ({}, {"props.a": "unknown property"})


# -- G03 check_geometry
@pytest.mark.task("G03")
def test_g03_defaults_on_create():
    fields, errors = m.check_geometry({}, partial=False)
    assert errors == {}
    assert fields == {
        "x": 0.0,
        "y": 0.0,
        "w": 1.0,
        "d": 1.0,
        "h": 0.2,
        "rotation": 0.0,
        "color": None,
    }


@pytest.mark.task("G03")
def test_g03_values_and_partial():
    fields, errors = m.check_geometry(
        {"x": 3, "w": 2.5, "rotation": -90, "color": "#00FF00"}, partial=True
    )
    assert errors == {}
    assert fields == {"x": 3.0, "w": 2.5, "rotation": 270.0, "color": "#00ff00"}
    assert m.check_geometry({"rotation": 450, "color": ""}, partial=True) == (
        {"rotation": 90.0, "color": None},
        {},
    )
    assert m.check_geometry({}, partial=True) == ({}, {})


@pytest.mark.task("G03")
@pytest.mark.parametrize(
    "data, key, err",
    [
        ({"x": "1"}, "x", "must be a number"),
        ({"y": True}, "y", "must be a number"),
        ({"x": 501}, "x", "must be from -500 to 500"),
        ({"y": -501}, "y", "must be from -500 to 500"),
        ({"w": 0}, "w", "must be more than 0 and at most 100"),
        ({"d": 101}, "d", "must be more than 0 and at most 100"),
        ({"h": -1}, "h", "must be from 0 to 20"),
        ({"h": 21}, "h", "must be from 0 to 20"),
        ({"color": "green"}, "color", "must be a colour like #a1b2c3"),
    ],
)
def test_g03_bad(data, key, err):
    fields, errors = m.check_geometry(data, partial=True)
    assert errors == {key: err}
    assert key not in fields


# -- G04 validate_object
@pytest.mark.task("G04")
def test_g04_create_good(db):
    add_node(db, "soil-1", "soil")
    fields, errors = m.validate_object(
        db, {"kind": "sensor", "name": "  Probe A ", "x": 2, "y": 3, "node_id": "soil-1"}
    )
    assert errors == {}
    assert fields["kind"] == "sensor" and fields["name"] == "Probe A"
    assert fields["x"] == 2.0 and fields["w"] == 1.0 and fields["color"] is None
    assert fields["node_id"] == "soil-1" and fields["props"] == {}


@pytest.mark.task("G04")
def test_g04_create_bad(db):
    fields, errors = m.validate_object(
        db, {"kind": "castle", "name": "", "x": 900, "node_id": "ghost", "props": {"a": 1}}
    )
    assert errors == {
        "kind": "unknown kind",
        "name": "1 to 80 characters",
        "x": "must be from -500 to 500",
        "node_id": "unknown node",
        "props.a": "unknown property",
    }
    assert m.validate_object(db, ["x"]) == ({}, {"_": "send a JSON object"})
    assert m.validate_object(db, {"kind": "bed"})[1] == {"name": "1 to 80 characters"}
    assert m.validate_object(db, {"kind": "bed", "name": "x" * 81})[1] == {
        "name": "1 to 80 characters"
    }


@pytest.mark.task("G04")
def test_g04_update_only_sent_keys(db):
    o = obj(db, kind="bed", name="Bed 1")
    fields, errors = m.validate_object(db, {"x": 5, "props": {"soil": "clay"}}, o)
    assert errors == {}
    assert fields == {"x": 5.0, "props": {"soil": "clay"}}
    fields, errors = m.validate_object(db, {"props": {"litres": 200}}, o)
    assert errors == {"props.litres": "unknown property"}
    fields, errors = m.validate_object(db, {"kind": "water", "props": {"litres": 200}}, o)
    assert errors == {} and fields == {"kind": "water", "props": {"litres": 200.0}}
    assert m.validate_object(db, {"node_id": ""}, o) == ({"node_id": None}, {})


# -- G05 object_json
@pytest.mark.task("G05")
def test_g05_object_json(db):
    o = obj(
        db,
        kind="tree",
        name="Apple",
        x=4.0,
        y=5.5,
        w=3.0,
        d=3.0,
        h=4.0,
        rotation=10.0,
        color="#228833",
        props={"crown": 3.0},
    )
    j = m.object_json(o)
    assert set(j) == {
        "id",
        "kind",
        "name",
        "x",
        "y",
        "w",
        "d",
        "h",
        "rotation",
        "color",
        "props",
        "node_id",
        "updated_at",
    }
    assert j["id"] == o.id and j["kind"] == "tree" and j["name"] == "Apple"
    assert (j["x"], j["y"], j["w"], j["d"], j["h"], j["rotation"]) == (
        4.0,
        5.5,
        3.0,
        3.0,
        4.0,
        10.0,
    )
    assert j["color"] == "#228833" and j["props"] == {"crown": 3.0} and j["node_id"] is None
    assert isinstance(j["updated_at"], str) and j["updated_at"].startswith(str(o.updated_at.date()))


# -- G06 apply_fields, find_objects
@pytest.mark.task("G06")
def test_g06_apply_fields():
    o = GardenObject(kind="bed", name="Old")
    m.apply_fields(o, {"name": "New", "x": 2.0, "props": {"raised": True}})
    assert (o.name, o.x, o.props) == ("New", 2.0, {"raised": True})
    m.apply_fields(o, {})
    assert o.name == "New"


@pytest.mark.task("G06")
def test_g06_find_objects(db):
    a = obj(db, kind="bed", name="B")
    b = obj(db, kind="tree", name="A")
    c = obj(db, kind="bed", name="C")
    assert [o.id for o in m.find_objects(db, None)] == [a.id, b.id, c.id]
    assert [o.id for o in m.find_objects(db, "bed")] == [a.id, c.id]
    assert m.find_objects(db, "water") == []


# -- G07 idw
@pytest.mark.task("G07")
def test_g07_idw():
    pts = [(0.0, 0.0, 10.0), (2.0, 0.0, 30.0)]
    assert m.idw(1.0, 0.0, []) is None
    assert m.idw(0.0, 0.0, pts) == 10.0
    assert m.idw(1.0, 0.0, pts) == pytest.approx(20.0)
    # distance 1 and 3 → weights 1 and 1/9
    assert m.idw(-1.0, 0.0, pts) == pytest.approx((10 + 30 / 9) / (1 + 1 / 9))
    assert m.idw(-1.0, 0.0, pts, power=1.0) == pytest.approx((10 + 30 / 3) / (1 + 1 / 3))
    assert m.idw(5.0, 5.0, [(1.0, 1.0, 42.0)]) == pytest.approx(42.0)


# -- G08 soil_grid
@pytest.mark.task("G08")
def test_g08_soil_grid():
    assert m.soil_grid([], 10, 20, 1) == []
    grid = m.soil_grid([(0.5, 0.5, 20.0), (1.5, 0.5, 40.0)], 2, 1.5, 1)
    assert len(grid) == 2 and all(len(r) == 2 for r in grid)  # ceil(1.5) rows, 2 columns
    assert grid[0] == [20.0, 40.0]  # centres sit on the points
    assert grid[1][0] == round(m.idw(0.5, 1.5, [(0.5, 0.5, 20.0), (1.5, 0.5, 40.0)]), 1)
    assert grid[1][0] < 30 < grid[1][1]
    assert all(isinstance(v, float) for r in grid for v in r)


# -- G09 soil_points
@pytest.mark.task("G09")
def test_g09_soil_points(db):
    add_node(db, "soil-1", "soil")
    add_node(db, "soil-2", "soil")
    add_node(db, "soil-3", "soil")
    add_readings(db, "soil-1", "soil_moisture_pct", [(hours_ago(3), 10.0), (hours_ago(1), 35.5)])
    add_readings(db, "soil-1", "soil_temp_c", [(hours_ago(0.5), 12.0)])
    add_readings(db, "soil-2", "soil_moisture_pct", [(hours_ago(2), 50.0)])
    a = obj(db, kind="sensor", name="A", x=1.0, y=1.0, node_id="soil-1")
    obj(db, kind="sensor", name="No node", x=2.0, y=2.0)
    obj(db, kind="bed", name="Bed with node", x=3.0, y=3.0, node_id="soil-2")
    obj(db, kind="sensor", name="No readings", x=4.0, y=4.0, node_id="soil-3")
    b = obj(db, kind="sensor", name="B", x=5.0, y=6.0, node_id="soil-2")
    assert a.id < b.id
    assert m.soil_points(db) == [(1.0, 1.0, 35.5), (5.0, 6.0, 50.0)]


# -- G10 pins
@pytest.mark.task("G10")
def test_g10_pins(db):
    shed = obj(db, kind="house", name="Shed", x=8.0, y=9.0)
    t1 = Task(title="Fix fence", urgency="high", status="open", category="repair", x=1.0, y=2.0)
    t2 = Task(title="Oil door", urgency="low", status="open", category="repair", object_id=shed.id)
    t3 = Task(title="Done one", urgency="critical", status="done", category="repair", x=1.0, y=1.0)
    t4 = Task(title="Nowhere", urgency="normal", status="open", category="other")
    db.add_all([t1, t2, t3, t4])
    slug = Species(name="Slug", kind="animal", verdict="harmful")
    knot = Species(name="Knotweed", kind="plant", verdict="invasive")
    bee = Species(name="Bee", kind="animal", verdict="beneficial")
    db.add_all([slug, knot, bee])
    db.flush()
    s1 = Sighting(species_id=slug.id, seen_on=date(2026, 6, 1), x=3.0, y=4.0)
    s2 = Sighting(species_id=knot.id, seen_on=date(2026, 6, 2), object_id=shed.id)
    s3 = Sighting(species_id=slug.id, seen_on=date(2026, 6, 3), x=1.0, y=1.0, removed=True)
    s4 = Sighting(species_id=bee.id, seen_on=date(2026, 6, 4), x=1.0, y=1.0)
    db.add_all([s1, s2, s3, s4])
    db.flush()
    assert m.pins(db) == [
        {"type": "task", "id": t1.id, "label": "Fix fence", "x": 1.0, "y": 2.0, "level": "bad"},
        {"type": "task", "id": t2.id, "label": "Oil door", "x": 8.0, "y": 9.0, "level": "info"},
        {"type": "sighting", "id": s1.id, "label": "Slug", "x": 3.0, "y": 4.0, "level": "warn"},
        {"type": "sighting", "id": s2.id, "label": "Knotweed", "x": 8.0, "y": 9.0, "level": "warn"},
    ]
