# Frontend (website)

Server-rendered Jinja2 + HTMX, served by the FastAPI app. No SPA, no build step. The look is finished:
read `docs/design.md` first and build pages only from `templates/ui.html` components.

## Structure
- Routes: one module per area in `backend/app/` (`web.py` overview/about, `sensors.py`, `tasks.py`,
  `species.py`, …). Include new routers in `app/main.py`. Keep a module under ~300 lines.
- Render every page through `app.templating.render(request, "<name>.html", active="<nav key>", **ctx)`.
- Private pages take `user: str = RequireUser` (from `app.auth`). Signed out, HTML pages redirect to
  `/login?next=…` and `/api/` paths answer 401. Tests sign in with HTTP Basic:
  `client.get(path, auth=(Settings().ADMIN_USER, Settings().ADMIN_PASSWORD))`.
- Forms: plain HTML `<form method="post">` with `ui.field(...)`. On success redirect with 303. On a
  validation error re-render the same template with status 400 and the message in `ui.field(error=…)`.
  Read forms with FastAPI `Form(...)`; validate in a small pure function you can unit-test.
- Page logic lives in Python functions; templates only display. Shared formatting is in `app/fmt.py`
  (`local_time`, `ago`, `compass`).
- HTMX (vendored) for partial updates; no inline `<script>`. Page JS, if any: `static/js/pages/`.
- Times: stored in UTC; shown in Europe/Amsterdam via the `local_time` filter or `ui.when(dt)`.

## Charts
Use `ui.chart(title, [(node, metric, label), ...], unit=, kind="line|bar|area", range=)`. `charts.js`
fetches `/api/v1/series` and draws it. Range buttons: put the charts and a
`ui.seg_buttons([("24h","Day"),("7d","Week"),("30d","Month"),("90d","Season"),("365d","Year")], current)`
inside one element with the `data-chart-group` attribute. Compare days: `x="hour"` with series
`(node, metric, label, "YYYY-MM-DD")`. Never add another chart library.

## §vendor
`backend/app/static/vendor/`: uPlot 1.6.32 and htmx 2.0.11 (with licences). The 3D map will add
three.js there (human task). Downloads only inside the repo (`.agent/tmp/`), never `/tmp`.

## Testing
Render routes with TestClient and assert on the HTML: names, values, empty states, links, status codes,
redirects. Don't assert styling. See `docs/testing.md`.
