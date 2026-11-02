"""Read API endpoints: /current, /series, /nodes per SPEC 4.1–4.4."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy import ColumnElement, func, literal_column, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Node, Reading

router = APIRouter()

_VALID_STEPS = {"raw", "5m", "1h", "1d"}


class SeriesParams(BaseModel):
    """Validated series query parameters."""

    node: str | None = None
    metric: str | None = None
    step: str = "raw"
    from_ts: str | None = None
    to_ts: str | None = None

    @field_validator("step")
    @classmethod
    def validate_step(cls, v: str) -> str:
        if v not in _VALID_STEPS:
            raise ValueError(f"Invalid step '{v}'. Must be one of: raw, 5m, 1h, 1d")
        return v

    @field_validator("from_ts", "to_ts")
    @classmethod
    def validate_datetime(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        # Handle URL-decoded + as space (legacy query string behavior)
        v = v.replace(" ", "+")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError) as err:
            raise ValueError(
                f"Invalid datetime '{v}'. Must be RFC3339 UTC (e.g. 2026-05-01T12:00:00Z)"
            ) from err
        return v


def _parse_dt(s: str | None) -> datetime | None:
    """Parse an RFC3339 datetime string to UTC datetime."""
    if s is None or s == "":
        return None
    # Handle URL-decoded + as space and also space-separated timezone offsets
    s = s.replace(" ", "+")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _bucket_column(step: str) -> ColumnElement[Any] | None:
    """Return the SQL expression for bucketing timestamps."""
    if step == "raw":
        return None
    if step == "5m":
        return func.date_trunc("hour", Reading.ts) + (
            func.floor(func.extract("minute", Reading.ts) / 5.0)
            * literal_column("INTERVAL '5 minutes'")
        )
    if step == "1h":
        return func.date_trunc("hour", Reading.ts)
    if step == "1d":
        return func.date_trunc("day", Reading.ts)
    return None


@router.get("/api/v1/series")
async def series(
    node: str | None = Query(None),
    metric: str | None = Query(None),
    step: str = Query("raw"),
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
) -> list[dict[str, Any]]:
    """Return time-ordered series points, optionally bucketed.

    SPEC 4.2: step=raw returns stored points; 5m|1h|1d return averages per bucket
    (sum for rain_mm).
    SPEC 4.4: Invalid step or non-RFC3339 dates -> 400.
    """
    from fastapi import HTTPException

    # Validate parameters
    try:
        params = SeriesParams(
            node=node,
            metric=metric,
            step=step,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail="Invalid query parameter") from err

    from_dt = _parse_dt(params.from_ts)
    to_dt = _parse_dt(params.to_ts)

    # Build filter conditions
    conditions: list[ColumnElement[Any]] = []
    if params.node:
        conditions.append(Reading.node_id == params.node)
    if params.metric:
        conditions.append(Reading.metric == params.metric)
    if from_dt:
        conditions.append(Reading.ts >= from_dt)  # type: ignore[arg-type]
    if to_dt:
        conditions.append(Reading.ts <= to_dt)  # type: ignore[arg-type]

    db = SessionLocal()
    try:
        if params.step == "raw":
            # Return all individual points, ordered by timestamp
            stmt = select(Reading).where(*conditions).order_by(Reading.ts.asc())
            rows = db.execute(stmt).scalars().all()
            result = [
                {
                    "ts": r.ts.isoformat(),
                    "metric": str(r.metric),
                    "value": float(r.value),
                }
                for r in rows
            ]
        else:
            # Bucketed aggregation
            bucket = _bucket_column(params.step)
            assert bucket is not None, f"Expected bucket for step={params.step}"
            agg_fn = (
                func.sum(Reading.value) if params.metric == "rain_mm" else func.avg(Reading.value)
            )

            stmt = (
                select(
                    bucket.label("bucket"),
                    Reading.metric,
                    agg_fn.label("avg_value"),
                )
                .where(*conditions)
                .group_by(bucket, Reading.metric)
                .order_by(bucket.asc())
            )

            rows = db.execute(stmt).mappings().all()

            result = [
                {
                    "ts": r["bucket"].isoformat(),
                    "metric": str(r["metric"]),
                    "value": (float(r["avg_value"]) if r["avg_value"] is not None else 0.0),
                }
                for r in rows
            ]

        return result
    finally:
        db.close()


def _current_readings(db: Session) -> list[dict[str, Any]]:
    """Return latest reading per node (used by GET / and GET /api/v1/current)."""

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
    node_reading_time: dict[str, datetime] = {}
    for r in reading_rows:
        nid = str(r.node_id)
        if nid not in by_node:
            by_node[nid] = {}
        by_node[nid][str(r.metric)] = float(r.value)
        if nid not in node_reading_time or r.ts > node_reading_time[nid]:
            node_reading_time[nid] = r.ts  # type: ignore[assignment]

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
        reading_time = node_reading_time.get(nid)
        result.append(
            {
                "node_id": nid,
                "node_type": node.node_type,
                "last_seen": node.last_seen.isoformat(),
                "battery_v": battery_v,
                "rssi_dbm": node.last_rssi_dbm,
                "metrics": metrics,
                "reading_time": reading_time,
            }
        )
    return result


@router.get("/api/v1/current")
async def current() -> list[dict[str, Any]]:
    """Return latest reading per node per SPEC 4.1."""
    db = SessionLocal()
    try:
        return _current_readings(db)
    finally:
        db.close()


def _daily_aggregation(
    db: Session,
    *,
    node: str | None = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Return daily aggregation for *node* over the last *days* days.

    One row per UTC day with *date*, *temp_min*, *temp_max*, *temp_avg*,
    *rain_total*, *humidity_avg* (None when that day has no such data).

    *days* must be 1-366; values outside this range raise ValueError.

    Rows are returned **oldest first** (caller may reverse).
    """
    if days < 1 or days > 366:
        raise ValueError("days must be 1-366")

    now = datetime.now(UTC)
    from_dt = now - timedelta(days=days)

    conditions: list[ColumnElement[Any]] = []
    conditions.append(Reading.ts >= from_dt)  # type: ignore[arg-type]
    if node:
        conditions.append(Reading.node_id == node)

    # Fetch all readings for the period, grouped by day bucket + metric.
    # We bucket by day using date_trunc to keep everything in SQL.
    day_col = func.date_trunc("day", Reading.ts)

    stmt = (
        select(
            day_col.label("day"),
            Reading.metric,
            Reading.value,
        )
        .where(*conditions)
        .order_by(day_col.asc())
    )

    rows = db.execute(stmt).mappings().all()

    # Pivot into per-day dicts, aggregating per metric.
    # Different metrics need different aggregate functions:
    #   temp_c  -> min, max, avg
    #   rain_mm -> sum
    #   humidity_pct -> avg
    days_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        day_val = row["day"]
        d = day_val.date() if hasattr(day_val, "date") else day_val
        d_str = str(d)
        if d_str not in days_map:
            days_map[d_str] = {"date": d}
        m = row["metric"]
        v = float(row["value"]) if row["value"] is not None else None
        if m == "temp_c":
            if v is not None:
                days_map[d_str].setdefault("temp_min", v)
                days_map[d_str]["temp_min"] = min(days_map[d_str]["temp_min"], v)
                days_map[d_str].setdefault("temp_max", v)
                days_map[d_str]["temp_max"] = max(days_map[d_str]["temp_max"], v)
                days_map[d_str]["_temp_sum"] = days_map[d_str].get("_temp_sum", 0) + v
                days_map[d_str]["_temp_n"] = days_map[d_str].get("_temp_n", 0) + 1
        elif m == "rain_mm":
            if v is not None:
                days_map[d_str]["rain_total"] = days_map[d_str].get("rain_total", 0) + v
        elif m == "humidity_pct" and v is not None:
            days_map[d_str]["_hum_sum"] = days_map[d_str].get("_hum_sum", 0) + v
            days_map[d_str]["_hum_n"] = days_map[d_str].get("_hum_n", 0) + 1

    # Build final result list sorted oldest-first
    result: list[dict[str, Any]] = []
    for d_str in sorted(days_map):
        d = days_map[d_str]["date"]
        tn = days_map[d_str].get("_temp_n", 0)
        hn = days_map[d_str].get("_hum_n", 0)
        entry = {
            "date": d,
            "temp_min": round(days_map[d_str]["temp_min"], 2)
            if "temp_min" in days_map[d_str]
            else None,
            "temp_max": round(days_map[d_str]["temp_max"], 2)
            if "temp_max" in days_map[d_str]
            else None,
            "temp_avg": round(days_map[d_str]["_temp_sum"] / tn, 2) if tn else None,
            "rain_total": round(days_map[d_str].get("rain_total", 0), 2),
            "humidity_avg": round(days_map[d_str]["_hum_sum"] / hn, 2) if hn else None,
        }
        result.append(entry)

    return result


@router.get("/api/v1/export.csv")
async def export_csv(
    node: str | None = Query(None),
    metric: str | None = Query(None),
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
) -> Response:
    """Return raw readings as CSV per SPEC 10.7.

    Header: ts,node_id,metric,value
    ISO-8601 UTC timestamps, time-ordered.
    Same date validation as /series (bad dates -> 400).
    metric is optional (all metrics when omitted).
    """
    from fastapi import HTTPException

    # Validate date params (same validation as /series)
    try:
        SeriesParams(
            node=node,
            metric=metric,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail="Invalid query parameter") from err

    from_dt = _parse_dt(from_ts)
    to_dt = _parse_dt(to_ts)

    # Build filter conditions
    conditions: list[ColumnElement[Any]] = []
    if node:
        conditions.append(Reading.node_id == node)
    if metric:
        conditions.append(Reading.metric == metric)
    if from_dt:
        conditions.append(Reading.ts >= from_dt)  # type: ignore[arg-type]
    if to_dt:
        conditions.append(Reading.ts <= to_dt)  # type: ignore[arg-type]

    db = SessionLocal()
    try:
        stmt = select(Reading).where(*conditions).order_by(Reading.ts.asc())
        rows = db.execute(stmt).scalars().all()

        # Build CSV content
        csv_lines = ["ts,node_id,metric,value"]
        for r in rows:
            csv_lines.append(f"{r.ts.isoformat()},{r.node_id},{r.metric},{r.value}")
        csv_content = "\n".join(csv_lines) + "\n"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=readings.csv"},
        )
    finally:
        db.close()


@router.get("/api/v1/nodes")
async def nodes_list() -> list[dict[str, str | bool]]:
    """Return all known nodes with online status per contract.

    SPEC 4.3: online=true iff last_seen within 15 minutes of now.
    """
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=15)
        stmt = select(Node).order_by(Node.node_id.asc())
        try:
            rows = db.execute(stmt).scalars().all()
        except ProgrammingError:
            return []
        result: list[dict[str, Any]] = []
        for n in rows:
            last_seen = n.last_seen
            online = bool(last_seen and last_seen >= cutoff)
            result.append(
                {
                    "node_id": str(n.node_id),
                    "node_type": str(n.node_type),
                    "last_seen": (n.last_seen.isoformat() if n.last_seen else None),
                    "online": online,
                }
            )
        return result
    finally:
        db.close()
