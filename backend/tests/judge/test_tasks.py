"""Acceptance tests for Tasks (SPEC §14). Human-owned."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.accept  # loop D; removed after review

from app.models import GardenObject, Task

from ._helpers import auth

TODAY = datetime.now(ZoneInfo("Europe/Amsterdam")).date()  # SPEC 14.2: 'today' is local


def add(
    db,
    title,
    urgency="normal",
    deadline=None,
    status="open",
    category="other",
    notes="",
    object_id=None,
):
    t = Task(
        title=title,
        urgency=urgency,
        deadline=deadline,
        status=status,
        category=category,
        notes=notes,
        object_id=object_id,
    )
    db.add(t)
    db.flush()
    return t.id


def page(client, **params):
    r = client.get("/tasks", params=params, auth=auth())
    assert r.status_code == 200
    return r.text


def order(html, titles):
    pos = [html.index(t) for t in titles]
    return pos == sorted(pos)


def post(client, url, data=None):
    return client.post(url, data=data or {}, auth=auth(), follow_redirects=False)


# --- 14.0 private
def test_private(client, db):
    assert client.get("/tasks", follow_redirects=False).status_code == 303
    assert client.get("/api/v1/tasks").status_code == 401


# --- 14.1 list, tabs, order, filters
def test_empty_state(client, db):
    t = page(client)
    assert 'class="empty"' in t and 'href="/tasks/new"' in t


def test_order_urgency_then_deadline(client, db):
    add(db, "Low later", "low")
    add(db, "High no deadline", "high")
    add(db, "High soon", "high", TODAY + timedelta(days=2))
    add(db, "Critical", "critical", TODAY + timedelta(days=30))
    add(db, "Normal", "normal", TODAY)
    t = page(client)
    assert order(t, ["Critical", "High soon", "High no deadline", "Normal", "Low later"])


def test_tabs_and_counts(client, db):
    add(db, "Open one")
    add(db, "Open two")
    add(db, "Finished", status="done")
    t = page(client)
    assert "Open one" in t and "Finished" not in t
    assert re.search(r'href="/tasks\?status=done"', t) and re.search(
        r'href="/tasks\?status=all"', t
    )
    assert re.search(r">\s*Open\s*<span class=\"tab-count\">2<", t)
    assert re.search(r">\s*Done\s*<span class=\"tab-count\">1<", t)
    assert "Finished" in page(client, status="done") and "Open one" not in page(
        client, status="done"
    )
    assert "Finished" in page(client, status="all") and "Open one" in page(client, status="all")


def test_filters(client, db):
    add(db, "Fix compost bin", category="repair", notes="the lid is broken")
    add(db, "Finish the edging", category="build")
    assert "Finish the edging" not in page(client, category="repair")
    t = page(client, q="LID")
    assert "Fix compost bin" in t and "Finish the edging" not in t


# --- 14.2 row contents
def test_row_deadline_texts_and_object(client, db):
    obj = GardenObject(kind="compost", name="Compost bin", x=1, y=1, w=1, d=1, h=1, props={})
    db.add(obj)
    db.flush()
    add(db, "Today task", deadline=TODAY)
    add(db, "Tomorrow task", deadline=TODAY + timedelta(days=1))
    add(db, "Later task", deadline=TODAY + timedelta(days=5), object_id=obj.id)
    add(db, "Late task", deadline=TODAY - timedelta(days=3))
    t = page(client)
    assert (
        "due today" in t
        and "due tomorrow" in t
        and "due in 5 days" in t
        and "overdue by 3 days" in t
    )
    assert "Compost bin" in t
    assert "chip-bad" in t
    assert "u-normal" in t
    assert re.search(r'action="/tasks/\d+/done"', t) and re.search(r'href="/tasks/\d+/edit"', t)


# --- 14.3 create, validate, edit
def test_create(client, db):
    r = post(
        client,
        "/tasks",
        {
            "title": "  Fix the compost bin  ",
            "category": "repair",
            "urgency": "high",
            "deadline": (TODAY + timedelta(days=3)).isoformat(),
            "notes": "lid",
            "object_id": "",
        },
    )
    assert r.status_code == 303 and r.headers["location"] == "/tasks"
    task = db.query(Task).one()
    assert (task.title, task.category, task.urgency, task.status) == (
        "Fix the compost bin",
        "repair",
        "high",
        "open",
    )
    assert task.deadline == TODAY + timedelta(days=3)


@pytest.mark.parametrize(
    "bad",
    [
        {"title": "   "},
        {"title": "x" * 121},
        {"category": "party"},
        {"urgency": "whenever"},
        {"deadline": "next week"},
        {"object_id": "999"},
        {"notes": "n" * 2001},
    ],
)
def test_validation(client, db, bad):
    data = {
        "title": "Valid",
        "category": "other",
        "urgency": "normal",
        "deadline": "",
        "notes": "",
        "object_id": "",
    }
    data.update(bad)
    r = post(client, "/tasks", data)
    assert r.status_code == 400
    assert 'class="field-error"' in r.text
    if "title" not in bad:
        assert 'value="Valid"' in r.text  # typed values are kept
    assert db.query(Task).count() == 0


def test_new_and_edit_forms(client, db):
    assert 'action="/tasks"' in client.get("/tasks/new", auth=auth()).text
    tid = add(db, "Paint the shed", "low")
    t = client.get(f"/tasks/{tid}/edit", auth=auth()).text
    assert f'action="/tasks/{tid}"' in t and 'value="Paint the shed"' in t
    r = post(
        client,
        f"/tasks/{tid}",
        {
            "title": "Paint the shed green",
            "category": "maintenance",
            "urgency": "normal",
            "deadline": "",
            "notes": "",
            "object_id": "",
        },
    )
    assert r.status_code == 303
    db.expire_all()
    assert db.get(Task, tid).title == "Paint the shed green"
    assert client.get("/tasks/999/edit", auth=auth()).status_code == 404


# --- 14.4 done, reopen, delete
def test_done_reopen_delete(client, db):
    tid = add(db, "Water the beans")
    assert post(client, f"/tasks/{tid}/done").status_code == 303
    db.expire_all()
    task = db.get(Task, tid)
    assert task.status == "done" and task.done_at is not None
    post(client, f"/tasks/{tid}/reopen")
    db.expire_all()
    assert db.get(Task, tid).status == "open" and db.get(Task, tid).done_at is None
    post(client, f"/tasks/{tid}/delete")
    db.expire_all()
    assert db.get(Task, tid) is None
    for action in ("done", "reopen", "delete"):
        assert post(client, f"/tasks/999/{action}").status_code == 404


# --- 14.5 API, 14.6 stats
def test_api(client, db):
    add(db, "B", "low")
    add(db, "A", "critical", TODAY)
    add(db, "Z", status="done")
    rows = client.get("/api/v1/tasks", auth=auth()).json()
    assert [r["title"] for r in rows] == ["A", "B"]
    assert set(rows[0]) == {
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
    assert rows[0]["deadline"] == TODAY.isoformat()
    assert [r["title"] for r in client.get("/api/v1/tasks?status=all", auth=auth()).json()] == [
        "A",
        "B",
        "Z",
    ]


def test_stats(client, db):
    add(db, "Late", deadline=TODAY - timedelta(days=1))
    add(db, "Soon", deadline=TODAY + timedelta(days=3))
    add(db, "Someday")
    t = page(client)
    stats = re.findall(r'class="stat-label">(.*?)</div>\s*<div class="stat-value">(\d+)', t, re.S)
    labels = {re.sub(r"<.*?>", "", k).strip().lower(): int(v) for k, v in stats}
    assert labels.get("open") == 3
    assert labels.get("overdue") == 1
    assert (
        any(k.startswith("due this week") or k == "this week" for k in labels)
        and 2 in labels.values()
    )
