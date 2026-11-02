"""Tests for static asset serving (T21).

SPEC 10.x: The site serves its own static assets (HTMX, uPlot) from
the /static/ mount rather than relying on CDNs.
"""

from __future__ import annotations


def test_htmx_serves_200_js(client) -> None:
    """htmx.min.js is served at /static/vendor/htmx.min.js with JS content type."""
    resp = client.get("/static/vendor/htmx.min.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("Content-Type", "").lower()


def test_uplot_iife_serves_200_js(client) -> None:
    """uPlot.iife.min.js is served at /static/vendor/uPlot.iife.min.js with JS content type."""
    resp = client.get("/static/vendor/uPlot.iife.min.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("Content-Type", "").lower()


def test_uplot_css_serves_200_css(client) -> None:
    """uPlot.min.css is served at /static/vendor/uPlot.min.css with CSS content type."""
    resp = client.get("/static/vendor/uPlot.min.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("Content-Type", "").lower()


def test_home_references_htmx(client) -> None:
    """The home page includes a reference to htmx in its HTML."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "htmx.min.js" in resp.text
