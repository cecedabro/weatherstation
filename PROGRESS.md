# PROGRESS.md

## G01 — clean_prop (objects.py)
Implemented `clean_prop` in `backend/app/objects.py:67` following the 7 steps in its docstring: handles None/empty clearing, choice validation, bool string coercion, number range checking (excluding booleans), date parsing via `date.fromisoformat`, text stripping with length limit, and color hex validation. All 21 G01 judge tests pass. `make check` exits 0 (454 passed, 47 skipped, 93.49% coverage).

## G02 — validate_props (objects.py)
Implemented `validate_props` in `backend/app/objects.py:138`: if raw is not a dict returns error, otherwise iterates raw keys against `KIND_PROPS[kind]` specs, reports unknown properties and passes known ones through `clean_prop`, collecting clean non-None values into the result dict. Both G02 judge tests pass. `make check` exits 0 (475 passed, 26 skipped, 95.02% coverage).
