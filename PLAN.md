# PLAN: Tasks, step by step (SPEC §14)

The pages, routes, forms and templates are already built by the human: `backend/app/tasks.py` (glue at the
bottom), `backend/app/templates/tasks.html` and `task_form.html`. What is left are small functions that return
placeholders now. Each task fills in 1–2 of them; the steps are in their docstrings:
`grep -n "TODO (task Dxx)" backend/app/tasks.py`. Each task has its own step test in
`backend/tests/judge/test_step_tasks.py` (named `test_dxx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the bodies of the functions the task names. Keep signatures and docstrings, but delete the
  "TODO (task Dxx)" line(s) you finish. Don't touch the glue (everything under `# -- glue (done)`), constants or
  other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/tasks.py && uv run ruff check app/tasks.py`.
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] D01: In backend/app/tasks.py fill in `local_today` and `deadline_text`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d01
- [x] D02: In backend/app/tasks.py fill in `sort_key`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d02
- [ ] D03: In backend/app/tasks.py fill in `validate_form` (follow the 5 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d03
- [ ] D04: In backend/app/tasks.py fill in `find_tasks`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d04
- [ ] D05: In backend/app/tasks.py fill in `counts`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d05
- [ ] D06: In backend/app/tasks.py fill in `task_json`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d06
- [ ] D07: In backend/app/tasks.py fill in `apply_form` and `set_done`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_tasks.py -q -k d07
- [ ] D08: Make the whole-feature tests pass: run them, read the first failing assert, fix only the function bodies from D01–D07
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_tasks.py tests/judge/test_step_tasks.py -q
