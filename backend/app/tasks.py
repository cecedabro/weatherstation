"""Tasks (SPEC §14, private): to-dos with urgency, category and deadline.

The routes, forms and templates (`tasks.html`, `task_form.html`) are done (human-owned glue at the bottom). The
loop fills in the small functions marked ``TODO (task Dxx)``: ``grep -n "TODO (task" app/tasks.py``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

from datetime import UTC, date, datetime, timedelta  # noqa: F401  (timedelta: task D05)
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.db import SessionLocal
from app.models import TASK_CATEGORIES, TASK_URGENCIES, GardenObject, Task
from app.templating import render

router = APIRouter()

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
URGENCY_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}
STATUSES = ("open", "done", "all")
FORM_FIELDS = ("title", "notes", "category", "urgency", "deadline", "object_id")


def local_today(now: datetime | None = None) -> date:
    """Today's date in Europe/Amsterdam (SPEC 14.2). *now* defaults to ``datetime.now(UTC)``.

    TODO (task D01): ``(now or datetime.now(UTC)).astimezone(AMSTERDAM).date()``.
    """
    return (now or datetime.now(UTC)).astimezone(AMSTERDAM).date()


def deadline_text(deadline: date, today: date) -> tuple[str, bool]:
    """``(text, overdue)``: "due today", "due tomorrow", "due in N days" or "overdue by N days" (then True).

    TODO (task D01): ``n = (deadline - today).days``; n < 0 → (f"overdue by {-n} days", True);
    0 → "due today"; 1 → "due tomorrow"; else f"due in {n} days" (all with False).
    Note "overdue by 1 days" is fine (the spec keeps it simple).
    """
    n = (deadline - today).days
    if n < 0:
        return (f"overdue by {-n} days", True)
    if n == 0:
        return ("due today", False)
    if n == 1:
        return ("due tomorrow", False)
    return (f"due in {n} days", False)


def sort_key(task: Task) -> tuple[int, date, float]:
    """Sort key for SPEC 14.1: urgency (critical first), deadline (soonest first, none last), newest first.

    TODO (task D02): return ``(URGENCY_RANK.get(task.urgency, 9), task.deadline or date.max,
    -task.created_at.timestamp())``. (``created_at`` is always set once the row is flushed.)
    """
    return (0, date.max, 0.0)


def validate_form(
    form: dict[str, str], object_ids: set[int]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the task form (SPEC 14.3). Returns ``(values, errors)``; errors maps field name → message.

    *values* always has every key of FORM_FIELDS: ``title`` (stripped), ``notes``, ``category``, ``urgency``,
    ``deadline`` (a ``date`` or None) and ``object_id`` (an int or None). When a value is invalid, keep the
    raw text in *values* for deadline/category/urgency (so the form can show it again) and add an error.

    TODO (task D03) steps, ``get = lambda k: (form.get(k) or "").strip()``:
    1. title: stripped; empty → "Give the task a title"; longer than 120 → "At most 120 characters".
    2. notes: ``form.get("notes") or ""`` (not stripped); longer than 2000 → "At most 2000 characters".
    3. category not in TASK_CATEGORIES → "Pick a category"; urgency not in TASK_URGENCIES → "Pick an urgency".
    4. deadline: "" → None; else ``date.fromisoformat``; ValueError → keep the text, "Use a date (YYYY-MM-DD)".
    5. object_id: "" → None; else ``int(...)`` that is in *object_ids*; otherwise None and "Pick an object from the list".
    """
    return {k: form.get(k) for k in FORM_FIELDS}, {}


def find_tasks(
    db: Session, status: str, category: str | None = None, q: str | None = None
) -> list[Task]:
    """Tasks for the list (SPEC 14.1), sorted with ``sort_key``.

    *status*: "open" or "done" filters on ``Task.status``; "all" (or anything else) doesn't filter.
    *category*: when set, only that category. *q*: when set, case-insensitive substring of title or notes.

    TODO (task D04) steps:
    1. ``stmt = select(Task)``; add ``.where(...)`` for status and category as above.
    2. For q: ``pat = f"%{q}%"``, ``.where(or_(Task.title.ilike(pat), Task.notes.ilike(pat)))``
       (``from sqlalchemy import or_``).
    3. ``return sorted(db.execute(stmt).scalars(), key=sort_key)``.
    """
    return []


def counts(db: Session, today: date) -> dict[str, int]:
    """Numbers for the tabs and tiles: ``{"open", "done", "all", "overdue", "week"}``.

    overdue = open tasks with a deadline before *today*; week = open tasks with a deadline from *today* to
    *today* + 6 days (both included).

    TODO (task D05): load all tasks once (``db.execute(select(Task)).scalars().all()``) and count in Python.
    """
    return {"open": 0, "done": 0, "all": 0, "overdue": 0, "week": 0}


def task_json(task: Task) -> dict[str, Any]:
    """One task for ``GET /api/v1/tasks`` (SPEC 14.5).

    Keys: id, title, notes, category, urgency, status, deadline, object_id, x, y, created_at, done_at.
    Dates and datetimes as ``.isoformat()`` strings, or None when not set.

    TODO (task D06): build the dict.
    """
    return {"id": task.id}


def apply_form(task: Task, values: dict[str, Any]) -> None:
    """Copy validated form *values* (title, notes, category, urgency, deadline, object_id) onto *task*.

    TODO (task D07): one ``setattr`` per key of FORM_FIELDS.
    """


def set_done(task: Task, done: bool, now: datetime) -> None:
    """Mark done (status "done", ``done_at = now``) or reopen (status "open", ``done_at = None``).

    TODO (task D07): two assignments per branch.
    """


# -- glue (done)
def _objects(db: Session) -> dict[int, str]:
    return {
        o.id: o.name for o in db.execute(select(GardenObject).order_by(GardenObject.name)).scalars()
    }


def _get(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="No such task")
    return task


def _form_page(
    request: Request, db: Session, task: Task | None, values: dict[str, Any], errors: dict[str, str]
) -> HTMLResponse:
    objects = _objects(db)
    return render(
        request,
        "task_form.html",
        status_code=400 if errors else 200,
        active="tasks",
        task=task,
        values=values,
        errors=errors,
        categories=[(c, c.title()) for c in TASK_CATEGORIES],
        urgencies=[(u, u.title()) for u in TASK_URGENCIES],
        objects=[("", "— none —")] + [(str(k), v) for k, v in objects.items()],
    )


@router.get("/tasks")
async def tasks_page(
    request: Request, status: str = "open", category: str = "", q: str = "", user: str = RequireUser
) -> HTMLResponse:
    status = status if status in STATUSES else "open"
    db = SessionLocal()
    try:
        today = local_today()
        rows = find_tasks(db, status, category or None, q.strip() or None)
        n = counts(db, today)
        objects = _objects(db)
    finally:
        db.close()
    items = []
    for t in rows:
        text, overdue = deadline_text(t.deadline, today) if t.deadline else ("", False)
        items.append(
            {
                "task": t,
                "deadline": text,
                "overdue": overdue and t.status == "open",
                "object": objects.get(t.object_id or -1),
            }
        )
    keep = "".join(f"&{k}={v}" for k, v in (("category", category), ("q", q)) if v)
    return render(
        request,
        "tasks.html",
        active="tasks",
        items=items,
        n=n,
        status=status,
        category=category,
        q=q,
        categories=[("", "All categories")] + [(c, c.title()) for c in TASK_CATEGORIES],
        tabs=[(f"/tasks?status={s}{keep}", s.title(), None, n[s]) for s in STATUSES],
        current_tab=f"/tasks?status={status}{keep}",
    )


@router.get("/tasks/new")
async def task_new(request: Request, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        return _form_page(request, db, None, {"category": "other", "urgency": "normal"}, {})
    finally:
        db.close()


@router.get("/tasks/{task_id}/edit")
async def task_edit(request: Request, task_id: int, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        task = _get(db, task_id)
        values = {k: getattr(task, k) for k in FORM_FIELDS}
        return _form_page(request, db, task, values, {})
    finally:
        db.close()


async def _save(request: Request, task_id: int | None) -> HTMLResponse | RedirectResponse:
    form = {k: str(v) for k, v in (await request.form()).items()}
    db = SessionLocal()
    try:
        task = _get(db, task_id) if task_id is not None else None
        values, errors = validate_form(form, set(_objects(db)))
        if errors:
            return _form_page(request, db, task, values, errors)
        if task is None:
            task = Task(status="open")
            db.add(task)
        apply_form(task, values)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks", response_model=None)
async def task_create(request: Request, user: str = RequireUser) -> HTMLResponse | RedirectResponse:
    return await _save(request, None)


@router.post("/tasks/{task_id}", response_model=None)
async def task_update(
    request: Request, task_id: int, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, task_id)


def _action(task_id: int, act: str) -> RedirectResponse:
    db = SessionLocal()
    try:
        task = _get(db, task_id)
        if act == "delete":
            db.delete(task)
        else:
            set_done(task, act == "done", datetime.now(UTC))
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks/{task_id}/done")
async def task_done(task_id: int, user: str = RequireUser) -> RedirectResponse:
    return _action(task_id, "done")


@router.post("/tasks/{task_id}/reopen")
async def task_reopen(task_id: int, user: str = RequireUser) -> RedirectResponse:
    return _action(task_id, "reopen")


@router.post("/tasks/{task_id}/delete")
async def task_delete(task_id: int, user: str = RequireUser) -> RedirectResponse:
    return _action(task_id, "delete")


@router.get("/api/v1/tasks")
async def api_tasks(status: str = "open", user: str = RequireUser) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        return [task_json(t) for t in find_tasks(db, status if status in STATUSES else "open")]
    finally:
        db.close()
