## Task D01 — tasks.py: local_today & deadline_text
Filled in `local_today()` in `backend/app/tasks.py:36` to convert the input datetime (or `datetime.now(UTC)`) to Europe/Amsterdam timezone and return the date. Filled in `deadline_text()` at `backend/app/tasks.py:46` to compute the difference in days and return the appropriate ("due today", "due tomorrow", "due in N days", "overdue by N days") text and overdue boolean. Both judge tests pass. `make check` passes.

## Task D02 — tasks.py: sort_key
Filled in `sort_key()` in `backend/app/tasks.py:56` to return `(URGENCY_RANK.get(task.urgency, 9), task.deadline or date.max, -task.created_at.timestamp())`. This sorts tasks by urgency (critical first), then by deadline (soonest first, None last), then by created_at (newest first). Judge test `test_d02_sort_key` passes. `make check` passes.

## Task D03 — tasks.py: validate_form
Filled in `validate_form()` in `backend/app/tasks.py:65` with 5 validation steps: title (stripped, required, max 120 chars), notes (not stripped, max 2000 chars), category/urgency (must be in allowed lists), deadline (parsed as date or kept as raw text on error), object_id (parsed as int, must be in object_ids). All 9 D03 judge tests pass. `make check` passes.

## Task D04 — tasks.py: find_tasks
Filled in `find_tasks()` in `backend/app/tasks.py:142` to build a SQLAlchemy query with `select(Task)`, filter by status ("open"/"done"), category, and search text `q` (case-insensitive ilike on title/notes using `or_`). Returns results sorted by `sort_key`. Added `or_` to the sqlalchemy import. Judge test `test_d04_find_tasks` passes. `make check` passes.

## Task D05 — tasks.py: counts
Filled in `counts()` in `backend/app/tasks.py:169` to load all tasks once and count: open, done, all, overdue (open tasks with deadline before today), and week (open tasks with deadline from today to today+6 days inclusive). Judge test `test_d05_counts` passes. `make check` passes.
