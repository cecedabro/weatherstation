SHELL := bash
.PHONY: setup fmt check run migrate dev migcheck
# Targets MUST exist and `make check` MUST pass after every task. `check` runs
# each part of the repo that exists so far; later tasks extend it, never weaken it.

setup:
	cd backend && uv sync

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

check:
	@if [ -d backend ]; then cd backend && uv run ruff check . && uv run mypy app && uv run pytest -q ../contract/tests tests --cov=app --cov-fail-under=90 && bandit -r app -q -ll; fi
	@for f in $(wildcard backend/app/static/*.js); do node --check $$f || exit 1; done
	@if [ -d gateway ]; then cd gateway && uv run ruff check . && uv run mypy gateway && uv run pytest -q; fi
	@if [ -n "$${DATABASE_URL:-}" ] && [ -f tests/ci/check-migrations.sh ]; then $(MAKE) -s migcheck; fi
	@if [ -f deploy/Makefile ]; then $(MAKE) -s -C deploy validate; fi
	@if [ -d firmware ]; then cd firmware && pio test -e native; fi

run:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

migrate:
	cd backend && uv run alembic upgrade head

dev:
	cd backend && uv run python scripts/dev.py

# Human-owned migration check (tests/ci/). Uses a separate, wiped database next to DATABASE_URL.
migcheck:
	@DATABASE_URL="$${DATABASE_URL%/*}/migcheck" bash tests/ci/check-migrations.sh
