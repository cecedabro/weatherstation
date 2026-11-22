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
- 9.6 A human-owned migration check (`tests/ci/check-migrations.sh`, workflow
      `migrations.yml`) passes: one Alembic head, empty DB → head, models match the
      migrations (`alembic check`), re-running is a no-op, downgrade to base and back,
      and data written by the last release survives the upgrade. No release when it fails.
- 9.5 Secrets are referenced by name (`weatherstation-app`, `weatherstation-db`),
      never inline; `deploy/secret.example.yaml` documents every key.

## 10. Website pages (round 3; partly replaced by §11)
Note: `/weather`, `/soil`, `/soil/{node_id}` and `/history` become redirects to `/sensors` (§11.7). The
current look is the design system in `docs/design.md` (§11.0).

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

## 11. Design system, sign-in and the Sensors page (garden v2)
- 11.0 (done by the human) One design system: `static/css/`, `templates/ui.html`, `/styleguide`. Pages use
       only its classes (tests/test_design_system.py). Private pages need sign-in (`app/auth.py`):
       `/garden`, `/seeds`, `/tasks`, `/species`, `/admin`; signed out they redirect to
       `/login?next=<path>`, and `/api/` paths answer 401. HTTP Basic with the admin credentials also works.
- 11.1 `GET /sensors` (public) has category tabs Air, Soil, Rain and Wind (`?cat=air|soil|rain|wind`,
       default `air`, unknown → `air`), a range switch (`?range=24h|7d|30d|90d|365d`, default `7d`,
       unknown → `7d`) and, for air, rain and wind, a node picker (`?node=`, default: the first weather node
       alphabetically). Tabs and switches are links that keep the other parameters.
- 11.2 Metrics per category: air = `temp_c`, `humidity_pct`, `pressure_hpa`; rain = `rain_mm`;
       wind = `wind_speed_ms`, `wind_dir_deg`; soil = `soil_moisture_pct`, `soil_temp_c` for every soil node
       (one chart per metric with a line per node). Each metric has a `ui.chart` for the chosen range
       (rain as bars) and stat tiles with the latest value plus min, max and average over the range
       (rain: total). Wind direction is shown as a compass point next to the degrees.
- 11.3 `GET /api/v1/summary?node=&metric=&from=&to=` returns
       `{"node","metric","count","min","max","avg","sum","first_ts","last_ts"}` over raw readings in
       `[from, to)`. No readings → `count` 0 and the other numbers `null`. Bad dates → 400. `from`/`to`
       default to the last 7 days.
- 11.4 Every category shows a daily table for the range (at most the last 31 days, newest first): one
       row per UTC day with min / max / avg per metric (rain: total), from
       `GET /api/v1/daily_stats?node=&metric=&days=` → `[{"date","min","max","avg","sum","count"}]`,
       oldest first, `days` 1–366 (default 30), otherwise 400. Days without readings are left out.
- 11.5 Compare days: `?compare=YYYY-MM-DD,YYYY-MM-DD[,YYYY-MM-DD]` (1–3 valid dates; invalid ones are
       ignored) adds a "Compare days" card with a `ui.chart(..., x="hour")` for the category's first metric
       and a table with each day's min / max / avg. A small form with date inputs builds this parameter.
- 11.6 A "Download CSV" link per metric points at `/api/v1/export.csv` with the node, metric and range.
- 11.7 `/weather` → 301 `/sensors?cat=air`, `/history` → 301 `/sensors?cat=air&range=30d`,
       `/soil` → 301 `/sensors?cat=soil`, `/soil/{node_id}` → 301 `/sensors?cat=soil&node={node_id}`.
- 11.8 No nodes of a category → `ui.empty` with a friendly text, never an error. The page has
       `<title>Sensors · …` and works at 360 px.

## 12. Garden map (later; the human builds the 3D core first — plan in docs/roadmap.md)
`GET /garden`: a 3D map of the plot from `garden_object` rows (beds, garden house, compost, paths,
trees, water, fences, sensors). Objects can be added, moved, rotated and resized, and each kind has its
own properties (`props`). Sensors link to a node; soil readings colour the ground between sensors.

## 13. Seed log (later — plan in docs/roadmap.md)
`GET /seeds`: plantings (`planting` rows) placed on the map by bed or by point, with sown date, status
timeline and expected harvest.

## 14. Tasks (private)
- 14.1 `GET /tasks` lists tasks with tabs Open / Done / All (`?status=open|done|all`, default open) that
       show counts. Order: urgency (critical, high, normal, low), then deadline (soonest first, none last),
       then newest first. Filters: `?category=` (one of the categories) and `?q=` (case-insensitive match
       in title or notes). No tasks → `ui.empty` with a "New task" button.
- 14.2 Each task shows its title, an urgency chip, the category, the deadline as text — "due today",
       "due tomorrow", "due in N days", "overdue by N days" (overdue open tasks also get a `bad` chip) —
       the pinned object's name when `object_id` is set, and buttons Done (or Reopen) and Edit.
       "Today" is the Europe/Amsterdam date.
- 14.3 `GET /tasks/new` and `GET /tasks/{id}/edit` show the form (title, notes, category, urgency,
       deadline, object). `POST /tasks` creates and `POST /tasks/{id}` updates. Validation: title 1–120
       characters after trimming; notes ≤ 2000; category in `TASK_CATEGORIES`; urgency in
       `TASK_URGENCIES`; deadline empty or `YYYY-MM-DD`; object empty or an existing `garden_object` id.
       Errors → 400, the form again with the message next to the field and the typed values kept.
       Success → 303 to `/tasks`.
- 14.4 `POST /tasks/{id}/done` sets status done and `done_at`; `POST /tasks/{id}/reopen` sets it open and
       clears `done_at`; `POST /tasks/{id}/delete` deletes. All → 303 to `/tasks`. Unknown id → 404.
- 14.5 `GET /api/v1/tasks?status=open|done|all` (private, default open) returns
       `[{"id","title","notes","category","urgency","status","deadline","object_id","x","y","created_at","done_at"}]`
       in the §14.1 order; dates ISO 8601.
- 14.6 `GET /tasks` shows three `ui.stat` tiles at the top, labelled "Open", "Overdue" and "Due this week"
       (open tasks with a deadline from today to today + 6 days).

## 15. Species (private)
- 15.1 `GET /species` has tabs Found (species with at least one sighting) and Catalogue (`common` true),
       `?tab=found|catalogue` (default found), search `?q=` (name or latin, case-insensitive) and
       `?verdict=` filter. Empty → `ui.empty` with a "New species" button.
- 15.2 A row shows name, latin name, a verdict chip (harmful and invasive → bad, beneficial → ok,
       neutral → info, unknown → off), kind, number of sightings, last seen date, and for harmful or
       invasive species with sightings not marked removed: a warn chip "N to remove".
- 15.3 `GET /species/{id}` shows the details, description and all sightings newest first (date, count,
       notes, object name, removed state, photo thumbnail), and a form to add a sighting. Unknown → 404.
- 15.4 `GET /species/new`, `POST /species` create; `GET /species/{id}/edit`, `POST /species/{id}` update;
       `POST /species/{id}/delete` deletes with its sightings. Validation: name 1–120 (unique,
       case-insensitive), latin ≤ 120, kind in `SPECIES_KINDS`, verdict in `SPECIES_VERDICTS`, description
       ≤ 4000. Errors → 400 with the form again; success → 303 to the species page.
- 15.5 `POST /species/{id}/sightings` (multipart) adds a sighting: `seen_on` required date, `count`
       empty or ≥ 1, notes ≤ 2000, `removed` checkbox, `object_id` optional existing object, `photo`
       optional JPEG/PNG/WebP ≤ 8 MB (checked by content, not by name). The photo is saved as
       `MEDIA_DIR/sightings/<random hex>.<ext>` and served by `GET /media/sightings/<name>` (signed-in only;
       names other than `<hex>.<jpg|png|webp>` → 404). Success → 303 to the species page.
- 15.6 `POST /sightings/{id}/removed` toggles `removed`; `POST /sightings/{id}/delete` deletes (and its
       photo). Both → 303 to the species page; unknown → 404.
- 15.7 The catalogue is seeded from `backend/app/data/common_species.json` by `seed_catalogue(db)`: it
       inserts entries whose name is not there yet (idempotent) and runs on app startup.
- 15.8 `GET /api/v1/sightings` (private) returns `[{"id","species_id","species","verdict","seen_on",
       "x","y","object_id","removed"}]`, newest first.

## 16. Growth model and advisor (later — plan in docs/roadmap.md)
Growth from growing degree days on the station's own temperatures and the `crop` table; a suitability
score per bed from soil readings; an optional local-LLM advisor (`LLM_BASE_URL`) that may only use the
`source` table and the computed numbers, and always cites them.
