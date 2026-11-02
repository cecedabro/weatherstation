"""Pure formatting helpers registered as Jinja filters on the shared environment.

SPEC 10.11 – Times on pages are shown in Europe/Amsterdam with a relative age
("5 min ago"); wind direction is shown as a compass point next to degrees.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment

_CWIND = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def compass(deg: float) -> str:
    """Return the 16-point compass name for *deg* (0–360).

    0 and 360 map to N.  Each sector is 22.5 degrees wide, centred on the
    named direction.
    """
    return _CWIND[int((deg + 11.25) % 360 / 22.5) % 16]


def local_time(dt: datetime, fmt: str = "%H:%M, %-d %b") -> str:
    """Format *dt* as a local Europe/Amsterdam string like ``14:05, 2 Nov``."""
    amster = ZoneInfo("Europe/Amsterdam")
    local = dt.astimezone(amster)
    return local.strftime(fmt)


def ago(dt: datetime, now: datetime | None = None) -> str:
    """Return a human-friendly age string for *dt* relative to *now*.

    Examples: ``just now`` (< 1 min), ``5 min ago``, ``3 h ago``, ``2 days ago``.

    When *now* is ``None`` the current time is used (for template rendering).
    """
    if now is None:
        now = datetime.now(UTC)
    diff = now - dt
    total_seconds = int(diff.total_seconds())
    if total_seconds < 60:
        return "just now"
    minutes = total_seconds // 60
    if minutes < 120:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} h ago"
    days = hours // 24
    return f"{days} days ago"


def _register_filters(env: Environment) -> None:
    """Register :func:`compass`, :func:`local_time`, :func:`ago` as Jinja filters."""
    env.globals["ago"] = ago  # also available in templates directly
    env.filters["compass"] = compass
    env.filters["local_time"] = local_time
    env.filters["ago"] = ago
