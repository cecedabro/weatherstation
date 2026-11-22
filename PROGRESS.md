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
