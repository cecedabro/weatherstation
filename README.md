# Weather station

Private garden weather station: ESP32 sensor nodes → Raspberry Pi → k3s backend
→ public site at garden.cedricschippers.dev, with an admin view of node health.

The look is a finished design system (Frutiger Aero, frosted glass): see `docs/design.md` and `/styleguide`.
What is done, running and planned: [docs/roadmap.md](docs/roadmap.md). How agent loops are built: [docs/loops.md](docs/loops.md).

Built incrementally by a local coding agent. If you are that agent, start with
`AGENTS.md`. If you are a human, the plan is `PLAN.md` and the requirements are
`SPEC.md`; everything else is generated.

## Website

### Pages
| Route | Description |
|---|---|
| `/` | Overview: live conditions, alerts, last days in charts |
| `/sensors` | Every sensor by category, range, daily table, compare days (loop `agent/sensors-steps`) |
| `/garden` | 3D garden map (private, planned: map core + loop G) |
| `/seeds` | Seed log (private, planned: loop P) |
| `/tasks` | Tasks and reminders (private, loop `agent/tasks-steps`) |
| `/species` | Found species and the common-species catalogue (private, loop `agent/species-steps`) |
| `/about` | Station info, data path and node registry |
| `/admin` | Node health (private) |
| `/styleguide` | Every UI component with its template code |
| `/login` | Sign in (ADMIN_USER / ADMIN_PASSWORD) |

### API endpoints
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/readings` | Ingest sensor readings (bearer token auth) |
| `GET` | `/api/v1/series` | Time-series data (raw or bucketed 5m/1h/1d) |
| `GET` | `/api/v1/current` | Latest reading per node per metric |
| `GET` | `/api/v1/nodes` | List all known nodes with online/offline status |
| `GET` | `/api/v1/export.csv` | Export readings as CSV with filters |
| `GET` | `/admin/nodes.json` | Node health data as JSON (Basic auth) |
| `GET` | `/api/v1/summary`, `/api/v1/daily_stats` | Reading statistics (Sensors loop) |
| `GET` | `/api/v1/tasks`, `/api/v1/sightings` | Tasks and sightings (private; Tasks and Species loops) |
| `GET` | `/healthz` | Health check returning `{"status": "ok"}` |

Preview locally with `make dev` (runs on `:8000` with a throwaway Postgres).

## Quick start (human)
1. Fill in `backend/.env.example` → copy to `.env` for local runs.
2. `make setup && make check` should pass on an empty skeleton once T01 is done.
3. Hand the repo to the agent loop (`agent-loop`) from the devbox.
4. Try the production image on your machine: [docs/docker-local.md](docs/docker-local.md)
   (build, run with Postgres, check it). Short version: `docker build -t weatherstation:local .`

## Deploying

A merge to `main` triggers the release workflow: it runs `make check`, computes
the next version, builds and pushes
`ghcr.io/cecedabro/weatherstation:X.Y.Z` (plus `:sha-<short>`), and creates the
git tag `vX.Y.Z`. Flux then rolls out the new image on the k3s homelab.

Bump control in the commit message: `[minor]` increments the minor version,
`[major]` the major version; `[skip release]` skips the build entirely while
still running checks.

The app reads secrets from two Kubernetes Secrets (see
`deploy/secret.example.yaml`): `weatherstation-app` provides
`DATABASE_URL`, `INGEST_TOKEN`, `ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET` (and optional
`LLM_BASE_URL`, `LLM_API_KEY`, `MEDIA_DIR`); `weatherstation-db`
provides `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

Draft manifests live in `deploy/` (Kustomize). The live copy is maintained in the
homelab repo and applied by Flux.
