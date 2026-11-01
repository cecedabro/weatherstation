"""Application factory and entry point."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal
from app.models import Node, Reading

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR / "static"

# Jinja2 environment
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Weather Station")
    _ = Settings()  # validate defaults at startup

    # Serve static files (CSS, JS, vendor libs)
    application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    def _current_readings(db: Session) -> list[dict[str, Any]]:
        """Return latest reading per node (used by both GET / and GET /api/v1/current)."""
        latest_subq = (
            select(
                Reading.node_id,
                Reading.metric,
                func.max(Reading.ts).label("max_ts"),
            )
            .group_by(Reading.node_id, Reading.metric)
            .subquery()
        )
        reading_stmt = select(Reading).join(
            latest_subq,
            (Reading.node_id == latest_subq.c.node_id)
            & (Reading.metric == latest_subq.c.metric)
            & (Reading.ts == latest_subq.c.max_ts),
        )
        reading_rows = db.execute(reading_stmt).scalars().all()

        by_node: dict[str, dict[str, float]] = {}
        for r in reading_rows:
            nid = str(r.node_id)
            if nid not in by_node:
                by_node[nid] = {}
            by_node[nid][str(r.metric)] = float(r.value)

        node_stmt = select(Node)
        nodes_rows = db.execute(node_stmt).scalars().all()
        result: list[dict[str, Any]] = []
        for node in nodes_rows:
            nid = str(node.node_id)
            metrics: dict[str, float] = {}
            if nid in by_node:
                for m in sorted(by_node[nid]):
                    metrics[m] = by_node[nid][m]
            battery_v = float(node.last_battery_v) if node.last_battery_v is not None else None
            result.append(
                {
                    "node_id": nid,
                    "node_type": node.node_type,
                    "last_seen": node.last_seen.isoformat(),
                    "battery_v": battery_v,
                    "rssi_dbm": node.last_rssi_dbm,
                    "metrics": metrics,
                }
            )
        return result

    @application.get("/")
    async def index() -> HTMLResponse:
        """Render the home page with current conditions per SPEC 5.1."""
        db = SessionLocal()
        try:
            all_nodes = _current_readings(db)
            weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
            soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
            template = _jinja_env.get_template("home.html")
            html = template.render(
                weather_nodes=weather_nodes,
                soil_nodes=soil_nodes,
            )
            return HTMLResponse(content=html)
        finally:
            db.close()

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/v1/nodes")
    async def nodes() -> list[dict[str, str | bool]]:
        return []

    @application.get("/api/v1/current")
    async def current() -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            return _current_readings(db)
        finally:
            db.close()

    from app.readapi import router as readapi_router

    application.include_router(readapi_router)

    from app.ingest import router as ingest_router

    application.include_router(ingest_router)

    return application


app = create_app()
