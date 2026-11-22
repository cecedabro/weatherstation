# PLAN: Seed log, step by step (SPEC §13, roadmap loop P)

The pages, routes and templates are already built by the human (glue at the bottom of `backend/app/seeds.py`).
What is left are small functions that return placeholders now. Each task fills in 1–2 of them; the steps are in
their docstrings: `grep -n "TODO (task Pxx)" backend/app/seeds.py`. Each task has its own step test in
`backend/tests/judge/test_step_seeds.py` (named `test_pxx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the bodies of the functions the task names. Keep signatures and docstrings, but delete the
  "TODO (task Pxx)" line(s) you finish. Don't touch the glue (everything under `# -- glue (done)`), constants or
  other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/seeds.py && uv run ruff check app/seeds.py`.
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] P01: In backend/app/seeds.py fill in `parse_months` and `sowable` (follow the 4 steps in the docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p01
- [x] P02: In backend/app/seeds.py fill in `expected_harvest` and `harvest_text`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p02
- [x] P03: In backend/app/seeds.py fill in `validate_planting` (follow the 7 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p03
- [x] P04: In backend/app/seeds.py fill in `next_status` and `timeline`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p04
- [x] P05: In backend/app/seeds.py fill in `rotation_warning` (follow the 3 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p05
- [x] P06: In backend/app/seeds.py fill in `find_plantings`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p06
- [ ] P07: In backend/app/seeds.py fill in `group_by_bed`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p07
- [ ] P08: In backend/app/seeds.py fill in `planting_json`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p08
- [ ] P09: In backend/app/seeds.py fill in `seed_crops`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p09
- [ ] P10: In backend/app/seeds.py fill in `apply_form` and `set_status`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_seeds.py -q -k p10
- [ ] P11: Make the whole-feature tests pass: run them, read the first failing assert, fix only the function bodies from P01–P10
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_seeds.py tests/judge/test_step_seeds.py -q
