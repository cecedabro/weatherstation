"""Sensors page (SPEC §11.1, 11.2, 11.4–11.8): `/sensors` and the 301 redirects of the old pages.

The routes, `page_context` and `templates/sensors.html` are done (human-owned glue). The loop fills in the
small functions marked ``TODO (task Sxx)``, one task at a time: ``grep -n "TODO (task" app/sensors.py``.
Every function here gets plain values (no request), so its step test can call it directly.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.fmt import compass  # noqa: F401  (task S05 uses it)
from app.models import Node, Reading  # noqa: F401  (tasks S05 and S07 query Reading)
from app.stats import daily_stats, summarize
from app.templating import render

router = APIRouter()

# key -> (label, icon, metrics). Air, rain and wind read one weather node; soil reads every soil node.
CATEGORIES: dict[str, tuple[str, str, list[str]]] = {
    "air": ("Air", "🌡️", ["temp_c", "humidity_pct", "pressure_hpa"]),
    "soil": ("Soil", "🌱", ["soil_moisture_pct", "soil_temp_c"]),
    "rain": ("Rain", "🌧️", ["rain_mm"]),
    "wind": ("Wind", "💨", ["wind_speed_ms", "wind_dir_deg"]),
}
# key -> (label, hours)
RANGES: dict[str, tuple[str, int]] = {
    "24h": ("Day", 24),
    "7d": ("Week", 168),
    "30d": ("Month", 720),
    "90d": ("Season", 2160),
    "365d": ("Year", 8760),
}
# metric -> (title, unit)
METRICS: dict[str, tuple[str, str]] = {
    "temp_c": ("Temperature", "°C"),
    "humidity_pct": ("Humidity", "%"),
    "pressure_hpa": ("Pressure", "hPa"),
    "rain_mm": ("Rain", "mm"),
    "wind_speed_ms": ("Wind speed", "m/s"),
    "wind_dir_deg": ("Wind direction", "°"),
    "soil_moisture_pct": ("Soil moisture", "%"),
    "soil_temp_c": ("Soil temperature", "°C"),
}
MAX_DAILY_ROWS = 31


@dataclass(frozen=True)
class View:
    """What the page shows: category, range key, node id (None = no node of that kind) and compare days."""

    cat: str = "air"
    range: str = "7d"
    node: str | None = None
    compare: tuple[date, ...] = ()


def parse_compare(raw: str | None) -> tuple[date, ...]:
    """``"2026-11-20,2026-11-21,oops"`` → ``(date(2026, 11, 20), date(2026, 11, 21))``.

    TODO (task S03) steps:
    1. ``None`` or ``""`` → ``()``.
    2. Split on ``","``, strip each part, keep the parts that ``date.fromisoformat`` accepts
       (catch ``ValueError``); skip a date that is already in the list.
    3. Return at most the first 3 as a tuple, in the given order.
    """
    if not raw:
        return ()
    result: list[date] = []
    seen: set[str] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            d = date.fromisoformat(part)
        except ValueError:
            continue
        key = d.isoformat()
        if key in seen:
            continue
        seen.add(key)
        result.append(d)
        if len(result) >= 3:
            break
    return tuple(result)


def parse_view(params: dict[str, str], nodes: list[str]) -> View:
    """Turn query parameters into a View (SPEC 11.1). *nodes* are the ids of the category's nodes.

    TODO (task S03) steps:
    1. ``cat = params.get("cat")``; not a key of ``CATEGORIES`` → ``"air"``.
    2. ``range = params.get("range")``; not a key of ``RANGES`` → ``"7d"``.
    3. ``node = params.get("node")`` if it is in *nodes*, else ``sorted(nodes)[0]``, or ``None`` when
       *nodes* is empty.
    4. ``compare = parse_compare(params.get("compare"))``.
    (The route works out *nodes* from the category, so it calls this twice: once to learn the category.)
    """
    cat = params.get("cat", "") if params.get("cat") in CATEGORIES else "air"
    rng = params.get("range", "") if params.get("range") in RANGES else "7d"
    if not nodes:
        node: str | None = None
    else:
        node = params.get("node")
        if node not in nodes:
            node = sorted(nodes)[0]
    compare = parse_compare(params.get("compare"))
    return View(cat=cat, range=rng, node=node, compare=compare)


def view_href(view: View, **changes: Any) -> str:
    """Link to /sensors for *view* with *changes* applied, e.g. ``view_href(v, range="30d")``.

    Query order: cat, range, node, compare. Leave out ``node`` when it is None and ``compare`` when it is
    empty; compare is the dates joined with ``","`` (``date.isoformat()``). Changing ``cat`` drops node and
    compare (nodes differ per category).
    Example: ``view_href(View("air", "7d", "weather-b"), range="30d")`` →
    ``"/sensors?cat=air&range=30d&node=weather-b"``.

    TODO (task S04) steps:
    1. ``data = {"cat": view.cat, "range": view.range, "node": view.node, "compare": view.compare}``;
       if ``"cat"`` is in *changes*, set node to None and compare to ``()`` first; then ``data.update(changes)``.
    2. Build a list of (key, value) pairs in that order, skipping None node and empty compare.
    3. Return ``"/sensors?" + urlencode(pairs, safe=",")``.
    """
    data: dict[str, Any] = {"cat": view.cat, "range": view.range, "node": view.node, "compare": view.compare}
    if "cat" in changes:
        data["node"] = None
        data["compare"] = ()
    data.update(changes)
    pairs: list[tuple[str, str]] = []
    pairs.append(("cat", str(data["cat"])))
    pairs.append(("range", str(data["range"])))
    node = data.get("node")
    if node is not None:
        pairs.append(("node", str(node)))
    compare = data.get("compare")
    if compare:
        pairs.append(("compare", ",".join(d.isoformat() for d in compare)))
    return "/sensors?" + urlencode(pairs, safe=",")


def range_window(range_key: str, now: datetime) -> tuple[datetime, datetime]:
    """``(now - hours of RANGES[range_key], now)``. Unknown key → the 7d window.

    TODO (task S04): one line per step: look up the hours (default 168), return the tuple.
    """
    hours = RANGES.get(range_key, ("Week", 168))[1]
    return now - timedelta(hours=hours), now


def daily_days(range_key: str) -> int:
    """Number of days for the daily table: range hours / 24, at least 1, at most MAX_DAILY_ROWS (31).

    TODO (task S04): ``24h`` → 1, ``7d`` → 7, ``30d`` → 30, ``90d`` and ``365d`` → 31; unknown → 7.
    """
    hours = RANGES.get(range_key, ("Week", 168))[1]
    return max(1, min(hours // 24, MAX_DAILY_ROWS))


def latest(db: Session, node: str, metric: str) -> float | None:
    """The value of the newest reading of *node*/*metric*, or None."""
    stmt = (
        select(Reading.value)
        .where(Reading.node_id == node, Reading.metric == metric)
        .order_by(Reading.ts.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    return float(row) if row is not None else None


def tiles(metric: str, summary: dict[str, Any], last: float | None) -> list[tuple[str, Any, str]]:
    """Stat tiles for one metric card: a list of ``(label, value, unit)``; unit from ``METRICS``.

    - ``rain_mm``: ``[("Latest", last, "mm"), ("Total", summary["sum"], "mm")]``
    - ``wind_dir_deg``: ``[("Latest", text, "")]`` where text is ``"W 270°"`` (``compass(last)`` + space +
      the degrees rounded to an int + ``"°"``), or ``None`` when *last* is None.
    - any other metric: ``Latest`` (*last*), ``Min``, ``Max``, ``Average`` (summary min, max, avg).
    """
    unit = METRICS.get(metric, ("", ""))[1]
    if metric == "rain_mm":
        return [("Latest", last, "mm"), ("Total", summary["sum"], "mm")]
    elif metric == "wind_dir_deg":
        if last is None:
            return [("Latest", None, "")]
        return [("Latest", f"{compass(last)} {round(last)}°", "")]
    else:
        return [
            ("Latest", last, unit),
            ("Min", summary["min"], unit),
            ("Max", summary["max"], unit),
            ("Average", summary["avg"], unit),
        ]


def merge_daily(per_metric: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Join the daily_stats rows of several metrics into table rows, newest day first, at most 31.

    Input: ``{"temp_c": [{"date": "2026-11-20", "min": …}, …], "rain_mm": [...]}``.
    Output: ``[{"date": "2026-11-21", "temp_c": {row}, "rain_mm": None}, …]``: one row per date that any
    metric has, every metric of the input as a key (its row for that date, or None).

    TODO (task S06) steps:
    1. Collect all dates (a set) from every metric's rows.
    2. For each date, sorted newest first, make ``{"date": d}`` plus ``{metric: row or None}``.
    3. Return the first ``MAX_DAILY_ROWS``.
    """
    return []


def soil_rows(db: Session, nodes: list[str]) -> list[dict[str, Any]]:
    """Latest soil values per node, for the soil table: ``[{"node", "soil_moisture_pct", "soil_temp_c"}]``.

    In the order of *nodes*; a value is None when the node has no such reading.

    TODO (task S07): for each node call ``latest(db, node, metric)`` for both metrics.
    """
    return []


def compare_rows(
    db: Session, node: str, metric: str, days: tuple[date, ...]
) -> list[dict[str, Any]]:
    """Per compare day: ``{"date": "YYYY-MM-DD", "min", "max", "avg"}`` over that UTC day.

    TODO (task S08): for each day, ``start = datetime(d.year, d.month, d.day, tzinfo=UTC)``,
    ``s = summarize(db, node, metric, start, start + timedelta(days=1))``, take min/max/avg from *s*.
    """
    return []


def csv_href(node: str, metric: str, start: datetime, end: datetime) -> str:
    """Link to the CSV export (SPEC 11.6): ``/api/v1/export.csv?node=…&metric=…&from=…&to=…``.

    Times as RFC3339 UTC with a ``Z`` and no microseconds, e.g. ``2026-11-21T08:00:00Z``.

    TODO (task S08): format both times (``.astimezone(UTC).replace(microsecond=0).isoformat()`` and
    swap ``+00:00`` for ``Z``), then ``"/api/v1/export.csv?" + urlencode([...])``.
    """
    return "/api/v1/export.csv"


# -- page (done)
def _node_ids(db: Session, cat: str) -> list[str]:
    kind = "soil" if cat == "soil" else "weather"
    return list(
        db.execute(
            select(Node.node_id).where(Node.node_type == kind).order_by(Node.node_id)
        ).scalars()
    )


def page_context(db: Session, view: View, nodes: list[str], now: datetime) -> dict[str, Any]:
    """Everything sensors.html needs. Human-owned glue around the functions above."""
    label, icon, metrics = CATEGORIES[view.cat]
    start, end = range_window(view.range, now)
    ctx: dict[str, Any] = {
        "view": view,
        "cat_label": label,
        "nodes": nodes,
        "tabs": [
            (view_href(view, cat=k), lbl, ic, None) for k, (lbl, ic, _m) in CATEGORIES.items()
        ],
        "current_tab": view_href(view, cat=view.cat),
        "ranges": [(k, lbl) for k, (lbl, _h) in RANGES.items()],
        "range_href": lambda k: view_href(view, range=k),
        "node_href": lambda n: view_href(view, node=n),
        "cards": [],
        "daily": [],
        "metrics": [(m, *METRICS[m]) for m in metrics],
    }
    if not view.node:
        return ctx
    for m in metrics:
        title, unit = METRICS[m]
        if view.cat == "soil":
            series = [(n, m, n) for n in nodes]
            tile_list: list[tuple[str, Any, str]] = []
        else:
            series = [(view.node, m, title)]
            tile_list = tiles(m, summarize(db, view.node, m, start, end), latest(db, view.node, m))
        ctx["cards"].append(
            {
                "metric": m,
                "title": title,
                "unit": unit,
                "kind": "bar" if m == "rain_mm" else "line",
                "series": series,
                "tiles": tile_list,
                "csv": csv_href(view.node, m, start, end),
            }
        )
    days = daily_days(view.range)
    ctx["daily"] = merge_daily({m: daily_stats(db, view.node, m, days, now) for m in metrics})
    if view.cat == "soil":
        ctx["soil"] = soil_rows(db, nodes)
    if view.compare:
        m0 = metrics[0]
        ctx["compare_metric"] = (m0, *METRICS[m0])
        ctx["compare_series"] = [
            (view.node, m0, METRICS[m0][0], d.isoformat()) for d in view.compare
        ]
        ctx["compare_rows"] = compare_rows(db, view.node, m0, view.compare)
    return ctx


@router.get("/sensors")
async def sensors(request: Request) -> HTMLResponse:
    """SPEC 11.1. The compare form sends d1..d3; they are joined into ``compare``."""
    params = dict(request.query_params)
    if not params.get("compare"):
        picked = [params.get(f"d{i}", "") for i in (1, 2, 3)]
        params["compare"] = ",".join(p for p in picked if p)
    db = SessionLocal()
    try:
        cat = parse_view(params, []).cat
        nodes = _node_ids(db, cat)
        view = parse_view(params, nodes)
        ctx = page_context(db, view, nodes, datetime.now(UTC))
    finally:
        db.close()
    return render(request, "sensors.html", active="sensors", **ctx)


# -- SPEC 11.7 redirects (done)
@router.get("/weather")
async def old_weather() -> RedirectResponse:
    return RedirectResponse("/sensors?cat=air", status_code=301)


@router.get("/history")
async def old_history() -> RedirectResponse:
    return RedirectResponse("/sensors?cat=air&range=30d", status_code=301)


@router.get("/soil")
async def old_soil() -> RedirectResponse:
    return RedirectResponse("/sensors?cat=soil", status_code=301)


@router.get("/soil/{node_id}")
async def old_soil_node(node_id: str) -> RedirectResponse:
    return RedirectResponse(
        "/sensors?" + urlencode({"cat": "soil", "node": node_id}), status_code=301
    )
