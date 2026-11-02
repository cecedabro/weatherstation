"""HTML routes: GET / (home page)."""

from pathlib import Path
from typing import TypedDict
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.db import SessionLocal
from app.fmt import _register_filters
from app.readapi import _current_readings


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
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        first_weather_node = weather_nodes[0]["node_id"] if weather_nodes else None
        template = _jinja_env.get_template("home.html")
        html = template.render(
            weather_nodes=weather_nodes,
            soil_nodes=soil_nodes,
            chart_selectors=_selector_links(),
            first_weather_node=first_weather_node,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()
