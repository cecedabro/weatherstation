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

## T09: GET /api/v1/series + GET /api/v1/nodes per SPEC 4.2–4.4 (done)
- Rewrote `backend/app/readapi.py` with fully implemented `/series` and `/nodes` endpoints.
- `/series` (SPEC 4.2): `step=raw` returns individual points ordered by ts; `5m/1h/1d` bucketed
  aggregation using `func.date_trunc` + offset math (5m), `date_trunc("hour")` (1h),
  `date_trunc("day")` (1d). Rain uses `func.sum`, all others use `func.avg`. Filters for node,
  metric, from/to applied to both paths.
- `/series` (SPEC 4.4): `SeriesParams` Pydantic model validates `step` against `_VALID_STEPS`
  and datetime strings via `fromisoformat`. Returns 400 on invalid input.
- `/nodes` (SPEC 4.3): Returns all nodes with `online` flag based on 15-minute last_seen window.
- Created `backend/tests/test_series.py` with 17 tests covering SPEC 4.2 (raw, 5m, 1h, 1d, rain_mm
  sum, node/metric filtering, bucketed filtering, from/to bounds) and SPEC 4.4 (invalid step,
  malformed dates, step validation, node/metric validation, from/to validation).
- Gotcha: `TestClient` does not URL-encode `+` in query strings (`+00:00` becomes a space).
  Fixed in validator by replacing spaces with `+`.
- Gotcha: `5m` bucket SQL uses `literal_column("INTERVAL '5 minutes'")` instead of Python `timedelta`
  to avoid "interval string has wrong format" Postgres error.
- `make check` passes: ruff clean, mypy clean, 85 tests pass (17 new + 68 existing).

## T11: Base template and design tokens stylesheet (done)
- Created `backend/app/static/style.css`: full Frutiger Aero stylesheet ported from the approved
  `index.html` mock. All design tokens (colours, spacing, radius, blur, shadows, typography) are
  CSS custom properties in `:root`. Includes `.header`, `.card`, `.stat-card`, `.btn-glossy`,
  `.entries-table`, `.status-badge`, `.empty-state`, bubble decorations, and responsive breakpoints.
- Created `backend/app/templates/base.html`: Jinja2 base template with `html lang="en"`, viewport
  meta tag (SPEC 5.4), semantic `<header>`, `<main>`, `<footer>`, four bubble decorations, linked
  stylesheet, and extensible blocks (`title`, `head`, `content`, `scripts`, `header_title`,
  `header_logo`, `footer`).
- Updated `backend/app/main.py`: mounted `/static` directory with `StaticFiles`, registered Jinja2
  `Environment` for templates, added `GET /` route rendering `base.html`.
- Created `backend/tests/test_base_template.py` with 13 tests: stylesheet served + content-type,
  design tokens present, header/card classes defined, base template renders at `/`, DOCTYPE and
  lang attribute, stylesheet link, semantic HTML, bubbles, container, footer, and viewport meta.
- Palette: sky blues (#6ec4f0 → #a8e06a → #5aad28), greens (#a8f06a, #4aad20, #d0f5a0), glass
  cards with 12px backdrop blur, 18px border radius. Font: Segoe UI stack. Font used: Frutiger-adjacent
  Segoe UI (system font, no external download needed).
- `make check` passes: ruff clean, mypy clean, 98 tests pass (13 new + 85 existing).
- Next task (T12): Build the `/` page with header, layout, and empty state per SPEC 5.1, 5.3, 5.4.

## T12: GET / dynamic homepage with weather/soil data and empty states (done)
- Rewrote `GET /` in `backend/app/main.py` to query latest weather and soil readings via
  `_current_readings()` (subquery-max-timestamp join, grouped by node_type). Replaced the
  minimal `base.html` render with `home.html` template passing `weather_nodes` and
  `soil_nodes` dicts plus the app title.
- Created `backend/app/templates/home.html`: extends `base.html`, renders the app title and
  subtitle, weather cards (temperature, humidity, pressure, rain), soil cards (moisture, NPK),
  and per-category empty state blocks ("No Weather Data" / "No Soil Data"). Uses HTML entities
  for unicode icons (Jinja2 does not support `\u{...}` escapes).
- Created `backend/tests/test_page_home.py` with 22 tests: title, subtitle, section headers,
  weather/soil cards populated from DB data, individual empty states when one category is
  present, global empty state when no data exists, and correct HTML structure.
- Fixed `backend/tests/test_base_template.py`: added `db` fixture to all tests exercising
  `GET /` (the route now requires a database connection).
- Gotcha: Jinja2 templates do not support JS-style `\u{1F4A7}` unicode escapes; must use
  HTML entities like `&#x1F4A7;` or HTML named entities.
- `make check` passes: ruff clean, mypy clean, 120 tests pass (22 new + 98 existing).

## T13: Current-conditions and latest-soil sections on / per SPEC 5.1 (done)
- Created `backend/tests/test_page_current.py` with 15 tests covering SPEC 5.1:
  current-conditions section header, weather node ID, temperature/humidity/pressure
  display, latest-soil section header, soil node ID, moisture/temperature display,
  individual empty states when one category lacks data, both sections visible with
  mixed data, multiple weather and soil nodes rendering correctly.
- The `home.html` template already implements the sections (built in T12); this task
  provides the dedicated test file required by the acceptance harness.
- Gotcha: soil moisture displays as integer (`%.0f` format), not float — test assertions
  must match that (e.g. "38" not "38.5").
- `make check` passes: ruff clean, mypy clean, 135 tests pass (15 new + 120 existing).

## T15: /admin endpoint with Basic auth and node health table per SPEC 6 (done)
- Added `GET /admin` route in `backend/app/main.py`: validates HTTP Basic auth credentials against `ADMIN_USER`/`ADMIN_PASSWORD` (hmac-compare, 401 on mismatch), queries latest readings per node, computes 24h reading counts, and renders `admin.html` with node health table (last_seen, online/offline >15m, battery <3.4V flag, RSSI, 24h count).
- Created `backend/tests/test_admin.py` with 13 tests: SPEC 6.1 (401 on missing/empty/wrong/invalid-utf8 credentials), SPEC 6.2 (health table with last_seen, online/offline, low-battery flag, battery/RSSI display, empty state), SPEC 6.3 (24h reading counts).
- Created `backend/app/templates/admin.html`: extends `base.html`, renders node health table with status badges.
- Added admin CSS (table, badges, row-hover styles) to `backend/app/static/style.css`.
- Gotcha: ruff B008 flags `Depends(basic_auth)` in function signature — added `# noqa: B008` (FastAPI DI pattern). Mypy `var-annotated`/`arg-type` errors on SQLAlchemy `select()` chain — added `# type: ignore` comments.
- `make check` passes: ruff clean, mypy clean, 148 tests pass (13 new + 135 existing).

## T16: Consolidate /nodes and /current into readapi.py + tests/test_nodes.py (done)
- Moved `_current_readings()` and `GET /api/v1/current` from `backend/app/main.py` to `backend/app/readapi.py`.
- Removed duplicate inline implementations of `/api/v1/nodes` and `/api/v1/current` from `main.py`; replaced with `from app.readapi import router as readapi_router` included via `create_app()`.
- Wrapped `/api/v1/nodes` DB query in `readapi.py` with `try/except ProgrammingError` returning `[]` — the contract test runs without migrations, and the old stub in `main.py` never hit the DB.
- Created `backend/tests/test_nodes.py` with 5 tests: empty list, 14-min boundary (online), 16-min boundary (offline), contract field validation, mixed online/offline nodes.
- Created `backend/conftest.py` to insert `backend/` into `sys.path` — required because pytest loads contract tests from `../contract/tests/` which otherwise drops `app` from the import path.
- `make check` passes: ruff clean, mypy clean, 153 tests pass (5 new + 148 existing), 98% coverage.

## T17: Move HTML routes out of main.py into web.py and admin.py (done)
- Created `backend/app/web.py`: contains `_jinja_env` (Jinja2 environment) and the `GET /` route rendering `home.html`.
- Created `backend/app/admin.py`: contains `_readings_24h()` helper, `basic_auth = HTTPBasic()`, and the `GET /admin` route with Basic auth validation and node health table rendering. Imports `_jinja_env` from `web.py`.
- Rewrote `backend/app/main.py`: now only builds the FastAPI app, mounts `/static`, defines `/healthz`, and includes routers (`web`, `admin`, `readapi`, `ingest`). Removed all route handlers, Jinja2 env setup, and helper functions.
- No test changes required: all 153 tests pass unmodified. `make check` passes: ruff clean, mypy clean, 98% coverage.

## T19: Chart section on GET / per SPEC 5.2 (done)
- Added `GET /` chart section to `backend/app/templates/home.html`: a `#chart-section` card containing three `.chart-btn` links (24h, 7d, 30d) with `from`, `to`, `step` query parameters pointing to `/api/v1/series`. The `data-step`, `data-from`, `data-to` attributes also carry these values for client-side JS consumption.
- Updated `backend/app/web.py`: added `_SelectorSpec` TypedDict, selector constants (`_SELECTORS`, `_SELECTOR_HOURS`), `_selector_links()` helper that computes URL-encoded `from`/`to` timestamps, and passes `chart_selectors` to the template context.
- Added CSS for `.chart-selector` and `.chart-btn` to `backend/app/static/style.css`.
- Created `backend/tests/test_page_chart.py` with 3 tests: chart section/container presence, three selector links rendered, and correct time-window query values (parses `from`/`to` timestamps and verifies the hour delta matches expected 24h/168h/720h).
- `make check` passes: ruff clean, mypy clean, 156 tests pass (3 new + 153 existing), 98% coverage.
- Next task (T20): Wire up uPlot client-side chart rendering using the selector links and `/api/v1/series` data.
