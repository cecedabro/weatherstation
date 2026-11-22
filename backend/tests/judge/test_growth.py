"""Acceptance tests for growth, best spot and the advisor (SPEC §16, loop A). Human-owned."""

# ruff: noqa: E501

from datetime import UTC, datetime, timedelta

import pytest

from app import advisor
from app.config import Settings
from app.models import Crop, GardenObject, Planting, Source
from app.tasks import local_today

from ._helpers import add_node, add_readings, auth

pytestmark = pytest.mark.task("A14")  # the whole feature; A14 makes it pass


def test_growth_progress_and_eta(client, db):
    today = local_today()
    add_node(db, "wx", "weather")
    pts = []
    for back in range(1, 11):  # 10 full days of 10 °C min / 20 °C max → 10 GDD a day at base 5
        day = datetime.combine(today - timedelta(days=back), datetime.min.time(), tzinfo=UTC)
        pts += [(day + timedelta(hours=4), 10.0), (day + timedelta(hours=13), 20.0)]
    add_readings(db, "wx", "temp_c", pts)
    c = Crop(name="Radish", base_temp_c=5.0, gdd_to_harvest=200.0)
    db.add(c)
    db.flush()
    db.add(
        Planting(
            crop="Radish",
            crop_id=c.id,
            sown_on=today - timedelta(days=10),
            status="growing",
            method="sown",
        )
    )
    db.flush()
    api = client.get("/api/v1/growth", auth=auth()).json()
    assert len(api) == 1
    row = api[0]
    assert row["gdd"] == 100 and row["progress"] == 50
    assert row["eta"] == (today + timedelta(days=10)).isoformat()
    page = client.get("/growth", auth=auth()).text
    assert "Radish" in page and "100 GDD in 10 days" in page and "50%" in page


def test_best_spot(client, db):
    c = Crop(
        name="Carrot", family="Apiaceae", sun="full", moisture_min_pct=35.0, moisture_max_pct=65.0
    )
    db.add_all(
        [
            c,
            GardenObject(kind="bed", name="Sunny", props={"sun_hours": 8}),
            GardenObject(kind="bed", name="Shady", props={"sun_hours": 2}),
            GardenObject(kind="path", name="Path", props={}),
        ]
    )
    db.flush()
    page = client.get(f"/growth?crop={c.id}", auth=auth()).text
    assert page.index("1. Sunny") < page.index("2. Shady")
    assert "8 h sun (needs 6+)" in page and "only 2 h sun (needs 6+)" in page
    assert "Path" not in page.split("Best spot")[1]


def test_sources_crud(client, db):
    r = client.post(
        "/sources",
        data={
            "title": "Leeks",
            "kind": "guide",
            "url": "",
            "publisher": "",
            "body": "Sow leeks in March.",
            "tags": "Leek",
        },
        auth=auth(),
        follow_redirects=False,
    )
    assert r.status_code == 303
    s = db.query(Source).one()
    assert (s.title, s.tags, s.url) == ("Leeks", "leek", None)
    r = client.post("/sources", data={"title": "", "kind": "x", "body": ""}, auth=auth())
    assert r.status_code == 400 and "Pick a kind" in r.text
    assert "Leeks" in client.get("/sources", auth=auth()).text


@pytest.fixture()
def llm_on(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gateway.test/v1")
    assert Settings().LLM_BASE_URL


def test_advisor_cites_sources(client, db, llm_on, monkeypatch):
    db.add_all(
        [
            Source(
                title="Growing leeks",
                kind="guide",
                body="Sow leeks in March, 15 cm apart.",
                tags="leek",
            ),
            Source(title="Tomatoes", kind="guide", body="Warmth.", tags=""),
        ]
    )
    db.flush()
    seen = {}

    def fake(messages):
        seen["prompt"] = messages[-1]["content"]
        return "Sow them in March, 15 cm apart [1]."

    monkeypatch.setattr(advisor, "ask_llm", fake)
    page = client.post("/advisor", data={"question": "When do I sow leeks?"}, auth=auth()).text
    assert "[1] Growing leeks" in seen["prompt"] and "Tomatoes" not in seen["prompt"]
    assert "Sow them in March, 15 cm apart [1]." in page
    assert "Not in the sources" not in page


@pytest.mark.parametrize("reply", ["Sow in March.", "Sow in March [3].", "NOT IN SOURCES"])
def test_advisor_rejects_uncited(client, db, llm_on, monkeypatch, reply):
    db.add(Source(title="Growing leeks", kind="guide", body="Sow leeks in March.", tags="leek"))
    db.flush()
    monkeypatch.setattr(advisor, "ask_llm", lambda messages: reply)
    page = client.post("/advisor", data={"question": "When do I sow leeks?"}, auth=auth()).text
    assert (
        "Not in the sources" in page
        and reply not in page.split("Your question")[1].split("</form>")[1]
    )


def test_advisor_no_match_and_errors(client, db, llm_on, monkeypatch):
    db.add(Source(title="Growing leeks", kind="guide", body="Sow leeks in March.", tags="leek"))
    db.flush()
    called = []
    monkeypatch.setattr(advisor, "ask_llm", lambda m: called.append(1) or "x [1]")
    assert (
        "Not in the sources"
        in client.post("/advisor", data={"question": "pumpkins?"}, auth=auth()).text
    )
    assert called == []  # no matching source: the model isn't asked

    def boom(messages):
        raise OSError("gateway down")

    monkeypatch.setattr(advisor, "ask_llm", boom)
    assert (
        "No answer right now"
        in client.post("/advisor", data={"question": "leeks?"}, auth=auth()).text
    )
