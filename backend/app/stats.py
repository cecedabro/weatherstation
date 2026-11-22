"""Reading statistics (SPEC 11.3, 11.4): `summarize` and `daily_stats`, plus their two API routes.

The routes are done (human-owned glue). The loop fills in the two functions, one task each:
`grep -n "TODO (task" app/stats.py`.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Reading  # noqa: F401  (the functions below query it)
from app.readapi import _parse_dt

router = APIRouter()


def summarize(
    db: Session, node: str, metric: str, start: datetime, end: datetime
) -> dict[str, Any]:
    """Statistics over the raw readings of *node*/*metric* with ``start <= ts < end``.

    Returns ``{"node", "metric", "count", "min", "max", "avg", "sum", "first_ts", "last_ts"}``:
    ``count`` is an int, ``min``/``max``/``avg``/``sum`` are floats, ``first_ts``/``last_ts`` are the
    datetimes of the oldest and newest reading. No readings → ``count`` 0 and all the others ``None``.

    TODO (task S01) steps:
    1. One query: ``select(func.count(), func.min(Reading.value), func.max(Reading.value),
       func.avg(Reading.value), func.sum(Reading.value), func.min(Reading.ts), func.max(Reading.ts))``
       ``.where(Reading.node_id == node, Reading.metric == metric, Reading.ts >= start, Reading.ts < end)``,
       run it with ``db.execute(stmt).one()``.
    2. Convert min/max/avg/sum with ``float(x)`` when they are not None (avg comes back as Decimal).
    3. If count is 0 return the dict with count 0 and every other value None (node and metric filled).
    Imports you need: ``from sqlalchemy import func, select``.
    """
    stmt = (
        select(
            func.count(),
            func.min(Reading.value),
            func.max(Reading.value),
            func.avg(Reading.value),
            func.sum(Reading.value),
            func.min(Reading.ts),
            func.max(Reading.ts),
        )
        .where(
            Reading.node_id == node,
            Reading.metric == metric,
            Reading.ts >= start,
            Reading.ts < end,
        )
    )
    row = db.execute(stmt).one()

    count = row[0]
    if count == 0:
        return {"node": node, "metric": metric, "count": 0, "min": None, "max": None,
                "avg": None, "sum": None, "first_ts": None, "last_ts": None}

    return {
        "node": node,
        "metric": metric,
        "count": count,
        "min": float(row[1]),
        "max": float(row[2]),
        "avg": float(row[3]),
        "sum": float(row[4]),
        "first_ts": row[5],
        "last_ts": row[6],
    }


def daily_stats(
    db: Session, node: str, metric: str, days: int, now: datetime | None = None
) -> list[dict[str, Any]]:
    """One row per UTC day over the last *days* days, oldest first; days without readings are left out.

    A row is ``{"date": "YYYY-MM-DD", "min", "max", "avg", "sum", "count"}`` (floats, count an int).
    The window starts at midnight UTC ``days - 1`` days before *now* (default: ``datetime.now(UTC)``),
    so ``days=1`` is today only. *days* outside 1–366 raises ``ValueError``.

    TODO (task S02) steps:
    1. Validate *days* (1–366) first, else ``raise ValueError("days must be 1-366")``.
    2. ``start = (now).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)``.
    3. ``day = func.date_trunc("day", func.timezone("UTC", Reading.ts))``; select ``day``, count, min, max,
       avg, sum of ``Reading.value`` where node, metric and ``Reading.ts >= start``; ``group_by(day)``,
       ``order_by(day)``.
    4. Each row → the dict above, ``"date": row_day.date().isoformat()``, numbers through ``float()``.
    Imports you need: ``from sqlalchemy import func, select``.
    """
    if not 1 <= days <= 366:
        raise ValueError("days must be 1-366")
    return []


# -- routes (done)
def _window(from_ts: str | None, to_ts: str | None) -> tuple[datetime, datetime]:
    try:
        start, end = _parse_dt(from_ts), _parse_dt(to_ts)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Bad date; use RFC3339 UTC") from None
    end = end or datetime.now(UTC)
    return (start or end - timedelta(days=7)), end


@router.get("/api/v1/summary")
async def api_summary(
    node: str = Query(...),
    metric: str = Query(...),
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    """SPEC 11.3."""
    start, end = _window(from_ts, to_ts)
    db = SessionLocal()
    try:
        out = summarize(db, node, metric, start, end)
    finally:
        db.close()
    for key in ("first_ts", "last_ts"):
        if out.get(key) is not None:
            out[key] = out[key].astimezone(UTC).isoformat().replace("+00:00", "Z")
    return out


@router.get("/api/v1/daily_stats")
async def api_daily_stats(
    node: str = Query(...), metric: str = Query(...), days: str = Query("30")
) -> list[dict[str, Any]]:
    """SPEC 11.4."""
    try:
        n = int(days)
        if not 1 <= n <= 366:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="days must be 1-366") from None
    db = SessionLocal()
    try:
        return daily_stats(db, node, metric, n)
    finally:
        db.close()
