# PROGRESS.md

## G01 — clean_prop (objects.py)
Implemented `clean_prop` in `backend/app/objects.py:67` following the 7 steps in its docstring: handles None/empty clearing, choice validation, bool string coercion, number range checking (excluding booleans), date parsing via `date.fromisoformat`, text stripping with length limit, and color hex validation. All 21 G01 judge tests pass. `make check` exits 0 (454 passed, 47 skipped, 93.49% coverage).

## G02 — validate_props (objects.py)
Implemented `validate_props` in `backend/app/objects.py:138`: if raw is not a dict returns error, otherwise iterates raw keys against `KIND_PROPS[kind]` specs, reports unknown properties and passes known ones through `clean_prop`, collecting clean non-None values into the result dict. Both G02 judge tests pass. `make check` exits 0 (475 passed, 26 skipped, 95.02% coverage).

## G03 — check_geometry (objects.py)
Implemented `check_geometry` in `backend/app/objects.py:166`: iterates GEOMETRY_DEFAULTS keys with range validation per key type (x/y: -500..500, w/d: 0..100 exclusive start, h: 0..20, rotation: mod 360), skips missing keys when partial, applies defaults otherwise; handles color with None/empty→None, hex validation via COLOR_RE, and lowercase normalization. All 11 G03 judge tests pass. `make check` exits 0 (477 passed, 24 skipped).
