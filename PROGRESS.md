## E01 - species.py: verdict_kind and to_remove
Implemented `verdict_kind()` in `backend/app/species.py:35` as a dict lookup mapping harmful/invasive→"bad", beneficial→"ok", neutral→"info", default→"off". Implemented `to_remove()` in `backend/app/species.py:47` to count sightings with `removed=False` only for harmful/invasive verdicts, returning 0 otherwise. Both tests pass. `make check` passes (92% coverage, 308 passed).

## E02 - species.py: validate_species
Implemented `validate_species()` in `backend/app/species.py:55` following the 4 docstring steps: (1) name validation — empty/over 120/duplicate case-insensitive checks; (2) latin over 120 check, empty→None; (3) kind/verdict must be in their respective allowed lists; (4) description over 4000 check. All 8 E02 tests pass. `make check` passes (90% coverage, 310 passed).

## E03 - species.py: validate_sighting
Implemented `validate_sighting()` in `backend/app/species.py:111` following the 4 docstring steps: (1) seen_on parsed via `date.fromisoformat()`, ValueError → keep text with error; (2) count: empty→None, else int or error "A whole number, 1 or more"; (3) notes: over 2000 chars → error; (4) object_id: empty→None, else must be in object_ids set. Added unit tests in `backend/tests/test_validate_sighting.py` to ensure coverage stays above 90% when judge tests are skipped. All 7 E03 judge tests and 11 unit tests pass. `make check` passes (93% coverage, 329 passed).

## E04 - species.py: image_ext and media_name_ok
Implemented `image_ext()` in `backend/app/species.py:181` with three magic-byte checks: JPEG (`\xff\xd8\xff` prefix), PNG (`\x89PNG\r\n\x1a\n` prefix), WebP (`RIFF` at 0 and `WEBP` at 8). Implemented `media_name_ok()` in `backend/app/species.py:191` using `re.fullmatch(r"[0-9a-f]{16,64}\.(jpg|png|webp)", name)`. Both E04 judge tests pass. `make check` passes (92% coverage, 336 passed).

## E05 - species.py: save_photo
Implemented `save_photo()` in `backend/app/species.py:208`: checks image type via `image_ext()` and size against `MAX_PHOTO`, creates the `sightings` subdirectory, generates a 32-char hex filename with `secrets.token_hex(16)`, writes the data, and returns the filename. Returns `None` for invalid/unrecognized data or oversized files. Both E05 judge tests pass. `make check` passes (92% coverage, 338 passed).
