# Weather station

Private garden weather station: ESP32 sensor nodes → Raspberry Pi → k3s backend
→ public site at garden.cedricschippers.dev, with an admin view of node health.

`index.html` is the approved look-and-feel mock (reference only).

Built incrementally by a local coding agent. If you are that agent, start with
`AGENTS.md`. If you are a human, the plan is `PLAN.md` and the requirements are
`SPEC.md`; everything else is generated.

## Quick start (human)
1. Fill in `backend/.env.example` → copy to `.env` for local runs.
2. `make setup && make check` should pass on an empty skeleton once T01 is done.
3. Hand the repo to the agent loop (`agent-loop`) from the devbox.
