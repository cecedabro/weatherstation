"""Species and sightings (SPEC §15, private): what was found in the garden, and a catalogue of common species.

The routes, forms, photo serving and templates (`species*.html`) are done (human-owned glue at the bottom). The
loop fills in the small functions marked ``TODO (task Exx)``: ``grep -n "TODO (task" app/species.py``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

import json  # noqa: F401  (task E08)
import re  # noqa: F401  (task E04)
import secrets  # noqa: F401  (task E05)
from datetime import UTC, date, datetime  # noqa: F401
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.config import Settings
from app.db import SessionLocal
from app.models import SPECIES_KINDS, SPECIES_VERDICTS, GardenObject, Sighting, Species
from app.templating import render

router = APIRouter()

CATALOGUE = Path(__file__).resolve().parent / "data" / "common_species.json"
MAX_PHOTO = 8 * 1024 * 1024
SPECIES_FIELDS = ("name", "latin", "kind", "verdict", "description")
SIGHTING_FIELDS = ("seen_on", "count", "notes", "removed", "object_id")


def verdict_kind(verdict: str) -> str:
    """Chip kind for a verdict (SPEC 15.2): harmful and invasive → "bad", beneficial → "ok", neutral → "info",
    anything else → "off".

    TODO (task E01): a dict lookup with default "off".
    """
    return {"harmful": "bad", "invasive": "bad", "beneficial": "ok", "neutral": "info"}.get(
        verdict, "off"
    )


def to_remove(verdict: str, sightings: list[Sighting]) -> int:
    """How many sightings still need removing: for "harmful" or "invasive" species the number of *sightings*
    with ``removed`` False; for any other verdict 0.

    TODO (task E01): one ``if`` and a ``sum(...)``.
    """
    if verdict in ("harmful", "invasive"):
        return sum(1 for x in sightings if not x.removed)
    return 0


def validate_species(
    form: dict[str, str], taken: dict[str, int], current_id: int | None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the species form (SPEC 15.4). Returns ``(values, errors)``; errors maps field → message.

    *taken* maps every existing species name, lower-cased, to its id. *current_id* is the species being edited
    (None when creating): its own name is not a clash.
    *values* has every key of SPECIES_FIELDS: name (stripped), latin (stripped, None when empty), kind, verdict,
    description (``form.get("description") or ""``).

    TODO (task E02) steps, ``get = lambda k: (form.get(k) or "").strip()``:
    1. name empty → "Give it a name"; over 120 → "At most 120 characters"; ``taken.get(name.lower())`` is
       an id other than *current_id* → "There is already a species with this name".
    2. latin over 120 → "At most 120 characters".
    3. kind not in SPECIES_KINDS → "Pick a kind"; verdict not in SPECIES_VERDICTS → "Pick a verdict".
    4. description over 4000 → "At most 4000 characters".
    """

    def get(k: str) -> str:
        return (form.get(k) or "").strip()

    name = get("name")
    latin = get("latin") or None
    kind = get("kind")
    verdict = get("verdict")
    description = form.get("description") or ""

    errors: dict[str, str] = {}

    if not name:
        errors["name"] = "Give it a name"
    elif len(name) > 120:
        errors["name"] = "At most 120 characters"
    elif taken.get(name.lower()) and taken[name.lower()] != current_id:
        errors["name"] = "There is already a species with this name"

    if len(latin) > 120 if latin else False:
        errors["latin"] = "At most 120 characters"

    if kind not in SPECIES_KINDS:
        errors["kind"] = "Pick a kind"
    if verdict not in SPECIES_VERDICTS:
        errors["verdict"] = "Pick a verdict"

    if len(description) > 4000:
        errors["description"] = "At most 4000 characters"

    values = {
        "name": name,
        "latin": latin,
        "kind": kind,
        "verdict": verdict,
        "description": description,
    }
    return values, errors


def validate_sighting(
    form: dict[str, str], object_ids: set[int]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the sighting form (SPEC 15.5), without the photo. Returns ``(values, errors)``.

    *values*: seen_on (a ``date``, or the raw text when invalid), count (int or None), notes (str),
    removed (bool: True when ``form.get("removed")`` is non-empty), object_id (int or None).

    TODO (task E03) steps, ``get = lambda k: (form.get(k) or "").strip()``:
    1. seen_on: ``date.fromisoformat(get("seen_on"))``; ValueError (also for "") → keep the text,
       error "Pick the date you saw it".
    2. count: "" → None; else ``int``; ValueError or below 1 → error "A whole number, 1 or more" (value None).
    3. notes: ``form.get("notes") or ""``; over 2000 → "At most 2000 characters".
    4. object_id: "" → None; else int in *object_ids*, otherwise error "Pick an object from the list" (value None).
    """
    errors: dict[str, str] = {}

    def get(k: str) -> str:
        return (form.get(k) or "").strip()

    # Step 1: seen_on
    seen_on: date | str
    seen_on_raw = get("seen_on")
    try:
        seen_on = date.fromisoformat(seen_on_raw)
    except (ValueError, TypeError):
        seen_on = seen_on_raw
        errors["seen_on"] = "Pick the date you saw it"

    # Step 2: count
    count_raw = get("count")
    if count_raw == "":
        count = None
    else:
        try:
            count = int(count_raw)
            if count < 1:
                raise ValueError
        except (ValueError, TypeError):
            count = None
            errors["count"] = "A whole number, 1 or more"

    # Step 3: notes
    notes = form.get("notes") or ""
    if len(notes) > 2000:
        errors["notes"] = "At most 2000 characters"

    # Step 4: object_id
    object_id_raw = get("object_id")
    if object_id_raw == "":
        object_id = None
    else:
        try:
            object_id = int(object_id_raw)
            if object_id not in object_ids:
                raise ValueError
        except (ValueError, TypeError):
            object_id = None
            errors["object_id"] = "Pick an object from the list"

    values = {
        "seen_on": seen_on,
        "count": count,
        "notes": notes,
        "removed": bool(form.get("removed")),
        "object_id": object_id,
    }
    return values, errors


def image_ext(data: bytes) -> str | None:
    """File extension from the first bytes (SPEC 15.5: checked by content, not by name):
    ``b"\\xff\\xd8\\xff"`` → "jpg"; ``b"\\x89PNG\\r\\n\\x1a\\n"`` → "png"; ``b"RIFF"`` at 0 and ``b"WEBP"`` at 8 → "webp";
    anything else → None.

    TODO (task E04): three ``startswith`` / slice checks.
    """
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def media_name_ok(name: str) -> bool:
    """True only for names we make ourselves: 16–64 lowercase hex characters, a dot, then jpg, png or webp.

    TODO (task E04): ``re.fullmatch(r"[0-9a-f]{16,64}\\.(jpg|png|webp)", name) is not None``.
    """
    return re.fullmatch(r"[0-9a-f]{16,64}\.(jpg|png|webp)", name) is not None


def save_photo(data: bytes, media_dir: str) -> str | None:
    """Store an uploaded photo and return its file name, or None when *data* is not a JPEG/PNG/WebP
    (use ``image_ext``) or is larger than MAX_PHOTO bytes.

    TODO (task E05) steps:
    1. ``ext = image_ext(data)``; None or ``len(data) > MAX_PHOTO`` → return None.
    2. ``folder = Path(media_dir) / "sightings"``; ``folder.mkdir(parents=True, exist_ok=True)``.
    3. ``name = secrets.token_hex(16) + "." + ext``; ``(folder / name).write_bytes(data)``; return name.
    """
    ext = image_ext(data)
    if ext is None or len(data) > MAX_PHOTO:
        return None
    folder = Path(media_dir) / "sightings"
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(16) + "." + ext
    (folder / name).write_bytes(data)
    return name


def sighting_stats(db: Session) -> dict[int, dict[str, Any]]:
    """Per species id that has sightings: ``{"count": int, "last": date}`` (number of sightings, newest seen_on).

    TODO (task E06): ``select(Sighting.species_id, func.count(), func.max(Sighting.seen_on)).group_by(Sighting.species_id)``,
    then a dict comprehension over the rows.
    """
    return {}


def find_species(db: Session, tab: str, q: str | None, verdict: str | None) -> list[Species]:
    """Species for the list (SPEC 15.1), ordered by name (case-insensitive).

    tab "catalogue": only ``Species.common`` true. Any other tab ("found"): only species with at least one
    sighting (``Species.id.in_(select(Sighting.species_id))``). *q*: case-insensitive substring of name or latin.
    *verdict*: when set, only that verdict.

    TODO (task E07): build the select with those ``where`` clauses (``from sqlalchemy import or_``),
    ``.order_by(func.lower(Species.name))``, return ``list(db.execute(stmt).scalars())``.
    """
    return []


def seed_catalogue(db: Session, path: Path = CATALOGUE) -> int:
    """Insert the catalogue entries whose name (case-insensitive) is not in the table yet; return how many.

    The file is a JSON list of ``{"name", "latin", "kind", "verdict", "description"}``; new rows get
    ``common=True``. Running it twice adds nothing the second time. End with ``db.flush()``
    (not commit: the caller commits).

    TODO (task E08) steps:
    1. ``have = {n.lower() for n in db.execute(select(Species.name)).scalars()}``.
    2. For each entry of ``json.loads(path.read_text())`` whose lower-cased name is not in *have*:
       ``db.add(Species(**entry, common=True))`` and add the name to *have*.
    3. ``db.flush()``; return the number added.
    """
    return 0


def sighting_json(x: Sighting, species: Species) -> dict[str, Any]:
    """One row of ``GET /api/v1/sightings`` (SPEC 15.8): id, species_id, species (the name), verdict,
    seen_on (``.isoformat()``), x, y, object_id, removed.

    TODO (task E09): build the dict.
    """
    return {"id": x.id}


# -- glue (done)
def _objects(db: Session) -> dict[int, str]:
    return {
        o.id: o.name for o in db.execute(select(GardenObject).order_by(GardenObject.name)).scalars()
    }


def _species(db: Session, species_id: int) -> Species:
    s = db.get(Species, species_id)
    if s is None:
        raise HTTPException(status_code=404, detail="No such species")
    return s


def _sightings(db: Session, species_id: int) -> list[Sighting]:
    stmt = (
        select(Sighting)
        .where(Sighting.species_id == species_id)
        .order_by(Sighting.seen_on.desc(), Sighting.id.desc())
    )
    return list(db.execute(stmt).scalars())


@router.get("/species")
async def species_page(
    request: Request, tab: str = "found", q: str = "", verdict: str = "", user: str = RequireUser
) -> HTMLResponse:
    tab = "catalogue" if tab == "catalogue" else "found"
    db = SessionLocal()
    try:
        rows = find_species(db, tab, q.strip() or None, verdict or None)
        stats = sighting_stats(db)
        items = [
            {
                "s": s,
                "kind": verdict_kind(s.verdict),
                "stats": stats.get(s.id),
                "remove": to_remove(s.verdict, _sightings(db, s.id)) if s.id in stats else 0,
            }
            for s in rows
        ]
        n_found = len(stats)
        n_cat = db.execute(
            select(func.count()).select_from(Species).where(Species.common.is_(True))
        ).scalar_one()
    finally:
        db.close()
    keep = "".join(f"&{k}={v}" for k, v in (("q", q), ("verdict", verdict)) if v)
    return render(
        request,
        "species.html",
        active="species",
        items=items,
        tab=tab,
        q=q,
        verdict=verdict,
        verdicts=[("", "Every verdict")] + [(v, v.title()) for v in SPECIES_VERDICTS],
        tabs=[
            (f"/species?tab=found{keep}", "Found", "🔎", n_found),
            (f"/species?tab=catalogue{keep}", "Catalogue", "📚", n_cat),
        ],
        current_tab=f"/species?tab={tab}{keep}",
    )


def _form_page(
    request: Request, s: Species | None, values: dict[str, Any], errors: dict[str, str]
) -> HTMLResponse:
    return render(
        request,
        "species_form.html",
        status_code=400 if errors else 200,
        active="species",
        sp=s,
        values=values,
        errors=errors,
        kinds=[(k, k.title()) for k in SPECIES_KINDS],
        verdicts=[(v, v.title()) for v in SPECIES_VERDICTS],
    )


def _detail(
    request: Request, db: Session, s: Species, values: dict[str, Any], errors: dict[str, str]
) -> HTMLResponse:
    objects = _objects(db)
    return render(
        request,
        "species_detail.html",
        status_code=400 if errors else 200,
        active="species",
        sp=s,
        kind=verdict_kind(s.verdict),
        sightings=[(x, objects.get(x.object_id or -1)) for x in _sightings(db, s.id)],
        values=values,
        errors=errors,
        objects=[("", "— none —")] + [(str(k), v) for k, v in objects.items()],
    )


@router.get("/species/new")
async def species_new(request: Request, user: str = RequireUser) -> HTMLResponse:
    return _form_page(request, None, {"kind": "plant", "verdict": "unknown"}, {})


@router.get("/species/{species_id}")
async def species_detail(
    request: Request, species_id: int, user: str = RequireUser
) -> HTMLResponse:
    db = SessionLocal()
    try:
        return _detail(
            request, db, _species(db, species_id), {"seen_on": date.today().isoformat()}, {}
        )
    finally:
        db.close()


@router.get("/species/{species_id}/edit")
async def species_edit(request: Request, species_id: int, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        s = _species(db, species_id)
        return _form_page(request, s, {k: getattr(s, k) for k in SPECIES_FIELDS}, {})
    finally:
        db.close()


async def _save(request: Request, species_id: int | None) -> HTMLResponse | RedirectResponse:
    form = {k: str(v) for k, v in (await request.form()).items()}
    db = SessionLocal()
    try:
        s = _species(db, species_id) if species_id is not None else None
        taken = {n.lower(): i for i, n in db.execute(select(Species.id, Species.name)).all()}
        values, errors = validate_species(form, taken, species_id)
        if errors:
            return _form_page(request, s, values, errors)
        if s is None:
            s = Species(common=False)
            db.add(s)
        for k in SPECIES_FIELDS:
            setattr(s, k, values[k])
        db.commit()
        sid = s.id
    finally:
        db.close()
    return RedirectResponse(f"/species/{sid}", status_code=303)


@router.post("/species", response_model=None)
async def species_create(
    request: Request, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, None)


@router.post("/species/{species_id}", response_model=None)
async def species_update(
    request: Request, species_id: int, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, species_id)


@router.post("/species/{species_id}/delete")
async def species_delete(species_id: int, user: str = RequireUser) -> RedirectResponse:
    db = SessionLocal()
    try:
        s = _species(db, species_id)
        for x in _sightings(db, species_id):
            _drop_photo(x)
            db.delete(x)
        db.delete(s)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/species", status_code=303)


@router.post("/species/{species_id}/sightings", response_model=None)
async def sighting_add(
    request: Request, species_id: int, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    text = {k: v for k, v in form.items() if isinstance(v, str)}
    upload = form.get("photo")
    db = SessionLocal()
    try:
        s = _species(db, species_id)
        values, errors = validate_sighting(text, set(_objects(db)))
        photo = None
        if not errors and upload is not None and not isinstance(upload, str) and upload.filename:
            photo = save_photo(await upload.read(MAX_PHOTO + 1), Settings().MEDIA_DIR)
            if photo is None:
                errors["photo"] = "A JPEG, PNG or WebP photo of at most 8 MB"
        if errors:
            return _detail(request, db, s, values, errors)
        db.add(Sighting(species_id=s.id, photo=photo, **values))
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/species/{species_id}", status_code=303)


def _drop_photo(x: Sighting) -> None:
    if x.photo and media_name_ok(x.photo):
        (Path(Settings().MEDIA_DIR) / "sightings" / x.photo).unlink(missing_ok=True)


def _sighting_action(sighting_id: int, act: str) -> RedirectResponse:
    db = SessionLocal()
    try:
        x = db.get(Sighting, sighting_id)
        if x is None:
            raise HTTPException(status_code=404, detail="No such sighting")
        sid = x.species_id
        if act == "delete":
            _drop_photo(x)
            db.delete(x)
        else:
            x.removed = not x.removed
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/species/{sid}", status_code=303)


@router.post("/sightings/{sighting_id}/removed")
async def sighting_removed(sighting_id: int, user: str = RequireUser) -> RedirectResponse:
    return _sighting_action(sighting_id, "removed")


@router.post("/sightings/{sighting_id}/delete")
async def sighting_delete(sighting_id: int, user: str = RequireUser) -> RedirectResponse:
    return _sighting_action(sighting_id, "delete")


@router.get("/media/sightings/{name}")
async def media(name: str, user: str = RequireUser) -> FileResponse:
    path = Path(Settings().MEDIA_DIR) / "sightings" / name
    if not media_name_ok(name) or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


@router.get("/api/v1/sightings")
async def api_sightings(user: str = RequireUser) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        stmt = (
            select(Sighting, Species)
            .join(Species, Species.id == Sighting.species_id)
            .order_by(Sighting.seen_on.desc(), Sighting.id.desc())
        )
        return [sighting_json(x, s) for x, s in db.execute(stmt).all()]
    finally:
        db.close()


def startup_seed() -> None:
    """Run seed_catalogue once when the app starts (main.py), unless SEED_CATALOGUE is off or the DB is down."""
    if not Settings().SEED_CATALOGUE:
        return
    db = SessionLocal()
    try:
        seed_catalogue(db)
        db.commit()
    except Exception:  # noqa: BLE001  (a missing DB must not stop the site)
        db.rollback()
    finally:
        db.close()
