"""Pure helpers for the Tasks feature (SPEC §14).

Functions: ``deadline_text``, ``task_sort_key``, ``local_today``,
``validate_task_form``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models import TASK_CATEGORIES, TASK_URGENCIES

_URGENCY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}
_AMP = ZoneInfo("Europe/Amsterdam")


def local_today() -> date:
    """Return today's date in Europe/Amsterdam timezone."""
    return datetime.now(UTC).astimezone(_AMP).date()


def deadline_text(deadline: date, today: date) -> tuple[str, bool]:
    """Return ``(text, overdue)`` for a deadline relative to *today*.

    Per SPEC 14.2 the labels are:

    - 0 days → ``"due today"``
    - 1 day → ``"due tomorrow"``
    - 2+ days → ``"due in N days"``
    - negative (overdue) → ``"overdue by N days"``
    """
    delta = (deadline - today).days
    if delta < 0:
        return f"overdue by {-delta} days", True
    if delta == 0:
        return "due today", False
    if delta == 1:
        return "due tomorrow", False
    return f"due in {delta} days", False


def task_sort_key(task: Any) -> tuple[int, int | date, int]:
    """Sort key for tasks per SPEC 14.1.

    Order: urgency (critical > high > normal > low), then deadline
    (soonest first, ``None`` last), then newest first (most recent).

    Returns a tuple ``(urgency_rank, deadline_rank, -created_at)`` that
    sorts in the correct order.
    """
    urgency_rank = _URGENCY_ORDER.get(task.urgency, 99)

    deadline_rank = task.deadline if task.deadline is not None else date.max

    # newest first → negate timestamp (but date is already ordered correctly
    # with ascending sort if we use it as-is)
    created_rank = (
        -int(task.created_at.timestamp())
        if task.created_at is not None
        else 0
    )

    return (urgency_rank, deadline_rank, created_rank)


def validate_task_form(
    form: dict[str, Any], object_ids: list[int] | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate task form data per SPEC 14.3.

    Returns ``(values, errors)`` where *values* has cleaned fields and
    *errors* maps field names to error strings (empty dict on success).
    """
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}

    # title: 1-120 chars after trimming
    title = form.get("title", "")
    title = title.strip() if isinstance(title, str) else ""
    if not title:
        errors["title"] = "Title is required"
    elif len(title) > 120:
        errors["title"] = "Title must be at most 120 characters"
    values["title"] = title

    # notes: ≤ 2000
    notes = form.get("notes", "")
    notes = notes[:2000] if isinstance(notes, str) else ""
    values["notes"] = notes

    # category: in TASK_CATEGORIES
    category = form.get("category", "")
    if category not in TASK_CATEGORIES:
        errors["category"] = "Invalid category"
    values["category"] = category

    # urgency: in TASK_URGENCIES
    urgency = form.get("urgency", "")
    if urgency not in TASK_URGENCIES:
        errors["urgency"] = "Invalid urgency"
    values["urgency"] = urgency

    # deadline: empty or YYYY-MM-DD
    deadline_str = form.get("deadline", "")
    if isinstance(deadline_str, str):
        deadline_str = deadline_str.strip()
    if not deadline_str:
        values["deadline"] = None
    else:
        try:
            parsed = date.fromisoformat(deadline_str)
            values["deadline"] = parsed
        except (ValueError, TypeError):
            errors["deadline"] = "Invalid date format (use YYYY-MM-DD)"
            values["deadline"] = deadline_str

    # object_id: empty or existing garden_object id
    object_id_str = form.get("object_id", "")
    if isinstance(object_id_str, str):
        object_id_str = object_id_str.strip()
    if not object_id_str:
        values["object_id"] = None
    elif object_ids is not None:
        try:
            oid = int(object_id_str)
            if oid not in object_ids:
                errors["object_id"] = "Invalid object"
                values["object_id"] = None
            else:
                values["object_id"] = oid
        except (ValueError, TypeError):
            errors["object_id"] = "Invalid object"
            values["object_id"] = None
    else:
        # No object_ids list provided — accept any integer
        try:
            values["object_id"] = int(object_id_str)
        except (ValueError, TypeError):
            errors["object_id"] = "Invalid object"
            values["object_id"] = None

    return values, errors
