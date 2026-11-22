"""Acceptance tests for the seed log (SPEC §13, roadmap loop P). Human-owned."""

import re
from datetime import date, timedelta

import pytest

from app.models import Crop, GardenObject, Planting
from app.tasks import local_today

from ._helpers import auth

pytestmark = pytest.mark.task("P11")  # the whole feature; P11 makes it pass


@pytest.fixture()
def garden(db):
    b1 = GardenObject(kind="bed", name="Bed 1", props={})
    b2 = GardenObject(kind="bed", name="Bed 2", props={})
    carrot = Crop(name="Carrot", family="Apiaceae", days_to_harvest=80, sow_months="1-12")
    parsnip = Crop(name="Parsnip", family="Apiaceae", days_to_harvest=120, sow_months="3-5")
    db.add_all([b1, b2, carrot, parsnip])
    db.flush()
    return {"b1": b1, "b2": b2, "carrot": carrot, "parsnip": parsnip}


def form(**kw):
    base = {
        "crop": "Carrot",
        "variety": "",
        "object_id": "",
        "method": "sown",
        "status": "sown",
        "sown_on": local_today().isoformat(),
        "count": "",
        "notes": "",
    }
    return base | {k: str(v) for k, v in kw.items()}


def test_create_and_list(client, db, garden):
    sown = local_today() - timedelta(days=10)
    r = client.post(
        "/seeds",
        data=form(
            crop="carrot",
            variety="Nantes",
            object_id=garden["b1"].id,
            sown_on=sown.isoformat(),
            count=40,
        ),
        auth=auth(),
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/seeds"
    p = db.query(Planting).one()
    assert (p.crop, p.crop_id, p.variety, p.count) == ("carrot", garden["carrot"].id, "Nantes", 40)
    assert p.expected_harvest == sown + timedelta(days=80)

    page = client.get("/seeds", auth=auth()).text
    assert "Bed 1" in page and "carrot · Nantes" in page
    assert "ready in 70 days" in page
    assert "→ Sprouted" in page

    api = client.get("/api/v1/plantings", auth=auth()).json()
    assert (
        api[0]["crop_id"] == garden["carrot"].id
        and api[0]["expected_harvest"] == (sown + timedelta(days=80)).isoformat()
    )


def test_form_errors_keep_values(client, db, garden):
    r = client.post("/seeds", data=form(crop="", sown_on="soon", count="0"), auth=auth())
    assert r.status_code == 400
    assert (
        "Which crop?" in r.text
        and "Use a date (YYYY-MM-DD)" in r.text
        and "A whole number, 1 or more" in r.text
    )
    assert 'value="soon"' in r.text
    assert db.query(Planting).count() == 0


def test_advance_to_done_and_tabs(client, db, garden):
    client.post("/seeds", data=form(status="harvesting"), auth=auth())
    p = db.query(Planting).one()
    assert (
        client.post(f"/seeds/{p.id}/advance", auth=auth(), follow_redirects=False).status_code
        == 303
    )
    db.refresh(p)
    assert (p.status, p.harvested_on) == ("done", local_today())
    client.post(f"/seeds/{p.id}/advance", auth=auth())  # nothing after done
    db.refresh(p)
    assert p.status == "done"
    active = client.get("/seeds", auth=auth()).text
    assert "Nothing sown yet" in active
    done = client.get("/seeds?show=done", auth=auth()).text
    assert "harvested" in done
    assert re.search(r"Done\D*1", done)


def test_rotation_warning_shown(client, db, garden):
    last_year = date(local_today().year - 1, 4, 1)
    db.add(
        Planting(
            crop="Parsnip",
            crop_id=garden["parsnip"].id,
            object_id=garden["b2"].id,
            sown_on=last_year,
            status="done",
            method="sown",
        )
    )
    db.flush()
    client.post("/seeds", data=form(object_id=garden["b2"].id), auth=auth())
    page = client.get("/seeds", auth=auth()).text
    assert f"Apiaceae grew here in {last_year.year} (Parsnip)" in page
    client.post("/seeds", data=form(object_id=garden["b1"].id, crop="Pea"), auth=auth())
    assert client.get("/seeds", auth=auth()).text.count("grew here") == 1


def test_crops_page(client, db, garden):
    page = client.get("/crops", auth=auth()).text
    assert "Carrot" in page and "Parsnip" in page
    assert "Sow now" in page  # Carrot is sowable all year in this test
    assert "/seeds/new?crop=Carrot" in page
