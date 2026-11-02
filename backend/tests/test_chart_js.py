"""Tests for client-side chart.js (T20).

SPEC 5.2: The home page provides a chart container with data attributes
and loads the uPlot library plus chart.js which fetches from
/api/v1/series.
"""

from __future__ import annotations

from pathlib import Path


def test_page_loads_chart_assets(client) -> None:
    """The home page includes uPlot CSS, uPlot IIFE JS, and chart.js."""
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/static/vendor/uPlot.min.css"' in r.text
    assert 'src="/static/vendor/uPlot.iife.min.js"' in r.text
    assert 'src="/static/chart.js"' in r.text


def test_chart_container_has_data_attributes(client) -> None:
    """The chart container carries data-chart, data-node, and data-metric."""
    r = client.get("/")
    assert r.status_code == 200
    assert "data-chart" in r.text
    assert 'data-metric="temp_c"' in r.text
    assert "data-node=" in r.text


def test_chart_js_mentions_series_api() -> None:
    """chart.js exists and references /api/v1/series."""
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "app",
        "static",
        "chart.js",
    )
    assert os.path.isfile(path), "chart.js must exist in app/static/"
    content = Path(path).read_text()
    assert "/api/v1/series" in content
