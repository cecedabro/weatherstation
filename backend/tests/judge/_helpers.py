"""Shared helpers for the human-owned acceptance tests."""

from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.models import Node, Reading


def add_node(db, node_id: str, node_type: str, last_seen: datetime | None = None) -> None:
    ts = last_seen or datetime.now(UTC)
    db.add(Node(node_id=node_id, node_type=node_type, first_seen=ts, last_seen=ts))
    db.flush()


def add_readings(db, node_id: str, metric: str, points: list[tuple[datetime, float]]) -> None:
    for ts, v in points:
        db.add(Reading(node_id=node_id, metric=metric, ts=ts, value=v))
    db.flush()


def hours_ago(h: float) -> datetime:
    return datetime.now(UTC).replace(microsecond=0) - timedelta(hours=h)


def auth() -> tuple[str, str]:
    s = Settings()
    return (s.ADMIN_USER, s.ADMIN_PASSWORD)
