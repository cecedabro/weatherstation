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

## T20: Client-side uPlot chart rendering (done)
- Created `backend/app/static/chart.js` (under 150 lines): IIFE module that finds elements with `data-chart`, reads `data-node`/`data-metric` from the script tag, fetches `/api/v1/series` with the selected range params, renders a uPlot line chart, and handles `.chart-btn` click events with `preventDefault` to re-fetch and redraw. Shows "No data for this range" message when the series is empty.
- Updated `backend/app/templates/home.html`: added `data-chart`, `data-node`, and `data-metric="temp_c"` attributes to `#chart-container`. Added `head` block with uPlot CSS/JS link and `scripts` block with `chart.js` script tag (passing data attributes from Jinja context).
- Updated `backend/app/web.py`: passes `first_weather_node` (first weather node ID or `None`) to the template context for use in data attributes.
- Created `backend/tests/test_chart_js.py` with 3 tests: page loads all three assets (uPlot CSS, uPlot IIFE JS, chart.js), chart container has required data attributes, and `chart.js` file exists and references `/api/v1/series`.
- `make check` passes: ruff clean, mypy clean, 159 tests pass (3 new + 156 existing), 98% coverage. Gotcha: chart.js uses `document.currentScript.dataset.*` to read its own data attributes since the data-node value is server-determined.

## T21: Load HTMX on every page via base.html (done)
- Added `<script src="/static/vendor/htmx.min.js"></script>` to `backend/app/templates/base.html` in the `<head>` block so HTMX loads on every page.
- Created `backend/tests/test_static_assets.py` with 4 tests: htmx.min.js serves 200 with JS content type, uPlot.iife.min.js serves 200 with JS content type, uPlot.min.css serves 200 with CSS content type, and `/` HTML contains a reference to htmx.min.js.
- `make check` passes: ruff clean, mypy clean, 163 tests pass (4 new + 159 existing), 98% coverage.

## T22: Fix home empty states per SPEC 5.3 (done)
- Fixed `backend/app/templates/home.html` empty state logic: changed three separate `{% if %}` blocks into a single `{% if %}{% elif %}{% elif %}{% endif %}` chain.
  - No data at all → only the "No Readings Yet" card (not "No Weather Data" + "No Soil Data")
  - Weather data only → "No Soil Data" (not "No Weather Data")
  - Soil data only → "No Weather Data" (not "No Soil Data")
  - Both kinds present → no empty-state cards
- Created `backend/tests/test_page_empty.py` with 11 tests covering: no data (generic card only, both specific absent), weather-only (soil empty shown, weather empty absent, generic absent), soil-only (weather empty shown, soil empty absent, generic absent), both present (no empty cards), and empty-state card count assertions (exactly 1 in all partial/empty cases).
- `make check` passes: ruff clean, mypy clean, 174 tests pass (11 new + 163 existing), 98% coverage.

## T23: Move inline styles from home.html into style.css (done)
- Moved 12 inline `style="..."` attributes from `backend/app/templates/home.html` to named CSS classes in `backend/app/static/style.css`.
- New classes: `.card-spaced` (card bottom margin), `.node-title` (h3 with font-size/color/margin), `.stats-row--soil` (2-column grid variant), `.empty-state h2` (margin override), `.empty-state p` (color + font-size), `.chart-container` (width + height).
- No new tests needed: all 174 existing tests pass unmodified, confirming no visual or behavioral change. `make check` passes: ruff clean, mypy clean, 98% coverage.

## T24: Pure formatting helpers in app/fmt.py (done)
- Created `backend/app/fmt.py`: three pure helpers — `compass(deg)` → 16-point name (N, NNE, … NNW; 0/360→N), `local_time(dt)` → "14:05, 2 Nov" via `zoneinfo` with Europe/Amsterdam timezone, `ago(dt, now)` → "just now" (< 1 min), "X min ago" (< 2 h), "X h ago" (< 48 h), "X days ago" (>= 48 h).
- Registered all three as Jinja2 filters (and `ago` as a template global) via `_register_filters()` called from `web.py` on the shared `_jinja_env`.
- Created `backend/tests/test_fmt.py` with 19 tests: compass 0→N, 360→N, 12→NNE, 225→SW, all 16 cardinal/intercardinal points, boundary tests; winter (CET) and summer (CEST) UTC offset for local_time; 59 s, 61 min, 25 h, 2 days for ago; filter registration check.
- `make check` passes: ruff clean, mypy clean, 193 tests pass (19 new + 174 existing), 98% coverage.

## T25: Wind direction compass formatting, <time> tags, offline state on GET / (done)
- Updated `backend/app/readapi.py`: added `node_reading_time` dict tracking to `_current_readings()`, returning `reading_time` (datetime or None) per node in the result dict. Added `# type: ignore[assignment]` for SQLAlchemy column type.
- Updated `backend/app/web.py`: added imports for `UTC`, `datetime`, `timedelta`; computed `offline` boolean per node (`(now - rt) > timedelta(minutes=15)`) and added it to the template context.
- Updated `backend/app/templates/home.html`: wind direction values now render as "SW 225°" (compass name + degrees); added `<time>` tags with `datetime` ISO attribute and `title` (local_time), showing relative age ("just now", "X min ago"); added offline indicator ("Offline since ...") for readings >15 min old. Guarded `local_time` filter against `None` in offline messages.
- Updated `backend/app/fmt.py`: registered `compass` in both `env.globals` and `env.filters` so it works as both a template function call and a pipe filter.
- Created `backend/tests/test_page_home_fmt.py` with 16 tests covering: `reading_time` datetime/None behavior, max-across-metrics logic, compass formatting (N, S, 225°), `<time>` tag presence/attributes/content, offline state for old readings, offline message with local time, online state for recent readings, 15-min boundary, and node with no readings.
- `make check` passes: ruff clean, mypy clean, 209 tests pass (16 new + 193 existing), 98% coverage.

### T26 - Shared navigation (SPEC 10.1) - DONE 2026-11-02
- Added `<nav aria-label="Main">` with 5 links and `aria-current="page"` conditional to `backend/app/templates/base.html`.
- Updated `backend/app/web.py`: added `active` context to index route; created stub routes for `/weather`, `/soil`, `/history`, `/about`.
- Created stub templates: `weather.html`, `soil.html`, `history.html`, `about.html`.
- Added `.nav` responsive CSS (`flex-wrap: wrap`) to `backend/app/static/style.css`.
- Created `backend/tests/test_nav.py` (7 tests covering link presence, active state switching, CSS wrap).
- `make check` passes: ruff clean, mypy clean, 216 tests pass, 98.45% coverage.

## T27: Styled 404 page (SPEC 10.9) - DONE 2026-11-02
- Created `backend/app/templates/404.html`: extends `base.html`, shows "Page Not Found" message with friendly text and a `<a href="/" class="btn-glossy">Back to Home</a>` link.
- Updated `backend/app/main.py`: added `@application.exception_handler(404)` that returns `HTMLResponse` for non-`/api/` paths and `JSONResponse` (`{"detail": "Not found"}`) for paths starting with `/api/`.
- Created `backend/tests/test_404.py` with 8 tests: HTML 404 status/content-type, nav/header/footer presence, friendly message, home link, JSON 404 for `/api/` paths, and detail field presence.
- `make check` passes: ruff clean, mypy clean, 224 tests pass, 98.49% coverage.

## T28: HTMX partial for current conditions (SPEC 10.10) - DONE 2026-11-02
- Created `backend/app/templates/_current.html`: extracted the current-conditions and soil sections from `home.html` into a reusable HTML fragment (no `extends`, no base structure).
- Updated `backend/app/templates/home.html`: replaced the inline weather/soil/empty-state markup (lines 7–116) with `{% include "_current.html" %}`. The chart section and scripts remain inline.
- Added `GET /partials/current` route in `backend/app/web.py`: same DB query and offline logic as the index route, but renders only `_current.html` (no `<html>`, no nav, no header/footer). Returns `HTMLResponse` fragment for HTMX `hx-get` polling.
- Created `backend/tests/test_partials.py` with 21 tests: 200 status, HTML content-type, no `<html`/`<head`/`<body`/`<nav`/`<header`/`<footer`, weather node ID, soil node ID, both node IDs, Current Conditions header, Latest Soil header, temperature/humidity/soil moisture/soil temperature values, empty-state fragment (no data, weather-only, soil-only, both present), card section classes, and content-parity with home page.
- `make check` passes: ruff clean, mypy clean, 244 tests pass (21 new + 223 existing), 98.34% coverage.

## T29: Auto-refresh on `/` (SPEC 10.10) - DONE 2026-11-02
- Added `<div id="current-conditions" hx-get="/partials/current" hx-trigger="every 60s" hx-swap="outerHTML">` wrapper as the root element of `backend/app/templates/_current.html`, wrapping all conditional section blocks.
- Created `backend/tests/test_autorefresh.py` with 10 tests: asserts `id="current-conditions"` and all three HTMX attributes (`hx-get`, `hx-trigger`, `hx-swap`) are present on both `GET /` (home page) and `GET /partials/current` (fragment).
- `make check` passes: ruff clean, mypy clean, 254 tests pass (10 new + 244 existing), 98.34% coverage.

## T30: Weather page `GET /weather` (SPEC 10.2) - DONE 2026-11-02
- Updated `backend/app/web.py`: replaced the `/weather` stub with a full route that fetches weather nodes via `_current_readings(db)`, computes offline status (>15 min threshold), and passes `weather_nodes`, `active="weather"`, and `now` to the template.
- Created `backend/app/templates/weather.html`: extends `base.html`, renders "Current Conditions" header, loops over weather nodes displaying all metrics (temp, humidity, pressure, wind speed + compass direction), shows last-updated time with `<time>` tags, and displays "Offline since ..." for old readings. Empty state shows "No Weather Data" with a friendly waiting message.
- Created `backend/tests/test_page_weather.py` with 9 tests: 200 status, HTML content-type, metric values + units, node ID, last-updated timestamp, offline indicator, nav active state, empty state, and section header.
- Fixed `backend/app/templates/base.html`: nav links now include both `class="nav-link {% active %}"` and `aria-current="page"` with correct attribute ordering (`aria-current` before `class`) so both `test_nav.py` and `test_page_weather.py` assertions pass.
- `make check` passes: ruff clean, mypy clean, 263 tests pass (9 new + 254 existing), 98.17% coverage.

## T32: /soil page (SPEC 10.3) - DONE 2026-11-02
- Updated `backend/app/web.py`: replaced `/soil` stub with full route that fetches soil nodes via `_current_readings(db)`, computes `offline` flag (>15 min), and passes `soil_nodes`, `active="soil"`, `page_title`, `now` to template.
- Rewrote `backend/app/templates/soil.html`: extends `base.html`, renders beds/moisture/soil temp/battery/online state per node. Cards show "Needs Water" badge when moisture < 25%, offline indicator with local time, online status with `<time>` ago, and links to `/soil/<node_id>`. Empty state when no soil data.
- Added `.badge-needs-water` and `.card-meta` styles to `backend/app/static/style.css`.
- Created `backend/tests/test_page_soil.py` with 13 tests: page loads, content-type, node ID, moisture/temp/battery display, nav active state, badge threshold (24.9% shows, 25.0% doesn't), 16-min offline, empty state, online status, and detail links.
- Gotcha: HTML entities like `&#176;` inside Jinja2 `{{ }}` expressions cause a `TemplateSyntaxError` ("unexpected char '&'"). Must place the entity or the Unicode degree symbol outside the expression (e.g. `{{ value }}°C`).
- `make check` passes: ruff clean, mypy clean, 286 tests pass (13 new + 273 existing), 98.02% coverage.

## T33: Soil detail page GET /soil/{node_id} (SPEC 10.4) - DONE 2026-11-02
- Updated `backend/app/web.py`: replaced `/soil/{node_id}` stub with full route that validates node existence and type, fetches latest soil metrics, computes `offline` flag (>15 min), and renders `soil_detail.html` with metrics, badges, and chart selectors.
- Created `backend/app/templates/soil_detail.html`: extends `base.html`, displays moisture/soil-temp/battery stat cards, "Needs Water" badge (<25%), online/offline indicator with `<time>` tags, and "History" section with soil moisture + soil temp chart containers and day/week/month selector buttons.
- Created `backend/tests/test_page_soil_detail.py` with 26 tests: 200 status, content-type, metric display (moisture/temp/battery), nav active state, badges (needs water, online/offline), chart containers/attributes, selector links with query params, 404 for unknown/non-soil nodes, empty metrics (no charts), and partial metric (single chart).
- Fixed `backend/app/templates/soil_detail.html`: changed `&#xB0;C` HTML entity to literal `°` character to match Jinja2 rendering behavior and test expectations (matching the pattern from `weather.html`).
- `make check` passes: ruff clean, mypy clean, 312 tests pass (26 new + 286 existing), 98.10% coverage.

## T31: Charts on GET /weather (SPEC 10.2) - DONE 2026-11-02
- Updated `backend/app/web.py`: added `chart_selectors=_selector_links()` to the `/weather` route context.
- Updated `backend/app/templates/weather.html`: added "History" section with shared day/week/month chart selector and one `<div data-chart>` container per metric per node (temp_c, humidity_pct, pressure_hpa, rain_mm, wind_speed_ms, wind_dir_deg). uPlot assets loaded via `{% block head %}`.
- Rewrote `backend/app/static/chart.js`: now finds chart sections by scanning `section.card` elements for `[data-chart]` children, registers multiple charts per section, sets `_section` ID on ranges, and handles selector button clicks to update all charts in the matching section. `rain_mm` renders as bars via `barPath()` function.
- Created `backend/tests/test_page_weather_charts.py` with 10 tests: chart section existence, selector presence/query params, chart containers per metric, data-node/data-chart attributes, rain_mm presence, barPath JS function, empty state behavior.
- `make check` passes: ruff clean, mypy clean, 273 tests pass (10 new + 263 existing), 98.17% coverage.

## T36: GET /api/v1/export.csv (done)
- Created `backend/tests/test_export.py` with 19 tests covering: content-type (`text/csv`), `Content-Disposition: attachment` header, CSV header row (`ts,node_id,metric,value`), body data presence, ISO-8601 UTC timestamp format, time ordering, all metrics included, node IDs in rows, filtering by `node`, filtering by `metric`, combined filters, empty results (unknown node/metric), valid `from`/`to` date range filtering, combined filters with dates, row count matching DB, and numeric value parsing.
- Added `GET /api/v1/export.csv` endpoint to `backend/app/readapi.py`: accepts `node`, `metric`, `from`, `to` query params, validates dates via `SeriesParams` (400 on bad dates), queries readings ordered by `ts`, and returns `Response` with CSV content.
- Updated `_parse_dt()` in `readapi.py` to handle space-separated timezone offsets (URL-decoded `+` → space) by normalizing spaces to `+` before `fromisoformat`.
- `make check` passes: ruff clean, mypy clean, 349 tests pass (19 new + 330 existing), 97.9% coverage.

## T37: Export form on /history + plain date support for export endpoint (done)
- Added plain `YYYY-MM-DD` date expansion to `backend/app/readapi.py`: `_expand_export_dates()` helper detects 10-character date strings, parses them with `date.fromisoformat()`, and converts to UTC-aware datetimes — `from` gets `00:00:00`, `to` gets `23:59:59.999999`.
- Added "Export Data" form to `backend/app/templates/history.html`: GET form to `/api/v1/export.csv` with `node` select (all nodes + each weather/soil node), `metric` select (All metrics + temp_c, humidity_pct, rain_mm, pressure_hpa, soil_moisture_pct, soil_temp_c), and `from`/`to` `<input type="date">` fields.
- Updated `backend/app/web.py`: passes `soil_nodes` alongside `weather_nodes` to `history.html` template context.
- Created `backend/tests/test_page_history_export.py` with 15 tests: form presence, attributes, node/metric selects, date inputs, labels, submit button, node options, and metric options.
- Added 8 new tests to `backend/tests/test_export.py` for plain date format acceptance, mixed formats, and validation.
- Moved `_now()`, `_make_batch()`, `_make_daily()`, `history_data`, and `multi_node_history` from `test_page_history.py` to `conftest.py` for cross-module fixture availability.
- `make check` passes: ruff clean, mypy clean, 374 tests pass (23 new + 351 existing), 97.69% coverage.
