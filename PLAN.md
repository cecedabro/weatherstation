# PLAN

One task per line, smallest useful units. `accept:` exits 0 when done. The
harness also runs `make check`. Keep each task to roughly one module or endpoint.
Read the named doc before starting. Mark boxes: the harness does, not you.

## Backend foundation
- [x] T01: Create the backend skeleton (uv project, FastAPI app factory, ruff+mypy+pytest wired, one trivial passing test) so `make check` passes. See docs/backend.md §skeleton.
  accept: make check
- [x] T02: Add GET /healthz per SPEC 1.2–1.3, config from env. See docs/backend.md §config.
  accept: cd backend && uv run pytest tests/test_health.py -q
- [x] T03: Test Postgres fixture (pgserver, see docs/testing.md), models, and Alembic migration for readings and nodes per SPEC 2.1. See docs/backend.md §storage.
  accept: cd backend && uv run pytest tests/test_storage.py -q
- [x] T04: Store-reading service with upsert per SPEC 2.2–2.3.
  accept: cd backend && uv run pytest tests/test_store.py -q

## Ingest
- [x] T05: POST /api/v1/readings happy path per SPEC 3.1. See docs/backend.md §ingest.
  accept: cd backend && uv run pytest tests/test_ingest_ok.py -q
- [x] T06: Ingest validation, per-item rejection and node_type/metric rule per SPEC 3.2–3.3.
  accept: cd backend && uv run pytest tests/test_ingest_validation.py -q
- [x] T07: Ingest auth and malformed envelope per SPEC 3.4–3.5.
  accept: cd backend && uv run pytest tests/test_ingest_auth.py -q

## Read API
- [x] T08: GET /api/v1/current per SPEC 4.1.
  accept: cd backend && uv run pytest tests/test_current.py -q
- [x] T09: GET /api/v1/series with step buckets per SPEC 4.2, 4.4.
  accept: cd backend && uv run pytest tests/test_series.py -q
- [~] T10: GET /api/v1/nodes per SPEC 4.3 (must satisfy the contract tests). — superseded by T16
  accept: cd backend && uv run pytest tests/test_nodes.py ../contract/tests -q

## Website
- [x] T11: Base template and one stylesheet of design tokens, ported from the root index.html. See docs/frontend.md, docs/design.md.
  accept: cd backend && uv run pytest tests/test_base_template.py -q
- [x] T12: GET / page with header, layout and the "no readings yet" empty state per SPEC 5.1, 5.3, 5.4.
  accept: cd backend && uv run pytest tests/test_page_home.py -q
- [x] T13: Current-conditions and latest-soil sections on / per SPEC 5.1.
  accept: cd backend && uv run pytest tests/test_page_current.py -q
- [~] T14: History chart with day/week/month selector per SPEC 5.2. See docs/frontend.md §charts. — superseded by T19, T20
  accept: cd backend && uv run pytest tests/test_page_chart.py -q

## Admin
- [x] T15: /admin with Basic auth and node health table per SPEC 6. See docs/frontend.md §admin.
  accept: cd backend && uv run pytest tests/test_admin.py -q

## Round 2: fixes and the history chart
T10 and T14 above were skipped; these replace them. Do them in order.
- [x] T16: Delete the duplicate `/api/v1/nodes` and `/api/v1/current` from `app/main.py`; keep one implementation of each in `app/readapi.py` (SPEC 4.1, 4.3). Write `tests/test_nodes.py`: online true iff last_seen within 15 min (test 14 and 16 minutes), contract field names, empty list when no nodes.
  accept: cd backend && uv run pytest tests/test_nodes.py tests/test_current.py ../contract/tests -q
- [x] T17: Move the HTML routes out of `app/main.py` (`/` into `app/web.py`, `/admin` into `app/admin.py`) so `main.py` only builds the app and includes routers. No behaviour change: every existing test must still pass unmodified.
  accept: cd backend && uv run pytest -q
- [x] T18: Vendor uPlot into `app/static/vendor/` (see docs/frontend.md §vendor). — done by hand: uPlot 1.6.32 and htmx 2.0.11 are vendored (the agent cannot download to /tmp)
  accept: test -f backend/app/static/vendor/uPlot.iife.min.js
- [x] T19: Chart section on `/` (SPEC 5.2): a container, and a day/week/month selector rendered server-side as links or buttons carrying the `from`, `to` and `step` for `/api/v1/series` (day→5m, week→1h, month→1d). Write `tests/test_page_chart.py` asserting the container, the three selector options, and the exact series query values.
  accept: cd backend && uv run pytest tests/test_page_chart.py -q
- [x] T20: `app/static/chart.js` (under 150 lines, no inline script in templates): for every element with a `data-chart` attribute, read `data-node` and `data-metric`, fetch `/api/v1/series` for the range of the selected button in the same section, draw it with uPlot, redraw when another range button is clicked (preventDefault), and show "No data for this range" when the series is empty. On `/`, give `#chart-container` `data-chart`, `data-node` (first weather node, if any) and `data-metric="temp_c"`, and load `vendor/uPlot.min.css`, `vendor/uPlot.iife.min.js` and `chart.js`. Write `tests/test_chart_js.py`: the page loads all three files, the container has the data attributes, `chart.js` exists and mentions `/api/v1/series`.
  accept: cd backend && uv run pytest tests/test_chart_js.py -q && node --check app/static/chart.js

## Round 3: a complete multi-page site
Read SPEC §10 and docs/frontend.md §pages first. Do the tasks in order; each builds on the
ones before. Every new page extends `base.html` and reuses the design tokens in `style.css`.
- [x] T21: Load HTMX on every page: `base.html` includes `/static/vendor/htmx.min.js` (already vendored). Write `tests/test_static_assets.py`: `/static/vendor/htmx.min.js`, `/static/vendor/uPlot.iife.min.js` and `/static/vendor/uPlot.min.css` return 200 with a JavaScript/CSS content type, and `/` references htmx.
  accept: cd backend && uv run pytest tests/test_static_assets.py -q
- [x] T22: Fix the home empty states (SPEC 5.3): with no data at all show only the single "No readings yet" card; show "No weather data" or "No soil data" only when the other kind exists. Write `tests/test_page_empty.py` covering nothing / only weather / only soil, asserting which messages appear and which do not.
  accept: cd backend && uv run pytest tests/test_page_empty.py -q
- [x] T23: Move every inline `style="..."` in `templates/home.html` into named classes in `static/style.css`. No visual or behaviour change; existing tests must pass unmodified.
  accept: ! grep -n 'style="' backend/app/templates/home.html && cd backend && uv run pytest -q
- [x] T24: `app/fmt.py` with pure helpers registered as Jinja filters on the shared environment: `compass(deg)` → 16-point name (N, NNE, … NNW; 0 and 360 → N), `local_time(dt)` → Europe/Amsterdam like "14:05, 2 Nov" via `zoneinfo`, `ago(dt, now)` → "just now" (< 1 min), "5 min ago", "3 h ago", "2 days ago". Write `tests/test_fmt.py` (350→N, 12→NNE, 225→SW, a winter and a summer date for the UTC offset, 59 s, 61 min, 25 h).
  accept: cd backend && uv run pytest tests/test_fmt.py -q
- [x] T25: Home cards use the filters (SPEC 10.11, 10.13): wind direction shows compass plus degrees ("SW 225°"), each node card shows "updated 5 min ago" inside a `<time datetime="...">` with the local time as `title`, and a node whose last reading is older than 15 min shows "offline since <local time>". Extend `_current_readings` to return the reading time if it does not already. Write `tests/test_page_home_fmt.py`.
  accept: cd backend && uv run pytest tests/test_page_home_fmt.py -q
- [x] T26: Shared navigation (SPEC 10.1): a `<nav aria-label="Main">` in `base.html` linking Home `/`, Weather `/weather`, Soil `/soil`, History `/history`, About `/about`. Each route passes `active` ("home", "weather", …) and that link gets `aria-current="page"`. It must wrap without horizontal scroll at 360 px. Write `tests/test_nav.py` for `/` (all five links, only Home is current).
  accept: cd backend && uv run pytest tests/test_nav.py -q
- [x] T27: Styled 404 page (SPEC 10.9): an exception handler that renders `templates/404.html` (extends base, friendly message, link home) with status 404 for paths outside `/api/`, and keeps the JSON 404 for `/api/...`. Write `tests/test_404.py`.
  accept: cd backend && uv run pytest tests/test_404.py -q
- [x] T28: `GET /partials/current` (SPEC 10.10): move the current-conditions and soil markup of the home page into `templates/_current.html`; `/` includes it and the new route returns only that fragment (no `<html>`, no nav). Write `tests/test_partials.py` (node ids present, no `<html`, empty-state fragment when there is no data). Existing home tests must still pass.
  accept: cd backend && uv run pytest tests/test_partials.py tests/test_page_current.py tests/test_page_home.py -q
- [x] T29: Auto-refresh on `/` (SPEC 10.10): the root element of `_current.html` carries `hx-get="/partials/current" hx-trigger="every 60s" hx-swap="outerHTML"`, so it keeps refreshing after each swap. Write `tests/test_autorefresh.py` asserting those attributes on `/` and on the fragment.
  accept: cd backend && uv run pytest tests/test_autorefresh.py -q
- [x] T30: `/weather` page (SPEC 10.2, first half): route in `web.py`, `templates/weather.html`, nav active "weather". Per weather node: every current metric with label, value and unit (wind as compass), and its last-updated time. Empty state when there are no weather nodes. Write `tests/test_page_weather.py`.
  accept: cd backend && uv run pytest tests/test_page_weather.py -q
- [x] T31: Charts on `/weather` (SPEC 10.2, second half): one chart element per metric the node reports (same `data-chart`/`data-node`/`data-metric` contract as `/`) and one shared day/week/month selector; `chart.js` handles several charts on one page and draws `rain_mm` as bars. Write `tests/test_page_weather_charts.py`.
  accept: cd backend && uv run pytest tests/test_page_weather_charts.py -q && node --check app/static/chart.js
- [x] T32: `/soil` page (SPEC 10.3): one card per soil node with moisture, soil temperature, battery voltage, online/offline and last seen (`ago`), plus a "needs water" badge when moisture < 25 %. Each card links to `/soil/<node_id>`. Empty state. Write `tests/test_page_soil.py` (24.9 % shows the badge, 25.0 % does not; a node last seen 16 min ago is offline).
  accept: cd backend && uv run pytest tests/test_page_soil.py -q
- [x] T33: `/soil/{node_id}` page (SPEC 10.4): current values plus moisture and soil-temperature charts (same chart contract and selector). An unknown or non-soil node returns the styled 404 page. Write `tests/test_page_soil_detail.py`.
  accept: cd backend && uv run pytest tests/test_page_soil_detail.py -q
- [~] T34: `GET /api/v1/daily?node=&days=` (SPEC 10.6) in `readapi.py`: one row per UTC day, oldest first, with `date`, `temp_min`, `temp_max`, `temp_avg`, `rain_total`, `humidity_avg` (null when that day has no such data). `days` 1–366, default 30, otherwise 400; unknown node → `[]`. Put the query in a plain function the history page can reuse. Write `tests/test_daily.py` with hand-computed values for two days. — superseded by T46
  accept: cd backend && uv run pytest tests/test_daily.py -q
- [x] T35: `/history` page (SPEC 10.5): a table of the last 30 days for the first weather node using the T34 function (date, min/max/avg °C, rain mm, humidity %), newest first, with a node picker (`?node=`) when there are several weather nodes. Empty state. Write `tests/test_page_history.py`.
  accept: cd backend && uv run pytest tests/test_page_history.py -q
- [x] T36: `GET /api/v1/export.csv?node=&metric=&from=&to=` (SPEC 10.7): `text/csv` with header `ts,node_id,metric,value`, ISO-8601 UTC timestamps, time-ordered, `Content-Disposition: attachment`. `metric` is optional (all metrics). Same date validation as `/series` (bad dates → 400). Write `tests/test_export.py`.
  accept: cd backend && uv run pytest tests/test_export.py -q
- [x] T37: Download form on `/history`: a plain GET form (node, metric including "all", from/to as `<input type="date">`) that submits to `/api/v1/export.csv`; the endpoint also accepts plain `YYYY-MM-DD` (from = start of that day, to = end of that day, UTC). Write `tests/test_page_history_export.py`.
  accept: cd backend && uv run pytest tests/test_page_history_export.py tests/test_export.py -q
- [x] T38: `/about` page (SPEC 10.8): what the station is, the data path (nodes → MQTT → Pi → backend → website) as a simple HTML/CSS diagram or list, the units used, and a table of known nodes from the registry (id, type, first seen, last seen). Write `tests/test_page_about.py`.
  accept: cd backend && uv run pytest tests/test_page_about.py -q
- [x] T39: Garden alerts on `/` (SPEC 10.14): a frost banner when any weather node's current `temp_c` ≤ 2.0, a "rain in the last 24 h: X mm" figure, and a "beds needing water: n" link to `/soil` (same < 25 % rule as T32). Write `tests/test_page_alerts.py` (2.0 shows frost, 2.1 does not).
  accept: cd backend && uv run pytest tests/test_page_alerts.py -q
- [x] T40: Page metadata (SPEC 10.12): every public page sets its own `<title>` and `<meta name="description">`; `base.html` links an SVG favicon at `/static/favicon.svg` (draw a simple leaf or sun) and has `<main>` and `<footer>` landmarks. Write `tests/test_meta.py` looping over `/`, `/weather`, `/soil`, `/history`, `/about` (titles unique, description present, favicon returns 200).
  accept: cd backend && uv run pytest tests/test_meta.py -q
- [x] T41: Accessibility pass (SPEC 10.12): every chart element has `role="img"` and an `aria-label` naming metric and node, a `<noscript>` note says the charts need JavaScript, decorative emoji are `aria-hidden="true"`, and every form control has a `<label>`. Write `tests/test_a11y.py` that parses each public page with `html.parser` and checks these rules.
  accept: cd backend && uv run pytest tests/test_a11y.py -q
- [x] T42: Security headers (SPEC 10.15): middleware adding `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY` and `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:` to every response; `/static/` responses also get `Cache-Control: public, max-age=3600`. Templates must not contain inline `<script>` code. Write `tests/test_security_headers.py`.
  accept: cd backend && uv run pytest tests/test_security_headers.py -q
- [x] T43: Admin polish: `/admin` links back to the public site, shows each node's last seen with `ago` and local time, lists problem nodes (offline, low battery) first, and adds `GET /admin/nodes.json` (same Basic auth) with the table data. Write `tests/test_admin_polish.py` (ordering, 401 on the JSON without auth).
  accept: cd backend && uv run pytest tests/test_admin_polish.py -q
- [x] T44: Add a "Website" section to `README.md`: every page and API endpoint with one line each, and how to preview with `make dev`. Do not change other sections.
  accept: grep -q '/api/v1/export.csv' README.md && grep -q '/soil/' README.md && grep -q 'make dev' README.md
- [x] T45: Preview data: make the seed in `backend/scripts/dev.py` a function that generates 30 days with daily temperature curves, a few rain showers, one frost night (≤ 2 °C) and one bed below 25 % moisture, so every page has something to show under `make dev`. Write `tests/test_dev_seed.py` that calls the generator (no server, no database) and checks those properties.
  accept: cd backend && uv run pytest tests/test_dev_seed.py -q

## Round 4: leftovers, hardening, and a deployable image
Read SPEC §1, §3, §9 and docs/deployment.md first. Do them in order.
- [ ] T46: `GET /api/v1/daily?node=&days=` (SPEC 10.6) in `readapi.py`, reusing `_daily_aggregation` (the history page already uses it). `days` 1–366, default 30, else 400 with a JSON error; unknown node → `[]`. Write `tests/test_daily.py` with hand-computed values for two fixed days. Build timestamps with `timedelta` (docs/testing.md §dates).
  accept: cd backend && uv run pytest tests/test_daily.py -q
- [ ] T47: Bring `static/chart.js` under 150 lines (split helpers into a second file in `static/` if needed; update the templates that load it). No behaviour change; existing tests must still pass.
  accept: test "$(wc -l < backend/app/static/chart.js)" -le 150 && cd backend && uv run pytest -q
- [ ] T48: Remove lint/type suppressions in `backend/app`: fix the code instead of `# type: ignore`, and replace the FastAPI `Depends` `# noqa: B008` lines with ruff's `lint.flake8-bugbear.extend-immutable-calls` setting in `pyproject.toml`. At most 3 suppressions may remain, each with a reason comment.
  accept: test "$(grep -rE 'type: ignore|noqa' backend/app | wc -l)" -le 3 && cd backend && uv run pytest -q
- [ ] T49: Ingest hardening (SPEC 3.6, 3.7): compare the bearer token with `hmac.compare_digest`; reject bodies over 1 MiB with 413 before parsing (check `Content-Length` and the bytes actually read), storing nothing. Write `tests/test_ingest_limits.py`.
  accept: cd backend && uv run pytest tests/test_ingest_limits.py tests/test_ingest_auth.py -q
- [ ] T50: Ingest rate limit (SPEC 3.8): an in-process sliding window of 60 requests per minute per client on `POST /api/v1/readings` → 429 with a JSON error and a `Retry-After` header. Client key is `CF-Connecting-IP` if present, else `request.client.host`. Make the clock injectable so tests don't sleep, and reset state between tests. Write `tests/test_ingest_ratelimit.py`.
  accept: cd backend && uv run pytest tests/test_ingest_ratelimit.py -q
- [ ] T51: `GET /readyz` (SPEC 1.5): runs `SELECT 1`; 200 `{"status": "ready"}` or 503 `{"status": "unavailable"}` on any database error. `/healthz` stays DB-free. Write `tests/test_readyz.py` (the failure case by pointing the session at an unreachable database or overriding the dependency).
  accept: cd backend && uv run pytest tests/test_readyz.py tests/test_health.py -q
- [ ] T52: Production settings (SPEC 1.4): add `APP_ENV` (default `development`) to `Settings`; when it is `production`, `create_app()` raises a clear error if `INGEST_TOKEN` or `ADMIN_PASSWORD` is still the default. Log to stdout with the level from `LOG_LEVEL` (default `INFO`). Write `tests/test_config_prod.py`.
  accept: cd backend && uv run pytest tests/test_config_prod.py -q
- [ ] T53: Root `Dockerfile` and `.dockerignore` exactly as docs/deployment.md §image says (multi-stage, uv, python slim pinned, uid 10001, port 8000, contract at `/contract`). Write `backend/tests/test_dockerfile.py` that reads the Dockerfile as text and asserts USER 10001, EXPOSE 8000, no `:latest`, that `contract/` is copied, and that `.dockerignore` excludes `.git`, `.agent` and `.venv`.
  accept: uvx --from hadolint-py hadolint --failure-threshold warning Dockerfile && cd backend && uv run pytest tests/test_dockerfile.py -q
- [ ] T54: CI workflow `.github/workflows/ci.yml`: on pull_request and on push to `main` and `agent/**` (the harness waits for CI on agent branches), on ubuntu-latest: checkout, install uv (`astral-sh/setup-uv`, pinned major), Node 22, `uv tool install bandit`, then `make setup && make check`. Pin every action to a version tag. Also run `hadolint` on the Dockerfile.
  accept: uvx --from actionlint-py actionlint .github/workflows/ci.yml
- [ ] T55: `backend/scripts/next_version.py` (stdlib only): given the existing tags and the commit message, print the next version per SPEC 9.3 (`v0.1.0` when there are no `v*` tags; ignore tags that are not `vX.Y.Z`; `[minor]` resets patch; `[major]` resets minor and patch). Write `tests/test_next_version.py` with those cases.
  accept: cd backend && uv run pytest tests/test_next_version.py -q
- [ ] T56: Release workflow `.github/workflows/release.yml` (SPEC 9.3): on push to main; `permissions: contents: write, packages: write`; concurrency group `release` (no cancel); full-history checkout; `make check`; next version from `next_version.py`; `docker/login-action`, `docker/setup-buildx-action` and `docker/build-push-action` (pinned) pushing `ghcr.io/cecedabro/weatherstation:X.Y.Z` and `:sha-<short>`; then create and push tag `vX.Y.Z`. A first job `uses: ./.github/workflows/migrations.yml` (do not edit that file) and the build job `needs` it, so a failing migration check blocks the release. Skip everything when the commit message contains `[skip release]`.
  accept: uvx --from actionlint-py actionlint .github/workflows/release.yml
- [ ] T60: Image smoke test in CI, `.github/workflows/image.yml` (the devbox has no Docker; CI is the Docker environment): on pull_request and on push to `agent/**`, build the image with buildx (load, no push), start `postgres:16` as a service container, run `alembic upgrade head` in the image, then run the container with `--read-only --tmpfs /tmp --user 10001 -e APP_ENV=production` (non-default test secrets), wait for it, and `curl -fsS` `/healthz`, `/readyz` and `/`. Fail if any step fails. Put the shell steps in `scripts/smoke-image.sh` (bash, `set -euo pipefail`, shellcheck clean).
  accept: uvx --from actionlint-py actionlint .github/workflows/image.yml && shellcheck scripts/smoke-image.sh
- [ ] T57: `deploy/` part 1: `Makefile` (`validate` target), `kustomization.yaml`, `namespace.yaml`, and `app.yaml` with the Deployment and Service exactly per docs/deployment.md (initContainers wait-for-db using `pg_isready` from the Postgres image, then `alembic upgrade head` from the app image; probes; security context; resources; `/tmp` emptyDir; image marker comment). Postgres comes in T58, so validation must pass without it.
  accept: make -C deploy validate
- [ ] T58: `deploy/` part 2: `postgres.yaml` (StatefulSet `weatherstation-db`, `postgres:16` pinned to a minor tag, `envFrom` Secret `weatherstation-db`, `PGDATA` in a subdirectory, 5Gi Longhorn `volumeClaimTemplate`, `pg_isready` probes, resources, fsGroup 999, avoid k3s-gpu-01) and its Service; add it to the kustomization. Add `deploy/secret.example.yaml` with both Secrets and `REPLACE_ME` values (not in the kustomization).
  accept: make -C deploy validate && grep -q REPLACE_ME deploy/secret.example.yaml
- [ ] T59: README "Deploying" section: how a merge becomes a release and a rollout, the image name, the env vars and secrets, `[minor]`/`[major]`/`[skip release]`, and that the live manifests are in the homelab repo. Keep it short; do not change other sections.
  accept: grep -q 'skip release' README.md && grep -q 'ghcr.io/cecedabro/weatherstation' README.md

## Later (not for the loop yet)
Gateway (SPEC 7) and firmware (SPEC 8) tasks get added once the sensor hardware is
decided. Once the devbox has a Docker sandbox: build the image locally and smoke-test
`/healthz` and `/readyz` against a throwaway Postgres; a nightly `pg_dump` CronJob.
