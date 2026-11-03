# Weather station

Private garden weather station: ESP32 sensor nodes → Raspberry Pi → k3s backend
→ public site at garden.cedricschippers.dev, with an admin view of node health.

`index.html` is the approved look-and-feel mock (reference only).

Built incrementally by a local coding agent. If you are that agent, start with
`AGENTS.md`. If you are a human, the plan is `PLAN.md` and the requirements are
`SPEC.md`; everything else is generated.

## Website

### Pages
| Route | Description |
|---|---|
| `/` | Home — current conditions per node, alerts, and chart selectors |
| `/weather` | Weather readings with chart selector |
| `/soil` | All soil sensor readings |
| `/soil/{node_id}` | Single soil node detail page with charts |
| `/history` | 30-day daily aggregation table with node selector |
| `/about` | Station info, data path diagram, units, and node registry |
| `/admin` | Admin page showing node health (online status, battery, RSSI) |
| `/partials/current` | HTMX partial for live current conditions refresh |

### API endpoints
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/readings` | Ingest sensor readings (bearer token auth) |
| `GET` | `/api/v1/series` | Time-series data (raw or bucketed 5m/1h/1d) |
| `GET` | `/api/v1/current` | Latest reading per node per metric |
| `GET` | `/api/v1/nodes` | List all known nodes with online/offline status |
| `GET` | `/api/v1/export.csv` | Export readings as CSV with filters |
| `GET` | `/admin/nodes.json` | Node health data as JSON (Basic auth) |
| `GET` | `/healthz` | Health check returning `{"status": "ok"}` |

Preview locally with `make dev` (runs on `:8000` with a throwaway Postgres).

## Quick start (human)
1. Fill in `backend/.env.example` → copy to `.env` for local runs.
2. `make setup && make check` should pass on an empty skeleton once T01 is done.
3. Hand the repo to the agent loop (`agent-loop`) from the devbox.
4. Try the production image on your machine: [docs/docker-local.md](docs/docker-local.md)
   (build, run with Postgres, check it). Short version: `docker build -t weatherstation:local .`
