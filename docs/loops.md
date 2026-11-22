# How agent loops are built (human-owned)

The local agent (Qwen3.6-35B-A3B via OpenCode, run by `agent-loop` on the devbox) works best on **tiny,
fully specified tasks**. The first garden v2 loops asked it to build whole pages from the spec. Each task took
40–90 minutes and was then skipped. The rebuilt loops are the "fill in one function" kind, and each task takes
about 5 minutes. This is the recipe.

## Who writes what

| Part | Written by |
|---|---|
| Routes, wiring in `app/main.py`, page context (`page_context`, `_detail`, …) | human (Claude) |
| Templates, CSS, `ui.html` components, `charts.js`, vendored JS | human (Claude) |
| Small pure or DB functions marked `TODO (task Xnn)` | the agent |
| Tests in `backend/tests/judge/` | human (Claude) |

Each function the agent fills in starts as a **stub** that returns a safe placeholder (`[]`, `{}`, `None`). The
page therefore renders at every step. The docstring says what to return and lists numbered steps, with the
exact SQLAlchemy calls and the imports needed. If the agent has to design something itself, it gets lost.

## Tasks and tests

- One task = 1–3 named functions in one file. Order the tasks so each one needs only earlier ones.
- Each task has a **step test** group in `backend/tests/judge/test_step_<area>.py`. The functions are named
  `test_<id>_…` and tagged `@pytest.mark.task("S01")`.
- `accept: cd backend && TASKS=all uv run pytest tests/judge/test_step_<area>.py -q -k s01` runs in seconds.
- The last task of a loop makes the **whole-feature test** (`test_<area>.py`, tagged with that task's id) pass.
- A `test_<area>_smoke.py` (not tagged) covers the glue, so `make check` coverage stays above 90 % on the stubs.

**Task gating** (`backend/tests/conftest.py`): `make check` skips a tagged test until PLAN.md ticks its task
(`- [x] S01:`). Later tasks of a running loop therefore don't fail the check, and finished tasks stay tested.
`TASKS=all`, or having no PLAN.md (after merging to main), runs them all.

## Before queueing a loop

1. Write the stubs, glue, templates, step tests, smoke test and whole-feature test.
2. **Write a reference implementation of every stub and run all the tests** (`TASKS=all`). This found four
   wrong expectations in the earlier acceptance tests. The agent can never pass a wrong test, and gets stuck on it.
3. Put the stubs back, write PLAN.md (rules section plus tasks), and protect the new templates in `.agent-protected`.
4. `make check` must be green on the stubs. Commit, push the `agent/<name>` branch, and queue it on the status
   page (`POST /api/jobs`, repo `cecedabro/weatherstation`, ref = the branch, `max_hours` 5–6).

## Rules every PLAN.md repeats

- Non-interactive: make the edit, run the accept command, fix what fails, stop. No questions or plans.
- Change only the bodies of the named functions; leave the glue, constants and signatures alone.
- Never run `make fmt`, `ruff format .` or `ruff check --fix .`. They rewrite protected files and the attempt is
  rejected. Format only the file you changed.
- Never read a large file whole: `grep -n`, then `sed -n 'a,bp'`.

## Gotchas

- A hard stop from the status page leaves the half-done attempt in `/home/agent/repos/weatherstation`, and the
  next job fails with "uncommitted changes". Stash it (`git stash push -u`) before requeueing.
- Don't push to a branch while its loop runs; the loop's own pushes would then fail. Merge fixes in afterwards.
- The test session commits on flush (`_GracefulSession`), so agent functions use `db.flush()`, never `db.commit()`.
  Routes (glue) commit.
