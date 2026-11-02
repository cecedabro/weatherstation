"""Tests for styled 404 page (SPEC 10.9).

VERIFIES SPEC 10.9: Unknown URLs return a styled HTML 404 page with a link home;
/api/ paths keep JSON errors.
"""


def test_unknown_non_api_path_returns_html_404(client):
    """GET /unknown returns HTML 404 with status 404."""
    resp = client.get("/unknown-path")
    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]


def test_unknown_non_api_404_has_nav(client):
    """404 HTML page contains the shared navigation."""
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert '<nav aria-label="Main"' in resp.text


def test_unknown_non_api_404_has_friendly_message(client):
    """404 HTML page contains a friendly message."""
    resp = client.get("/foo/bar/baz")
    assert resp.status_code == 404
    assert "Page Not Found" in resp.text
    assert "couldn't find" in resp.text.lower() or "not found" in resp.text.lower()


def test_unknown_non_api_404_has_link_home(client):
    """404 HTML page contains a link back to home."""
    resp = client.get("/some/random/path")
    assert resp.status_code == 404
    assert 'href="/"' in resp.text


def test_unknown_non_api_404_extends_base(client):
    """404 HTML page extends base (has header and footer)."""
    resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert 'class="header"' in resp.text
    assert 'class="footer"' in resp.text
    assert "<main" in resp.text


def test_api_unknown_path_returns_json_404(client):
    """GET /api/v1/missing returns JSON 404 with status 404."""
    resp = client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]


def test_api_unknown_404_has_detail(client):
    """JSON 404 for /api/ paths includes a detail field."""
    resp = client.get("/api/v1/whatever")
    # This hits a known route pattern but wrong method/path, so may return 405
    # Let's use a path that truly doesn't match any route
    resp = client.get("/api/unknown/deep/path")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body


def test_api_prefix_anything_json(client):
    """Any path under /api/ returns JSON 404."""
    resp = client.get("/api/garden/foo")
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]
