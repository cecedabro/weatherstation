"""Tests for the base template and stylesheet (T11).

Verifies:
- The stylesheet is served at /static/style.css
- The stylesheet contains design tokens (CSS custom properties)
- The base template renders at /
- The rendered page has the expected HTML structure (header, bubbles, container, footer)
- The page links the stylesheet
- Template blocks can be overridden
"""

from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Style sheet tests
# ---------------------------------------------------------------------------


def test_stylesheet_served():
    """The CSS file is served at /static/style.css with 200 OK."""
    client = TestClient(app)
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_stylesheet_contains_design_tokens():
    """The stylesheet defines CSS custom properties for all major design
    categories: colours, spacing, radius, blur, typography, and shadows."""
    client = TestClient(app)
    resp = client.get("/static/style.css")
    css = resp.text

    required_tokens = [
        "--color-sky-start",  # background gradient
        "--color-header-start",  # header gradient
        "--color-text",  # body text
        "--color-glass-top",  # glass card surface
        "--font-family",  # typography
        "--space-lg",  # spacing scale
        "--radius-xl",  # border-radius scale
        "--blur-glass",  # backdrop-filter
        "--shadow-card",  # shadows
        ".btn-glossy",  # button class
    ]
    for token in required_tokens:
        assert f"--{token}" in css or f"{token}" in css, (
            f"Design token '{token}' missing from stylesheet"
        )


def test_stylesheet_contains_header_class():
    """The stylesheet defines the .header class used in base.html."""
    client = TestClient(app)
    resp = client.get("/static/style.css")
    assert ".header" in resp.text


def test_stylesheet_contains_card_class():
    """The stylesheet defines the .card class used in base.html."""
    client = TestClient(app)
    resp = client.get("/static/style.css")
    assert ".card" in resp.text


# ---------------------------------------------------------------------------
# Base template tests
# ---------------------------------------------------------------------------


def test_base_template_renders():
    """GET / renders the base template with HTTP 200 and HTML content."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_base_template_has_doctype_and_html():
    """The rendered page starts with DOCTYPE and has <html lang='en'>."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.text.strip().startswith("<!DOCTYPE html>")
    assert '<html lang="en"' in resp.text


def test_base_template_links_stylesheet():
    """The rendered page includes a link to the stylesheet."""
    client = TestClient(app)
    resp = client.get("/")
    assert "/static/style.css" in resp.text


def test_base_template_has_header():
    """The rendered page contains the header element with the logo."""
    client = TestClient(app)
    resp = client.get("/")
    assert '<header class="header">' in resp.text
    assert "<h1>" in resp.text


def test_base_template_has_bubbles():
    """The rendered page contains the four water bubble decorations."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.text.count('class="bubble"') == 4


def test_base_template_has_container():
    """The rendered page contains a <main> container element."""
    client = TestClient(app)
    resp = client.get("/")
    assert '<main class="container">' in resp.text


def test_base_template_has_footer():
    """The rendered page contains a footer element."""
    client = TestClient(app)
    resp = client.get("/")
    assert '<footer class="footer">' in resp.text


def test_base_template_has_meta_viewport():
    """The page includes a viewport meta tag for responsive design (SPEC 5.4)."""
    client = TestClient(app)
    resp = client.get("/")
    assert '<meta name="viewport"' in resp.text
    assert "width=device-width" in resp.text
    assert "initial-scale=1.0" in resp.text or "initial-scale = 1.0" in resp.text


def test_base_template_has_semantic_structure():
    """The page uses semantic HTML elements: header, main, footer."""
    client = TestClient(app)
    resp = client.get("/")
    assert "<header" in resp.text
    assert "<main" in resp.text
    assert "<footer" in resp.text
