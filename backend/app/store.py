"""Store-reading service: upsert batches per SPEC 2.2-2.3.

A reading batch is stored as one row per metric value (SPEC 2.2).
Re-storing a batch with the same (node_id, ts) does not create
duplicate metric rows (SPEC 2.3).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Node, Reading

Batch = dict[str, Any]


def upsert_readings(
    db: Session, batches: Sequence[Batch]
) -> dict[str, Any]:
    """Upsert reading batches and return acceptance summary.

    For each batch:
    1. Upsert the node row (upsert on node_id = PK).
    2. Upsert one metric row per metrics dict entry (ON CONFLICT on
       (node_id, metric, ts) DO UPDATE).

    Returns ``{"accepted": <n>, "rejected": [<index>, ...]}``.
    """
    accepted = 0
    rejected: list[int] = []

    for idx, batch in enumerate(batches):
        node_id = batch["node_id"]
        node_type = batch["node_type"]
        ts_str = batch["ts"]
        battery_v = batch.get("battery_v")
        rssi_dbm = batch.get("rssi_dbm")
        metrics = batch.get("metrics", {})

        # Parse the timestamp once for node + readings
        ts = _parse_ts(ts_str)
        if ts is None:
            rejected.append(idx)
            continue

        # 1. Upsert node
        _upsert_node(db, node_id, node_type, ts, battery_v, rssi_dbm)

        # 2. Upsert one metric row per entry (SPEC 2.2)
        for metric, value in metrics.items():
            _upsert_metric(db, node_id, metric, ts, value)

        accepted += 1

    db.commit()
    return {"accepted": accepted, "rejected": rejected}


def _parse_ts(ts_str: str) -> datetime | None:
    """Parse an RFC3339 timestamp string to a timezone-aware datetime."""
    try:
        # Handle 'Z' suffix and other RFC3339 variants
        s = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, AttributeError):
        return None


def _upsert_node(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    battery_v: float | None,
    rssi_dbm: int | None,
) -> None:
    """Insert or update a node row (node_id is PK)."""
    stmt = (
        insert(Node)
        .values(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
            last_battery_v=battery_v,
            last_rssi_dbm=rssi_dbm,
        )
        .on_conflict_do_update(
            index_elements=["node_id"],
            set_={
                "node_type": excluded("node_type"),
                "last_seen": excluded("last_seen"),
                "last_battery_v": excluded("last_battery_v"),
                "last_rssi_dbm": excluded("last_rssi_dbm"),
            },
        )
    )
    db.execute(stmt)


def _upsert_metric(
    db: Session,
    node_id: str,
    metric: str,
    ts: datetime,
    value: float,
) -> None:
    """Insert or update a single metric reading (SPEC 2.3 upsert).

    Uses PostgreSQL ``INSERT ... ON CONFLICT (node_id, metric, ts)
    DO UPDATE`` so that re-storing a batch with the same timestamp
    never creates duplicate rows.
    """
    stmt = (
        insert(Reading)
        .values(
            node_id=node_id,
            metric=metric,
            ts=ts,
            value=value,
        )
        .on_conflict_do_update(
            index_elements=["node_id", "metric", "ts"],
            set_={
                "value": excluded("value"),
            },
        )
    )
    db.execute(stmt)


def excluded(column: str) -> Any:
    """Return the ``excluded.<column>`` reference for ON CONFLICT DO UPDATE.

    Uses the PostgreSQL ``excluded`` pseudo-table, which holds the
    values that would have been inserted.
    """
    return text(f"excluded.{column}")
