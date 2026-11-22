# PROGRESS.md

## G01 — clean_prop (objects.py)
Implemented `clean_prop` in `backend/app/objects.py:67` following the 7 steps in its docstring: handles None/empty clearing, choice validation, bool string coercion, number range checking (excluding booleans), date parsing via `date.fromisoformat`, text stripping with length limit, and color hex validation. All 21 G01 judge tests pass. `make check` exits 0 (454 passed, 47 skipped, 93.49% coverage).

## G02 — validate_props (objects.py)
Implemented `validate_props` in `backend/app/objects.py:138`: if raw is not a dict returns error, otherwise iterates raw keys against `KIND_PROPS[kind]` specs, reports unknown properties and passes known ones through `clean_prop`, collecting clean non-None values into the result dict. Both G02 judge tests pass. `make check` exits 0 (475 passed, 26 skipped, 95.02% coverage).

## G03 — check_geometry (objects.py)
Implemented `check_geometry` in `backend/app/objects.py:166`: iterates GEOMETRY_DEFAULTS keys with range validation per key type (x/y: -500..500, w/d: 0..100 exclusive start, h: 0..20, rotation: mod 360), skips missing keys when partial, applies defaults otherwise; handles color with None/empty→None, hex validation via COLOR_RE, and lowercase normalization. All 11 G03 judge tests pass. `make check` exits 0 (477 passed, 24 skipped).

## G04 — validate_object (objects.py)
Implemented `validate_object` in `backend/app/objects.py:229`: checks data is a dict (else `{"_": "send a JSON object"}`), validates "kind" against OBJECT_KINDS, "name" as 1-80 char stripped string, delegates to `check_geometry` for spatial fields, validates "node_id" against Node DB, and delegates to `validate_props` for properties. Creates require kind/name always; updates only validate sent keys. All 3 G04 judge tests pass. `make check` exits 0 (488 passed, 13 skipped, 93.64% coverage).

## G05 — object_json (objects.py)
Implemented `object_json` in `backend/app/objects.py:315`: builds a dict with keys `id`, `kind`, `name`, `x`, `y`, `w`, `d`, `h`, `rotation`, `color`, `props`, `node_id`, `updated_at` from the GardenObject attributes; `updated_at` is serialized via `.isoformat()`. All G05 judge tests pass. `make check` exits 0 (491 passed, 10 skipped, 95.90% coverage).

## G06 — apply_fields, find_objects (objects.py)
Implemented `apply_fields` in `backend/app/objects.py:338`: iterates `fields.items()` and calls `setattr(obj, key, value)` for each. Implemented `find_objects` in `backend/app/objects.py:346`: builds a `select(GardenObject)` query, optionally filters by `kind` via `.where(GardenObject.kind == kind)`, orders by `GardenObject.id`, returns all results. Both G06 judge tests pass. `make check` exits 0 (492 passed, 9 skipped, 95.86% coverage).

## G07 — idw (objects.py)
Implemented `idw` in `backend/app/objects.py:360`: inverse-distance-weighted interpolation. Returns None for empty points, returns the exact value when a point is within 1e-9 of the query location, otherwise computes weighted average as `sum(w*value)/sum(w)` where `w = 1/dist^power`. All 1 G07 judge tests pass. `make check` exits 0 (494 passed, 7 skipped).
