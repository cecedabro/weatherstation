# Backend

FastAPI app that ingests readings, stores them in Postgres, serves the read API
and the website. Python 3.11+, managed with `uv`. This doc is prescriptive for
code; visual choices live in `docs/frontend.md` and `docs/design.md`.

## Allowed dependencies (pin versions)
fastapi, uvicorn[standard], sqlalchemy>=2, alembic, psycopg[binary], pydantic>=2,
jinja2, python-multipart, jsonschema, httpx (tests), pytest, pytest-asyncio,
ruff, mypy, pytest-cov, and `pgserver` (dev-only: a throwaway Postgres for tests). Add nothing else without noting why in PROGRESS.md.

## Layout (inside `backend/`)
```
backend/
  pyproject.toml        # uv project; ruff + mypy + pytest config
  app/
    main.py             # FastAPI app factory + router includes
    config.py           # Settings from env (pydantic BaseSettings)
    db.py               # engine, session dependency
    models.py           # SQLAlchemy models
    schema.py           # loads ../contract/reading.schema.json; validation helpers
    ingest.py           # POST /api/v1/readings
    readapi.py          # /current, /series, /nodes
    web.py              # HTML routes (Jinja + HTMX)
    admin.py            # /admin
    templates/ , static/
  alembic/              # migrations
  tests/
```

## §skeleton (T01)
- `uv init`, add deps, configure ruff (line length 100), mypy (strict on `app`),
  pytest. `app/main.py` exposes `app = create_app()`. `make check` must pass with
  an app that has only `/healthz` stubbed returning 200. Commit a working empty shell.

## §config (T02)
- `Settings(BaseSettings)` reads `DATABASE_URL` (default
  `postgresql+psycopg://weather:weather@localhost:5432/weather`), `INGEST_TOKEN`
  (default `dev-token`), `ADMIN_USER`/`ADMIN_PASSWORD` (default `admin`/`admin`).
- `/healthz` must not touch the database. No SQLite anywhere: production and
  tests are both Postgres.

## §storage (T03)
- Tables (names are yours; shape is fixed by SPEC 2):
  - `node(node_id pk, node_type, first_seen, last_seen, last_battery_v, last_rssi_dbm)`
  - `reading(id, node_id fk, metric, ts, value)` with a unique constraint on
    `(node_id, metric, ts)` to make upsert possible and prevent duplicates.
  - Index `(node_id, metric, ts)` for series queries.
- Alembic migration generates these. `make migrate` is idempotent.
- Tests run against a real Postgres started by `pgserver` (see `docs/testing.md`).
  Never mock the DB for storage tests. If `DATABASE_URL` is already set to a
  Postgres, tests may use that instead.

## §ingest (T05–T07)
- Validate each batch against the JSON schema (`app/schema.py`), then the
  node_type/metric agreement rule (weather metrics only for weather, etc.).
- Upsert the node row (update last_seen/battery/rssi), insert metric rows with
  `INSERT ... ON CONFLICT (node_id, metric, ts) DO UPDATE`.
- Response and status codes exactly as `contract/README.md` says.
- Keep the whole POST in one transaction per batch; one bad batch never rolls
  back a good one in the same request.

## read API (T08–T10)
- `/series` buckets: use Postgres `date_trunc` (or `date_bin` for 5m) and
  `avg(value)`, except `metric = 'rain_mm'` which uses `sum(value)`.
- `/nodes` must return exactly the contract fields (contract tests enforce this).
- Validate query params; bad `step` or non-RFC3339 dates → 400 with a JSON error.

## Testing
See `docs/testing.md`. For every endpoint, test one success and at least one
failure path, asserting on response body and status, against a real app via
`fastapi.testclient.TestClient`. Storage and API tests use a real Postgres.
