"""POST /api/v1/readings — reading ingestion per SPEC 3.1."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError  # type: ignore[import-untyped]

from app.config import Settings
from app.db import get_db_context
from app.schema import _VALIDATOR, ALLOWED_METRICS
from app.store import upsert_readings

router = APIRouter()


@router.post("/api/v1/readings")
async def ingest_readings(request: Request) -> JSONResponse:
    settings = Settings()
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    if auth[len("Bearer ") :] != settings.INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be valid JSON") from None

    if not isinstance(body, dict) or "readings" not in body:
        raise HTTPException(status_code=400, detail="Missing 'readings' array")

    readings = body["readings"]
    valid_batches: list[dict[str, Any]] = []
    rejected: list[int] = []

    for idx, batch in enumerate(readings):
        try:
            _VALIDATOR.validate(batch)
        except ValidationError:
            rejected.append(idx)
            continue

        node_type = batch.get("node_type", "")
        allowed = ALLOWED_METRICS.get(node_type, set())
        if not all(m in allowed for m in batch.get("metrics", {})):
            rejected.append(idx)
            continue

        valid_batches.append(batch)

    with get_db_context() as db:
        result = upsert_readings(db, valid_batches)

    return JSONResponse(
        status_code=200,
        content={"accepted": result["accepted"], "rejected": rejected},
    )
