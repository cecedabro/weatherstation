"""Public pages: overview (/), its live partial, about, the styleguide, and the placeholders for the
pages later loops build. Page code renders through app.templating.render (layout context)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.auth import RequireUser
from app.db import SessionLocal
from app.models import Node
from app.readapi import _current_readings, _garden_alerts
from app.templating import env as _jinja_env  # noqa: F401  (admin.py and older code import it from here)
from app.templating import render

router = APIRouter()

OFFLINE_AFTER = timedelta(minutes=15)


def _now_context() -> dict[str, Any]:
    """Latest readings split by node type, each node flagged offline after 15 min."""
    db = SessionLocal()
    try:
        nodes = _current_readings(db)
        alerts = _garden_alerts(db)
    finally:
        db.close()
    now = datetime.now(UTC)
    for n in nodes:
        rt = n.get("reading_time")
        n["offline"] = rt is None or now - rt > OFFLINE_AFTER
    return {
        "weather_nodes": [n for n in nodes if n["node_type"] == "weather"],
        "soil_nodes": [n for n in nodes if n["node_type"] == "soil"],
        "alerts": alerts,
    }


@router.get("/")
async def overview(request: Request) -> HTMLResponse:
    """SPEC 5.1, 10.14, 11.1: what is happening in the garden right now."""
    return render(request, "home.html", active="home", **_now_context())


@router.get("/partials/current")
async def current_partial(request: Request) -> HTMLResponse:
    """SPEC 10.10: the live part of the overview, refreshed by HTMX every 60 s."""
    return render(request, "_now.html", **_now_context())


@router.get("/about")
async def about(request: Request) -> HTMLResponse:
    """SPEC 10.8: the station, the data path and the known nodes."""
    db = SessionLocal()
    try:
        rows = db.execute(select(Node).order_by(Node.node_id)).scalars().all()
    finally:
        db.close()
    cutoff = datetime.now(UTC) - OFFLINE_AFTER
    nodes = [
        {
            "node_id": n.node_id,
            "node_type": n.node_type,
            "first_seen": n.first_seen,
            "last_seen": n.last_seen,
            "online": bool(n.last_seen and n.last_seen >= cutoff),
        }
        for n in rows
    ]
    return render(request, "about.html", active="about", nodes=nodes)


@router.get("/styleguide")
async def styleguide(request: Request) -> HTMLResponse:
    """Every UI component with the macro call that makes it (docs/design.md)."""
    from app.styleguide import render_examples

    return render(request, "styleguide.html", active="", examples=render_examples())


# --------------------------------------------------------------------------- placeholders
# Each loop replaces its placeholder with a real router module (see PLAN.md / SPEC §11–§16).
COMING: dict[str, tuple[str, str, str]] = {
    "garden": (
        "Garden map",
        "🗺️",
        "A 3D map of the plot: beds, the garden house, sensors and what grows where.",
    ),
    "seeds": (
        "Seed log",
        "🌱",
        "What you sowed and planted, where and when, and when it should be ready.",
    ),
}


def _placeholder(key: str) -> Any:
    async def page(request: Request, user: str = RequireUser) -> HTMLResponse:
        title, icon, text = COMING[key]
        return render(request, "coming_soon.html", active=key, title=title, icon=icon, text=text)

    page.__name__ = f"{key}_placeholder"
    return page


for _key in COMING:
    router.add_api_route(f"/{_key}", _placeholder(_key), methods=["GET"])
