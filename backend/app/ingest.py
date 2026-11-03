"""POST /api/v1/readings — reading ingestion per SPEC 3.1–3.3."""

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from app.config import Settings
from app.db import get_db_context
from app.schema import _VALIDATOR, ALLOWED_METRICS
from app.store import upsert_readings

router = APIRouter()

Rejected = dict[str, Any]


def _validate_batches(
    readings: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[Rejected]]:
    """Validate all batches against schema and node_type/metric rules.

    Returns (valid_batches, rejected) where rejected items contain
    ``{"index": i, "error": "..."}`` per the contract README.
    """
    valid_batches: list[dict[str, Any]] = []
    rejected: list[Rejected] = []

    for idx, batch in enumerate(readings):
        try:
            _VALIDATOR.validate(batch)
        except ValidationError as exc:
            rejected.append({"index": idx, "error": str(exc.message)})
            continue

        node_type = batch.get("node_type", "")
        allowed = ALLOWED_METRICS.get(node_type, set())
        bad_metrics = [m for m in batch.get("metrics", {}) if m not in allowed]
        if bad_metrics:
            rejected.append(
                {
                    "index": idx,
                    "error": (f"node_type={node_type} does not allow metrics: {bad_metrics}"),
                }
            )
            continue

        valid_batches.append(batch)

    return valid_batches, rejected


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
    if not isinstance(readings, list):
        raise HTTPException(status_code=400, detail="'readings' must be an array")
    valid_batches, rejected = _validate_batches(readings)

    with get_db_context() as db:
        result = upsert_readings(db, valid_batches)

    return JSONResponse(
        status_code=200,
        content={"accepted": result["accepted"], "rejected": rejected},
    )
