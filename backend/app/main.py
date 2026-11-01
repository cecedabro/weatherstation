"""Application factory and entry point."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal
from app.models import Reading
from app.readapi import _current_readings

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

    basic_auth = HTTPBasic()

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

    def _readings_24h(db: Session) -> dict[str, int]:
        """Return a dict mapping node_id → count of readings in the last 24 h."""
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            select(Reading.node_id, func.count().label("cnt"))  # type: ignore[var-annotated]
            .where(Reading.ts >= cutoff)  # type: ignore[arg-type]
            .group_by(Reading.node_id)
        )
        rows = db.execute(stmt).all()
        return {str(r.node_id): r.cnt for r in rows}

    @application.get("/admin")
    async def admin(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(basic_auth),  # noqa: B008
    ) -> HTMLResponse:
        """Admin page with node health table per SPEC 6."""
        import hmac

        settings = Settings()
        if not hmac.compare_digest(
            credentials.username.encode("utf-8"),
            settings.ADMIN_USER.encode("utf-8"),
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not hmac.compare_digest(
            credentials.password.encode("utf-8"),
            settings.ADMIN_PASSWORD.encode("utf-8"),
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        db = SessionLocal()
        try:
            all_nodes = _current_readings(db)
            reading_counts = _readings_24h(db)
            now = datetime.now(UTC)

            node_rows = []
            for node in all_nodes:
                nid = node["node_id"]
                last_seen_str = node["last_seen"]
                last_seen_dt = datetime.fromisoformat(last_seen_str)
                offline = (now - last_seen_dt) > timedelta(minutes=15)
                battery_v = node.get("battery_v")
                low_battery = battery_v is not None and battery_v < 3.4
                rssi_dbm = node.get("rssi_dbm")
                count_24h = reading_counts.get(nid, 0)
                node_rows.append(
                    {
                        "node_id": nid,
                        "node_type": node["node_type"],
                        "last_seen": last_seen_str,
                        "online": not offline,
                        "battery_v": battery_v,
                        "low_battery": low_battery,
                        "rssi_dbm": rssi_dbm,
                        "readings_24h": count_24h,
                    }
                )

            template = _jinja_env.get_template("admin.html")
            html = template.render(
                nodes=node_rows,
            )
            return HTMLResponse(content=html)
        finally:
            db.close()

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    from app.readapi import router as readapi_router

    application.include_router(readapi_router)

    from app.ingest import router as ingest_router

    application.include_router(ingest_router)

    return application


app = create_app()
