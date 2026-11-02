"""Routes: /admin (node health table per SPEC 6) and /admin/nodes.json."""

import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal
from app.models import Reading
from app.readapi import _current_readings
from app.web import _jinja_env

router = APIRouter()

basic_auth = HTTPBasic()


def _check_auth(credentials: HTTPBasicCredentials) -> None:
    """Validate Basic auth credentials; raises 401 on failure."""
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


@router.get("/admin")
async def admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(basic_auth),  # noqa: B008
) -> HTMLResponse:
    """Admin page with node health table per SPEC 6."""
    _check_auth(credentials)

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

        # Problem nodes (offline or low battery) first, then alphabetical
        node_rows.sort(key=lambda n: (n["online"] and not n["low_battery"], n["node_id"]))

        template = _jinja_env.get_template("admin.html")
        html = template.render(
            nodes=node_rows,
            now=now,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()


@router.get("/admin/nodes.json")
async def admin_nodes_json(
    credentials: HTTPBasicCredentials = Depends(basic_auth),  # noqa: B008
) -> JSONResponse:
    """Return node health table data as JSON per SPEC 6."""
    _check_auth(credentials)

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

        node_rows.sort(key=lambda n: (n["online"] and not n["low_battery"], n["node_id"]))

        return JSONResponse(content=node_rows)
    finally:
        db.close()
