# PLAN: Garden map data, step by step (SPEC §12, roadmap loop G)

The JSON routes are already built by the human: `backend/app/objects.py` (glue at the bottom). What is left are
small functions that return placeholders now. Each task fills in 1–2 of them; the steps are in their docstrings:
`grep -n "TODO (task Gxx)" backend/app/objects.py`. Each task has its own step test in
`backend/tests/judge/test_step_objects.py` (named `test_gxx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the bodies of the functions the task names. Keep signatures and docstrings, but delete the
  "TODO (task Gxx)" line(s) you finish. Don't touch the glue (everything under `# -- glue (done)`), constants or
  other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/objects.py && uv run ruff check app/objects.py`.
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] G01: In backend/app/objects.py fill in `clean_prop` (follow the 7 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g01
- [x] G02: In backend/app/objects.py fill in `validate_props`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g02
- [x] G03: In backend/app/objects.py fill in `check_geometry` (follow the 3 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g03
- [x] G04: In backend/app/objects.py fill in `validate_object` (follow the 7 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g04
- [x] G05: In backend/app/objects.py fill in `object_json`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g05
- [ ] G06: In backend/app/objects.py fill in `apply_fields` and `find_objects`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g06
- [ ] G07: In backend/app/objects.py fill in `idw`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g07
- [ ] G08: In backend/app/objects.py fill in `soil_grid`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g08
- [ ] G09: In backend/app/objects.py fill in `soil_points`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g09
- [ ] G10: In backend/app/objects.py fill in `pins` (follow the 4 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_objects.py -q -k g10
- [ ] G11: Make the whole-feature tests pass: run them, read the first failing assert, fix only the function bodies from G01–G10
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_objects.py tests/judge/test_step_objects.py -q
