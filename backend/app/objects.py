"""Garden map data (SPEC §12, private): the objects on the plot, soil moisture between sensors, and map pins.

Coordinates are metres. ``x``/``y`` is an object's centre on the ground, measured from the plot's south-west
corner (``x`` east, ``y`` north); ``w``/``d`` are its size along x/y before rotation, ``h`` its height, and
``rotation`` is degrees clockwise. The 3D map (``static/js/garden3d.js``, human-built later) only talks to the
JSON routes at the bottom.

The routes are done (human-owned glue at the bottom). The loop fills in the small functions marked
``TODO (task Gxx)``: ``grep -n "TODO (task" app/objects.py``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

import math  # noqa: F401  (math: task G08)
import re
from datetime import date  # noqa: F401  (date: task G01)
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select  # noqa: F401  (select: tasks G06, G09, G10)
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.config import Settings
from app.db import SessionLocal
from app.models import GardenObject, Node, Reading, Sighting, Species, Task  # noqa: F401  (tasks G04, G09, G10)

router = APIRouter()

OBJECT_KINDS = ("bed", "house", "patch", "compost", "path", "tree", "water", "fence", "sensor")

# kind -> property -> spec. Spec forms: ("choice", options), ("bool",), ("number", low, high), ("date",),
# ("text", max_length), ("color",).
KIND_PROPS: dict[str, dict[str, tuple[Any, ...]]] = {
    "bed": {
        "soil": ("choice", ("clay", "sand", "loam", "peat")),
        "raised": ("bool",),
        "sun_hours": ("number", 0, 16),
    },
    "house": {
        "door_side": ("choice", ("north", "east", "south", "west")),
        "roof_color": ("color",),
    },
    "patch": {"dug": ("bool",), "last_compost": ("date",)},
    "water": {"litres": ("number", 0, 5000)},
    "tree": {"species": ("text", 80), "crown": ("number", 0, 30)},
    "compost": {},
    "path": {},
    "fence": {},
    "sensor": {},
}

GEOMETRY_DEFAULTS: dict[str, float] = {
    "x": 0.0,
    "y": 0.0,
    "w": 1.0,
    "d": 1.0,
    "h": 0.2,
    "rotation": 0.0,
}
LIMIT = 500.0  # |x| and |y| at most this many metres
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")
HARMFUL = ("harmful", "invasive")


def clean_prop(spec: tuple[Any, ...], value: Any) -> tuple[Any, str | None]:
    """Check one property value against its spec; return ``(clean value, None)`` or ``(None, error)``.

    TODO (task G01) steps:
    1. ``value`` is None or ``""`` → ``(None, None)`` (the property is cleared). Otherwise look at ``spec[0]``:
    2. "choice": value in ``spec[1]`` → ``(value, None)``, else ``(None, "must be one of " + ", ".join(spec[1]))``.
    3. "bool": ``True``/``False`` as they are; the strings "true", "on", "1" → True and "false", "off", "0" → False;
       anything else → ``(None, "must be yes or no")``.
    4. "number": an int or float but not a bool, with ``spec[1] <= value <= spec[2]`` → ``(float(value), None)``,
       else ``(None, f"must be a number from {spec[1]} to {spec[2]}")``.
    5. "date": a str that ``date.fromisoformat`` accepts → ``(the same str, None)``, else
       ``(None, "must be a date (YYYY-MM-DD)")``.
    6. "text": a str whose ``.strip()`` is at most ``spec[1]`` long → ``(stripped, None)``, else
       ``(None, f"at most {spec[1]} characters")``.
    7. "color": a str that ``COLOR_RE.fullmatch`` accepts → ``(value.lower(), None)``, else
       ``(None, "must be a colour like #a1b2c3")``.
    """
    # 1. None or empty string → cleared
    if value is None or value == "":
        return None, None

    kind = spec[0]

    if kind == "choice":
        if value in spec[1]:
            return value, None
        return None, "must be one of " + ", ".join(spec[1])

    if kind == "bool":
        if value in (True, False):
            return value, None
        if value in ("true", "on", "1"):
            return True, None
        if value in ("false", "off", "0"):
            return False, None
        return None, "must be yes or no"

    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, f"must be a number from {spec[1]} to {spec[2]}"
        if spec[1] <= value <= spec[2]:
            return float(value), None
        return None, f"must be a number from {spec[1]} to {spec[2]}"

    if kind == "date":
        if not isinstance(value, str):
            return None, "must be a date (YYYY-MM-DD)"
        try:
            date.fromisoformat(value)
            return value, None
        except (ValueError, TypeError):
            return None, "must be a date (YYYY-MM-DD)"

    if kind == "text":
        if not isinstance(value, str):
            return None, f"at most {spec[1]} characters"
        stripped = value.strip()
        if len(stripped) <= spec[1]:
            return stripped, None
        return None, f"at most {spec[1]} characters"

    if kind == "color":
        if not isinstance(value, str):
            return None, "must be a colour like #a1b2c3"
        if COLOR_RE.fullmatch(value):
            return value.lower(), None
        return None, "must be a colour like #a1b2c3"

    return None, None


def validate_props(kind: str, raw: Any) -> tuple[dict[str, Any], dict[str, str]]:
    """Check an object's ``props`` for its *kind*; return ``(props, errors)``.

    TODO (task G02) steps:
    1. *raw* is not a dict → ``({}, {"props": "must be an object"})``.
    2. ``specs = KIND_PROPS.get(kind, {})``. For each ``key, value`` in *raw*:
       - key not in specs → ``errors[f"props.{key}"] = "unknown property"``;
       - else ``clean, err = clean_prop(specs[key], value)``: an error goes to ``errors[f"props.{key}"]``; a clean
         value that is not None goes to ``props[key]`` (None means "cleared": leave the key out).
    3. Return ``(props, errors)``.
    """
    if not isinstance(raw, dict):
        return {}, {"props": "must be an object"}
    specs = KIND_PROPS.get(kind, {})
    props: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, value in raw.items():
        if key not in specs:
            errors[f"props.{key}"] = "unknown property"
        else:
            clean, err = clean_prop(specs[key], value)
            if err is not None:
                errors[f"props.{key}"] = err
            elif clean is not None:
                props[key] = clean
    return props, errors


def check_geometry(data: dict[str, Any], partial: bool) -> tuple[dict[str, Any], dict[str, str]]:
    """Check position, size, rotation and colour; return ``(fields, errors)``.

    TODO (task G03) steps:
    1. For each key in ``GEOMETRY_DEFAULTS`` ("x", "y", "w", "d", "h", "rotation"):
       - key missing from *data*: skip it when *partial*, else use ``GEOMETRY_DEFAULTS[key]``;
       - the value must be an int or float but not a bool, else ``errors[key] = "must be a number"``;
       - "x"/"y": ``-LIMIT <= v <= LIMIT``, else ``errors[key] = "must be from -500 to 500"``;
       - "w"/"d": ``0 < v <= 100``, else ``errors[key] = "must be more than 0 and at most 100"``;
       - "h": ``0 <= v <= 20``, else ``errors[key] = "must be from 0 to 20"``;
       - "rotation": any number, stored as ``float(v) % 360``;
       - a good value is stored as ``fields[key] = float(v)`` (rotation as above).
    2. "color": missing → skip when *partial*, else ``fields["color"] = None``. None or "" → None. A str that
       ``COLOR_RE.fullmatch`` accepts → ``value.lower()``. Anything else → ``errors["color"] = "must be a colour like #a1b2c3"``.
    3. Return ``(fields, errors)``.
    """
    fields: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for key in GEOMETRY_DEFAULTS:
        if key not in data:
            if not partial:
                fields[key] = float(GEOMETRY_DEFAULTS[key])
            continue

        v = data[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errors[key] = "must be a number"
            continue

        if key in ("x", "y"):
            if -LIMIT <= v <= LIMIT:
                fields[key] = float(v)
            else:
                errors[key] = "must be from -500 to 500"
        elif key in ("w", "d"):
            if 0 < v <= 100:
                fields[key] = float(v)
            else:
                errors[key] = "must be more than 0 and at most 100"
        elif key == "h":
            if 0 <= v <= 20:
                fields[key] = float(v)
            else:
                errors[key] = "must be from 0 to 20"
        elif key == "rotation":
            fields[key] = float(v) % 360

    if "color" not in data:
        if not partial:
            fields["color"] = None
    else:
        v = data["color"]
        if v is None or v == "":
            fields["color"] = None
        elif isinstance(v, str) and COLOR_RE.fullmatch(v):
            fields["color"] = v.lower()
        else:
            errors["color"] = "must be a colour like #a1b2c3"

    return fields, errors


def validate_object(
    db: Session, data: Any, current: GardenObject | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check a whole object from JSON. *current* None = create (all fields); else update (only the keys sent).

    TODO (task G04) steps:
    1. *data* is not a dict → ``({}, {"_": "send a JSON object"})``. ``partial = current is not None``.
    2. "kind" (when sent, or always when not partial): must be in ``OBJECT_KINDS``, else
       ``errors["kind"] = "unknown kind"``; good → ``fields["kind"]``.
    3. "name" (when sent, or always when not partial): a str of 1–80 characters after ``.strip()`` →
       ``fields["name"] = stripped``, else ``errors["name"] = "1 to 80 characters"``.
    4. ``geo, geo_errors = check_geometry(data, partial)``; ``fields.update(geo)``, ``errors.update(geo_errors)``.
    5. "node_id" (only when sent): None or "" → ``fields["node_id"] = None``; otherwise ``db.get(Node, value)``
       must find a node, else ``errors["node_id"] = "unknown node"``; good → ``fields["node_id"] = value``.
    6. "props": the kind to check against is ``fields.get("kind")``, else ``current.kind`` when partial. When
       "props" is sent: ``validate_props(that kind, data["props"])`` → ``fields["props"]`` and its errors. When
       not sent and not partial → ``fields["props"] = {}``.
    7. Return ``(fields, errors)``.
    """
    if not isinstance(data, dict):
        return {}, {"_": "send a JSON object"}
    partial = current is not None

    fields: dict[str, Any] = {}
    errors: dict[str, str] = {}

    # 3. name: when sent, or always when not partial
    if "name" in data:
        name = data["name"]
        if isinstance(name, str):
            stripped = name.strip()
            if 1 <= len(stripped) <= 80:
                fields["name"] = stripped
            else:
                errors["name"] = "1 to 80 characters"
        else:
            errors["name"] = "1 to 80 characters"
    elif not partial:
        errors["name"] = "1 to 80 characters"

    # 2. kind: when sent, or always when not partial
    if "kind" in data:
        if data["kind"] in OBJECT_KINDS:
            fields["kind"] = data["kind"]
        else:
            errors["kind"] = "unknown kind"
    elif not partial:
        errors["kind"] = "unknown kind"

    # 4. geometry
    geo, geo_errors = check_geometry(data, partial)
    fields.update(geo)
    errors.update(geo_errors)

    # 5. node_id: only when sent
    if "node_id" in data:
        nid = data["node_id"]
        if nid is None or nid == "":
            fields["node_id"] = None
        else:
            if db.get(Node, nid) is not None:
                fields["node_id"] = nid
            else:
                errors["node_id"] = "unknown node"

    # 6. props
    kind_for_props: str | None
    if partial and "kind" in data:
        kind_for_props = fields.get("kind")
    elif partial:
        assert current is not None
        kind_for_props = current.kind
    else:
        kind_for_props = fields.get("kind")
    if "props" in data:
        props, props_errors = validate_props(kind_for_props or "", data["props"])
        if props:
            fields["props"] = props
        errors.update(props_errors)
    elif not partial:
        fields["props"] = {}

    # 7.
    return fields, errors


def object_json(obj: GardenObject) -> dict[str, Any]:
    """One object for the API.

    TODO (task G05): return ``{"id", "kind", "name", "x", "y", "w", "d", "h", "rotation", "color", "props",
    "node_id", "updated_at"}`` from the attributes of the same name; ``updated_at`` as ``.isoformat()`` (or None).
    """
    return {
        "id": obj.id,
        "kind": obj.kind,
        "name": obj.name,
        "x": obj.x,
        "y": obj.y,
        "w": obj.w,
        "d": obj.d,
        "h": obj.h,
        "rotation": obj.rotation,
        "color": obj.color,
        "props": obj.props,
        "node_id": obj.node_id,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def apply_fields(obj: GardenObject, fields: dict[str, Any]) -> None:
    """Copy checked *fields* onto *obj*.

    TODO (task G06): ``for key, value in fields.items(): setattr(obj, key, value)``.
    """
    for key, value in fields.items():
        setattr(obj, key, value)


def find_objects(db: Session, kind: str | None) -> list[GardenObject]:
    """All objects ordered by id; only those of *kind* when it is set.

    TODO (task G06): ``select(GardenObject)``, ``.where(GardenObject.kind == kind)`` when *kind*,
    ``.order_by(GardenObject.id)``, return ``list(db.execute(stmt).scalars())``.
    """
    stmt = select(GardenObject)
    if kind is not None:
        stmt = stmt.where(GardenObject.kind == kind)
    stmt = stmt.order_by(GardenObject.id)
    return list(db.execute(stmt).scalars().all())


def idw(
    px: float, py: float, points: list[tuple[float, float, float]], power: float = 2.0
) -> float | None:
    """Inverse-distance-weighted value at (*px*, *py*) from ``points = [(x, y, value)]``.

    TODO (task G07) steps:
    1. No points → None.
    2. For each point: ``dist = math.hypot(x - px, y - py)``. A point closer than ``1e-9`` → return its value.
    3. Otherwise ``weight = 1 / dist ** power``; return ``sum(weight * value) / sum(weight)``.
    """
    if not points:
        return None

    for x, y, value in points:
        dist = math.hypot(x - px, y - py)
        if dist < 1e-9:
            return value

    numerator = 0.0
    denominator = 0.0
    for x, y, value in points:
        dist = math.hypot(x - px, y - py)
        w = 1.0 / dist ** power
        numerator += w * value
        denominator += w
    return numerator / denominator


def soil_grid(
    points: list[tuple[float, float, float]], width: float, depth: float, cell: float
) -> list[list[float]]:
    """A grid of interpolated soil moisture over the plot, for colouring the ground.

    TODO (task G08) steps:
    1. No points → ``[]``.
    2. ``cols = math.ceil(width / cell)``, ``rows = math.ceil(depth / cell)``.
    3. Row ``r`` (0 = south) and column ``c`` (0 = west) hold ``round(idw(cx, cy, points) or 0.0, 1)`` with the cell centre
       ``cx = (c + 0.5) * cell``, ``cy = (r + 0.5) * cell``. Return the list of rows (each a list of floats).
    """
    return []


def soil_points(db: Session) -> list[tuple[float, float, float]]:
    """``[(x, y, latest soil_moisture_pct)]`` for every sensor object linked to a node, ordered by object id.

    TODO (task G09) steps:
    1. Select ``GardenObject`` rows with ``kind == "sensor"`` and ``node_id`` not None (``.is_not(None)``),
       ordered by id.
    2. For each, the newest ``Reading.value`` with that ``node_id`` and ``metric == "soil_moisture_pct"``
       (``order_by(Reading.ts.desc()).limit(1)``, then ``db.execute(stmt).scalar()``).
    3. Skip objects without a reading; return ``(obj.x, obj.y, float(value))`` for the others.
    """
    return []


def pins(db: Session) -> list[dict[str, Any]]:
    """Things to mark on the map: open tasks, then harmful or invasive sightings not yet removed.

    A pin is ``{"type", "id", "label", "x", "y", "level"}``. Where it goes: its own ``x``/``y`` when both are set,
    else the centre of its ``object_id`` object; with neither it gets no pin.

    TODO (task G10) steps:
    1. A helper ``where(item)``: ``(item.x, item.y)`` when both are not None; else when ``item.object_id`` is set
       and ``db.get(GardenObject, item.object_id)`` finds it → ``(obj.x, obj.y)``; else None.
    2. Open tasks (``Task.status == "open"``) ordered by id → ``{"type": "task", "id": t.id, "label": t.title,
       "x", "y", "level": "bad" if t.urgency in ("high", "critical") else "info"}``.
    3. Sightings joined with their Species where ``Species.verdict`` in ``HARMFUL`` and ``Sighting.removed`` is
       false, ordered by sighting id → ``{"type": "sighting", "id": s.id, "label": species.name, "x", "y",
       "level": "warn"}``.
    4. Return the task pins followed by the sighting pins (skip items with no place).
    """
    return []


# -- glue (done)
async def _json_body(request: Request) -> Any:
    """Writes must be JSON (a cross-site form can't send it without a preflight)."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Send application/json")
    try:
        return await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Bad JSON") from exc


def _object(db: Session, object_id: int) -> GardenObject:
    obj = db.get(GardenObject, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="No such object")
    return obj


@router.get("/api/v1/objects")
async def api_objects(kind: str = "", user: str = RequireUser) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        return [object_json(o) for o in find_objects(db, kind or None)]
    finally:
        db.close()


@router.get("/api/v1/objects/kinds")
async def api_object_kinds(user: str = RequireUser) -> dict[str, Any]:
    props = {k: {p: list(spec) for p, spec in v.items()} for k, v in KIND_PROPS.items()}
    return {"kinds": list(OBJECT_KINDS), "props": props, "defaults": GEOMETRY_DEFAULTS}


@router.get("/api/v1/objects/{object_id}")
async def api_object(object_id: int, user: str = RequireUser) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return object_json(_object(db, object_id))
    finally:
        db.close()


@router.post("/api/v1/objects", response_model=None)
async def api_object_create(request: Request, user: str = RequireUser) -> JSONResponse:
    data = await _json_body(request)
    db = SessionLocal()
    try:
        fields, errors = validate_object(db, data)
        if errors:
            return JSONResponse({"errors": errors}, status_code=400)
        obj = GardenObject()
        apply_fields(obj, fields)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return JSONResponse(object_json(obj), status_code=201)
    finally:
        db.close()


@router.patch("/api/v1/objects/{object_id}", response_model=None)
async def api_object_update(
    request: Request, object_id: int, user: str = RequireUser
) -> JSONResponse:
    data = await _json_body(request)
    db = SessionLocal()
    try:
        obj = _object(db, object_id)
        fields, errors = validate_object(db, data, obj)
        if errors:
            return JSONResponse({"errors": errors}, status_code=400)
        apply_fields(obj, fields)
        db.commit()
        db.refresh(obj)
        return JSONResponse(object_json(obj))
    finally:
        db.close()


@router.delete("/api/v1/objects/{object_id}", status_code=204, response_model=None)
async def api_object_delete(object_id: int, user: str = RequireUser) -> Response:
    db = SessionLocal()
    try:
        db.delete(_object(db, object_id))
        db.commit()
        return Response(status_code=204)
    finally:
        db.close()


@router.get("/api/v1/garden/soil")
async def api_garden_soil(
    cell: float = Query(0.5, ge=0.1, le=5.0), user: str = RequireUser
) -> dict[str, Any]:
    s = Settings()
    db = SessionLocal()
    try:
        rows = soil_grid(soil_points(db), s.GARDEN_WIDTH, s.GARDEN_DEPTH, cell)
    finally:
        db.close()
    return {"width": s.GARDEN_WIDTH, "depth": s.GARDEN_DEPTH, "cell": cell, "rows": rows}


@router.get("/api/v1/garden/pins")
async def api_garden_pins(user: str = RequireUser) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        return pins(db)
    finally:
        db.close()
