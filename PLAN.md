# PLAN: Species and sightings, step by step (SPEC §15)

The pages, routes, photo serving and templates are already built by the human: `backend/app/species.py` (glue
at the bottom) and `backend/app/templates/species.html`, `species_detail.html`, `species_form.html`. What is left
are small functions that return placeholders now. Each task fills in 1–2 of them; the steps are in their
docstrings: `grep -n "TODO (task Exx)" backend/app/species.py`. Each task has its own step test in
`backend/tests/judge/test_step_species.py` (named `test_exx_…`).

Rules for every task:
- Non-interactive: nobody reads questions. Make the edit, run the accept command, fix what fails, stop.
- Only change the bodies of the functions the task names. Keep signatures and docstrings, but delete the
  "TODO (task Exx)" line(s) you finish. Don't touch the glue (everything under `# -- glue (done)`), constants or
  other functions.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .` on the whole repo: that rewrites human-owned
  files and the attempt is rejected. Format only the file you changed:
  `cd backend && uv run ruff format app/species.py && uv run ruff check app/species.py`.
- Run the accept command yourself, then `make check`. If a step test fails, read its assert and fix the function.
- Never edit tests, templates, `Makefile`, `pyproject.toml`, `PLAN.md`, `SPEC.md`, `docs/`.

- [x] E01: In backend/app/species.py fill in `verdict_kind` and `to_remove`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e01
- [ ] E02: In backend/app/species.py fill in `validate_species` (follow the 4 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e02
- [ ] E03: In backend/app/species.py fill in `validate_sighting` (follow the 4 steps in its docstring)
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e03
- [ ] E04: In backend/app/species.py fill in `image_ext` and `media_name_ok`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e04
- [ ] E05: In backend/app/species.py fill in `save_photo`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e05
- [ ] E06: In backend/app/species.py fill in `sighting_stats`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e06
- [ ] E07: In backend/app/species.py fill in `find_species`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e07
- [ ] E08: In backend/app/species.py fill in `seed_catalogue`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e08
- [ ] E09: In backend/app/species.py fill in `sighting_json`
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_species.py -q -k e09
- [ ] E10: Make the whole-feature tests pass: run them, read the first failing assert, fix only the function bodies from E01–E09
  accept: cd backend && TASKS=all uv run pytest tests/judge/test_species.py tests/judge/test_step_species.py -q
