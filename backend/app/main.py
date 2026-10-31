"""Application factory and entry point."""

from fastapi import FastAPI

from app.config import Settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Weather Station")
    _ = Settings()  # validate defaults at startup

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/v1/nodes")
    async def nodes() -> list[dict[str, str | bool]]:
        return []

    from app.ingest import router as ingest_router

    application.include_router(ingest_router)

    return application


app = create_app()
