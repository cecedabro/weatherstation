"""Application factory and entry point."""

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text
from starlette.responses import Response

from app.config import _DEV_ADMIN_PASSWORD, _DEV_INGEST_TOKEN, Settings

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Weather Station")

    # SECURITY HEADERS per SPEC 10.15
    @application.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add security headers to every response per SPEC 10.15."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        )
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    settings = Settings()

    # Logging setup
    _logger = logging.getLogger()
    _logger.handlers.clear()
    _logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = True

    # Production hardening (SPEC 1.4)
    if settings.APP_ENV == "production":
        if settings.INGEST_TOKEN == _DEV_INGEST_TOKEN:
            raise RuntimeError(
                "APP_ENV=production but INGEST_TOKEN has its development default. "
                "Set a strong INGEST_TOKEN before starting in production."
            )
        if settings.ADMIN_PASSWORD == _DEV_ADMIN_PASSWORD:
            raise RuntimeError(
                "APP_ENV=production but ADMIN_PASSWORD has its development default. "
                "Set a strong ADMIN_PASSWORD before starting in production."
            )

    # Serve static files (CSS, JS, vendor libs)
    application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", response_model=None)
    async def readyz() -> JSONResponse | dict[str, str]:
        from app.db import engine as _engine

        try:
            with _engine.connect() as _conn:
                _conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})

    from app.web import router as web_router

    application.include_router(web_router)

    from app.admin import router as admin_router

    application.include_router(admin_router)

    from app.readapi import router as readapi_router

    application.include_router(readapi_router)

    from app.ingest import router as ingest_router

    application.include_router(ingest_router)

    _BASE_DIR = Path(__file__).resolve().parent
    _TEMPLATE_DIR = _BASE_DIR / "templates"
    _jinja_env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )

    @application.exception_handler(404)
    async def not_found_handler(
        request: Request, exc: HTTPException
    ) -> HTMLResponse | JSONResponse:
        """SPEC 10.9: HTML 404 for non-API paths, JSON 404 for /api/ paths."""
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        template = _jinja_env.get_template("404.html")
        html = template.render()
        return HTMLResponse(content=html, status_code=404)

    return application


app = create_app()
