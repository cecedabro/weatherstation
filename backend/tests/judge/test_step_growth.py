"""Step tests for the growth and advisor loop: one group per task (A01–A13). Human-owned.

`make check` skips a group while PLAN.md lists its task as open (tests/conftest.py); accept runs it with TASKS=all.
"""

# ruff: noqa: E501

from datetime import UTC, date, datetime

import pytest

from app import advisor as adv
from app import growth as m
from app.models import Crop, Source


# -- A01 daily_gdd
@pytest.mark.task("A01")
@pytest.mark.parametrize(
    "tmin, tmax, base, want",
    [
        (10, 20, 5, 10.0),  # (20 + 10) / 2 - 5
        (2, 14, 5, 4.5),  # min raised to base: (14 + 5) / 2 - 5
        (18, 36, 10, 14.0),  # max capped at 30: (30 + 18) / 2 - 10
        (-3, 4, 5, 0.0),  # whole day below base
        (8, 8, 5, 3.0),
        (31, 35, 10, 21.0),  # hi = min(35, 30) = 30 is below lo = 31, so hi = lo: 31 - 10
    ],
)
def test_a01_daily_gdd(tmin, tmax, base, want):
    assert m.daily_gdd(tmin, tmax, base) == pytest.approx(want)


@pytest.mark.task("A01")
def test_a01_custom_cap():
    assert m.daily_gdd(10, 40, 0, cap=35) == pytest.approx(22.5)


# -- A02 local_daily_temps
@pytest.mark.task("A02")
def test_a02_local_daily_temps():
    rows = [
        (datetime(2026, 6, 1, 3, 0, tzinfo=UTC), 9.0),
        (datetime(2026, 6, 1, 13, 0, tzinfo=UTC), 21.5),
        (datetime(2026, 6, 1, 22, 30, tzinfo=UTC), 30.0),  # 00:30 on 2 June in Amsterdam (CEST, +2)
        (datetime(2026, 6, 2, 12, 0), 18.0),  # no tzinfo: UTC
        (datetime(2026, 6, 1, 8, 0, tzinfo=UTC), 12.0),
    ]
    assert m.local_daily_temps(rows) == {
        date(2026, 6, 1): (9.0, 21.5),
        date(2026, 6, 2): (18.0, 30.0),
    }
    assert m.local_daily_temps([]) == {}


# -- A03 gdd_series
@pytest.mark.task("A03")
def test_a03_gdd_series():
    temps = {
        date(2026, 5, 1): (10.0, 20.0),
        date(2026, 5, 3): (0.0, 4.0),
        date(2026, 5, 4): (12.0, 16.0),
        date(2026, 4, 30): (10.0, 30.0),
    }
    assert m.gdd_series(temps, date(2026, 5, 1), date(2026, 5, 4), 5.0) == [
        (date(2026, 5, 1), 10.0),
        (date(2026, 5, 3), 0.0),
        (date(2026, 5, 4), 9.0),
    ]
    assert m.gdd_series(temps, date(2026, 5, 5), date(2026, 5, 9), 5.0) == []
    assert m.gdd_series(temps, date(2026, 5, 4), date(2026, 5, 1), 5.0) == []


# -- A04 progress
@pytest.mark.task("A04")
def test_a04_progress():
    assert m.progress(300, 1200) == 0.25
    assert m.progress(1000, 1200) == 0.833
    assert m.progress(1500, 1200) == 1.0
    assert m.progress(0, 800) == 0.0
    assert m.progress(300, None) is None
    assert m.progress(300, 0) is None


# -- A05 harvest_eta
@pytest.mark.task("A05")
def test_a05_harvest_eta():
    today = date(2026, 6, 1)
    assert m.harvest_eta(900, 1000, [10.0, 10.0, 12.0], today) == date(
        2026, 6, 11
    )  # 100 / 10.67 → 10 days
    assert m.harvest_eta(900, 1000, [9.0], today) == date(2026, 6, 13)  # 100 / 9 = 11.1 → 12 days
    assert m.harvest_eta(1000, 1000, [], today) == today
    assert m.harvest_eta(1200, 1000, [0.0], today) == today
    assert m.harvest_eta(500, 1000, [], today) is None
    assert m.harvest_eta(500, 1000, [0.0, 0.1], today) is None  # rate 0.05: too cold
    assert m.harvest_eta(500, None, [10.0], today) is None
    assert m.harvest_eta(500, 0, [10.0], today) is None


# -- A06 sun_fit
@pytest.mark.task("A06")
@pytest.mark.parametrize(
    "sun, hours, want",
    [
        ("full", 8, (1.0, "8 h sun (needs 6+)")),
        ("full", 6.0, (1.0, "6 h sun (needs 6+)")),
        ("full", 4.5, (0.75, "only 4.5 h sun (needs 6+)")),
        ("partial", 3, (1.0, "3 h sun (needs 3+)")),
        ("partial", 2, (0.67, "only 2 h sun (needs 3+)")),
        ("shade", 0, (1.0, "0 h sun (needs 0+)")),
        (None, 5, (0.83, "only 5 h sun (needs 6+)")),
        ("full", None, (0.5, "sun hours unknown")),
    ],
)
def test_a06_sun_fit(sun, hours, want):
    assert m.sun_fit(sun, hours) == want


# -- A07 moisture_fit
@pytest.mark.task("A07")
@pytest.mark.parametrize(
    "avg, want",
    [
        (55.0, (1.0, "soil 55% suits it (40–70%)")),
        (40.0, (1.0, "soil 40% suits it (40–70%)")),
        (30.0, (0.5, "too dry: 30% (needs 40–70%)")),
        (12.0, (0.0, "too dry: 12% (needs 40–70%)")),
        (75.0, (0.75, "too wet: 75% (needs 40–70%)")),
        (None, (0.5, "no soil data")),
    ],
)
def test_a07_moisture_fit(avg, want):
    assert m.moisture_fit(avg, 40.0, 70.0) == want


@pytest.mark.task("A07")
def test_a07_unknown_range():
    assert m.moisture_fit(50.0, None, 70.0) == (0.5, "no soil data")
    assert m.moisture_fit(50.0, 40.0, None) == (0.5, "no soil data")


# -- A08 score_spot
@pytest.mark.task("A08")
def test_a08_score_spot():
    crop = Crop(name="Carrot", sun="full", moisture_min_pct=35.0, moisture_max_pct=65.0)
    assert m.score_spot(crop, 8, 50.0, False) == (
        100,
        ["8 h sun (needs 6+)", "soil 50% suits it (35–65%)", "rotation ok"],
    )
    score, why = m.score_spot(crop, 3, 25.0, True)
    assert score == round(100 * (0.4 * 0.5 + 0.4 * 0.5 + 0.2 * 0.0)) == 40
    assert why == [
        "only 3 h sun (needs 6+)",
        "too dry: 25% (needs 35–65%)",
        "same family here in the last 3 years",
    ]
    assert m.score_spot(crop, None, None, False) == (
        60,
        ["sun hours unknown", "no soil data", "rotation ok"],
    )


# -- A09 best_spots
@pytest.mark.task("A09")
def test_a09_best_spots():
    c = [
        {"name": n, "score": s, "reasons": []}
        for n, s in (("Bed C", 70), ("bed b", 90), ("Bed A", 70), ("Bed D", 20), ("Bed E", 90))
    ]
    assert [x["name"] for x in m.best_spots(c)] == ["bed b", "Bed E", "Bed A"]
    assert [x["name"] for x in m.best_spots(c, 5)] == ["bed b", "Bed E", "Bed A", "Bed C", "Bed D"]
    assert m.best_spots([]) == []


# -- A10 tokenize
@pytest.mark.task("A10")
def test_a10_tokenize():
    assert adv.tokenize("When should I sow LEEKS, and how far apart? Leeks!") == [
        "sow",
        "leeks",
        "far",
        "apart",
        "leeks",
    ]
    assert adv.tokenize("Wanneer moet ik prei zaaien? 20 cm") == ["prei", "zaaien"]
    assert adv.tokenize("Pompoen (Cucurbita maxima): 150cm") == [
        "pompoen",
        "cucurbita",
        "maxima",
        "150cm",
    ]
    assert adv.tokenize("") == []


# -- A11 rank_sources
def src(i, title, body="", tags=""):
    return Source(id=i, title=title, body=body, tags=tags, kind="guide")


@pytest.mark.task("A11")
def test_a11_rank_sources():
    s1 = src(1, "Growing leeks", "Sow leeks in March. Leeks need 15 cm.", "leek, sowing")
    s2 = src(2, "Carrots", "Sow carrots thinly. Leeks next to carrots deter carrot fly.", "carrot")
    s3 = src(3, "Tomatoes", "Tomatoes need warmth.", "tomato")
    s4 = src(4, "Leeks and onions", "Alliums.", "leeks")
    # s1: leeks 3 (title) + 2 (body), sow 1 (body) = 6; s4: leeks 3 (title) + 2 (tags) = 5; s2: sow 1 + leeks 1 = 2
    assert [s.id for s in adv.rank_sources([s3, s4, s2, s1], "When do I sow leeks?")] == [1, 4, 2]
    assert [s.id for s in adv.rank_sources([s1, s2, s3, s4], "sow leeks", k=2)] == [1, 4]
    assert adv.rank_sources([s1, s2], "pumpkins") == []
    assert adv.rank_sources([s1], "the and how") == []


# -- A12 snippet
@pytest.mark.task("A12")
def test_a12_snippet():
    body = "a" * 300 + "LEEKS go here" + "b" * 300
    s = adv.snippet(body, {"leeks"}, width=100)
    assert s == "…" + body[275:375] + "…"
    assert "LEEKS" in s
    assert adv.snippet("short text", {"x"}, width=100) == "short text"
    assert adv.snippet("c" * 200, {"zz"}, width=50) == "c" * 50
    assert (
        adv.snippet("leeks " + "d" * 200, {"leeks"}, width=50) == ("leeks " + "d" * 200)[:50] + "…"
    )


# -- A13 validate_source
GOOD = {
    "title": " Leeks guide ",
    "kind": "guide",
    "url": "https://example.org/leeks",
    "publisher": "RHS",
    "body": "Sow in March.",
    "tags": " Leek, SOWING ,, spacing ",
}


@pytest.mark.task("A13")
def test_a13_good():
    values, errors = adv.validate_source(GOOD)
    assert errors == {}
    assert values == {
        "title": "Leeks guide",
        "kind": "guide",
        "url": "https://example.org/leeks",
        "publisher": "RHS",
        "body": "Sow in March.",
        "tags": "leek, sowing, spacing",
    }
    values, errors = adv.validate_source(GOOD | {"url": "", "publisher": " ", "tags": ""})
    assert errors == {} and (values["url"], values["publisher"], values["tags"]) == (None, None, "")


@pytest.mark.task("A13")
@pytest.mark.parametrize(
    "change, field, msg",
    [
        ({"title": ""}, "title", "Give it a title (at most 200 characters)"),
        ({"title": "t" * 201}, "title", "Give it a title (at most 200 characters)"),
        ({"kind": "rumour"}, "kind", "Pick a kind"),
        ({"url": "example.org"}, "url", "Use a full link (https://…)"),
        ({"url": "javascript:alert(1)"}, "url", "Use a full link (https://…)"),
        ({"url": "https://" + "x" * 500}, "url", "Use a full link (https://…)"),
        ({"publisher": "p" * 121}, "publisher", "At most 120 characters"),
        ({"body": "  "}, "body", "Paste the text the advisor may use (at most 20000 characters)"),
        (
            {"body": "b" * 20001},
            "body",
            "Paste the text the advisor may use (at most 20000 characters)",
        ),
        ({"tags": ",".join(["tag"] * 60)}, "tags", "At most 200 characters"),
    ],
)
def test_a13_bad(change, field, msg):
    values, errors = adv.validate_source(GOOD | change)
    assert errors == {field: msg}
    assert set(values) == set(adv.FORM_FIELDS)
