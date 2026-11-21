# PLAN: garden species

One task per line. `accept:` must exit 0, then the harness runs `make check`. Read AGENTS.md,
docs/design.md and docs/frontend.md first. Pages use only `templates/ui.html` components (no CSS).
The acceptance tests in `backend/tests/judge/` are the human's; write your own tests in `backend/tests/`.

## Species (SPEC §15) — all routes need `user: str = RequireUser`; read MEDIA_DIR from `Settings()` at request time
- [ ] E01: New `app/species.py` with `seed_catalogue(db)` per SPEC 15.7 (reads `app/data/common_species.json`, inserts missing names with `common=True`, idempotent) and run it at startup in `app/main.py` (a lifespan or startup hook that logs a warning and carries on when the database is not reachable, so tests without a database still start).
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k seed_catalogue
- [ ] E02: `GET /api/v1/sightings` per SPEC 15.8 (router in `app/species.py`, included in `app/main.py`).
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k test_api
- [ ] E03: `GET /species` (delete the placeholder in `app/web.py`) with `templates/species.html`: `ui.page_head` with a "New species" button, `ui.tabs` Found/Catalogue, a `ul.list` of `ui.list_item` rows per SPEC 15.2 (verdict chip: harmful/invasive bad, beneficial ok, neutral info, unknown off; "N to remove" warn chip; last seen as "3 Jun 2026"), empty state linking to `/species/new`.
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k "found_and_catalogue or empty"
- [ ] E04: Search and verdict filter per SPEC 15.1 in a GET `toolbar` form.
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k search_and_filter
- [ ] E05: `GET /species/{id}` per SPEC 15.3 with `templates/species_detail.html`: details with `ui.kv`, description, sightings newest first as a `ul.timeline`, and an add-sighting form (`method="post" enctype="multipart/form-data"`, fields seen_on date, count, notes, removed checkbox, object select, photo file).
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k detail
- [ ] E06: `GET /species/new` and `POST /species` per SPEC 15.4 with `templates/species_form.html`; validation in a pure function with unit tests; duplicate names (case-insensitive) → 400.
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k "create_and_unique or species_validation"
- [ ] E07: `GET /species/{id}/edit`, `POST /species/{id}`, `POST /species/{id}/delete` (cascade sightings and delete their photo files; the delete form uses `data-confirm`).
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k edit_and_delete
- [ ] E08: `POST /species/{id}/sightings` and `GET /media/sightings/{name}` per SPEC 15.5 in a new `app/media.py`: detect JPEG/PNG/WebP from the first bytes (no new dependency), limit 8 MB, save as `secrets.token_hex(16) + ext` under `MEDIA_DIR/sightings/` (create the folder), serve only names matching `^[0-9a-f]{16,64}\.(jpg|png|webp)$`. Show the photo as `<img class="thumb" …>` on the detail page.
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k "add_sighting or sighting_validation or photo_must or media_names or media_dir"
- [ ] E09: `POST /sightings/{id}/removed` and `POST /sightings/{id}/delete` per SPEC 15.6.
  accept: cd backend && uv run pytest tests/judge/test_species.py -q -k toggle_and_delete
- [ ] E10: Tidy up: modules under ~300 lines, all judge tests green, `make check` green.
  accept: cd backend && uv run pytest tests/judge -q
