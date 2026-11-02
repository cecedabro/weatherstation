"""Tests for shared navigation (SPEC 10.1).

VERIFIES SPEC 10.1: Every public page shares one layout with a navigation bar
linking Home `/`, Weather `/weather`, Soil `/soil`, History `/history` and
About `/about`; the current page's link has `aria-current="page"`.
"""

NAV_LINKS = [
    ("/", "Home"),
    ("/weather", "Weather"),
    ("/soil", "Soil"),
    ("/history", "History"),
    ("/about", "About"),
]


def test_nav_contains_all_links(client):
    """GET / renders a <nav> with all 5 links."""
    resp = client.get("/")
    assert resp.status_code == 200
    nav = resp.text
    assert '<nav aria-label="Main"' in nav
    for href, label in NAV_LINKS:
        assert f'href="{href}"' in nav, f"Missing link to {href}"
        assert label in nav, f"Missing label '{label}'"


def test_nav_home_is_current(client):
    """On GET /, only the Home link has aria-current="page"."""
    resp = client.get("/")
    assert resp.status_code == 200
    # Home must be current
    assert 'href="/" aria-current="page"' in resp.text
    # Other links must NOT be current
    for href, _label in NAV_LINKS[1:]:
        assert f'href="{href}" aria-current="page"' not in resp.text


def test_nav_weather_is_current(client):
    """On GET /weather, only the Weather link has aria-current="page"."""
    resp = client.get("/weather")
    assert resp.status_code == 200
    assert 'href="/weather" aria-current="page"' in resp.text
    for href, _ in NAV_LINKS:
        if href != "/weather":
            assert f'href="{href}" aria-current="page"' not in resp.text


def test_nav_soil_is_current(client):
    """On GET /soil, only the Soil link has aria-current="page"."""
    resp = client.get("/soil")
    assert resp.status_code == 200
    assert 'href="/soil" aria-current="page"' in resp.text
    for href, _ in NAV_LINKS:
        if href != "/soil":
            assert f'href="{href}" aria-current="page"' not in resp.text


def test_nav_history_is_current(client):
    """On GET /history, only the History link has aria-current="page"."""
    resp = client.get("/history")
    assert resp.status_code == 200
    assert 'href="/history" aria-current="page"' in resp.text
    for href, _ in NAV_LINKS:
        if href != "/history":
            assert f'href="{href}" aria-current="page"' not in resp.text


def test_nav_about_is_current(client):
    """On GET /about, only the About link has aria-current="page"."""
    resp = client.get("/about")
    assert resp.status_code == 200
    assert 'href="/about" aria-current="page"' in resp.text
    for href, _ in NAV_LINKS:
        if href != "/about":
            assert f'href="{href}" aria-current="page"' not in resp.text


def test_nav_wrap_at_360px(client):
    """Nav uses flex-wrap so it wraps without horizontal scroll at 360 px.

    We verify the CSS contains `flex-wrap: wrap` for the nav element.
    """
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    assert ".nav" in css
    assert "flex-wrap: wrap" in css
