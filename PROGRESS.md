## E01 - species.py: verdict_kind and to_remove
Implemented `verdict_kind()` in `backend/app/species.py:35` as a dict lookup mapping harmful/invasive→"bad", beneficial→"ok", neutral→"info", default→"off". Implemented `to_remove()` in `backend/app/species.py:47` to count sightings with `removed=False` only for harmful/invasive verdicts, returning 0 otherwise. Both tests pass. `make check` passes (92% coverage, 308 passed).

## E02 - species.py: validate_species
Implemented `validate_species()` in `backend/app/species.py:55` following the 4 docstring steps: (1) name validation — empty/over 120/duplicate case-insensitive checks; (2) latin over 120 check, empty→None; (3) kind/verdict must be in their respective allowed lists; (4) description over 4000 check. All 8 E02 tests pass. `make check` passes (90% coverage, 310 passed).

## E03 - species.py: validate_sighting
Implemented `validate_sighting()` in `backend/app/species.py:111` following the 4 docstring steps: (1) seen_on parsed via `date.fromisoformat()`, ValueError → keep text with error; (2) count: empty→None, else int or error "A whole number, 1 or more"; (3) notes: over 2000 chars → error; (4) object_id: empty→None, else must be in object_ids set. Added unit tests in `backend/tests/test_validate_sighting.py` to ensure coverage stays above 90% when judge tests are skipped. All 7 E03 judge tests and 11 unit tests pass. `make check` passes (93% coverage, 329 passed).
