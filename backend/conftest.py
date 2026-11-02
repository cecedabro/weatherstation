"""Ensure backend/ is on sys.path for contract tests imported via ../contract/tests."""

import pathlib
import sys
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading

sys.path.insert(0, str(pathlib.Path(__file__).parent))


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_batch(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict[str, float],
) -> Node:
    """Insert a node and its metric readings into the database."""
    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    for metric, value in metrics.items():
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id) & (Reading.metric == metric) & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()
    return node


def _make_daily(
    db: Session,
    node_id: str,
    node_type: str,
    day_offset: int,
    metrics: dict[str, float],
) -> Node:
    """Insert one day of readings for a node (middle of the given day)."""
    now = _now().replace(hour=12, minute=0, second=0, microsecond=0)
    ts = now - timedelta(days=day_offset)
    return _make_batch(db, node_id, node_type, ts, metrics)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def history_data(db: Session) -> Session:
    """A weather node with readings spanning 10 days."""
    for i in range(10):
        _make_daily(
            db,
            "weather-main",
            "weather",
            i,
            {
                "temp_c": 15.0 + i,
                "humidity_pct": 55.0 + i * 2,
                "rain_mm": 2.0 + i,
                "pressure_hpa": 1010.0 + i,
            },
        )
    yield db


@pytest.fixture()
def multi_node_history(db: Session) -> Session:
    """Two weather nodes with overlapping readings."""
    now = _now()
    for i in range(5):
        day = now - timedelta(days=i)
        ts1 = day.replace(hour=8)
        ts2 = day.replace(hour=9)
        _make_batch(
            db,
            "weather-garden",
            "weather",
            ts1,
            {
                "temp_c": 18.0 + i,
                "humidity_pct": 60.0 + i,
                "rain_mm": 1.0 + i,
                "pressure_hpa": 1013.0,
            },
        )
        _make_batch(
            db,
            "weather-terrace",
            "weather",
            ts2,
            {
                "temp_c": 20.0 + i,
                "humidity_pct": 50.0 + i,
                "rain_mm": 0.5 + i,
                "pressure_hpa": 1015.0,
            },
        )
    yield db
