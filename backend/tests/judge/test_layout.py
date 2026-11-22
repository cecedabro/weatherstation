"""Shared layout (SPEC 10.1, 10.12, 11.0): nav, landmarks, titles, theme assets, styleguide."""

import re

import pytest

PUBLIC = ["/", "/sensors", "/about", "/styleguide", "/login"]


@pytest.mark.parametrize("path", PUBLIC)
def test_public_pages_render_with_landmarks(client, path):
    r = client.get(path)
    assert r.status_code == 200
    t = r.text
    for tag in ("<nav", "<main", "<footer", "<header"):
        assert tag in t
    assert re.search(r"<title>[^<]+</title>", t)
    assert '<meta name="description"' in t
    assert "/static/css/tokens.css" in t and "/static/css/components.css" in t
    assert '<link rel="icon"' in t


def test_nav_marks_current_page(client):
    t = client.get("/about").text
    assert 'href="/sensors"' in t
    assert t.count('aria-current="page"') == 0  # about is not a nav item
    t = client.get("/sensors").text
    assert re.search(r'<a href="/sensors" aria-current="page">', t)


def test_private_nav_items_hidden_when_signed_out(client):
    t = client.get("/").text
    for href in ("/garden", "/seeds", "/tasks", "/species"):
        assert f'<a href="{href}"' not in t
    assert "/login?next=" in t


def test_no_inline_scripts(client):
    for path in PUBLIC:
        t = client.get(path).text
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", t), path


def test_styleguide_shows_every_macro(client):
    from pathlib import Path

    ui = (Path(__file__).resolve().parents[2] / "app" / "templates" / "ui.html").read_text()
    macros = set(re.findall(r"{% macro (\w+)\(", ui))
    from app.styleguide import EXAMPLES

    shown = "".join(code for _, _, code in EXAMPLES)
    missing = [m for m in macros if f"ui.{m}(" not in shown]
    assert not missing, f"add a /styleguide example for: {missing}"
    assert client.get("/styleguide").status_code == 200


def test_unknown_page_is_styled_404(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "Page not found" in r.text and 'href="/"' in r.text
    assert client.get("/api/v1/nope").json() == {"detail": "Not found"}
