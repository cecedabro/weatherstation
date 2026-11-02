# SPEC (human-owned — do not edit)

Requirements as testable sentences. Each section maps to one or more tasks in
`PLAN.md`. "The system" means the backend unless stated. All times UTC.

## 1. Skeleton and health
- 1.1 `make check` passes on the skeleton: ruff clean, mypy clean, pytest green.
- 1.2 `GET /healthz` returns HTTP 200 and `{"status": "ok"}`.
- 1.3 The app reads config from env vars (`DATABASE_URL`, `INGEST_TOKEN`,
      `ADMIN_USER`, `ADMIN_PASSWORD`) with defaults suitable for local tests.

- 1.4 With `APP_ENV=production`, the app refuses to start when `INGEST_TOKEN` or
      `ADMIN_PASSWORD` still has its development default.
- 1.5 `GET /readyz` returns 200 `{"status": "ready"}` when the database answers a
      trivial query, and 503 `{"status": "unavailable"}` when it does not.

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

- 3.6 The bearer token is compared in constant time.
- 3.7 A request body larger than 1 MiB returns 413 and stores nothing.
- 3.8 More than 60 ingest requests per minute from one client return 429. The
      client is `CF-Connecting-IP` when present (Cloudflare tunnel), else the peer address.

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

## 9. Deployment (round 4)
- 9.1 The root `Dockerfile` builds one image, `ghcr.io/cecedabro/weatherstation`, that
      runs the backend on port 8000 as uid 10001 and works with a read-only root
      filesystem (only `/tmp` writable).
- 9.2 CI (GitHub Actions) runs `make check` on every pull request and push to `main`.
- 9.3 Every push to `main` that passes `make check` is a release: the next version
      `vX.Y.Z` (patch +1; `[minor]` or `[major]` in the commit message bumps more;
      the first is `v0.1.0`), images `:X.Y.Z` and `:sha-<short>`, then the git tag.
      Flux deploys `X.Y.Z` automatically.
- 9.4 `deploy/` has Kustomize manifests (namespace `weatherstation`, app Deployment
      with a migrate initContainer, Service, Postgres StatefulSet + Service + 5 Gi
      Longhorn PVC) that pass `kustomize build | kubeconform -strict`. They are drafts:
      the homelab repo holds the live copy.
- 9.5 Secrets are referenced by name (`weatherstation-app`, `weatherstation-db`),
      never inline; `deploy/secret.example.yaml` documents every key.

## 10. Website pages (round 3)
- 10.1 Every public page shares one layout with a navigation bar linking Home `/`,
       Weather `/weather`, Soil `/soil`, History `/history` and About `/about`; the
       current page's link has `aria-current="page"`.
- 10.2 `/weather` shows, per weather node, every current metric with its unit and a
       chart per metric with a day / week / month selector.
- 10.3 `/soil` lists every soil node as a card with moisture, soil temperature,
       battery, online state and last seen; moisture below 25 % shows "needs water".
- 10.4 `/soil/{node_id}` shows one bed's current values and moisture and soil
       temperature charts; an unknown node gives the styled 404 page.
- 10.5 `/history` shows daily summaries for the last 30 days: min / max / average
       temperature, total rain and average humidity; no data → a friendly state.
- 10.6 `GET /api/v1/daily?node=&days=` returns one row per UTC day with `date`,
       `temp_min`, `temp_max`, `temp_avg`, `rain_total`, `humidity_avg`.
       `days` is 1–366 (default 30), otherwise 400.
- 10.7 `GET /api/v1/export.csv?node=&metric=&from=&to=` downloads raw readings as
       CSV with the header `ts,node_id,metric,value`.
- 10.8 `/about` explains the station and the data path and lists the known nodes.
- 10.9 Unknown URLs return a styled HTML 404 page with a link home; `/api/` paths
       keep JSON errors.
- 10.10 The current conditions on `/` refresh every 60 s through HTMX from
        `GET /partials/current` (an HTML fragment) without a full page reload.
- 10.11 Times on pages are shown in Europe/Amsterdam with a relative age
        ("5 min ago"); wind direction is shown as a compass point next to degrees.
- 10.12 Every page has its own `<title>` and meta description, a favicon, and
        `<nav>` / `<main>` / `<footer>` landmarks; charts have text alternatives and
        every form control has a label.
- 10.13 A node whose last reading is older than 15 minutes is shown as
        "offline since …", never as live.
- 10.14 `/` shows a frost warning when any weather node reads ≤ 2.0 °C, the rain
        total of the last 24 h, and how many beds need water.
- 10.15 Every response sends `X-Content-Type-Options`, `Referrer-Policy`,
        `X-Frame-Options` and a same-origin `Content-Security-Policy`; pages use no
        inline scripts.
