# Frontend (website)

Server-rendered Jinja2 templates served by the FastAPI backend, with HTMX for
interactivity. No SPA, no build step. You own all visual design — read
`docs/design.md` for the Frutiger Aero brief. This doc fixes only structure and
the data it must show.

## Rules
- HTML comes from Jinja templates in `backend/app/templates/`. Static assets
  (CSS, the chart library, any JS) in `backend/app/static/`, served by FastAPI.
- Use HTMX (vendored, not from a CDN — the site must work without internet to
  third parties) for partial updates. Load HTMX and the chart library from
  `static/`; download and commit those files.
- Progressive enhancement: the page must render useful content server-side.
  Charts may hydrate client-side, but "no JS" still shows current numbers.
- Mobile first: usable at 360px wide, no horizontal scroll (SPEC 5.4).
- Accessibility: semantic HTML, label every control, sufficient contrast, alt text.

## Pages
- `/` (T12–T13): header, current conditions for each weather node (big readable
  numbers), latest soil readings, and a history chart section.
- The chart section (T14) has a range selector day/week/month that re-requests
  `/api/v1/series` with the matching `from`/`step` (day→5m, week→1h, month→1d)
  and redraws. HTMX swap or a small fetch+redraw, your choice.
- Empty state (SPEC 5.3): when `/current` is empty, show a friendly placeholder,
  never a stack trace or a broken chart.

## §vendor
Already in `backend/app/static/vendor/` (with their licences): `uPlot.iife.min.js`,
`uPlot.min.css` (uPlot 1.6.32) and `htmx.min.js` (htmx 2.0.11). If you ever need to
download a package, do it inside the repo: `mkdir -p .agent/tmp && cd .agent/tmp &&
npm pack <name>`. Never use `/tmp`; the agent is not allowed outside the repo.

## §pages
Public pages (SPEC 10): `/` home, `/weather`, `/soil`, `/soil/{node_id}`,
`/history`, `/about`, plus a styled 404. All extend `base.html` and share the nav.
Route handlers live in `app/web.py` (split into more modules if it grows past ~300
lines). Shared formatting (compass, local time, "5 min ago") lives in `app/fmt.py`
as Jinja filters. Keep page logic in Python functions you can unit-test; templates
only display. No inline `<script>`: all JS lives in `static/`.

## §charts
- The library is uPlot 1.6.32, already vendored (see §vendor). Do not add another.
- Chart contract: an element with `data-chart`, `data-node` and `data-metric` is a
  chart. `static/chart.js` finds them all, fetches `/api/v1/series`, and draws them.
  The range buttons in the same `<section>` pick `from`/`to`/`step`. `rain_mm` is
  drawn as bars, everything else as lines.
- Pick ONE small charting library (e.g. uPlot or Chart.js). Vendor it into
  `static/vendor/`. Note the choice and version in PROGRESS.md. Do not add a
  second chart library later.
- A chart reads JSON from `/api/v1/series`. Keep the data-fetching glue in one
  small JS module; keep it under ~150 lines.

## §admin (T15)
- `/admin` behind HTTP Basic auth. A table of nodes with last_seen, online dot,
  battery, RSSI, 24h reading count; highlight offline (>15min) and low battery
  (<3.4V). Plain and functional; the Frutiger Aero styling is nice-to-have here.

## Testing
Render routes via TestClient and assert on the HTML: that the expected node
names/metric labels appear, that the empty state renders when there is no data,
and that the chart container and its data endpoint are wired. Don't assert exact
pixel styling. See `docs/testing.md`.
