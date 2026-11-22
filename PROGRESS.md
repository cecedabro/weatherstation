## P01 - seeds.py: parse_months, sowable
Implemented `parse_months` and `sowable` in `backend/app/seeds.py`.
- `parse_months(text)`: parses month spec strings like "3-5,9" or "11-2" into a set of ints, handling ranges, wrapping, and invalid parts per the 4-step docstring.
- `sowable(crop, month)`: returns whether a month falls within the crop's sow_months.
All 10 P01 judge tests pass; `make check` exits 0 with 95% coverage.
