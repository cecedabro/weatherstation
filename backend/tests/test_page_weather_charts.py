"""Tests for charts on GET /weather page (T31).

SPEC 10.2 (second half): Each weather metric on /weather has its own chart
container with ``data-chart``, ``data-node``, ``data-metric`` attributes.
A shared day/week/month selector controls all charts.
``rain_mm`` is rendered as bars in chart.js.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.web import _SELECTORS

# ---------------------------------------------------------------------------
# Helpers (mirror test_page_weather.py)
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_batch(
    db,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict,
    battery_v: float | None = None,
    rssi_dbm: int | None = None,
):
    from sqlalchemy import select

    from app.models import Node, Reading

    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
            last_battery_v=battery_v,
            last_rssi_dbm=rssi_dbm,
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    node.last_battery_v = battery_v
    node.last_rssi_dbm = rssi_dbm
    for metric, value in metrics.items():
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id) & (Reading.metric == metric) & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()
    return node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def weather_data_with_all_metrics(db) -> None:
    """A weather node with all six metrics."""
    now = _now()
    _make_batch(
        db,
        "weather-main",
        "weather",
        now,
        {
            "temp_c": 21.5,
            "humidity_pct": 65.0,
            "pressure_hpa": 1013.4,
            "rain_mm": 3.2,
            "wind_speed_ms": 5.2,
            "wind_dir_deg": 164,
        },
        battery_v=3.75,
        rssi_dbm=-53,
    )
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_weather_chart_section_exists(client, weather_data_with_all_metrics) -> None:
    """The chart section is present on /weather."""
    r = client.get("/weather")
    assert r.status_code == 200
    assert 'id="chart-section"' in r.text
    assert "History" in r.text


def test_weather_chart_selector_present(client, weather_data_with_all_metrics) -> None:
    """Chart selector buttons are rendered with correct labels."""
    r = client.get("/weather")
    text = r.text
    for sel in _SELECTORS:
        assert sel["label"] in text
    assert 'class="btn-glossy chart-btn"' in text


def test_weather_chart_containers_per_metric(client, weather_data_with_all_metrics) -> None:
    """One chart container per metric is rendered."""
    r = client.get("/weather")
    text = r.text
    # Check each metric has a data-chart attribute
    metrics = ["temp_c", "humidity_pct", "pressure_hpa", "rain_mm", "wind_speed_ms", "wind_dir_deg"]
    for metric in metrics:
        assert f'data-metric="{metric}"' in text
    assert "data-chart" in text


def test_weather_chart_node_attribute(client, weather_data_with_all_metrics) -> None:
    """Each chart container carries data-node with the correct node ID."""
    r = client.get("/weather")
    assert 'data-node="weather-main"' in r.text


def test_weather_chart_has_data_chart_attr(client, weather_data_with_all_metrics) -> None:
    """All chart containers have the data-chart attribute."""
    r = client.get("/weather")
    assert "data-chart" in r.text


def test_weather_chart_rain_mm_present(client, weather_data_with_all_metrics) -> None:
    """rain_mm chart container is present."""
    r = client.get("/weather")
    assert 'data-metric="rain_mm"' in r.text


def test_weather_chart_selector_query_params(client, weather_data_with_all_metrics) -> None:
    """Selector links carry from/to/step query parameters."""
    r = client.get("/weather")
    text = r.text
    import re

    hrefs = re.findall(r'href="/api/v1/series\?([^"]+)"', text)
    # Should have 3 selector links (one per time range)
    assert len(hrefs) >= 3
    for href in hrefs[:3]:
        from urllib.parse import parse_qs

        params = parse_qs(href)
        assert "from" in params
        assert "to" in params
        assert "step" in params


def test_chart_js_has_bar_path() -> None:
    """chart.js defines a barPath function for rain_mm rendering."""
    import pathlib

    static_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "static"
    with open(static_dir / "chart.js") as f:
        source = f.read()
    assert "barPath" in source
    assert "function barPath" in source


def test_weather_empty_state_no_charts(client) -> None:
    """When no weather nodes exist, no chart section is rendered."""
    r = client.get("/weather")
    assert "No Weather Data" in r.text
    assert "data-chart" not in r.text


def test_weather_page_chart_selectors_context(client, weather_data_with_all_metrics) -> None:
    """chart_selectors is passed to the weather template."""
    r = client.get("/weather")
    # Should have 24h, 7d, 30d buttons
    assert "24h" in r.text
    assert "7d" in r.text
    assert "30d" in r.text
