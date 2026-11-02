"""Page metadata tests (SPEC 10.12 — T40).

Verifies that:
- Every public page sets a unique <title>.
- Every public page has a <meta name="description"> with non-empty content.
- The SVG favicon at /static/favicon.svg serves with HTTP 200.
- base.html has <main> and <footer> landmarks.
"""

from fastapi.testclient import TestClient

from app.main import app

PAGES = ["/", "/weather", "/soil", "/history", "/about"]


def _get_title(text):
    """Extract <title> text from HTML response."""
    start = text.find("<title>")
    if start == -1:
        return None
    start += len("<title>")
    end = text.find("</title>", start)
    if end == -1:
        return None
    return text[start:end].strip()


def _get_meta_description(text):
    """Extract <meta name="description"> content from HTML response."""
    import re

    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1)


def test_favicon_serves():
    """The SVG favicon must be served at /static/favicon.svg with status 200."""
    client = TestClient(app)
    resp = client.get("/static/favicon.svg")
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")
    assert "<svg" in resp.text


def test_titles_unique(db):
    """Each public page must have a unique <title> across all tested pages."""
    client = TestClient(app)
    titles = []
    for url in PAGES:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"
        title = _get_title(resp.text)
        assert title is not None, f"Missing <title> on {url}"
        titles.append(title)
    assert len(titles) == len(set(titles)), f"Duplicate titles found: {titles}"


def test_meta_description_present(db):
    """Every public page must have a <meta name="description"> with content."""
    client = TestClient(app)
    for url in PAGES:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"
        desc = _get_meta_description(resp.text)
        assert desc is not None, f"Missing <meta name='description'> on {url}"
        assert len(desc.strip()) > 0, f"<meta name='description'> on {url} has empty content"


def test_base_template_has_landmarks(db):
    """base.html must contain <main> and <footer> landmarks."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<main" in resp.text
    assert "<footer" in resp.text
