# ---- builder ----
FROM ghcr.io/astral-sh/uv:0.5.18 AS builder

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# ---- runtime ----
FROM python:3.11.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY backend .
COPY contract /contract

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

RUN useradd --create-home --uid 10001 appuser
USER 10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
