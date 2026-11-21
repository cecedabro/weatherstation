# PLAN: garden sensors page

One task per line. `accept:` must exit 0, then the harness runs `make check`. Read AGENTS.md,
docs/design.md and docs/frontend.md first. Pages use only `templates/ui.html` components (no CSS).
The acceptance tests in `backend/tests/judge/` are the human's; write your own tests in `backend/tests/`.

## Sensors (SPEC §11)
- [ ] S01: `GET /api/v1/summary` per SPEC 11.3 in a new module `app/stats.py` (router included in `app/main.py`). Put the query in a pure-ish function `summarize(db, node, metric, start, end) -> dict` that the page reuses. Reuse `_parse_dt` from `app/readapi.py` for dates.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k summary
- [ ] S02: `GET /api/v1/daily_stats` per SPEC 11.4 in `app/stats.py`, with a function `daily_stats(db, node, metric, days)` the page reuses (UTC days, oldest first, empty days left out).
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k daily_stats
- [ ] S03: New `app/sensors.py` router with the SPEC 11.7 redirects (301) for `/weather`, `/history`, `/soil`, `/soil/{node_id}`. Include it in `app/main.py`.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k old_pages
- [ ] S04: `GET /sensors` in `app/sensors.py` (delete the placeholder route in `app/web.py`) and `templates/sensors.html`: a pure function `parse_view(cat, range, node, compare, weather_nodes)` applies SPEC 11.1 defaults and fallbacks; the page has `ui.page_head("Sensors", …)`, `ui.tabs` for Air/Soil/Rain/Wind, `ui.seg` for the range (24h, 7d, 30d, 90d, 365d labelled Day, Week, Month, Season, Year) and `ui.seg` for the weather node; every link keeps the other parameters. No nodes → `ui.empty`. Render with `render(request, "sensors.html", active="sensors", …)`.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k "default_is_air or links_keep or node_picker or unknown_params or empty_station"
- [ ] S05: Air and wind content per SPEC 11.2: per metric a card with `ui.stat` tiles (latest, min, max, average over the range via `summarize`) and a `ui.chart` for the range (`range=` the chosen range). Wind direction shows the compass point (`compass` filter) next to the degrees.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k "air_tiles or wind_compass"
- [ ] S06: Rain (bars via `kind="bar"`, a "Total" tile with the sum) and soil (one chart per soil metric with a line per soil node, and a table of each node's latest moisture and soil temperature) per SPEC 11.2.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k "rain_is_bars or soil_one_line"
- [ ] S07: Daily table per SPEC 11.4 with `ui.table` (newest first, at most 31 days, min/max/avg per metric, rain total) under the charts.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k daily_table
- [ ] S08: Compare days per SPEC 11.5: a GET form with up to three `ui.field(..., type="date")` inputs that builds `compare=`; when set, a "Compare days" card with `ui.chart(..., x="hour")` for the category's first metric and a `ui.table` of each day's min/max/avg. Invalid dates are ignored.
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k compare_days
- [ ] S09: "Download CSV" link per metric per SPEC 11.6 (node, metric, from, to of the range).
  accept: cd backend && uv run pytest tests/judge/test_sensors.py -q -k csv_links
- [ ] S10: Tidy up: `app/sensors.py` under ~300 lines, unit tests for `parse_view`, all judge tests green, `make check` green (coverage ≥ 90 %).
  accept: cd backend && uv run pytest tests/judge -q
