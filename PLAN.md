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
- [~] T10: GET /api/v1/nodes per SPEC 4.3 (must satisfy the contract tests). — skipped: $ cd backend && uv run pytest tests/test_nodes.py ../contract/tests -q  (exit 1)
  accept: cd backend && uv run pytest tests/test_nodes.py ../contract/tests -q

## Website
- [x] T11: Base template and one stylesheet of design tokens, ported from the root index.html. See docs/frontend.md, docs/design.md.
  accept: cd backend && uv run pytest tests/test_base_template.py -q
- [x] T12: GET / page with header, layout and the "no readings yet" empty state per SPEC 5.1, 5.3, 5.4.
  accept: cd backend && uv run pytest tests/test_page_home.py -q
- [x] T13: Current-conditions and latest-soil sections on / per SPEC 5.1.
  accept: cd backend && uv run pytest tests/test_page_current.py -q
- [~] T14: History chart with day/week/month selector per SPEC 5.2. See docs/frontend.md §charts. — skipped: $ cd backend && uv run pytest tests/test_page_chart.py -q  (exit 4)
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
- [~] T18: Vendor uPlot into `app/static/vendor/` (see docs/frontend.md §charts) and serve it. Note the version in PROGRESS.md. Test that `/static/vendor/uPlot.iife.min.js` and the CSS return 200. — skipped: agent made no changes
  accept: cd backend && uv run pytest tests/test_vendor_assets.py -q
- [ ] T19: Chart section on `/` (SPEC 5.2): a container, and a day/week/month selector rendered server-side as links or buttons carrying the `from`, `to` and `step` for `/api/v1/series` (day→5m, week→1h, month→1d). Write `tests/test_page_chart.py` asserting the container, the three selector options, and the exact series query values.
  accept: cd backend && uv run pytest tests/test_page_chart.py -q
- [ ] T20: `app/static/chart.js` (under 150 lines): fetch `/api/v1/series` for the selected range, draw it with uPlot, redraw on selector change, show a friendly message when the series is empty. Test (Python) that the page loads `chart.js` and that the file exists and mentions `/api/v1/series`.
  accept: cd backend && uv run pytest tests/test_chart_js.py -q

## Later (not for the loop yet)
Gateway (SPEC 7), firmware (SPEC 8) and deployment (SPEC 9) tasks get added once
the website works and the sensor hardware is decided.
