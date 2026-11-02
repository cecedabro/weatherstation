"""Tests for the chart section on GET / (T19).

SPEC 5.2: The chart section has a container and day/week/month selector links
carrying the ``from``, ``to`` and ``step`` query parameters for
``/api/v1/series`` (day→5m, week→1h, month→1d).
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs

from app.web import _SELECTOR_HOURS, _SELECTORS


def test_chart_section_exists(client) -> None:
    """The chart container and section are present."""
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="chart-section"' in r.text
    assert 'id="chart-container"' in r.text


def test_chart_selector_links(client) -> None:
    """Three selector links (24h / 7d / 30d) are present."""
    r = client.get("/")
    text = r.text
    for sel in _SELECTORS:
        assert 'class="btn-glossy chart-btn"' in text
        assert sel["label"] in text


def test_chart_selector_query_values(client) -> None:
    """Each selector link carries the correct from/to/step parameters."""
    r = client.get("/")
    assert r.status_code == 200

    # Extract href values from chart buttons
    import re

    hrefs = re.findall(
        r'href="/api/v1/series\?([^"]+)"',
        r.text,
    )
    assert len(hrefs) == 3, "Expected 3 selector links"

    for href, expected in zip(hrefs, _SELECTORS, strict=False):
        params = parse_qs(href)
        step = params.get("step", [None])[0]
        from_str = params.get("from", [None])[0]
        to_str = params.get("to", [None])[0]

        assert step == expected["step"], f"Expected step={expected['step']}"
        assert from_str is not None
        assert to_str is not None

        from_dt = datetime.fromisoformat(from_str)
        to_dt = datetime.fromisoformat(to_str)

        hours = _SELECTOR_HOURS[expected["label"]]
        diff = (to_dt - from_dt).total_seconds() / 3600
        assert diff == hours, f"Expected {hours}h window, got {diff}h"
