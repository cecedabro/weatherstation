# PROGRESS.md — weatherstation

## Task S01 — summarize
Implemented `summarize()` in `backend/app/stats.py:22-60`. The function queries raw readings for a given node/metric within a half-open time window `[start, end)`, returning count, min, max, avg, sum, first_ts, and last_ts. Returns zeros/None for empty result sets. Imports added: `from sqlalchemy import func, select`. All 3 S01 tests pass; `make check` passes.

## Task S02 — daily_stats
Implemented `daily_stats()` in `backend/app/stats.py:78-117`. The function computes one row per UTC day for the last `days` days (oldest first), aggregating count, min, max, avg, and sum of `Reading.value` grouped by day via `date_trunc("day", timezone("UTC", ts))`. Window starts at midnight of `days - 1` days ago. Returns empty list for days with no readings. `ValueError` raised for days outside 1–366. All 2 S02 tests pass; `make check` passes.

## Task S03 — parse_compare, parse_view
Implemented `parse_compare()` and `parse_view()` in `backend/app/sensors.py:67-102`. `parse_compare()` splits a comma-separated string of ISO dates, strips whitespace, skips invalid/duplicate entries, and returns at most the first 3 as a tuple. `parse_view()` resolves cat (default "air"), range (default "7d"), node (sorted first or None), and compare (via `parse_compare`) from query params, falling back to defaults for unknown values. All 2 S03 tests pass; `make check` passes (319 passed, 96% coverage).
