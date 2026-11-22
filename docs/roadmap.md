# Roadmap: garden v2 (human-owned)

The goal: one place for the volkstuin. It has sensor graphs, a 3D map of the plot with what grows where, a seed
log, to-dos, the species found, and an advisor that uses the local LLM and only answers from trusted sources.
Styling is done by the human (Claude); features are filled in by the local agent in small loops (`docs/loops.md`).

Status as of 2026-11-22.

## Done

| What | Where | Notes |
|---|---|---|
| Design system: tokens, base, components, `ui.html` macros, `/styleguide` | `static/css/`, `templates/ui.html` | Frutiger Aero, frosted glass, light/dark; `test_design_system.py` checks every class |
| Charts (uPlot): ranges, compare days by hour, theme-aware | `static/js/charts.js` | |
| Sign-in (signed cookie + Basic fallback), private pages | `app/auth.py` | 10 failures per 10 min per IP, then 429 |
| Overview page with live partial | `/`, `templates/home.html` | |
| Garden data model and migration | `app/models.py`: objects, crops, plantings, tasks, species, sightings, sources | |
| Common-species catalogue (32 Dutch garden species) | `app/data/common_species.json` | |
| Loop tooling: task-gated step tests, smoke tests, reference-implemented plans | `tests/conftest.py`, `docs/loops.md` | |
| CI repaired: hadolint step, image smoke `SESSION_SECRET`, release calls migrations as a job | `.github/workflows/` | `main` CI had been red since 2026-11-19 |

The foundation is PR #7 (`garden-v2/foundation`), waiting for review.

## Running and queued loops

| Job | Branch | Loop | Tasks | State |
|---|---|---|---|---|
| #21 | `agent/sensors-steps` | Sensors page (SPEC §11) | S01–S09 | running; S01–S08 done |
| #20 | `agent/tasks-steps` | Tasks (SPEC §14) | D01–D08 | queued |
| #22 | `agent/species-steps` | Species and sightings (SPEC §15) | E01–E10 | queued |

Each loop ends with a PR. After review: merge it into the foundation (conflicts are only in `app/main.py`,
`app/web.py`, `.agent-protected` and `PLAN.md`), and remove the loop's PLAN.md.

Stopped and replaced: jobs #16–#18 (`agent/garden-sensors`, `-tasks`, `-species`; draft PRs #8, #9). Their
tasks were too large. Close those branches.

## Planned (proposals)

### 1. Garden map core (human, SPEC §12)
A 3D view of the plot with three.js (vendored), built by the human because it is all layout and interaction:
- `static/js/garden3d.js`: an orbit camera, a ground plane in metres, one mesh per `garden_object`, click to
  select, drag to move, handles to rotate and resize. Saving goes through the object API.
- `templates/garden.html`: the canvas, a toolbar (add object by kind) and an inspector card with the selected
  object's properties.
- A per-kind property schema (`app/objects.py: KIND_PROPS`), for example:
  - garden house: door side, height, roof colour;
  - bed: soil type, raised yes/no, sun hours;
  - dirt patch: dug yes/no, last compost date;
  - water butt: litres;
  - tree: species, crown diameter;
  - sensor: node id.

Needs from you: a sketch of the plot with its sizes, and where the shed, beds and sensors are.

### 2. Loop G: objects API and map data (agent, ~9 tasks)
`validate_object(form, kind)` per `KIND_PROPS`, `object_json`, the `/api/v1/objects` routes (GET, POST, PATCH,
DELETE) as fill-ins. Also `soil_grid(points, width, depth, cell)` (inverse-distance weighting of the latest
soil moisture between sensors, for the ground colour) and `pins(db)` (open tasks and unremoved harmful
sightings with x/y, to draw on the map).

### 3. Loop P: seed log (agent, ~10 tasks, SPEC §13)
The crop catalogue (days to germinate and to harvest, spacing, family for rotation) and plantings placed by bed
or by point:
- `validate_planting`, `expected_harvest(sown, crop)`, `status_timeline(planting)`;
- `rotation_warning(bed, crop, history)` (same family in the same bed within 3 years);
- the list grouped by bed, and plantings drawn on the map.

### 4. Loop A: growth model and advisor (agent + human, SPEC §16)
- **Growth model** (pure functions, ideal loop tasks): `growing_degree_days(temps, base)` from the station's
  temperature, `progress(planting, gdd)` against the crop's GDD-to-harvest, and an extrapolated harvest date
  from the last 14 days' GDD rate.
- **Best spot**: `score_spots(crop, beds, soil, sun, history)`. It ranks beds by sun hours, average soil moisture
  against the crop's needs, and rotation. It shows the top three with reasons.
- **Advisor**: a question box on the seed log, answered by the local model through the agent gateway
  (`LLM_BASE_URL`, alias `coder`). The answer comes only from `source` rows (growing guides, seed packets, your
  own notes) and must cite them. An answer without a valid citation is rejected and shown as "not in the
  sources". The human builds the prompt and the citation check; the loop fills in the source search and
  ranking.

### 5. Later
Photos on plantings, harvest weights and yearly totals, frost alerts from the station temperature (push via
ntfy), a mobile "walk the garden" check-in view.

## Open decisions (waiting on you)
- Plot sketch and sizes (blocks the map core).
- Which pages are public. The default is Overview and Sensors public, everything else private.
- The state of the Pi and the sensor hardware.
- A `SESSION_SECRET` in OpenBao before the first deploy of v2.
- Whether to make the repo private (an old email draft is in its history).
