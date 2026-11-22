## A01 - daily_gdd
Implemented `daily_gdd()` in `backend/app/growth.py:37`. The function computes growing degree days: clamps `tmax` to `cap`, clamps `tmin` to `base`, equalizes if `hi < lo`, then returns `max(0, (hi+lo)/2 - base)`. All 7 A01 tests pass. `make check` passes (503 passed).

## A02 - local_daily_temps
Implemented `local_daily_temps()` in `backend/app/growth.py:47`. The function groups `[(timestamp, temp_c)]` readings by local date (Europe/Amsterdam), converting naive datetimes as UTC, then returns `{date: (min_temp, max_temp)}`. A reading at 22:30 UTC on June 1 becomes 00:30 CEST on June 2 in Amsterdam. All A02 tests pass. `make check` passes (510 passed).

## A03 - gdd_series
Implemented `gdd_series()` in `backend/app/growth.py:64`. The function walks days from `start` to `end` (inclusive, oldest first), skipping days not in `temps`, and returns `[(day, daily_gdd(tmin, tmax, base))]` for days that have temperatures. Returns `[]` when `start > end`. All A03 tests pass. `make check` passes (511 passed).

## A04 - progress
Implemented `progress()` in `backend/app/growth.py:86`. Returns `None` when `gdd_needed` is `None` or `<= 0`; otherwise returns `min(1.0, gdd_done / gdd_needed)` rounded to 3 decimals. All A04 tests pass. `make check` passes (512 passed).

## A05 - harvest_eta
Implemented `harvest_eta()` in `backend/app/growth.py:96`. Returns `None` when `gdd_needed` is None/`<= 0`; `today` when already done; `None` when no recent data or rate < 0.1 (too cold); otherwise computes average rate from `recent`, divides remaining GDD by rate, and returns `today + timedelta(days=ceil(remaining/rate))`. All A05 tests pass. `make check` passes (513 passed).

## A06 - sun_fit
Implemented `sun_fit()` in `backend/app/growth.py:119`. The function looks up sun needs from `SUN_NEED` dict (defaulting to "full"=6h), returns `(0.5, "sun hours unknown")` when sun_hours is None, `(1.0, "...")` when sun_hours meets/exceeds need, and `(round(sun_hours/need, 2), "only ...")` otherwise. All 8 A06 tests pass. `make check` passes (514 passed).

## A07 - moisture_fit
Implemented `moisture_fit()` in `backend/app/growth.py:136`. Returns `(0.5, "no soil data")` when any param is None; `(1.0, "...")` when `lo <= avg <= hi`; below lo: `gap = lo - avg`, score `max(0, 1 - gap/20)`; above hi: `gap = avg - hi`, same score formula. All 7 A07 tests pass. `make check` passes (522 passed).

## A08 - score_spot
Implemented `score_spot()` in `backend/app/growth.py:157`. Scores a bed for a crop using weighted combination: sun (40%), moisture (40%), rotation (20%). Calls `sun_fit` and `moisture_fit` for the first two components, checks `rotation_hit` for the third, and returns `round(100 * (0.4 * s + 0.4 * m + 0.2 * r))` with a list of three reason strings. All A08 tests pass. `make check` passes (529 passed).

## A09 - best_spots
Implemented `best_spots()` in `backend/app/growth.py:176`. Sorts candidates by score descending, then name case-insensitive ascending, returns the first *n* ranked entries. All A09 tests pass. `make check` passes (530 passed).

## A10 - tokenize
Implemented `tokenize()` in `backend/app/advisor.py:93`. Tokenizes text: lowercases, extracts words matching `[a-z0-9à-ÿ]+`, filters to length >= 3, removes stopwords. Returns list keeping duplicates. All A10 tests pass. `make check` passes (531 passed).

## A11 - rank_sources
Implemented `rank_sources()` in `backend/app/advisor.py:101`. Tokenizes the question into terms, scores each source by weighted word matches (title×3, tags×2, body×1), drops zero-score sources, sorts by score descending then id ascending, returns top *k*. All A11 tests pass. `make check` passes (532 passed).

## A12 - snippet
Implemented `snippet()` in `backend/app/advisor.py:125`. Given a body of text, a set of search terms, and a width, it finds the first occurrence of any term (case-insensitive), extracts a window of `width` characters starting at `max(0, min_hit - width//4)`, and prepends/appends "…" when the snippet doesn't cover the full body. Returns `body[:width]` when there are no hits or the body fits. All A12 tests pass. `make check` passes (533 passed).

## A13 - validate_source
Implemented `validate_source()` in `backend/app/advisor.py:149`. Validates the source form fields: title (1-200 chars), kind (must be in SOURCE_KINDS), url (empty→None, must start with http/https, ≤500 chars), publisher (empty→None, ≤120 chars), body (1-20000 chars), tags (split/comma, strip, lower, join with ", ", ≤200 chars). Returns (values, errors) tuple with all FORM_FIELDS keys present. All A13 tests pass. `make check` passes (534 passed).
