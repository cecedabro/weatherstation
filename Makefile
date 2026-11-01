SHELL := bash
.PHONY: setup fmt check run migrate dev
# Targets MUST exist and `make check` MUST pass after every task. `check` runs
# each part of the repo that exists so far; later tasks extend it, never weaken it.

setup:
	cd backend && uv sync

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

check:
	@if [ -d backend ]; then cd backend && uv run ruff check . && uv run mypy app && uv run pytest -q ../contract/tests tests; fi
	@if [ -d gateway ]; then cd gateway && uv run ruff check . && uv run mypy gateway && uv run pytest -q; fi
	@if [ -d firmware ]; then cd firmware && pio test -e native; fi

run:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

migrate:
	cd backend && uv run alembic upgrade head

dev:
	cd backend && uv run python scripts/dev.py
