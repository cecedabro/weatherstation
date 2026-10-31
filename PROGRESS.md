# PROGRESS

Appended by the agent after each task: what changed, where, and gotchas for later tasks.

## T01: Backend skeleton (done)
- Created `backend/pyproject.toml` with uv project config: FastAPI, uvicorn, SQLAlchemy, alembic,
  psycopg, pydantic, pydantic-settings, jinja2, httpx, pytest, pytest-asyncio, ruff, mypy, pgserver.
  Ruff line-length 100, mypy strict on `app` package.
- Created `backend/app/config.py` with `Settings(BaseSettings)` reading `DATABASE_URL`, `INGEST_TOKEN`,
  `ADMIN_USER`, `ADMIN_PASSWORD` from env with safe local defaults (SPEC 1.3).
- Created `backend/app/main.py` with `create_app()` factory exposing `app`, `/healthz` endpoint
  returning `{"status": "ok"}` (SPEC 1.2), and a minimal `/api/v1/nodes` stub returning `[]` for
  contract test compatibility.
- Created `backend/app/__init__.py` re-exporting `app`.
- Created `backend/tests/test_healthz.py` asserting SPEC 1.2 (status code 200, body matches).
- Updated `.gitignore` to exclude `__pycache__/` and cache directories (prevents protected path errors
  when contract tests create pycache during `make check`).
- `make check` passes: ruff clean, mypy clean, 6 tests pass (1 new + 5 contract tests).
