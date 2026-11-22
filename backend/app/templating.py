"""Shared Jinja environment and the page renderer. Human-owned (docs/design.md).

Every HTML page goes through :func:`render`, which adds the navigation, the signed-in user and the
current path, so templates extending ``base.html`` always have what the layout needs.
"""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.auth import current_user
from app.fmt import _register_filters

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# (key, href, label, icon, private). Private pages need a signed-in user (app.auth.require_user).
NAV: list[tuple[str, str, str, str, bool]] = [
    ("home", "/", "Overview", "🏡", False),
    ("sensors", "/sensors", "Sensors", "📈", False),
    ("garden", "/garden", "Garden", "🗺️", True),
    ("seeds", "/seeds", "Seeds", "🌱", True),
    ("growth", "/growth", "Growth", "🌤️", True),
    ("tasks", "/tasks", "Tasks", "✅", True),
    ("species", "/species", "Species", "🐞", True),
]

env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
_register_filters(env)
env.globals["nav"] = NAV
env.filters["moisture_series"] = lambda node_id: (node_id, "soil_moisture_pct", node_id)


def render(request: Request, name: str, status_code: int = 200, **ctx: Any) -> HTMLResponse:
    """Render template *name* with the layout context (nav, user, path) plus *ctx*."""
    ctx.setdefault("user", current_user(request))
    ctx.setdefault("path", request.url.path)
    ctx.setdefault("active", "")
    return HTMLResponse(env.get_template(name).render(**ctx), status_code=status_code)
