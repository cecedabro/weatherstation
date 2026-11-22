"""Step tests for the Sensors loop: one group per task (S01–S08). Human-owned.

`make check` skips a group until PLAN.md ticks its task (tests/conftest.py); the task's accept command
runs it with TASKS=all.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

from datetime import UTC, date, datetime, timedelta

import pytest

from app import sensors as s
from app.stats import daily_stats, summarize

from ._helpers import add_node, add_readings

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.fixture()
def temps(db):
    add_node(db, "w1", "weather")
    add_readings(
        db,
        "w1",
        "temp_c",
        [
            (NOW - timedelta(hours=3), 10.0),
            (NOW - timedelta(hours=2), 14.0),
            (NOW - timedelta(hours=1), 12.0),
        ],
    )
    return db


# --- S01 summarize
@pytest.mark.task("S01")
def test_s01_summarize_numbers(temps):
    out = summarize(temps, "w1", "temp_c", NOW - timedelta(days=1), NOW)
    assert out["node"] == "w1" and out["metric"] == "temp_c" and out["count"] == 3
    assert (out["min"], out["max"], out["sum"]) == (10.0, 14.0, 36.0)
    assert out["avg"] == pytest.approx(12.0) and isinstance(out["avg"], float)
    assert out["first_ts"] == NOW - timedelta(hours=3) and out["last_ts"] == NOW - timedelta(
        hours=1
    )


@pytest.mark.task("S01")
def test_s01_summarize_window_is_half_open(temps):
    out = summarize(temps, "w1", "temp_c", NOW - timedelta(hours=2), NOW - timedelta(hours=1))
    assert out["count"] == 1 and out["min"] == 14.0


@pytest.mark.task("S01")
def test_s01_summarize_empty(temps):
    out = summarize(temps, "w1", "rain_mm", NOW - timedelta(days=1), NOW)
    assert out == {"node": "w1", "metric": "rain_mm", "count": 0, "min": None, "max": None,
                   "avg": None, "sum": None, "first_ts": None, "last_ts": None}  # fmt: skip


# --- S02 daily_stats
@pytest.mark.task("S02")
def test_s02_daily_stats_rows(db):
    add_node(db, "w1", "weather")
    d1 = datetime(2026, 11, 19, 10, tzinfo=UTC)
    add_readings(
        db,
        "w1",
        "temp_c",
        [(d1, 4.0), (d1 + timedelta(hours=2), 8.0), (d1 + timedelta(days=1), 20.0)],
    )
    rows = daily_stats(db, "w1", "temp_c", 5, NOW)
    assert rows == [
        {"date": "2026-11-19", "min": 4.0, "max": 8.0, "avg": 6.0, "sum": 12.0, "count": 2},
        {"date": "2026-11-20", "min": 20.0, "max": 20.0, "avg": 20.0, "sum": 20.0, "count": 1},
    ]


@pytest.mark.task("S02")
def test_s02_daily_stats_window_and_limits(db):
    add_node(db, "w1", "weather")
    add_readings(
        db, "w1", "temp_c", [(NOW - timedelta(days=1), 1.0), (NOW - timedelta(hours=1), 2.0)]
    )
    assert [r["date"] for r in daily_stats(db, "w1", "temp_c", 1, NOW)] == ["2026-11-21"]
    assert len(daily_stats(db, "w1", "temp_c", 2, NOW)) == 2
    for bad in (0, 367):
        with pytest.raises(ValueError):
            daily_stats(db, "w1", "temp_c", bad, NOW)


# --- S03 parse_compare, parse_view
@pytest.mark.task("S03")
def test_s03_parse_compare():
    assert s.parse_compare(None) == () and s.parse_compare("") == ()
    assert s.parse_compare(" 2026-11-20, oops,2026-11-21") == (
        date(2026, 11, 20),
        date(2026, 11, 21),
    )
    four = "2026-11-01,2026-11-02,2026-11-02,2026-11-03,2026-11-04"
    assert s.parse_compare(four) == (date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3))


@pytest.mark.task("S03")
def test_s03_parse_view_defaults_and_fallbacks():
    assert s.parse_view({}, ["w-b", "w-a"]) == s.View("air", "7d", "w-a", ())
    assert s.parse_view({"cat": "lava", "range": "forever", "node": "x"}, ["w-a"]) == s.View(
        "air", "7d", "w-a"
    )
    assert s.parse_view({"cat": "soil"}, []) == s.View("soil", "7d", None)
    v = s.parse_view(
        {"cat": "rain", "range": "30d", "node": "w-b", "compare": "2026-11-20"}, ["w-a", "w-b"]
    )
    assert v == s.View("rain", "30d", "w-b", (date(2026, 11, 20),))


# --- S04 view_href, range_window, daily_days
@pytest.mark.task("S04")
def test_s04_view_href():
    v = s.View("air", "7d", "weather-b")
    assert s.view_href(v, range="30d") == "/sensors?cat=air&range=30d&node=weather-b"
    assert s.view_href(v, cat="rain") == "/sensors?cat=rain&range=7d"
    c = s.View("air", "24h", "w", (date(2026, 11, 20), date(2026, 11, 21)))
    assert (
        s.view_href(c, node="w2")
        == "/sensors?cat=air&range=24h&node=w2&compare=2026-11-20,2026-11-21"
    )
    assert s.view_href(s.View("soil")) == "/sensors?cat=soil&range=7d"


@pytest.mark.task("S04")
def test_s04_range_window_and_daily_days():
    assert s.range_window("24h", NOW) == (NOW - timedelta(hours=24), NOW)
    assert s.range_window("365d", NOW) == (NOW - timedelta(hours=8760), NOW)
    assert s.range_window("nope", NOW) == (NOW - timedelta(hours=168), NOW)
    days = {k: s.daily_days(k) for k in ("24h", "7d", "30d", "90d", "365d", "nope")}
    assert days == {"24h": 1, "7d": 7, "30d": 30, "90d": 31, "365d": 31, "nope": 7}


# --- S05 latest, tiles
@pytest.mark.task("S05")
def test_s05_latest(temps):
    assert s.latest(temps, "w1", "temp_c") == 12.0
    assert s.latest(temps, "w1", "rain_mm") is None


@pytest.mark.task("S05")
def test_s05_tiles():
    summ = {"min": 10.0, "max": 14.0, "avg": 12.0, "sum": 36.0, "count": 3}
    assert s.tiles("temp_c", summ, 12.0) == [
        ("Latest", 12.0, "°C"),
        ("Min", 10.0, "°C"),
        ("Max", 14.0, "°C"),
        ("Average", 12.0, "°C"),
    ]
    assert s.tiles("rain_mm", summ, 2.0) == [("Latest", 2.0, "mm"), ("Total", 36.0, "mm")]
    assert s.tiles("wind_dir_deg", summ, 270.4) == [("Latest", "W 270°", "")]
    assert s.tiles("wind_dir_deg", summ, None) == [("Latest", None, "")]


# --- S06 merge_daily
@pytest.mark.task("S06")
def test_s06_merge_daily():
    t1 = {"date": "2026-11-20", "min": 1.0}
    t2 = {"date": "2026-11-21", "min": 2.0}
    r1 = {"date": "2026-11-19", "sum": 3.0}
    out = s.merge_daily({"temp_c": [t1, t2], "rain_mm": [r1]})
    assert out == [
        {"date": "2026-11-21", "temp_c": t2, "rain_mm": None},
        {"date": "2026-11-20", "temp_c": t1, "rain_mm": None},
        {"date": "2026-11-19", "temp_c": None, "rain_mm": r1},
    ]
    many = [{"date": (date(2026, 1, 1) + timedelta(days=i)).isoformat()} for i in range(40)]
    big = s.merge_daily({"temp_c": many})
    assert len(big) == 31 and big[0]["date"] == "2026-02-09"
    assert s.merge_daily({}) == []


# --- S07 soil_rows
@pytest.mark.task("S07")
def test_s07_soil_rows(db):
    add_node(db, "bed-1", "soil")
    add_node(db, "bed-2", "soil")
    add_readings(db, "bed-1", "soil_moisture_pct", [(NOW - timedelta(hours=2), 30.0), (NOW, 31.0)])
    add_readings(db, "bed-1", "soil_temp_c", [(NOW, 9.5)])
    add_readings(db, "bed-2", "soil_moisture_pct", [(NOW, 22.0)])
    assert s.soil_rows(db, ["bed-2", "bed-1"]) == [
        {"node": "bed-2", "soil_moisture_pct": 22.0, "soil_temp_c": None},
        {"node": "bed-1", "soil_moisture_pct": 31.0, "soil_temp_c": 9.5},
    ]


# --- S08 compare_rows, csv_href
@pytest.mark.task("S08")
def test_s08_compare_rows(temps):
    rows = s.compare_rows(temps, "w1", "temp_c", (date(2026, 11, 21), date(2026, 11, 1)))
    assert rows[0] == {"date": "2026-11-21", "min": 10.0, "max": 14.0, "avg": pytest.approx(12.0)}
    assert rows[1] == {"date": "2026-11-01", "min": None, "max": None, "avg": None}


@pytest.mark.task("S08")
def test_s08_csv_href():
    start = datetime(2026, 11, 20, 8, 0, 0, 123456, tzinfo=UTC)
    href = s.csv_href("w 1", "temp_c", start, start + timedelta(days=1))
    assert href == (
        "/api/v1/export.csv?node=w+1&metric=temp_c&from=2026-11-20T08%3A00%3A00Z&to=2026-11-21T08%3A00%3A00Z"
    )
