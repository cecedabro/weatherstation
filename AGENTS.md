# AGENTS.md — weather station

Read this first, every task. It is the contract between you (the coding agent)
and the human. Then read the area doc for the task (table below) and the part of
`SPEC.md` the task names.

You are a local model working one small task at a time with no human to ask.
Prefer the boring, explicit option. When unsure about **code**, follow the area
doc. When unsure about **look and feel**, you decide (see `docs/design.md`).

## What this builds
A weather station for a private garden (the *volkstuin* / Landsmeer garden).
Several ESP32 sensor nodes publish readings over MQTT to a Raspberry Pi. The Pi
forwards them to a backend on a k3s homelab, which stores them in Postgres and
serves a public website with live conditions and history charts, plus a private
admin page showing node health. Public URL: `https://garden.cedricschippers.dev`.

Data path:
`ESP32 nodes → MQTT (Mosquitto on the Pi) → Pi gateway → POST to backend on k3s → Postgres → website`

## Repository layout (top level is fixed; organise inside each as the doc says)
| Path | What | Doc |
| --- | --- | --- |
| `contract/` | Shared data contract: reading schema, units, API shape. **Do not edit.** | `contract/README.md` |
| `backend/` | FastAPI app, Postgres access, website (Jinja + HTMX) | `docs/backend.md`, `docs/frontend.md` |
| `gateway/` | Pi service: MQTT subscriber → batches → POST to backend | `docs/gateway.md` |
| `firmware/` | ESP32 nodes, Arduino C++ via PlatformIO | `docs/firmware.md` |
| `deploy/` | k3s manifests (Kustomize) for the backend + Postgres | `docs/deployment.md` |
| `docs/` | The area docs | — |
| `index.html` | Approved look-and-feel mock (Frutiger Aero). Reference for T11; do not edit or serve it. | `docs/design.md` |
| `SPEC.md` | Testable requirements. **Do not edit.** | — |
| `PLAN.md` | The task list. **Do not edit.** | — |
| `PROGRESS.md` | You append to this after each task | — |

## How you are judged (the loop)
After you stop, the harness runs the task's `accept:` command and then
`make check`. The task counts as done only if both exit 0. It then commits.
If they fail, your work is thrown away and the task is retried with the error.
So: **run `make check` yourself before you stop, and fix what fails.**

## Rules
- There is no human to answer questions. Never ask for confirmation or "would you like me to continue". Decide the simplest option, do the task, and note the choice in `PROGRESS.md`.
- Change only what the task needs. Do not start other tasks.
- Never edit `contract/`, `SPEC.md`, `PLAN.md`, or `AGENTS.md`. If a contract
  test seems wrong, make your code satisfy it and note the concern in `PROGRESS.md`.
- You write the code **and its tests** (except the contract tests, which exist
  already). Read `docs/testing.md` — weak tests that pass trivially are treated
  as a failed task. Tests must assert real behaviour from `SPEC.md`.
- Add a dependency only if the area doc allows it. Pin versions.
- No secrets in the repo. Read config from environment variables with safe
  local defaults. Example values live in `*.env.example` files.
- After each task, append 3–5 lines to `PROGRESS.md`: what you changed, where,
  and anything the next task must know (a new env var, a new endpoint, a gotcha).

## Fixed technical decisions (do not revisit)
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Postgres. Managed with `uv`.
- Website: server-rendered Jinja2 + HTMX, served by the same FastAPI app. No SPA.
- Charts: one small client library loaded from a vendored file (see `docs/frontend.md`).
- Firmware: Arduino framework in C++, built with PlatformIO. One source tree, per-node build env.
- Transport ESP32→Pi: MQTT (plaintext on the Pi's LAN). Pi→backend: HTTPS POST with a bearer token.
- Deploy: Kustomize manifests under `deploy/`, applied by Flux from the homelab repo. Postgres runs in-cluster with a Longhorn volume.
- Time is UTC everywhere in code and storage. The website may display a local timezone.
- Units are SI and fixed by the contract. Never invent new units or field names.

## You decide (design freedom)
- All visual design: layout, colour, typography, spacing, the Frutiger Aero look
  (`docs/design.md`), which chart library, how pages are composed.
- Internal code structure within each top-level directory.
- Names of internal modules, functions, CSS classes.
- Copy/wording on the site.

## Commands
- `make setup` — install backend deps (`uv sync`). Tests start their own throwaway Postgres (see `docs/testing.md`); there is no Docker here.
- `make check` — lint + type-check + all tests of every part that exists (also the contract tests). Must pass after every task.
- `make fmt` — autoformat (ruff). Run before `make check`.
- `make dev` — run the site on :8000 with a throwaway Postgres and fake readings (for humans previewing; don't use it in tests).
- `make run` — run the backend locally (needs a Postgres at `DATABASE_URL`; usually you only need the tests).
See each area doc for area-specific commands (PlatformIO builds, etc.).
