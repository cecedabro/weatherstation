# PLAN: Sensors page, step by step (SPEC §11)

The page, its routes and its template are already built by the human: `backend/app/sensors.py` (glue at the
bottom), `backend/app/stats.py` (routes at the bottom) and `backend/app/templates/sensors.html`. What is left are
small functions that return empty placeholders now. Each task fills in 1–3 of them; the steps are in their
docstrings: `grep -n "TODO (task Sxx)" backend/app/*.py`. Each task has its own step test in
`backend/tests/judge/test_step_sensors.py` (named `test_sxx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the functions the task names, and only their bodies. Keep the signatures and docstrings, but
  delete the "TODO (task Sxx)" line(s) you finish. Don't touch `page_context`, the routes, `CATEGORIES`, `RANGES`,
  `METRICS`, `View` or other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/sensors.py && uv run ruff check app/sensors.py`.
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] S01: In backend/app/stats.py fill in `summarize` as its docstring says
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s01
- [x] S02: In backend/app/stats.py fill in `daily_stats` as its docstring says
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s02
- [x] S03: In backend/app/sensors.py fill in `parse_compare` and `parse_view`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s03
- [x] S04: In backend/app/sensors.py fill in `view_href`, `range_window` and `daily_days`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s04
- [x] S05: In backend/app/sensors.py fill in `latest` and `tiles`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s05
- [x] S06: In backend/app/sensors.py fill in `merge_daily`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s06
- [ ] S07: In backend/app/sensors.py fill in `soil_rows`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s07
- [ ] S08: In backend/app/sensors.py fill in `compare_rows` and `csv_href`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_sensors.py -q -k s08
- [ ] S09: Make the whole-page tests pass: run them, read the first failing assert, fix only the function bodies from S01–S08
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_sensors.py tests/judge/test_step_sensors.py -q
