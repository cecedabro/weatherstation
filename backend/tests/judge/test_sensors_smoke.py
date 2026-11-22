"""Sensors page smoke tests that pass at every step of the loop (the glue in app/sensors.py and
app/stats.py). Human-owned."""

import pytest

from ._helpers import add_node, add_readings, hours_ago


@pytest.fixture()
def station(db):
    add_node(db, "weather-main", "weather")
    add_node(db, "soil-bed-1", "soil")
    add_readings(db, "weather-main", "temp_c", [(hours_ago(2), 10.0), (hours_ago(1), 12.0)])
    add_readings(db, "soil-bed-1", "soil_moisture_pct", [(hours_ago(1), 31.0)])
    return db


@pytest.mark.parametrize("cat", ["air", "soil", "rain", "wind"])
def test_page_renders(client, station, cat):
    q = {"cat": cat, "range": "24h", "d1": "2026-11-20", "d2": "2026-11-21"}
    r = client.get("/sensors", params=q)
    assert r.status_code == 200 and "<title>Sensors" in r.text


def test_apis_answer(client, station):
    p = {"node": "weather-main", "metric": "temp_c"}
    assert client.get("/api/v1/summary", params=p).status_code == 200
    assert client.get("/api/v1/summary", params=p | {"from": "yesterday"}).status_code == 400
    assert client.get("/api/v1/daily_stats", params=p | {"days": "5"}).status_code == 200
    for bad in ("0", "367", "x"):
        assert client.get("/api/v1/daily_stats", params=p | {"days": bad}).status_code == 400


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/weather", "/sensors?cat=air"),
        ("/history", "/sensors?cat=air&range=30d"),
        ("/soil", "/sensors?cat=soil"),
        ("/soil/soil-bed-1", "/sensors?cat=soil&node=soil-bed-1"),
    ],
)
def test_old_pages_redirect(client, old, new):
    r = client.get(old, follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == new
