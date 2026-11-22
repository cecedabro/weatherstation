"""Sensor pages and old-page redirects per SPEC 11.7."""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/weather")
async def redirect_weather() -> RedirectResponse:
    """SPEC 11.7: /weather → /sensors?cat=air (301)."""
    return RedirectResponse("/sensors?cat=air", status_code=301)


@router.get("/history")
async def redirect_history() -> RedirectResponse:
    """SPEC 11.7: /history → /sensors?cat=air&range=30d (301)."""
    return RedirectResponse("/sensors?cat=air&range=30d", status_code=301)


@router.get("/soil")
async def redirect_soil() -> RedirectResponse:
    """SPEC 11.7: /soil → /sensors?cat=soil (301)."""
    return RedirectResponse("/sensors?cat=soil", status_code=301)


@router.get("/soil/{node_id}")
async def redirect_soil_node(node_id: str) -> RedirectResponse:
    """SPEC 11.7: /soil/{node_id} → /sensors?cat=soil&node={node_id} (301)."""
    return RedirectResponse(f"/sensors?cat=soil&node={node_id}", status_code=301)
