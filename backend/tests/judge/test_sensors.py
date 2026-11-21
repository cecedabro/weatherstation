"""Acceptance tests for the Sensors page and its APIs (SPEC §11.1–§11.8). Human-owned."""

import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

pytestmark = pytest.mark.accept  # loop A; removed after review

from ._helpers import add_node, add_readings, hours_ago


@pytest.fixture()
def station(db):
    add_node(db, "weather-main", "weather")
    add_node(db, "weather-b", "weather")
    add_node(db, "soil-bed-1", "soil")
    add_node(db, "soil-bed-2", "soil")
    add_readings(
        db,
        "weather-main",
        "temp_c",
        [(hours_ago(3), 10.0), (hours_ago(2), 14.0), (hours_ago(1), 12.0)],
    )
    add_readings(db, "weather-main", "humidity_pct", [(hours_ago(1), 77.0)])
    add_readings(db, "weather-main", "rain_mm", [(hours_ago(2), 1.5), (hours_ago(1), 2.0)])
    add_readings(db, "weather-main", "wind_speed_ms", [(hours_ago(1), 4.0)])
    add_readings(db, "weather-main", "wind_dir_deg", [(hours_ago(1), 270.0)])
    add_readings(db, "soil-bed-1", "soil_moisture_pct", [(hours_ago(1), 31.0)])
    add_readings(db, "soil-bed-2", "soil_moisture_pct", [(hours_ago(1), 22.0)])
    return db


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# --- 11.3 summary API
def test_summary_numbers(client, station):
    r = client.get("/api/v1/summary", params={"node": "weather-main", "metric": "temp_c"})
    assert r.status_code == 200
    s = r.json()
    assert (s["node"], s["metric"], s["count"]) == ("weather-main", "temp_c", 3)
    assert (s["min"], s["max"], s["sum"]) == (10.0, 14.0, 36.0)
    assert s["avg"] == pytest.approx(12.0)
    assert s["first_ts"] < s["last_ts"]


def test_summary_window_and_empty(client, station):
    p = {
        "node": "weather-main",
        "metric": "temp_c",
        "from": iso(hours_ago(2.5)),
        "to": iso(hours_ago(1.5)),
    }
    assert client.get("/api/v1/summary", params=p).json()["count"] == 1
    e = client.get("/api/v1/summary", params={"node": "nope", "metric": "temp_c"}).json()
    assert e["count"] == 0 and e["min"] is None and e["avg"] is None and e["sum"] is None
    assert (
        client.get(
            "/api/v1/summary",
            params={"node": "weather-main", "metric": "temp_c", "from": "yesterday"},
        ).status_code
        == 400
    )


# --- 11.4 daily stats API
def test_daily_stats(client, db):
    add_node(db, "weather-main", "weather")
    day1 = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=2)
    day2 = day1 + timedelta(days=1)
    add_readings(
        db, "weather-main", "temp_c", [(day1, 4.0), (day1 + timedelta(hours=2), 8.0), (day2, 20.0)]
    )
    r = client.get(
        "/api/v1/daily_stats", params={"node": "weather-main", "metric": "temp_c", "days": 5}
    )
    assert r.status_code == 200
    rows = r.json()
    assert [x["date"] for x in rows] == [day1.date().isoformat(), day2.date().isoformat()]
    assert rows[0] == {
        "date": day1.date().isoformat(),
        "min": 4.0,
        "max": 8.0,
        "avg": 6.0,
        "sum": 12.0,
        "count": 2,
    }
    for bad in ("0", "367", "x"):
        assert (
            client.get(
                "/api/v1/daily_stats",
                params={"node": "weather-main", "metric": "temp_c", "days": bad},
            ).status_code
            == 400
        )


# --- 11.1 page, tabs, range, node picker
def links(html: str) -> list[str]:
    return [h.replace("&amp;", "&") for h in re.findall(r'href="([^"]*)"', html)]


def test_default_is_air_week(client, station):
    r = client.get("/sensors")
    assert r.status_code == 200
    t = r.text
    assert re.search(r"<title>Sensors", t)
    for cat in ("air", "soil", "rain", "wind"):
        assert any(
            "/sensors" in h and parse_qs(urlparse(h).query).get("cat") == [cat] for h in links(t)
        ), cat
    current = re.findall(r'<a[^>]*href="([^"]*)"[^>]*aria-current="page"', t)
    assert any("cat=air" in h for h in current)
    assert any("range=7d" in h for h in current)
    assert "temp_c" in t and "humidity_pct" in t and "pressure_hpa" in t


def test_links_keep_other_params(client, station):
    t = client.get("/sensors", params={"cat": "air", "range": "30d", "node": "weather-b"}).text
    tab = next(h for h in links(t) if "cat=rain" in h)
    q = parse_qs(urlparse(tab).query)
    assert q.get("range") == ["30d"]
    rng = next(h for h in links(t) if "range=90d" in h)
    assert parse_qs(urlparse(rng).query).get("cat") == ["air"]


def test_node_picker_and_default_node(client, station):
    t = client.get("/sensors", params={"cat": "air"}).text
    assert "weather-b" in t and "weather-main" in t
    assert (
        '"weather-b", "temp_c"' in t.replace("&#34;", '"')
        or "[&#34;weather-b&#34;, &#34;temp_c&#34;" in t
    )
    t2 = client.get("/sensors", params={"cat": "air", "node": "weather-main"}).text.replace(
        "&#34;", '"'
    )
    assert '"weather-main", "temp_c"' in t2


def test_unknown_params_fall_back(client, station):
    t = client.get("/sensors", params={"cat": "lava", "range": "forever"}).text
    current = re.findall(r'<a[^>]*href="([^"]*)"[^>]*aria-current="page"', t)
    assert any("cat=air" in h for h in current) and any("range=7d" in h for h in current)


# --- 11.2 metrics, tiles, charts
def test_air_tiles_show_latest_min_max_avg(client, station):
    t = client.get("/sensors", params={"cat": "air", "node": "weather-main", "range": "24h"}).text
    assert "data-chart" in t and 'data-range="24h"' in t
    for v in ("12.0", "10.0", "14.0"):  # latest, min, max
        assert v in t
    assert (
        re.search(r"\bmin\b", t, re.I)
        and re.search(r"\bmax\b", t, re.I)
        and re.search(r"\bav(era)?g", t, re.I)
    )


def test_rain_is_bars_with_total(client, station):
    t = client.get("/sensors", params={"cat": "rain", "node": "weather-main", "range": "24h"}).text
    assert 'data-kind="bar"' in t
    assert "3.5" in t  # total
    assert re.search(r"total", t, re.I)


def test_wind_compass(client, station):
    t = client.get("/sensors", params={"cat": "wind", "node": "weather-main"}).text
    assert "W 270" in t or "W (270" in t or ("W" in t and "270°" in t)


def test_soil_one_line_per_node(client, station):
    t = client.get("/sensors", params={"cat": "soil"}).text.replace("&#34;", '"')
    m = re.search(r"data-series='([^']*soil_moisture_pct[^']*)'", t)
    assert m, "soil moisture chart"
    assert "soil-bed-1" in m.group(1) and "soil-bed-2" in m.group(1)
    assert "31" in t and "22" in t


# --- 11.4 daily table, 11.5 compare, 11.6 CSV
def test_daily_table_on_page(client, station):
    t = client.get("/sensors", params={"cat": "air", "node": "weather-main"}).text
    assert "<table" in t
    assert date.today().strftime("%Y") in t or datetime.now(UTC).date().isoformat()[:4] in t


def test_compare_days(client, station):
    today = datetime.now(UTC).date()
    q = f"{today.isoformat()},{(today - timedelta(days=1)).isoformat()},not-a-date"
    t = client.get("/sensors", params={"cat": "air", "node": "weather-main", "compare": q}).text
    assert 'data-x="hour"' in t
    assert "Compare" in t
    assert today.isoformat() in t
    assert "not-a-date" not in t.split("data-series")[-1][:400]
    assert 'type="date"' in t


def test_csv_links(client, station):
    hrefs = [
        h
        for h in links(client.get("/sensors", params={"cat": "air", "node": "weather-main"}).text)
        if h.startswith("/api/v1/export.csv")
    ]
    assert hrefs
    q = parse_qs(urlparse(hrefs[0]).query)
    assert q["node"] == ["weather-main"] and q["metric"][0] in (
        "temp_c",
        "humidity_pct",
        "pressure_hpa",
    )
    assert "from" in q and "to" in q
    assert client.get(hrefs[0]).status_code == 200


# --- 11.7 redirects, 11.8 empty
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


@pytest.mark.parametrize("cat", ["air", "soil", "rain", "wind"])
def test_empty_station(client, db, cat):
    r = client.get("/sensors", params={"cat": cat})
    assert r.status_code == 200
    assert 'class="empty"' in r.text
