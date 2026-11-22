# PROGRESS.md — weatherstation

## Task S01 — summarize
Implemented `summarize()` in `backend/app/stats.py:22-60`. The function queries raw readings for a given node/metric within a half-open time window `[start, end)`, returning count, min, max, avg, sum, first_ts, and last_ts. Returns zeros/None for empty result sets. Imports added: `from sqlalchemy import func, select`. All 3 S01 tests pass; `make check` passes.

## Task S02 — daily_stats
Implemented `daily_stats()` in `backend/app/stats.py:78-117`. The function computes one row per UTC day for the last `days` days (oldest first), aggregating count, min, max, avg, and sum of `Reading.value` grouped by day via `date_trunc("day", timezone("UTC", ts))`. Window starts at midnight of `days - 1` days ago. Returns empty list for days with no readings. `ValueError` raised for days outside 1–366. All 2 S02 tests pass; `make check` passes.

## Task S03 — parse_compare, parse_view
Implemented `parse_compare()` and `parse_view()` in `backend/app/sensors.py:67-102`. `parse_compare()` splits a comma-separated string of ISO dates, strips whitespace, skips invalid/duplicate entries, and returns at most the first 3 as a tuple. `parse_view()` resolves cat (default "air"), range (default "7d"), node (sorted first or None), and compare (via `parse_compare`) from query params, falling back to defaults for unknown values. All 2 S03 tests pass; `make check` passes (319 passed, 96% coverage).

## Task S04 — view_href, range_window, daily_days
Implemented three functions in `backend/app/sensors.py`: `view_href()` builds a `/sensors?` query string from a `View` with changes applied, dropping node and compare when cat changes, and omitting None node / empty compare. `range_window()` returns `(now - timedelta(hours=RANGES[key][1]), now)` with a 168-hour default for unknown keys. `daily_days()` computes `hours // 24` clamped to `[1, MAX_DAILY_ROWS]`. All S04 judge tests pass; `make check` passes (321 passed, 96% coverage).

## Task S05 — latest, tiles
Implemented `latest()` and `tiles()` in `backend/app/sensors.py:171-211`. `latest()` queries `Reading.value` for a given node/metric, ordered by timestamp descending, returning the newest value or None. `tiles()` builds stat tiles per metric: rain_mm shows Latest + Total, wind_dir_deg shows Latest with compass direction (using `fmt.compass`), and all other metrics show Latest, Min, Max, Average. All S05 judge tests pass; `make check` passes (323 passed, 96% coverage).

## Task S06 — merge_daily
Implemented `merge_daily()` in `backend/app/sensors.py:207-232`. The function takes a dict mapping metric names to lists of daily-stats rows, collects all unique dates, and merges them into a single list sorted newest-first. Each output row has `{"date": d, metric: row_or_none, ...}` for every input metric. Limited to `MAX_DAILY_ROWS` (31). All S06 judge tests pass; `make check` passes (325 passed).

## Task S07 — soil_rows
Implemented `soil_rows()` in `backend/app/sensors.py:240-249`. The function takes a DB session and a list of soil node ids, and returns a list of dicts `{"node": id, "soil_moisture_pct": latest_value, "soil_temp_c": latest_value}` in the order of the input nodes. Uses the existing `latest()` helper to query the newest reading per node/metric. Returns None for a metric when the node has no such reading. All S07 judge tests pass; `make check` passes (326 passed, 96% coverage).

## Task S08 — compare_rows, csv_href
Implemented `compare_rows()` and `csv_href()` in `backend/app/sensors.py:255-285`. `compare_rows()` iterates over compare dates, calls `summarize()` for each UTC day (`datetime(d.year, d.month, d.day, tzinfo=UTC)` to `+ timedelta(days=1)`), and returns `{"date": iso, "min": s["min"], "max": s["max"], "avg": s["avg"]}`. `csv_href()` formats start/end as RFC3339 UTC with `Z` suffix (stripping microseconds via `.replace(microsecond=0).isoformat().replace("+00:00", "Z")`), then builds `/api/v1/export.csv?node=…&metric=…&from=…&to=…` via `urlencode`. All S08 judge tests pass; `make check` passes (327 passed, 96% coverage).
