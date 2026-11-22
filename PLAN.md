# PLAN: Growth, best spot and advisor search, step by step (SPEC §16, roadmap loop A)

The pages, routes and templates are already built by the human (glue at the bottom of `backend/app/growth.py` and `backend/app/advisor.py`).
What is left are small functions that return placeholders now. Each task fills in 1–2 of them; the steps are in
their docstrings: `grep -n "TODO (task A" backend/app/growth.py backend/app/advisor.py`. Each task has its own step test in
`backend/tests/judge/test_step_growth.py` (named `test_axx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the bodies of the functions the task names. Keep signatures and docstrings, but delete the
  "TODO (task Axx)" line(s) you finish. Don't touch the glue (everything under `# -- glue (done)`), constants or
  other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/<file>.py && uv run ruff check app/<file>.py` (the file the task names).
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] A01: In backend/app/growth.py fill in `daily_gdd`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a01
- [x] A02: In backend/app/growth.py fill in `local_daily_temps`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a02
- [x] A03: In backend/app/growth.py fill in `gdd_series`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a03
- [x] A04: In backend/app/growth.py fill in `progress`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a04
- [x] A05: In backend/app/growth.py fill in `harvest_eta` (follow the 3 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a05
- [x] A06: In backend/app/growth.py fill in `sun_fit` (follow the 4 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a06
- [x] A07: In backend/app/growth.py fill in `moisture_fit` (follow the 3 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a07
- [x] A08: In backend/app/growth.py fill in `score_spot`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a08
- [x] A09: In backend/app/growth.py fill in `best_spots`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a09
- [x] A10: In backend/app/advisor.py fill in `tokenize`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a10
- [ ] A11: In backend/app/advisor.py fill in `rank_sources` (follow the 3 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a11
- [ ] A12: In backend/app/advisor.py fill in `snippet` (follow the 4 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a12
- [ ] A13: In backend/app/advisor.py fill in `validate_source` (follow the 6 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_growth.py -q -k a13
- [ ] A14: Make the whole-feature tests pass: run them, read the first failing assert, fix only the function bodies from A01–A13
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_growth.py tests/judge/test_step_growth.py -q
