"""Seed log (SPEC §13, private): what was sown or planted, in which bed, and when it should be ready.

The routes, forms and templates (`seeds.html`, `seed_form.html`, `crops.html`) are done (human-owned glue at the
bottom). The loop fills in the small functions marked ``TODO (task Pxx)``: ``grep -n "TODO (task" app/seeds.py``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

import json  # noqa: F401  (json: task P09)
from datetime import date, timedelta  # noqa: F401  (timedelta: task P02)
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.config import Settings
from app.db import SessionLocal
from app.models import PLANTING_METHODS, PLANTING_STATUSES, Crop, GardenObject, Planting
from app.tasks import local_today
from app.templating import render

router = APIRouter()

CROPS_FILE = Path(__file__).resolve().parent / "data" / "crops.json"
# The normal path of a planting; "failed" can happen at any point.
PATH = ("planned", "sown", "sprouted", "growing", "flowering", "harvesting", "done")
FINISHED = ("done", "failed")
SHOWS = ("active", "done", "all")
FORM_FIELDS = ("crop", "variety", "object_id", "method", "status", "sown_on", "count", "notes")


def parse_months(text: str | None) -> set[int]:
    """Months from a text like ``"3-5,9"`` → ``{3, 4, 5, 9}``. A range may wrap the year: ``"11-2"`` → ``{11, 12, 1, 2}``.

    TODO (task P01) steps:
    1. None or "" → ``set()``.
    2. Split on ","; strip each part; skip empty parts.
    3. A part with "-": ``a, b = int(...)``, int(...); add a, a+1, … up to b, wrapping from 12 to 1 when a > b.
       A part without "-": add ``int(part)``.
    4. Skip a part that ``int`` can't read (ValueError) or whose months are not 1–12.
    """
    return set()


def sowable(crop: Crop, month: int) -> bool:
    """True when *month* is one of the crop's sowing months (``crop.sow_months``).

    TODO (task P01): ``return month in parse_months(crop.sow_months)``.
    """
    return False


def expected_harvest(sown_on: date, days_to_harvest: int | None) -> date | None:
    """The sowing date plus the crop's days to harvest; None when that is unknown.

    TODO (task P02): None → None; else ``sown_on + timedelta(days=days_to_harvest)``.
    """
    return None


def harvest_text(expected: date | None, today: date, status: str) -> str:
    """Short text for the list.

    TODO (task P02) steps:
    1. status "done" → "harvested"; status "failed" → "failed"; *expected* None → "".
    2. ``n = (expected - today).days``: n > 1 → f"ready in {n} days"; n == 1 → "ready tomorrow"; n == 0 →
       "ready today"; n == -1 → "ready since yesterday"; n < -1 → f"ready since {-n} days".
    """
    return ""


def validate_planting(
    form: dict[str, str], crops: dict[str, int], object_ids: set[int]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the planting form. *crops* maps lower-case crop name → crop id. Returns ``(values, errors)``.

    *values* always has every key of FORM_FIELDS plus ``crop_id``. Keep the raw text for a bad value so the form
    can show it again.

    TODO (task P03) steps, ``get = lambda k: (form.get(k) or "").strip()``:
    1. crop: stripped; empty → "Which crop?"; longer than 80 → "At most 80 characters".
       ``values["crop_id"] = crops.get(crop.lower())`` (None when it's not in the catalogue; that is allowed).
    2. variety: stripped, "" → None; longer than 80 → "At most 80 characters".
    3. method not in PLANTING_METHODS → "Pick a method"; status not in PLANTING_STATUSES → "Pick a status".
    4. sown_on: "" → "When was it sown or planted?"; else ``date.fromisoformat``; ValueError → keep the text,
       "Use a date (YYYY-MM-DD)".
    5. count: "" → None; else ``int(...)`` that is at least 1; otherwise keep the text and "A whole number, 1 or more".
    6. object_id: "" → None; else ``int(...)`` in *object_ids*; otherwise None and "Pick a bed from the list".
    7. notes: ``form.get("notes") or ""`` (not stripped); longer than 2000 → "At most 2000 characters".
    """
    return {}, {}


def next_status(status: str) -> str | None:
    """The status after *status* on PATH; None at the end ("done") and for "failed" or unknown statuses.

    TODO (task P04): find *status* in PATH; return the next one, or None.
    """
    return None


def timeline(status: str) -> list[tuple[str, str]]:
    """Steps for the status bar: ``[(step, state)]`` for every step on PATH, state "done", "current" or "todo".

    TODO (task P04) steps:
    1. *status* on PATH: steps before it are "done", it is "current", the rest "todo".
    2. "failed" (or unknown): every PATH step is "todo", then add ``("failed", "current")`` at the end.
    """
    return [(status, "current")]


def rotation_warning(
    db: Session, object_id: int | None, family: str | None, year: int, exclude_id: int | None = None
) -> str | None:
    """Crop rotation: warn when the same plant family grew in the same bed in the 3 years before *year*.

    TODO (task P05) steps:
    1. *object_id* or *family* is None → None.
    2. Select ``Planting, Crop`` joined on ``Crop.id == Planting.crop_id`` where ``Planting.object_id == object_id``,
       ``func.lower(Crop.family) == family.lower()``, ``Planting.sown_on`` from ``date(year - 3, 1, 1)`` up to
       (not including) ``date(year, 1, 1)``, and ``Planting.id != exclude_id`` when it is set. Newest
       ``sown_on`` first; take the first row.
    3. No row → None. Else ``f"{family} grew here in {p.sown_on.year} ({p.crop})"``.
    """
    return None


def find_plantings(db: Session, show: str, year: int | None) -> list[Planting]:
    """Plantings for the list, newest sowing first (then newest id first).

    TODO (task P06) steps:
    1. show "active": status not in FINISHED (``Planting.status.not_in(FINISHED)``); "done": status in FINISHED;
       anything else: all.
    2. *year* set: only ``sown_on`` from ``date(year, 1, 1)`` up to (not including) ``date(year + 1, 1, 1)``.
    3. ``.order_by(Planting.sown_on.desc(), Planting.id.desc())``; return a list.
    """
    return []


def group_by_bed(
    plantings: list[Planting], objects: dict[int, str]
) -> list[tuple[str, list[Planting]]]:
    """Group plantings by their bed name (``objects`` maps object id → name).

    TODO (task P07) steps:
    1. Put each planting under ``objects[p.object_id]``; when ``object_id`` is None or not in *objects*, under
       "Not placed". Keep the order of *plantings* inside each group.
    2. Return ``[(name, plantings)]`` sorted by name (case-insensitive), with "Not placed" always last.
    """
    return []


def planting_json(p: Planting) -> dict[str, Any]:
    """One planting for the API.

    TODO (task P08): ``{"id", "crop", "crop_id", "variety", "object_id", "method", "status", "sown_on",
    "expected_harvest", "harvested_on", "count", "x", "y", "notes"}``; the three dates as ``.isoformat()`` or None.
    """
    return {}


def seed_crops(db: Session, path: Path = CROPS_FILE) -> int:
    """Add the crops from *path* whose name (case-insensitive) is not in the ``crop`` table yet; return how many.

    TODO (task P09) steps:
    1. ``rows = json.loads(path.read_text(encoding="utf-8"))``: a list of dicts whose keys are Crop columns.
    2. ``have = {n.lower() for n in db.execute(select(Crop.name)).scalars()}``.
    3. For each row whose ``name.lower()`` is not in *have*: ``db.add(Crop(**row))`` and add it to *have*.
    4. ``db.flush()`` (not commit: the caller commits) and return the number added.
    """
    return 0


def apply_form(p: Planting, values: dict[str, Any], days_to_harvest: int | None) -> None:
    """Copy checked form *values* onto *p*.

    TODO (task P10) steps:
    1. Set ``crop``, ``crop_id``, ``variety``, ``object_id``, ``method``, ``status``, ``sown_on``, ``count`` and
       ``notes`` from *values*.
    2. ``p.expected_harvest = expected_harvest(p.sown_on, days_to_harvest)``.
    3. Leave ``harvested_on`` alone (``set_status`` handles it).
    """
    return None


def set_status(p: Planting, status: str, today: date) -> None:
    """Move *p* to *status*.

    TODO (task P10): set ``p.status``; when it becomes "done" and ``harvested_on`` is None, set it to *today*;
    for any other status set ``harvested_on`` back to None.
    """
    return None


# -- glue (done)
def _objects(db: Session) -> dict[int, str]:
    stmt = select(GardenObject).order_by(GardenObject.name)
    return {o.id: o.name for o in db.execute(stmt).scalars()}


def _beds(db: Session) -> dict[int, str]:
    stmt = (
        select(GardenObject)
        .where(GardenObject.kind.in_(("bed", "greenhouse", "patch")))
        .order_by(GardenObject.name)
    )
    beds = {o.id: o.name for o in db.execute(stmt).scalars()}
    return beds or _objects(db)


def _crops(db: Session) -> list[Crop]:
    return list(db.execute(select(Crop).order_by(func.lower(Crop.name))).scalars())


def _get(db: Session, planting_id: int) -> Planting:
    p = db.get(Planting, planting_id)
    if p is None:
        raise HTTPException(status_code=404, detail="No such planting")
    return p


def _form_page(
    request: Request,
    db: Session,
    p: Planting | None,
    values: dict[str, Any],
    errors: dict[str, str],
) -> HTMLResponse:
    return render(
        request,
        "seed_form.html",
        status_code=400 if errors else 200,
        active="seeds",
        planting=p,
        values=values,
        errors=errors,
        crops=[c.name for c in _crops(db)],
        methods=[(m, m.title()) for m in PLANTING_METHODS],
        statuses=[(s, s.title()) for s in PLANTING_STATUSES],
        objects=[("", "— not placed —")] + [(str(k), v) for k, v in _beds(db).items()],
    )


@router.get("/seeds")
async def seeds_page(
    request: Request, show: str = "active", year: str = "", user: str = RequireUser
) -> HTMLResponse:
    show = show if show in SHOWS else "active"
    y = int(year) if year.isdigit() else None
    today = local_today()
    db = SessionLocal()
    try:
        rows = find_plantings(db, show, y)
        counts = {s: len(find_plantings(db, s, y)) for s in SHOWS}
        objects = _objects(db)
        crops = {c.id: c for c in _crops(db)}
        years = sorted(
            {p.sown_on.year for p in find_plantings(db, "all", None)} | {today.year}, reverse=True
        )
        items: dict[int, dict[str, Any]] = {}
        for p in rows:
            crop = crops.get(p.crop_id or -1)
            family = crop.family if crop else None
            items[p.id] = {
                "harvest": harvest_text(p.expected_harvest, today, p.status),
                "next": next_status(p.status),
                "timeline": timeline(p.status),
                "rotation": rotation_warning(db, p.object_id, family, p.sown_on.year, p.id),
            }
    finally:
        db.close()
    soon = sum(
        1
        for p in rows
        if p.status not in FINISHED
        and p.expected_harvest
        and 0 <= (p.expected_harvest - today).days <= 14
    )
    keep = f"&year={y}" if y else ""
    return render(
        request,
        "seeds.html",
        active="seeds",
        groups=group_by_bed(rows, objects),
        items=items,
        show=show,
        year=y,
        years=[("", "All years")] + [(str(v), str(v)) for v in years],
        n={
            "active": counts["active"],
            "soon": soon,
            "beds": len({p.object_id for p in rows if p.object_id}),
        },
        tabs=[(f"/seeds?show={s}{keep}", s.title(), None, counts[s]) for s in SHOWS],
        current_tab=f"/seeds?show={show}{keep}",
    )


@router.get("/seeds/new")
async def seed_new(request: Request, crop: str = "", user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        values = {"crop": crop, "method": "sown", "status": "sown", "sown_on": local_today()}
        return _form_page(request, db, None, values, {})
    finally:
        db.close()


@router.get("/seeds/{planting_id}/edit")
async def seed_edit(request: Request, planting_id: int, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        p = _get(db, planting_id)
        return _form_page(request, db, p, {k: getattr(p, k) for k in FORM_FIELDS}, {})
    finally:
        db.close()


async def _save(request: Request, planting_id: int | None) -> HTMLResponse | RedirectResponse:
    form = {k: str(v) for k, v in (await request.form()).items()}
    db = SessionLocal()
    try:
        p = _get(db, planting_id) if planting_id is not None else None
        crops = _crops(db)
        values, errors = validate_planting(
            form, {c.name.lower(): c.id for c in crops}, set(_objects(db))
        )
        if errors:
            return _form_page(request, db, p, values, errors)
        if p is None:
            p = Planting()
            db.add(p)
        days = next((c.days_to_harvest for c in crops if c.id == values["crop_id"]), None)
        apply_form(p, values, days)
        set_status(p, values["status"], local_today())
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/seeds", status_code=303)


@router.post("/seeds", response_model=None)
async def seed_create(request: Request, user: str = RequireUser) -> HTMLResponse | RedirectResponse:
    return await _save(request, None)


@router.post("/seeds/{planting_id}", response_model=None)
async def seed_update(
    request: Request, planting_id: int, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, planting_id)


@router.post("/seeds/{planting_id}/advance")
async def seed_advance(planting_id: int, user: str = RequireUser) -> RedirectResponse:
    db = SessionLocal()
    try:
        p = _get(db, planting_id)
        nxt = next_status(p.status)
        if nxt:
            set_status(p, nxt, local_today())
            db.commit()
    finally:
        db.close()
    return RedirectResponse("/seeds", status_code=303)


@router.post("/seeds/{planting_id}/failed")
async def seed_failed(planting_id: int, user: str = RequireUser) -> RedirectResponse:
    db = SessionLocal()
    try:
        set_status(_get(db, planting_id), "failed", local_today())
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/seeds", status_code=303)


@router.post("/seeds/{planting_id}/delete")
async def seed_delete(planting_id: int, user: str = RequireUser) -> RedirectResponse:
    db = SessionLocal()
    try:
        db.delete(_get(db, planting_id))
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/seeds", status_code=303)


@router.get("/crops")
async def crops_page(request: Request, user: str = RequireUser) -> HTMLResponse:
    month = local_today().month
    db = SessionLocal()
    try:
        crops = _crops(db)
    finally:
        db.close()
    return render(
        request,
        "crops.html",
        active="seeds",
        crops=[(c, sowable(c, month)) for c in crops],
        now_sowable=sum(1 for c in crops if sowable(c, month)),
    )


@router.get("/api/v1/plantings")
async def api_plantings(show: str = "all", user: str = RequireUser) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        return [
            planting_json(p) for p in find_plantings(db, show if show in SHOWS else "all", None)
        ]
    finally:
        db.close()


def startup_seed() -> None:
    """Add the crop catalogue once when the app starts (main.py), unless SEED_CATALOGUE is off or the DB is down."""
    if not Settings().SEED_CATALOGUE:
        return
    db = SessionLocal()
    try:
        seed_crops(db)
        db.commit()
    except Exception:  # noqa: BLE001  (a missing DB must not stop the site)
        db.rollback()
    finally:
        db.close()
