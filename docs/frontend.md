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

## §charts
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
