"""POST /api/v1/readings — reading ingestion per SPEC 3.1–3.8."""

import hmac
import time
from collections import deque
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from app.config import Settings
from app.db import get_db_context
from app.schema import _VALIDATOR, ALLOWED_METRICS
from app.store import upsert_readings

_MAX_BODY = 1024 * 1024  # 1 MiB

router = APIRouter()

_MAX_REQUESTS = 60
_WINDOW_SECONDS = 60


class RateLimiter:
    """In-process sliding-window rate limiter: _MAX_REQUESTS per _WINDOW_SECONDS per client."""

    def __init__(self) -> None:
        self._clients: dict[str, deque[float]] = {}

    def is_allowed(self, client_key: str) -> bool:
        """Return ``True`` if the request should be accepted (sliding window)."""
        now = self._now() if hasattr(self, "_now") and callable(self._now) else time.time()
        cutoff = now - _WINDOW_SECONDS

        if client_key not in self._clients:
            self._clients[client_key] = deque()

        timestamps = self._clients[client_key]
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= _MAX_REQUESTS:
            return False

        timestamps.append(now)
        return True


# Module-level singleton (created at import time)
_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    """Return the global rate-limiter singleton."""
    return _limiter


def reset_rate_limiter() -> None:
    """Clear rate-limiter state (mainly for tests)."""
    _limiter._clients.clear()


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
    if not hmac.compare_digest(auth[len("Bearer ") :], settings.INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")

    # SPEC 3.8: rate-limit — 60 requests per minute per client
    client_key = request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )
    if not _limiter.is_allowed(client_key):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded (60 req/min)"},
            headers={"Retry-After": "60"},
        )

    # SPEC 3.7: reject bodies larger than 1 MiB before parsing
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY:
                raise HTTPException(status_code=413, detail="Body too large (max 1 MiB)")
        except ValueError:
            pass

    body_bytes = await request.body()
    if len(body_bytes) > _MAX_BODY:
        raise HTTPException(status_code=413, detail="Body too large (max 1 MiB)")

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
