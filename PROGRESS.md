## P01 - seeds.py: parse_months, sowable
Implemented `parse_months` and `sowable` in `backend/app/seeds.py`.
- `parse_months(text)`: parses month spec strings like "3-5,9" or "11-2" into a set of ints, handling ranges, wrapping, and invalid parts per the 4-step docstring.
- `sowable(crop, month)`: returns whether a month falls within the crop's sow_months.
All 10 P01 judge tests pass; `make check` exits 0 with 95% coverage.

## P02 - seeds.py: expected_harvest, harvest_text
Implemented `expected_harvest` and `harvest_text` in `backend/app/seeds.py`.
- `expected_harvest(sown_on, days_to_harvest)`: returns `sown_on + timedelta(days=days_to_harvest)`, or `None` if unknown.
- `harvest_text(expected, today, status)`: returns status-based text ("harvested"/"failed"/"") or relative readiness ("ready in N days"/"ready tomorrow"/"ready today"/"ready since N days"/"ready since yesterday").
All 10 P02 judge tests pass; `make check` exits 0 with 95% coverage.

## P03 - seeds.py: validate_planting
Implemented `validate_planting` in `backend/app/seeds.py` following the 7 docstring steps.
- Validates crop (strip, empty/length check), variety (strip, None if empty, length check),
  method/status (must be in PLANTING_METHODS/PLANTING_STATUSES), sown_on (date parsing),
  count (int >= 1), object_id (int in allowed set), notes (length check, no strip).
- Returns `(values, errors)` tuple with all FORM_FIELDS + crop_id; keeps raw text for invalid fields.
All 14 P03 judge tests pass; `make check` exits 0 with 93% overall coverage.

## P04 - seeds.py: next_status, timeline
Implemented `next_status` and `timeline` in `backend/app/seeds.py`.
- `next_status(status)`: finds status in PATH ("planned", "sown", "sprouted", "growing", "flowering", "harvesting", "done"), returns the next step or None for "done"/"failed"/unknown.
- `timeline(status)`: returns [(step, state)] for every PATH step; steps before status are "done", current is "current", rest "todo"; for "failed" all are "todo" plus ("failed", "current") at end.
All 2 P04 judge tests pass; `make check` exits 0 with 96% coverage.

## P05 - seeds.py: rotation_warning
Implemented `rotation_warning` in `backend/app/seeds.py` following the 3 docstring steps.
- Returns None when `object_id` or `family` is None.
- Queries Planting joined with Crop where the crop family matches (case-insensitive), the object matches, and sown_on is in [year-3, year), excluding a given planting id.
- Returns the newest matching row or None; formats as `"family grew here in year (crop)"`.
All 7 P05 judge tests pass; `make check` exits 0 with 96% coverage.

## P06 - seeds.py: find_plantings
Implemented `find_plantings` in `backend/app/seeds.py`.
- Filters by show: "active" excludes FINISHED statuses, "done" includes only FINISHED, anything else returns all.
- When year is set, filters sown_on to [year-01-01, year+1-01-01).
- Orders by sown_on desc, id desc; returns a list.
All 1 P06 judge test passes; `make check` exits 0 with 96% coverage.

## P07 - seeds.py: group_by_bed
Implemented `group_by_bed` in `backend/app/seeds.py`.
- Groups plantings by bed name using the `objects` dict (object_id → name).
- Plantings with `object_id` None or not in `objects` go under "Not placed".
- Returns `[(name, plantings)]` sorted case-insensitively, with "Not placed" always last.
All 1 P07 judge test passes; `make check` exits 0 with 96% coverage.

## P08 - seeds.py: planting_json
Implemented `planting_json` in `backend/app/seeds.py`.
- Takes a Planting ORM object and returns a dict with all seed log fields: id, crop, crop_id, variety, object_id, method, status, count, x, y, notes.
- Three date fields (sown_on, expected_harvest, harvested_on) are converted to ISO format strings via `.isoformat()`, or None when absent.
All 1 P08 judge test passes; `make check` exits 0 with 96% coverage.

## P09 - seeds.py: seed_crops
Implemented `seed_crops` in `backend/app/seeds.py`.
- Reads JSON from *path* (default `data/crops.json`), queries existing crop names case-insensitively,
  adds only new crops via `db.add(Crop(**row))`, flushes, and returns the count added.
- Idempotent: re-calling with the same data returns 0.
All 2 P09 judge tests pass; `make check` exits 0 with 96% coverage.
