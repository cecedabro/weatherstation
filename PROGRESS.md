## A01 - daily_gdd
Implemented `daily_gdd()` in `backend/app/growth.py:37`. The function computes growing degree days: clamps `tmax` to `cap`, clamps `tmin` to `base`, equalizes if `hi < lo`, then returns `max(0, (hi+lo)/2 - base)`. All 7 A01 tests pass. `make check` passes (503 passed).

## A02 - local_daily_temps
Implemented `local_daily_temps()` in `backend/app/growth.py:47`. The function groups `[(timestamp, temp_c)]` readings by local date (Europe/Amsterdam), converting naive datetimes as UTC, then returns `{date: (min_temp, max_temp)}`. A reading at 22:30 UTC on June 1 becomes 00:30 CEST on June 2 in Amsterdam. All A02 tests pass. `make check` passes (510 passed).
