"""Step tests for the Tasks loop: one group per task (D01–D07). Human-owned.

`make check` skips a group until PLAN.md ticks its task (tests/conftest.py); accept runs it with TASKS=all.
"""

# ruff: noqa: E501

from datetime import UTC, date, datetime, timedelta

import pytest

from app import tasks as m
from app.models import GardenObject, Task

TODAY = date(2026, 11, 21)


def add(
    db,
    title,
    urgency="normal",
    deadline=None,
    status="open",
    category="other",
    notes="",
    created=None,
):
    t = Task(
        title=title,
        urgency=urgency,
        deadline=deadline,
        status=status,
        category=category,
        notes=notes,
    )
    if created:
        t.created_at = created
    db.add(t)
    db.flush()
    return t


# --- D01
@pytest.mark.task("D01")
def test_d01_local_today():
    late = datetime(2026, 11, 21, 23, 30, tzinfo=UTC)  # already the 22nd in Amsterdam
    assert m.local_today(late) == date(2026, 11, 22)
    assert m.local_today(datetime(2026, 7, 1, 21, 59, tzinfo=UTC)) == date(2026, 7, 1)
    assert isinstance(m.local_today(), date)


@pytest.mark.task("D01")
def test_d01_deadline_text():
    assert m.deadline_text(TODAY, TODAY) == ("due today", False)
    assert m.deadline_text(TODAY + timedelta(days=1), TODAY) == ("due tomorrow", False)
    assert m.deadline_text(TODAY + timedelta(days=5), TODAY) == ("due in 5 days", False)
    assert m.deadline_text(TODAY - timedelta(days=3), TODAY) == ("overdue by 3 days", True)


# --- D02
@pytest.mark.task("D02")
def test_d02_sort_key():
    t0 = datetime(2026, 11, 1, tzinfo=UTC)

    def t(title, urgency, deadline=None, age=0):
        return Task(
            title=title, urgency=urgency, deadline=deadline, created_at=t0 - timedelta(days=age)
        )

    tasks = [
        t("low", "low"),
        t("high-none-old", "high", age=5),
        t("high-none-new", "high", age=1),
        t("high-soon", "high", TODAY),
        t("critical-late", "critical", TODAY + timedelta(days=30)),
    ]
    got = [x.title for x in sorted(tasks, key=m.sort_key)]
    assert got == ["critical-late", "high-soon", "high-none-new", "high-none-old", "low"]


# --- D03
GOOD = {
    "title": "  Fix the bin ",
    "notes": "lid",
    "category": "repair",
    "urgency": "high",
    "deadline": "2026-11-30",
    "object_id": "7",
}


@pytest.mark.task("D03")
def test_d03_validate_good():
    values, errors = m.validate_form(GOOD, {7})
    assert errors == {}
    assert values == {
        "title": "Fix the bin",
        "notes": "lid",
        "category": "repair",
        "urgency": "high",
        "deadline": date(2026, 11, 30),
        "object_id": 7,
    }
    values, errors = m.validate_form(GOOD | {"deadline": "", "object_id": ""}, set())
    assert errors == {} and values["deadline"] is None and values["object_id"] is None


@pytest.mark.task("D03")
@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ({"title": "   "}, "title"),
        ({"title": "x" * 121}, "title"),
        ({"notes": "n" * 2001}, "notes"),
        ({"category": "party"}, "category"),
        ({"urgency": "whenever"}, "urgency"),
        ({"deadline": "next week"}, "deadline"),
        ({"object_id": "999"}, "object_id"),
        ({"object_id": "abc"}, "object_id"),
    ],
)
def test_d03_validate_bad(bad, field):
    values, errors = m.validate_form(GOOD | bad, {7})
    assert list(errors) == [field] and errors[field]
    assert set(values) == set(m.FORM_FIELDS)
    if field == "deadline":
        assert values["deadline"] == "next week"


# --- D04
@pytest.mark.task("D04")
def test_d04_find_tasks(db):
    add(db, "Fix compost bin", category="repair", notes="the LID is broken")
    add(db, "Finish the edging", "high", category="build")
    add(db, "Old job", status="done")
    assert [t.title for t in m.find_tasks(db, "open")] == ["Finish the edging", "Fix compost bin"]
    assert [t.title for t in m.find_tasks(db, "done")] == ["Old job"]
    assert len(m.find_tasks(db, "all")) == 3
    assert [t.title for t in m.find_tasks(db, "open", category="repair")] == ["Fix compost bin"]
    assert [t.title for t in m.find_tasks(db, "all", q="lid")] == ["Fix compost bin"]
    assert [t.title for t in m.find_tasks(db, "all", q="EDGING")] == ["Finish the edging"]


# --- D05
@pytest.mark.task("D05")
def test_d05_counts(db):
    add(db, "Late", deadline=TODAY - timedelta(days=1))
    add(db, "Today", deadline=TODAY)
    add(db, "Six", deadline=TODAY + timedelta(days=6))
    add(db, "Seven", deadline=TODAY + timedelta(days=7))
    add(db, "Someday")
    add(db, "Done late", deadline=TODAY - timedelta(days=9), status="done")
    assert m.counts(db, TODAY) == {"open": 5, "done": 1, "all": 6, "overdue": 1, "week": 2}


# --- D06
@pytest.mark.task("D06")
def test_d06_task_json(db):
    t = add(db, "Water", "high", deadline=TODAY, notes="beans")
    t.x, t.y = 1.5, 2.0
    out = m.task_json(t)
    assert set(out) == {
        "id",
        "title",
        "notes",
        "category",
        "urgency",
        "status",
        "deadline",
        "object_id",
        "x",
        "y",
        "created_at",
        "done_at",
    }
    assert out["deadline"] == "2026-11-21" and out["done_at"] is None and out["x"] == 1.5
    assert (
        out["created_at"] == t.created_at.isoformat()
        and out["title"] == "Water"
        and out["id"] == t.id
    )
    assert m.task_json(Task(title="n", status="open"))["deadline"] is None


# --- D07
@pytest.mark.task("D07")
def test_d07_apply_form_and_set_done(db):
    obj = GardenObject(kind="compost", name="Bin", x=0, y=0, w=1, d=1, h=1, props={})
    db.add(obj)
    db.flush()
    t = Task(status="open")
    m.apply_form(
        t,
        {
            "title": "A",
            "notes": "n",
            "category": "build",
            "urgency": "low",
            "deadline": TODAY,
            "object_id": obj.id,
        },
    )
    assert (t.title, t.notes, t.category, t.urgency, t.deadline, t.object_id) == (
        "A",
        "n",
        "build",
        "low",
        TODAY,
        obj.id,
    )
    now = datetime(2026, 11, 21, 9, tzinfo=UTC)
    m.set_done(t, True, now)
    assert t.status == "done" and t.done_at == now
    m.set_done(t, False, now)
    assert t.status == "open" and t.done_at is None
