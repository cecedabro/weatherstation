# PROGRESS.md — weatherstation

## Task S01 — summarize
Implemented `summarize()` in `backend/app/stats.py:22-60`. The function queries raw readings for a given node/metric within a half-open time window `[start, end)`, returning count, min, max, avg, sum, first_ts, and last_ts. Returns zeros/None for empty result sets. Imports added: `from sqlalchemy import func, select`. All 3 S01 tests pass; `make check` passes.
