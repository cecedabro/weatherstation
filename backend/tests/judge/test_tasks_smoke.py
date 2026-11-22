"""Tasks glue smoke tests that pass at every step of the loop. Human-owned."""

from app.models import Task

from ._helpers import auth


def test_private(client, db):
    assert client.get("/tasks", follow_redirects=False).status_code == 303
    assert client.get("/api/v1/tasks").status_code == 401


def test_pages_render(client, db):
    db.add(Task(title="Water", status="open", category="other", urgency="normal"))
    db.flush()
    tid = db.query(Task).one().id
    for url in (
        "/tasks",
        "/tasks?status=done&category=repair&q=x",
        "/tasks/new",
        f"/tasks/{tid}/edit",
    ):
        assert client.get(url, auth=auth()).status_code == 200, url
    assert client.get("/api/v1/tasks?status=all", auth=auth()).status_code == 200
    assert client.get("/tasks/999/edit", auth=auth()).status_code == 404
    for act in ("done", "reopen"):
        r = client.post(f"/tasks/{tid}/{act}", auth=auth(), follow_redirects=False)
        assert r.status_code == 303
    assert client.post("/tasks/999/done", auth=auth()).status_code == 404
    assert (
        client.post(f"/tasks/{tid}/delete", auth=auth(), follow_redirects=False).status_code == 303
    )
