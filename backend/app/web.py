"""HTML routes: GET / (home page)."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.db import SessionLocal
from app.readapi import _current_readings

router = APIRouter()

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _BASE_DIR / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


@router.get("/")
async def index() -> HTMLResponse:
    """Render the home page with current conditions per SPEC 5.1."""
    db = SessionLocal()
    try:
        all_nodes = _current_readings(db)
        weather_nodes = [n for n in all_nodes if n["node_type"] == "weather"]
        soil_nodes = [n for n in all_nodes if n["node_type"] == "soil"]
        template = _jinja_env.get_template("home.html")
        html = template.render(
            weather_nodes=weather_nodes,
            soil_nodes=soil_nodes,
        )
        return HTMLResponse(content=html)
    finally:
        db.close()
