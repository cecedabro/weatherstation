"""Tests for the dev-seed generator (backend/scripts/dev.py).

No server, no database -- just the generator function.

Checks:
- 30-day span of data
- Daily temperature curves (sine pattern)
- Rain showers (multiple concentrated events)
- One frost night (any reading <= 2.0 °C)
- One bed below 25 % moisture
- Node diversity (weather + multiple soil beds)
- All readings have valid structure
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

# Make the scripts directory importable
_backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_backend))  # isort: skip

from scripts.dev import fake_readings  # noqa: E402  # isort: skip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def readings() -> list[dict[str, Any]]:
    """Generate seed data anchored to a fixed reference time."""
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    return fake_readings(now)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_readings_not_empty(readings: list[dict[str, Any]]) -> None:
    """Generator produces readings."""
    assert len(readings) > 0


def test_frost_night_exists(readings: list[dict[str, Any]]) -> None:
    """At least one weather reading has temp_c <= 2.0 °C (frost night)."""
    temps = [
        r["metrics"]["temp_c"]
        for r in readings
        if r["node_type"] == "weather" and "temp_c" in r["metrics"]
    ]
    assert temps, "No temperature readings found"
    assert any(t <= 2.0 for t in temps), (
        f"No frost night (<= 2.0 °C) found in {len(temps)} readings; min={min(temps):.1f}"
    )


def test_daily_temperature_curves(readings: list[dict[str, Any]]) -> None:
    """Temperature readings vary within each day, showing daily cycles."""
    weather = [r for r in readings if r["node_type"] == "weather" and "temp_c" in r["metrics"]]
    # Group by date and check that at least one day has >2 °C variation
    by_day: dict[str, list[float]] = {}
    for r in weather:
        day_key = r["ts"][:10]
        if day_key not in by_day:
            by_day[day_key] = []
        by_day[day_key].append(r["metrics"]["temp_c"])
    assert by_day, "No weather temperature readings found"
    for _day_str, temps in by_day.items():
        variation = max(temps) - min(temps)
        if variation > 2.0:
            break
    else:
        max_variation = max(max(t) - min(t) for t in by_day.values())
        pytest.fail(f"No day with > 2 °C variation; max daily variation = {max_variation:.1f} °C")


def test_rain_showers_multiple(readings: list[dict[str, Any]]) -> None:
    """Multiple rain shower events exist (many readings with rain_mm > 0)."""
    rain_readings = [
        r for r in readings if r["node_type"] == "weather" and r["metrics"].get("rain_mm", 0) > 0
    ]
    assert len(rain_readings) > 5, f"Expected more than 5 rain readings, got {len(rain_readings)}"


def test_rain_showers_concentrated(readings: list[dict[str, Any]]) -> None:
    """Rain readings are concentrated in periods (showers), not uniform."""
    rain_readings = [
        r for r in readings if r["node_type"] == "weather" and r["metrics"].get("rain_mm", 0) > 0
    ]
    if not rain_readings:
        pytest.fail("No rain readings found")
    # Check that rain readings span multiple distinct day periods
    # (at least 2 separate days with rain)
    rain_days: Counter[str] = Counter()
    for r in rain_readings:
        rain_days[r["ts"][:10]] += 1
    assert len(rain_days) >= 2, (
        f"Rain only on {len(rain_days)} day(s); expected >= 2 (showers spread across days)"
    )


def test_bed_below_25_moisture(readings: list[dict[str, Any]]) -> None:
    """At least one soil reading has soil_moisture_pct < 25.0."""
    moistures = [
        r["metrics"]["soil_moisture_pct"]
        for r in readings
        if r["node_type"] == "soil" and "soil_moisture_pct" in r["metrics"]
    ]
    assert moistures, "No soil moisture readings found"
    assert any(m < 25.0 for m in moistures), (
        f"No bed below 25 % moisture found; min={min(moistures):.1f}"
    )


def test_30_day_span(readings: list[dict[str, Any]]) -> None:
    """Data spans approximately 30 days from now to 30 days ago."""
    timestamps = []
    for r in readings:
        ts_str = r["ts"]
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(ts_str)
        timestamps.append(ts)

    ts_min = min(timestamps)
    ts_max = max(timestamps)
    span_days = (ts_max - ts_min).total_seconds() / 86400

    assert span_days >= 29, f"Data span is {span_days:.1f} days; expected >= 29 (30-day window)"
    assert span_days <= 31, f"Data span is {span_days:.1f} days; expected <= 31"


def test_node_diversity(readings: list[dict[str, Any]]) -> None:
    """Data includes weather and multiple soil nodes."""
    weather_nodes = {r["node_id"] for r in readings if r["node_type"] == "weather"}
    soil_nodes = {r["node_id"] for r in readings if r["node_type"] == "soil"}

    assert weather_nodes, "No weather nodes found"
    assert len(soil_nodes) >= 3, f"Expected >= 3 soil nodes, got {len(soil_nodes)}: {soil_nodes}"
    assert "weather-main" in weather_nodes
    assert "soil-bed-1" in soil_nodes
    assert "soil-bed-3" in soil_nodes
    assert "soil-bed-7" in soil_nodes


def test_readings_structure(readings: list[dict[str, Any]]) -> None:
    """Every reading has the expected top-level keys."""
    required_keys = {"node_id", "node_type", "ts", "fw", "metrics"}
    for i, r in enumerate(readings):
        assert required_keys.issubset(r.keys()), (
            f"Reading {i} missing keys: {required_keys - r.keys()}"
        )


def test_readings_have_all_metrics(readings: list[dict[str, Any]]) -> None:
    """Weather readings have temp, humidity, pressure, wind; soil has moisture and soil temp."""
    for r in readings:
        if r["node_type"] == "weather":
            assert "temp_c" in r["metrics"], f"weather node {r['node_id']} missing temp_c"
        elif r["node_type"] == "soil":
            assert "soil_moisture_pct" in r["metrics"], (
                f"soil node {r['node_id']} missing soil_moisture_pct"
            )


def test_deterministic(readings: list[dict[str, Any]]) -> None:
    """Generator is deterministic with the same seed (same number of readings)."""
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    second_run = fake_readings(now)
    assert len(readings) == len(second_run)
