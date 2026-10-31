# PROGRESS

Appended by the agent after each task: what changed, where, and gotchas for later tasks.

## T01: Backend skeleton (done)
- Created `backend/pyproject.toml` with uv project config: FastAPI, uvicorn, SQLAlchemy, alembic,
  psycopg, pydantic, pydantic-settings, jinja2, httpx, pytest, pytest-asyncio, ruff, mypy, pgserver.
  Ruff line-length 100, mypy strict on `app` package.
- Created `backend/app/config.py` with `Settings(BaseSettings)` reading `DATABASE_URL`, `INGEST_TOKEN`,
  `ADMIN_USER`, `ADMIN_PASSWORD` from env with safe local defaults (SPEC 1.3).
- Created `backend/app/main.py` with `create_app()` factory exposing `app`, `/healthz` endpoint
  returning `{"status": "ok"}` (SPEC 1.2), and a minimal `/api/v1/nodes` stub returning `[]` for
  contract test compatibility.
- Created `backend/app/__init__.py` re-exporting `app`.
- Created `backend/tests/test_healthz.py` asserting SPEC 1.2 (status code 200, body matches).
- Updated `.gitignore` to exclude `__pycache__/` and cache directories (prevents protected path errors
  when contract tests create pycache during `make check`).
- `make check` passes: ruff clean, mypy clean, 6 tests pass (1 new + 5 contract tests).

## T02: Config from env + health tests (done)
- Created `backend/tests/test_health.py` with 4 tests covering SPEC 1.2 (healthz returns 200 with correct body)
  and SPEC 1.3 (Settings defaults are correct, env var overrides work, /healthz works even with bad DATABASE_URL).
- Existing `backend/app/config.py` and `backend/app/main.py` already implement config and /healthz from T01.
- `make check` passes: ruff clean, mypy clean, 10 tests pass (5 new + 5 contract tests).

## T05: POST /api/v1/readings ingestion endpoint (done)
- Created `backend/app/schema.py` that loads `contract/reading.schema.json` at startup, exposes `_VALIDATOR` (jsonschema `Draft202012Validator`) and `ALLOWED_METRICS` dict mapping `node_type` → allowed metric keys.
- Created `backend/app/ingest.py` with `POST /api/v1/readings` endpoint: validates `Bearer <INGEST_TOKEN>`, requires `readings` array envelope, validates each batch against the JSON schema, checks `node_type` vs `metrics` alignment against `ALLOWED_METRICS`, rejects invalid batches by index, and calls `upsert_readings` for valid ones. Returns `{"accepted": n, "rejected": [...]}` with 200 status.
- Updated `backend/app/main.py` to lazily include `ingest_router` at startup.
- Updated `backend/tests/conftest.py` to add a `client` fixture using `fastapi.testclient.TestClient` for HTTP-level testing.
- Created `backend/tests/test_ingest_ok.py` with 6 happy-path tests covering single weather/soil batches, multiple batch acceptance, response format, data integrity (values stored correctly), and node registry updates.
- `make check` passes: ruff clean, mypy clean, 39 tests pass (6 new + 33 existing). Gotcha: `jsonschema` lacks type stubs (`# type: ignore[import-untyped]`), and `except` blocks use `raise ... from None` to satisfy ruff B904.

## T04: Store-reading service with upsert (done)
- Created `backend/app/store.py` with `upsert_readings(db, batches)` service function that
  upserts node rows (ON CONFLICT on `node_id` PK) and one metric reading row per entry
  (ON CONFLICT on `(node_id, metric, ts)` unique constraint). Returns `{"accepted": n,
  "rejected": [<indices>]}`. Invalid timestamps cause per-batch rejection.
- Created `backend/tests/test_store.py` with 11 tests covering SPEC 2.2 (one row per metric)
  and SPEC 2.3 (no duplicates on re-insert, value updates on conflict, node registry updates,
  mixed accepted/rejected batches, empty batch list, soil batch, partial metrics).
- `make check` passes: ruff clean, mypy clean, 33 tests pass (11 new + 22 existing).

## T06: Ingest validation, per-item rejection and node_type/metric rule (done)
- Updated `backend/app/ingest.py`: changed rejected list from `[indices]` to `[{"index": i, "error": "..."}]` per contract README format. Extracted `_validate_batches()` helper that validates each batch against JSON schema and node_type/metric alignment, collecting per-batch rejection details.
- Created `backend/tests/test_ingest_validation.py` with 8 tests: SPEC 3.2 (missing required field rejected, null timestamp rejected, integer timestamp rejected, mixed valid+invalid batches, all batches invalid) and SPEC 3.3 (soil metric on weather node rejected, weather metric on soil node rejected, mixed valid+type-mismatch batches). Each test asserts HTTP response, rejection index, error presence, and DB state (no rows for rejected batches).
- `make check` passes: ruff clean, mypy clean, 47 tests pass (8 new + 39 existing).

## T07: Ingest auth and malformed envelope per SPEC 3.4–3.5 (done)
- Updated `backend/app/ingest.py`: added `isinstance(readings, list)` guard so that a `"readings"` key with a non-array value (e.g. a string) returns 400 per SPEC 3.5.
- Created `backend/tests/test_ingest_auth.py` with 10 tests: SPEC 3.4 (missing Authorization header → 401, empty Authorization header → 401, wrong bearer token → 401, valid token succeeds, auth checked before body validation) and SPEC 3.5 (non-JSON body → 400, no `readings` key → 400, `readings` not an array → 400, empty readings array accepted with 0 accepted, malformed body does not store data). Each auth test verifies 0 rows stored.
- `make check` passes: ruff clean, mypy clean, 57 tests pass (10 new + 47 existing).

## T08: GET /api/v1/current per SPEC 4.1 (done)
- Implemented `GET /api/v1/current` in `backend/app/main.py`: uses a SQL subquery to find the latest
  timestamp per (node_id, metric), joins back to get the actual reading values, then groups by node
  and returns one entry per node with node_id, node_type, last_seen, battery_v, rssi_dbm, and a
  metrics dict mapping metric name to its latest value.
- Created `backend/tests/test_current.py` with 11 tests: empty DB returns empty list, latest values
  returned (not historical), multiple nodes, soil metrics, nodes without readings, response field
  validation, upsert updates reflected, battery_rssi included, node count correctness, empty metrics
  for nodes without readings, and unique node_id entries.
- `make check` passes: ruff clean, mypy clean, 68 tests pass (11 new + 57 existing).
