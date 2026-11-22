# PLAN: garden tasks

One task per line. `accept:` must exit 0, then the harness runs `make check`. Read AGENTS.md,
docs/design.md and docs/frontend.md first. Pages use only `templates/ui.html` components (no CSS).
The acceptance tests in `backend/tests/judge/` are the human's; write your own tests in `backend/tests/`.

## Tasks (SPEC §14) — all routes need `user: str = RequireUser`
- [x] D01: Pure helpers in a new `app/tasks.py`: `deadline_text(deadline, today) -> (text, overdue)` per SPEC 14.2, `task_sort_key(task)` per 14.1, `local_today()` (Europe/Amsterdam date) and `validate_task_form(form, object_ids) -> (values, errors)` per 14.3. Unit tests in `backend/tests/test_tasks_logic.py` (every rule, both sides of each limit).
  accept: cd backend && uv run pytest tests/test_tasks_logic.py -q
- [~] D02: `GET /api/v1/tasks` per SPEC 14.5 (router in `app/tasks.py`, included in `app/main.py`). — skipped: $ cd backend && uv run pytest tests/judge/test_tasks.py -q -k "api or private"  (exit 1)
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k "api or private"
- [ ] D03: `GET /tasks` (delete the placeholder in `app/web.py`) with `templates/tasks.html`: `ui.page_head` with a "New task" button, `ui.tabs` Open/Done/All with counts (`/tasks?status=done`, `/tasks?status=all`), tasks in SPEC 14.1 order as a `ul.list` of `ui.list_item`, empty state with a link to `/tasks/new`.
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k "empty_state or order_urgency or tabs_and_counts"
- [ ] D04: Filters per SPEC 14.1: a GET `toolbar` form with a search field (`q`) and a category select; the filters combine with the status tab.
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k filters
- [ ] D05: Row contents per SPEC 14.2: urgency chip (`ui.chip(u, urgency=u)`), category, deadline text (overdue open tasks get `ui.chip(text, "bad")`), pinned object name, a Done/Reopen form button and an Edit link.
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k row_deadline
- [ ] D06: Three `ui.stat` tiles at the top per SPEC 14.6: "Open", "Overdue", "Due this week" (use `fmt="%d"`).
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k stats
- [ ] D07: `GET /tasks/new` and `POST /tasks` per SPEC 14.3 with `templates/task_form.html` (`ui.field` for every field; object select lists garden objects by name). Validation errors re-render with 400, messages via `ui.field(error=…)`, typed values kept.
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k "create or validation"
- [ ] D08: `GET /tasks/{id}/edit` and `POST /tasks/{id}` (same template and validation). Unknown id → 404.
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k new_and_edit
- [ ] D09: `POST /tasks/{id}/done`, `/reopen`, `/delete` per SPEC 14.4 (delete asks first: `<form data-confirm="Delete this task?">`).
  accept: cd backend && uv run pytest tests/judge/test_tasks.py -q -k done_reopen
- [ ] D10: Tidy up: `app/tasks.py` under ~300 lines (split helpers if needed), all judge tests green, `make check` green.
  accept: cd backend && uv run pytest tests/judge -q
