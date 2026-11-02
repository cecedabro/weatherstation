"""Security headers tests (SPEC 10.15 — T42).

Verifies that:
- Every response sends X-Content-Type-Options: nosniff.
- Every response sends Referrer-Policy: same-origin.
- Every response sends X-Frame-Options: DENY.
- Every response sends Content-Security-Policy with the approved directive.
- /static/ responses also get Cache-Control: public, max-age=3600.
- Templates do not contain inline <script> code blocks.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

_STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static"
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

_CSP_VALUE = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"

_SECURE_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "x-frame-options": "DENY",
}

_SECURE_PAGE_URLS = [
    "/",
    "/weather",
    "/soil",
    "/history",
    "/about",
]

_SECURE_API_URLS = [
    "/healthz",
    "/api/v1/nodes",
    "/api/v1/current",
]

_SECURE_STATIC_URLS = [
    "/static/style.css",
    "/static/vendor/htmx.min.js",
    "/static/vendor/uPlot.iife.min.js",
    "/static/favicon.svg",
]


def _check_security_headers(resp, url):
    """Assert common security headers on a response. Returns headers dict for chaining."""
    headers_lower = {k.lower(): v for k, v in resp.headers.items()}
    for header, expected in _SECURE_HEADERS.items():
        assert headers_lower.get(header) == expected, (
            f"{url} missing {header}: expected {expected!r}, got {headers_lower.get(header)!r}"
        )
    actual_csp = headers_lower.get("content-security-policy")
    assert actual_csp == _CSP_VALUE, (
        f"{url} CSP mismatch: expected {_CSP_VALUE!r}, got {actual_csp!r}"
    )
    return headers_lower


def test_healthz_has_security_headers(client) -> None:
    """GET /healthz must carry all security headers."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    _check_security_headers(resp, "/healthz")


def test_api_routes_have_security_headers(client) -> None:
    """Every API route must carry all security headers."""
    client = TestClient(app)
    for url in _SECURE_API_URLS:
        resp = client.get(url)
        assert resp.status_code in (200, 401, 404), f"{url} returned {resp.status_code}"
        _check_security_headers(resp, url)


def test_public_pages_have_security_headers(client) -> None:
    """Every public page must carry all security headers."""
    client = TestClient(app)
    for url in _SECURE_PAGE_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"
        _check_security_headers(resp, url)


def test_static_urls_have_security_headers(client) -> None:
    """Static file responses must carry all security headers."""
    for url in _SECURE_STATIC_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"
        _check_security_headers(resp, url)


def test_static_has_cache_control(client) -> None:
    """/static/ responses must include Cache-Control: public, max-age=3600."""
    for url in _SECURE_STATIC_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"
        cache_control = resp.headers.get("Cache-Control", "")
        assert "public" in cache_control, f"{url} Cache-Control missing 'public': {cache_control!r}"
        assert "max-age=3600" in cache_control, (
            f"{url} Cache-Control missing 'max-age=3600': {cache_control!r}"
        )


def test_non_static_no_cache_control(client) -> None:
    """Non-static routes must NOT get Cache-Control from the static middleware."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    # The middleware only adds Cache-Control for /static/ paths
    assert "Cache-Control" not in resp.headers or "max-age=3600" not in resp.headers.get(
        "Cache-Control", ""
    ), "/healthz should not have Cache-Control: public, max-age=3600"


def test_not_found_page_has_security_headers(client) -> None:
    """404 HTML responses must carry security headers."""
    resp = client.get("/nonexistent-page-xyz")
    assert resp.status_code == 404
    _check_security_headers(resp, "/nonexistent-page-xyz")
    assert "<html" in resp.text or "<!DOCTYPE" in resp.text, (
        "Non-API 404 should return HTML, not JSON"
    )


def test_not_found_api_has_security_headers(client) -> None:
    """404 API responses must carry security headers and return JSON."""
    resp = client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    _check_security_headers(resp, "/api/v1/nonexistent")
    assert "application/json" in resp.headers.get("Content-Type", ""), "API 404 should return JSON"


def test_no_inline_scripts_in_templates() -> None:
    """Templates must not contain inline <script> code blocks."""
    template_files = glob.glob(str(_TEMPLATE_DIR / "*.html"))
    inline_script_re = re.compile(r"<script\b[^>]*>(?!</script>)(.*?)</script>", re.DOTALL)

    violations = []
    for path in template_files:
        content = Path(path).read_text()
        for match in inline_script_re.finditer(content):
            body = match.group(1).strip()
            # Skip empty scripts or ones that are only whitespace
            if body:
                violations.append(
                    f"{os.path.basename(path)}: contains inline script: {body[:80]}..."
                )

    assert violations == [], (
        "Inline <script> blocks found in templates (SPEC 10.15):\n" + "\n".join(violations)
    )


def test_no_inline_scripts_in_templates_v2() -> None:
    """
    Verify templates have no inline <script> tags by checking that all
    <script> tags use src attributes only (external scripts).
    """
    template_files = glob.glob(str(_TEMPLATE_DIR / "*.html"))
    script_tag_re = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)

    violations = []
    for path in template_files:
        content = Path(path).read_text()
        for match in script_tag_re.finditer(content):
            attrs = match.group(1)
            if "src=" not in attrs:
                violations.append(f"{os.path.basename(path)}: <script> without src attribute")

    assert violations == [], "Scripts without src (inline) found in templates:\n" + "\n".join(
        violations
    )
