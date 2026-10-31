# SPEC (human-owned — do not edit)

Requirements as testable sentences. Each section maps to one or more tasks in
`PLAN.md`. "The system" means the backend unless stated. All times UTC.

## 1. Skeleton and health
- 1.1 `make check` passes on the skeleton: ruff clean, mypy clean, pytest green.
- 1.2 `GET /healthz` returns HTTP 200 and `{"status": "ok"}`.
- 1.3 The app reads config from env vars (`DATABASE_URL`, `INGEST_TOKEN`,
      `ADMIN_USER`, `ADMIN_PASSWORD`) with defaults suitable for local tests.

## 2. Storage
- 2.1 An Alembic migration creates tables to store readings as (node, metric,
      ts, value) plus a node registry. Running `make migrate` on an empty
      Postgres succeeds and is idempotent on re-run.
- 2.2 A reading batch is stored as one row per metric value.
- 2.3 Re-storing a batch with the same (node_id, ts) does not create duplicate
      metric rows (upsert).

## 3. Ingest API (see contract/README.md)
- 3.1 `POST /api/v1/readings` with a valid body and correct bearer token stores
      the readings and returns `{"accepted": n, "rejected": []}`.
- 3.2 A batch that fails schema validation is rejected per-item (its index and a
      reason appear in `rejected`), without failing the whole request, as long as
      the envelope is well-formed.
- 3.3 A batch whose metrics do not match its `node_type` is rejected (soil metric
      on a weather node, or vice versa).
- 3.4 A request with a missing or wrong bearer token returns 401 and stores nothing.
- 3.5 A malformed envelope (not JSON, or no `readings` array) returns 400.

## 4. Read API
- 4.1 `GET /api/v1/current` returns the latest reading per node.
- 4.2 `GET /api/v1/series?node=&metric=&from=&to=&step=` returns time-ordered
      points. `step=raw` returns stored points; `5m|1h|1d` return averages per
      bucket (sum for `rain_mm`). Out-of-range or unknown node/metric → empty list, 200.
- 4.3 `GET /api/v1/nodes` returns the contract fields (see contract tests),
      with `online` true iff `last_seen` is within 15 minutes of now.
- 4.4 Invalid query params (bad `step`, non-RFC3339 dates) return 400.

## 5. Public website
- 5.1 `GET /` renders an HTML page showing current conditions for each weather
      node and the latest soil readings.
- 5.2 The page shows at least one time-series chart that loads data from
      `/api/v1/series` (via HTMX or a small JS fetch), with a range selector
      (day / week / month).
- 5.3 The site degrades gracefully when there is no data yet (no error page;
      a friendly "no readings yet" state).
- 5.4 Pages are responsive and usable on a phone screen (360px wide) without
      horizontal scrolling.

## 6. Admin view (private)
- 6.1 `GET /admin` requires HTTP Basic auth (`ADMIN_USER` / `ADMIN_PASSWORD`);
      wrong or missing credentials → 401.
- 6.2 It lists every node with `last_seen`, online state, last battery voltage
      and RSSI, and flags nodes offline > 15 min and batteries < 3.4 V.
- 6.3 It shows, per node, the count of readings in the last 24 h (to spot gaps).

## 7. Gateway (Pi)
- 7.1 Subscribes to `garden/+/reading`, validates each message against the
      schema, and batches valid readings.
- 7.2 POSTs batches to the backend with the bearer token; on network failure it
      buffers to local disk and retries, losing no readings across a restart.
- 7.3 Invalid messages are dropped and counted, never crash the service.

## 8. Firmware (ESP32, Arduino/PlatformIO)
- 8.1 The project builds for a `weather` node and a `soil` node env with
      `pio run` (host build of the pure logic must compile and unit-test without
      hardware — see docs/firmware.md).
- 8.2 Reading encoding (sensor values → the JSON batch) is in a pure function
      unit-tested on the host; the encoded JSON validates against the schema.
- 8.3 A node connects to Wi-Fi, publishes to the right topic at a configurable
      interval, and sleeps between readings (deep sleep for battery/soil nodes).

## 9. Deployment
- 9.1 `deploy/` has Kustomize manifests for the backend Deployment+Service,
      Postgres StatefulSet with a Longhorn PVC, and ingress via the existing
      Cloudflare tunnel to garden.cedricschippers.dev.
- 9.2 `kubeconform` passes on the rendered manifests (`make -C deploy validate`).
- 9.3 Secrets (`INGEST_TOKEN`, `ADMIN_PASSWORD`, DB password) are referenced from
      a Secret, never inline; a `*.example.yaml` documents the keys.
