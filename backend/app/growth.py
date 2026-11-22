"""Growth model and best spot (SPEC §16, private).

Growing degree days (GDD) from the station's own air temperature tell how far a planting is, and when it will be
ready at the current pace. "Best spot" ranks the beds for a crop by sun, soil moisture and crop rotation.

The page and its data queries are done (human-owned glue at the bottom). The loop fills in the small pure
functions marked ``TODO (task Axx)``: ``grep -n "TODO (task" app/growth.py``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

import math  # noqa: F401  (math: task A05)
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.db import SessionLocal
from app.models import Crop, GardenObject, Planting, Reading
from app.objects import idw, soil_points
from app.tasks import local_today
from app.templating import render

router = APIRouter()

AMS = ZoneInfo("Europe/Amsterdam")
CAP_C = 30.0  # above this, plants don't grow faster
SUN_NEED = {"full": 6, "partial": 3, "shade": 0}  # hours of direct sun a crop wants
BED_KINDS = ("bed", "greenhouse", "patch")


def daily_gdd(tmin: float, tmax: float, base: float, cap: float = CAP_C) -> float:
    """Growing degree days for one day."""
    hi = min(tmax, cap)
    lo = max(tmin, base)
    if hi < lo:
        hi = lo
    gdd = (hi + lo) / 2 - base
    return max(0.0, gdd)


def local_daily_temps(rows: list[tuple[datetime, float]]) -> dict[date, tuple[float, float]]:
    """Daily ``(min, max)`` per Europe/Amsterdam date from ``[(timestamp, temp_c)]`` readings.

    TODO (task A02) steps:
    1. For each ``(ts, value)``: a ``ts`` without tzinfo is UTC (``ts.replace(tzinfo=UTC)``); the day is
       ``ts.astimezone(AMS).date()``.
    2. Keep the lowest and highest value per day; return ``{day: (min, max)}``.
    """
    days: dict[date, list[float]] = {}
    for ts, value in rows:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        day = ts.astimezone(AMS).date()
        days.setdefault(day, []).append(value)
    return {d: (min(vs), max(vs)) for d, vs in days.items()}


def gdd_series(
    temps: dict[date, tuple[float, float]], start: date, end: date, base: float
) -> list[tuple[date, float]]:
    """``[(day, gdd)]`` for every day from *start* to *end* (both included) that has temperatures, oldest first.

    TODO (task A03) steps:
    1. ``start > end`` → ``[]``.
    2. Walk ``day = start`` … ``end`` with ``timedelta(days=1)``; skip days not in *temps*; for the others
       append ``(day, daily_gdd(tmin, tmax, base))``.
    """
    if start > end:
        return []
    result: list[tuple[date, float]] = []
    day = start
    while day <= end:
        if day in temps:
            tmin, tmax = temps[day]
            result.append((day, daily_gdd(tmin, tmax, base)))
        day = day + timedelta(days=1)
    return result


def progress(gdd_done: float, gdd_needed: float | None) -> float | None:
    """How far a planting is, 0.0–1.0; None when the crop's GDD to harvest is unknown or not positive.

    TODO (task A04): None or ``<= 0`` → None; else ``min(1.0, gdd_done / gdd_needed)``, rounded to 3 decimals.
    """
    if gdd_needed is None or gdd_needed <= 0:
        return None
    return round(min(1.0, gdd_done / gdd_needed), 3)


def harvest_eta(
    gdd_done: float, gdd_needed: float | None, recent: list[float], today: date
) -> date | None:
    """The day the planting reaches its GDD at the pace of the *recent* days (a list of daily GDD values).

    TODO (task A05) steps:
    1. *gdd_needed* None or ``<= 0`` → None. Already ``gdd_done >= gdd_needed`` → *today*.
    2. No *recent* values → None. ``rate = sum(recent) / len(recent)``; ``rate < 0.1`` → None (too cold to say).
    3. ``days = math.ceil((gdd_needed - gdd_done) / rate)``; return ``today + timedelta(days=days)``.
    """
    if gdd_needed is None or gdd_needed <= 0:
        return None
    if gdd_done >= gdd_needed:
        return today
    if not recent:
        return None
    rate = sum(recent) / len(recent)
    if rate < 0.1:
        return None
    days = math.ceil((gdd_needed - gdd_done) / rate)
    return today + timedelta(days=days)


def sun_fit(crop_sun: str | None, sun_hours: float | None) -> tuple[float, str]:
    """How well a bed's sun suits the crop: ``(score 0.0–1.0, reason)``.

    TODO (task A06) steps:
    1. ``need = SUN_NEED.get(crop_sun or "full", 6)``.
    2. *sun_hours* None → ``(0.5, "sun hours unknown")``.
    3. ``sun_hours >= need`` → ``(1.0, f"{sun_hours:g} h sun (needs {need}+)")``.
    4. Otherwise ``(round(sun_hours / need, 2), f"only {sun_hours:g} h sun (needs {need}+)")``.
    """
    need = SUN_NEED.get(crop_sun or "full", 6)
    if sun_hours is None:
        return 0.5, "sun hours unknown"
    if sun_hours >= need:
        return 1.0, f"{sun_hours:g} h sun (needs {need}+)"
    return round(sun_hours / need, 2), f"only {sun_hours:g} h sun (needs {need}+)"


def moisture_fit(avg: float | None, lo: float | None, hi: float | None) -> tuple[float, str]:
    """How well a bed's soil moisture suits the crop: ``(score 0.0–1.0, reason)``.

    TODO (task A07) steps:
    1. *avg*, *lo* or *hi* None → ``(0.5, "no soil data")``.
    2. ``lo <= avg <= hi`` → ``(1.0, f"soil {avg:.0f}% suits it ({lo:.0f}–{hi:.0f}%)")``.
    3. Below *lo*: ``gap = lo - avg``, reason ``f"too dry: {avg:.0f}% (needs {lo:.0f}–{hi:.0f}%)"``; above *hi*:
       ``gap = avg - hi``, reason ``f"too wet: {avg:.0f}% (needs {lo:.0f}–{hi:.0f}%)"``.
       Score ``round(max(0.0, 1 - gap / 20), 2)``.
    """
    return 0.5, ""


def score_spot(
    crop: Crop, sun_hours: float | None, moisture: float | None, rotation_hit: bool
) -> tuple[int, list[str]]:
    """Score one bed for *crop*: ``(0–100, reasons)``. Sun counts 40 %, moisture 40 %, rotation 20 %.

    TODO (task A08) steps:
    1. ``s, s_why = sun_fit(crop.sun, sun_hours)``; ``m, m_why = moisture_fit(moisture, crop.moisture_min_pct, crop.moisture_max_pct)``.
    2. Rotation: *rotation_hit* → ``r, r_why = 0.0, "same family here in the last 3 years"``; else ``1.0, "rotation ok"``.
    3. Return ``(round(100 * (0.4 * s + 0.4 * m + 0.2 * r)), [s_why, m_why, r_why])``.
    """
    return 0, []


def best_spots(candidates: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """The *n* best beds. Each candidate is ``{"name", "score", "reasons"}``.

    TODO (task A09): sort by score (highest first), then name (case-insensitive, A first); return the first *n*.
    """
    return []


# -- glue (done)
def _temps(db: Session, since: date) -> dict[date, tuple[float, float]]:
    start = datetime.combine(since - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    rows = db.execute(
        select(Reading.ts, Reading.value).where(Reading.metric == "temp_c", Reading.ts >= start)
    ).all()
    return local_daily_temps([(ts, float(v)) for ts, v in rows])


def _rotation_hit(db: Session, object_id: int, family: str | None, year: int) -> bool:
    if not family:
        return False
    stmt = (
        select(func.count())
        .select_from(Planting)
        .join(Crop, Crop.id == Planting.crop_id)
        .where(
            Planting.object_id == object_id,
            func.lower(Crop.family) == family.lower(),
            Planting.sown_on >= date(year - 3, 1, 1),
            Planting.sown_on < date(year, 1, 1),
        )
    )
    return bool(db.execute(stmt).scalar())


def growth_rows(db: Session, today: date) -> list[dict[str, Any]]:
    stmt = (
        select(Planting, Crop)
        .join(Crop, Crop.id == Planting.crop_id)
        .where(Planting.status.not_in(("done", "failed", "planned")))
        .order_by(Planting.sown_on)
    )
    pairs = db.execute(stmt).all()
    if not pairs:
        return []
    temps = _temps(db, min(p.sown_on for p, _ in pairs))
    objects = {o.id: o.name for o in db.execute(select(GardenObject)).scalars()}
    out = []
    for p, c in pairs:
        series = gdd_series(
            temps, p.sown_on, today, c.base_temp_c if c.base_temp_c is not None else 5.0
        )
        done = sum(g for _, g in series)
        recent = [g for d, g in series if d > today - timedelta(days=14)]
        frac = progress(done, c.gdd_to_harvest)
        out.append(
            {
                "planting": p,
                "crop": c,
                "bed": objects.get(p.object_id or -1),
                "gdd": round(done),
                "days": len(series),
                "pct": None if frac is None else round(frac * 100),
                "eta": harvest_eta(done, c.gdd_to_harvest, recent, today),
            }
        )
    return out


def spot_rows(db: Session, crop: Crop, today: date) -> list[dict[str, Any]]:
    beds = list(
        db.execute(
            select(GardenObject).where(GardenObject.kind.in_(BED_KINDS)).order_by(GardenObject.name)
        ).scalars()
    )
    points = soil_points(db)
    cands = []
    for b in beds:
        sun = b.props.get("sun_hours") if isinstance(b.props, dict) else None
        moisture = idw(b.x, b.y, points) if points else None
        score, reasons = score_spot(
            crop, sun, moisture, _rotation_hit(db, b.id, crop.family, today.year)
        )
        cands.append({"name": b.name, "score": score, "reasons": reasons})
    return best_spots(cands)


@router.get("/growth")
async def growth_page(request: Request, crop: str = "", user: str = RequireUser) -> HTMLResponse:
    today = local_today()
    db = SessionLocal()
    try:
        rows = growth_rows(db, today)
        crops = list(db.execute(select(Crop).order_by(func.lower(Crop.name))).scalars())
        chosen = next((c for c in crops if str(c.id) == crop), None)
        spots = spot_rows(db, chosen, today) if chosen else []
    finally:
        db.close()
    return render(
        request,
        "growth.html",
        active="growth",
        rows=rows,
        today=today,
        crops=[("", "Pick a crop…")] + [(str(c.id), c.name) for c in crops],
        chosen=chosen,
        spots=spots,
    )


@router.get("/api/v1/growth")
async def api_growth(user: str = RequireUser) -> list[dict[str, Any]]:
    today = local_today()
    db = SessionLocal()
    try:
        rows = growth_rows(db, today)
    finally:
        db.close()
    return [
        {
            "planting_id": r["planting"].id,
            "crop": r["crop"].name,
            "gdd": r["gdd"],
            "gdd_to_harvest": r["crop"].gdd_to_harvest,
            "progress": r["pct"],
            "eta": r["eta"].isoformat() if r["eta"] else None,
        }
        for r in rows
    ]
