"""HTML routes: GET / (home page)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from app.db import SessionLocal
from app.fmt import _register_filters
from app.readapi import _current_readings, _daily_aggregation, _garden_alerts


class _SelectorSpec(TypedDict):
    label: str
    step: str
    hours: int


DAY_LABEL = "24h"
WEEK_LABEL = "7d"
MONTH_LABEL = "30d"

DAY_SELECTOR: _SelectorSpec = {"label": DAY_LABEL, "step": "5m", "hours": 24}
WEEK_SELECTOR: _SelectorSpec = {"label": WEEK_LABEL, "step": "1h", "hours": 168}
MONTH_SELECTOR: _SelectorSpec = {"label": MONTH_LABEL, "step": "1d", "hours": 720}
_SELECTORS: list[_SelectorSpec] = [DAY_SELECTOR, WEEK_SELECTOR, MONTH_SELECTOR]

_SELECTOR_HOURS: dict[str, int] = {
    DAY_LABEL: 24,
    WEEK_LABEL: 168,
    MONTH_LABEL: 720,
}

router = APIRouter()

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _BASE_DIR / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)
_register_filters(_jinja_env)


def _selector_links() -> list[dict[str, str]]:
    """Build chart selector links with from/to/step for the series API."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    links: list[dict[str, str]] = []
    for sel in _SELECTORS:
        from_dt = now - timedelta(hours=sel["hours"])
        link: dict[str, str] = {
            "label": sel["label"],
            "step": sel["step"],
            "from": quote(from_dt.isoformat()),
            "to": quote(now.isoformat()),
        }
        links.append(link)
    return links


@router.get("/")
async def index() -> HTMLResponse:
    """Render the home page with current conditions per SPEC 5.1."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        now = datetime.now(UTC)
        for node in all_nodes:
            rt = node.get("reading_time")
            if rt is not None:
                offline = (now - rt) > timedelta(minutes=15)
                node["offline"] = offline
            else:
                node["offline"] = True
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        first_weather_node = weather_nodes[0]["node_id"] if weather_nodes else None
        alerts = _garden_alerts(db)
        template = _jinja_env.get_template("home.html")
        html = template.render(
            weather_nodes=weather_nodes,
            soil_nodes=soil_nodes,
            chart_selectors=_selector_links(),
            first_weather_node=first_weather_node,
            alerts=alerts,
            active="home",
            page_title="Current Conditions",
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/partials/current")
async def current_partial() -> HTMLResponse:
    """Return current-conditions + soil fragment for HTMX per SPEC 10.10."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        now = datetime.now(UTC)
        for node in all_nodes:
            rt = node.get("reading_time")
            if rt is not None:
                offline = (now - rt) > timedelta(minutes=15)
                node["offline"] = offline
            else:
                node["offline"] = True
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        template = _jinja_env.get_template("_current.html")
        html = template.render(
            weather_nodes=weather_nodes,
            soil_nodes=soil_nodes,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/weather")
async def weather_page() -> HTMLResponse:
    """Render the weather page per SPEC 10.2."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        now = datetime.now(UTC)
        for node in all_nodes:
            rt = node.get("reading_time")
            if rt is not None:
                offline = (now - rt) > timedelta(minutes=15)
                node["offline"] = offline
            else:
                node["offline"] = True
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
        template = _jinja_env.get_template("weather.html")
        html = template.render(
            weather_nodes=weather_nodes,
            chart_selectors=_selector_links(),
            active="weather",
            page_title="Weather",
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/soil")
async def soil_page() -> HTMLResponse:
    """Render the soil page per SPEC 10.3."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        now = datetime.now(UTC)
        for node in all_nodes:
            rt = node.get("reading_time")
            if rt is not None:
                offline = (now - rt) > timedelta(minutes=15)
                node["offline"] = offline
            else:
                node["offline"] = True
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        template = _jinja_env.get_template("soil.html")
        html = template.render(
            soil_nodes=soil_nodes,
            active="soil",
            page_title="Soil",
            now=now,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/soil/{node_id}")
async def soil_detail_page(node_id: str) -> HTMLResponse:
    """Render a single soil node detail page per SPEC 10.4."""
    from fastapi import HTTPException

    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        now = datetime.now(UTC)
        for node in all_nodes:
            rt = node.get("reading_time")
            if rt is not None:
                offline = (now - rt) > timedelta(minutes=15)
                node["offline"] = offline
            else:
                node["offline"] = True
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        detail = next((n for n in soil_nodes if n["node_id"] == node_id), None)
        if detail is None:
            raise HTTPException(status_code=404, detail="Node not found")
        template = _jinja_env.get_template("soil_detail.html")
        html = template.render(
            node=detail,
            chart_selectors=_selector_links(),
            active="soil",
            page_title=f"Soil — {node_id}",
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/history")
async def history_page(node: str | None = Query(None)) -> HTMLResponse:
    """Render the history page per SPEC 10.5."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]

        # Pick the node to show
        selected_node: str | None = None
        if node:
            # Use ?node= only if it matches a known weather node
            if any(n["node_id"] == node for n in weather_nodes):
                selected_node = node
        elif len(weather_nodes) > 1:
            # Default to first weather node when there are several
            selected_node = weather_nodes[0]["node_id"]
        elif len(weather_nodes) == 1:
            selected_node = weather_nodes[0]["node_id"]

        daily_data: list[dict[str, Any]] = []
        if selected_node:
            try:
                daily_data = _daily_aggregation(db, node=selected_node, days=30)
            except ValueError:
                daily_data = []
        # Reverse for newest-first display
        daily_data = list(reversed(daily_data))

        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        template = _jinja_env.get_template("history.html")
        html = template.render(
            daily_data=daily_data,
            weather_nodes=weather_nodes,
            soil_nodes=soil_nodes,
            selected_node=selected_node,
            active="history",
            page_title="History",
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/about")
async def about_page() -> HTMLResponse:
    """Render the about page per SPEC 10.8."""
    from app.models import Node

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=15)
        nodes_rows = db.execute(select(Node).order_by(Node.node_id.asc())).scalars().all()
        nodes = []
        for n in nodes_rows:
            last_seen = n.last_seen
            nodes.append(
                {
                    "node_id": str(n.node_id),
                    "node_type": n.node_type,
                    "first_seen": n.first_seen,
                    "last_seen": last_seen,
                    "online": bool(last_seen and last_seen >= cutoff),
                }
            )
        template = _jinja_env.get_template("about.html")
        html = template.render(
            nodes=nodes,
            active="about",
            page_title="About",
            now=now,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()
