"""Application factory and entry point."""

from typing import Any

from fastapi import FastAPI
from sqlalchemy import func, select

from app.config import Settings
from app.db import SessionLocal
from app.models import Node, Reading


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Weather Station")
    _ = Settings()  # validate defaults at startup

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
            # Subquery: latest ts per (node_id, metric)
            latest_subq = (
                select(
                    Reading.node_id,
                    Reading.metric,
                    func.max(Reading.ts).label("max_ts"),
                )
                .group_by(Reading.node_id, Reading.metric)
                .subquery()
            )
            # Join back to get the actual reading rows
            reading_stmt = (
                select(Reading)
                .join(
                    latest_subq,
                    (Reading.node_id == latest_subq.c.node_id)
                    & (Reading.metric == latest_subq.c.metric)
                    & (Reading.ts == latest_subq.c.max_ts),
                )
            )
            reading_rows = db.execute(reading_stmt).scalars().all()

            # Group readings by node_id
            by_node: dict[str, dict[str, float]] = {}
            for r in reading_rows:
                nid = str(r.node_id)
                if nid not in by_node:
                    by_node[nid] = {}
                by_node[nid][str(r.metric)] = float(r.value)

            # Build result: one entry per node
            node_stmt = select(Node)
            nodes_rows = db.execute(node_stmt).scalars().all()
            result: list[dict[str, Any]] = []
            for node in nodes_rows:
                nid = str(node.node_id)
                metrics: dict[str, float] = {}
                if nid in by_node:
                    # Sort metrics for deterministic output
                    for m in sorted(by_node[nid]):
                        metrics[m] = by_node[nid][m]
                battery_v = (
                    float(node.last_battery_v)
                    if node.last_battery_v is not None
                    else None
                )
                result.append({
                    "node_id": nid,
                    "node_type": node.node_type,
                    "last_seen": node.last_seen.isoformat(),
                    "battery_v": battery_v,
                    "rssi_dbm": node.last_rssi_dbm,
                    "metrics": metrics,
                })
            return result
        finally:
            db.close()

    from app.ingest import router as ingest_router

    application.include_router(ingest_router)

    return application


app = create_app()
