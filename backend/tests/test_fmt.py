"""Tests for pure formatting helpers in app/fmt.py (T24).

SPEC 10.11 – Times on pages are shown in Europe/Amsterdam with a relative age
("5 min ago"); wind direction is shown as a compass point next to degrees.
"""

from datetime import UTC, datetime, timedelta

from jinja2 import BaseLoader, Environment

from app.fmt import _register_filters, ago, compass, local_time

# ---------------------------------------------------------------------------
# compass
# ---------------------------------------------------------------------------


def test_compass_zero_is_n():
    """0 degrees maps to N."""
    assert compass(0) == "N"


def test_compass_360_is_n():
    """360 degrees maps to N (same as 0)."""
    assert compass(360) == "N"


def test_compass_12_is_nne():
    """12 degrees maps to NNE (centred on 22.5, within 11.25–33.75)."""
    assert compass(12) == "NNE"


def test_compass_225_is_sw():
    """225 degrees maps to SW (centred exactly on 225)."""
    assert compass(225) == "SW"


def test_compass_cardinal_points():
    """Cardinal directions map correctly."""
    assert compass(90) == "E"
    assert compass(180) == "S"
    assert compass(270) == "W"


def test_compass_intercardinal_points():
    """Intercardinal (ordinal) directions map correctly."""
    assert compass(45) == "NE"
    assert compass(135) == "SE"
    assert compass(315) == "NW"


def test_compass_all_16_points():
    """Each of the 16 compass points is reachable from some input."""
    known = {
        0: "N",
        22.5: "NNE",
        45: "NE",
        67.5: "ENE",
        90: "E",
        112.5: "ESE",
        135: "SE",
        157.5: "SSE",
        180: "S",
        202.5: "SSW",
        225: "SW",
        247.5: "WSW",
        270: "W",
        292.5: "WNW",
        315: "NW",
        337.5: "NNW",
    }
    for deg, expected in known.items():
        assert compass(deg) == expected, f"{deg}° should be {expected}"


def test_compass_boundaries():
    """Edge values at sector boundaries map to the expected direction."""
    # Just past N→NNE boundary (33.75)
    assert compass(33.76) == "NE"
    # Just at NE→ENE boundary (67.5)
    assert compass(67.5) == "ENE"
    # 359 is very close to N
    assert compass(359) == "N"


# ---------------------------------------------------------------------------
# local_time
# ---------------------------------------------------------------------------


def test_local_time_winter_offset():
    """Winter date uses CET (UTC+1) offset for Europe/Amsterdam."""
    dt = datetime(2025, 1, 15, 13, 5, 0)  # 13:05 UTC
    result = local_time(dt)
    assert result == "14:05, 15 Jan"


def test_local_time_summer_offset():
    """Summer date uses CEST (UTC+2) offset for Europe/Amsterdam."""
    dt = datetime(2025, 7, 15, 13, 5, 0)  # 13:05 UTC
    result = local_time(dt)
    assert result == "15:05, 15 Jul"


def test_local_time_leads_zero_hour():
    """Crosses midnight correctly."""
    dt = datetime(2025, 1, 15, 23, 10, 0)  # 23:10 UTC
    result = local_time(dt)
    assert result == "00:10, 16 Jan"


# ---------------------------------------------------------------------------
# ago
# ---------------------------------------------------------------------------


def test_ago_59_seconds():
    """59 seconds ago → 'just now'."""
    now = datetime.now(UTC)
    dt = now - timedelta(seconds=59)
    assert ago(dt, now) == "just now"


def test_ago_61_minutes():
    """61 minutes ago → '61 min ago'."""
    now = datetime.now(UTC)
    dt = now - timedelta(minutes=61)
    assert ago(dt, now) == "61 min ago"


def test_ago_25_hours():
    """25 hours ago → '25 h ago'."""
    now = datetime.now(UTC)
    dt = now - timedelta(hours=25)
    assert ago(dt, now) == "25 h ago"


def test_ago_zero_seconds():
    """Exactly now → 'just now'."""
    now = datetime.now(UTC)
    assert ago(now, now) == "just now"


def test_ago_2_days():
    """Exactly 2 days ago → '2 days ago'."""
    now = datetime.now(UTC)
    dt = now - timedelta(days=2)
    assert ago(dt, now) == "2 days ago"


def test_ago_47_hours():
    """47 hours → still under 48 h, so 'hours ago'."""
    now = datetime.now(UTC)
    dt = now - timedelta(hours=47)
    assert ago(dt, now) == "47 h ago"


def test_ago_48_hours():
    """48 hours → switches to days."""
    now = datetime.now(UTC)
    dt = now - timedelta(hours=48)
    assert ago(dt, now) == "2 days ago"


# ---------------------------------------------------------------------------
# Jinja filter registration
# ---------------------------------------------------------------------------


def test_filters_registered_on_env():
    """Compass, local_time, and ago are available as Jinja2 filters."""
    env = Environment(loader=BaseLoader())
    _register_filters(env)
    assert "compass" in env.filters
    assert "local_time" in env.filters
    assert "ago" in env.filters
