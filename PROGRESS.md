# PROGRESS.md — weatherstation

## Task S01 — summarize
Implemented `summarize()` in `backend/app/stats.py:22-60`. The function queries raw readings for a given node/metric within a half-open time window `[start, end)`, returning count, min, max, avg, sum, first_ts, and last_ts. Returns zeros/None for empty result sets. Imports added: `from sqlalchemy import func, select`. All 3 S01 tests pass; `make check` passes.

## Task S02 — daily_stats
Implemented `daily_stats()` in `backend/app/stats.py:78-117`. The function computes one row per UTC day for the last `days` days (oldest first), aggregating count, min, max, avg, and sum of `Reading.value` grouped by day via `date_trunc("day", timezone("UTC", ts))`. Window starts at midnight of `days - 1` days ago. Returns empty list for days with no readings. `ValueError` raised for days outside 1–366. All 2 S02 tests pass; `make check` passes.
