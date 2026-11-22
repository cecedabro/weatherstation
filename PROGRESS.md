## Task D01 — tasks.py: local_today & deadline_text
Filled in `local_today()` in `backend/app/tasks.py:36` to convert the input datetime (or `datetime.now(UTC)`) to Europe/Amsterdam timezone and return the date. Filled in `deadline_text()` at `backend/app/tasks.py:46` to compute the difference in days and return the appropriate ("due today", "due tomorrow", "due in N days", "overdue by N days") text and overdue boolean. Both judge tests pass. `make check` passes.

## Task D02 — tasks.py: sort_key
Filled in `sort_key()` in `backend/app/tasks.py:56` to return `(URGENCY_RANK.get(task.urgency, 9), task.deadline or date.max, -task.created_at.timestamp())`. This sorts tasks by urgency (critical first), then by deadline (soonest first, None last), then by created_at (newest first). Judge test `test_d02_sort_key` passes. `make check` passes.
