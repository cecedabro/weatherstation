# Design system (human-owned)

The look is **Frutiger Aero, fresh-Apple frosted glass**: sky and leaf colours, glass cards with a soft
sheen, glossy candy buttons, calm motion. It is finished and lives in a few human-owned files. **You do not
write CSS.** You build pages from the components that exist.

## Where it lives
| File | What |
|---|---|
| `backend/app/static/css/tokens.css` | Colours, glass, shadows, radius, spacing (light + dark) |
| `backend/app/static/css/base.css` | Reset, background scene, type, page frame, layout helpers |
| `backend/app/static/css/components.css` | Every component class |
| `backend/app/templates/ui.html` | Jinja macros that output those components |
| `backend/app/templates/base.html` | The page layout (top bar, nav, main, footer) |
| `backend/app/styleguide.py` + `/styleguide` | Every component, live, with the exact call |
| `backend/app/static/js/ui.js` | Theme switch, dialogs, confirm, live "x min ago" |
| `backend/app/static/js/charts.js` | Draws every `ui.chart()` with uPlot |

All of these are in `.agent-protected`: the harness rejects changes to them.

## How to build a page
1. `{% extends "base.html" %}` (it already imports `ui`). Set `active` in the route (a key of `NAV` in
   `app/templating.py`) so the nav marks the page.
2. Open `/styleguide` (or `app/styleguide.py`) and copy the calls you need: `ui.page_head`, `ui.card`,
   `ui.stat`, `ui.table`, `ui.field`, `ui.chart`, `ui.chip`, `ui.alert`, `ui.empty`, `ui.list_item`, …
3. Lay cards out with the layout classes from `base.css`: `grid`, `grid-2`, `grid-3`, `split`, `stack`,
   `row`, `row-between`, `section`, `span-all`. Text helpers: `muted`, `small`, `num`, `strong`.
4. Render from the route with `app.templating.render(request, "page.html", active="tasks", **ctx)`.

## Rules (tests/test_design_system.py enforces them)
- Only classes defined in `static/css/` may appear in templates and JS.
- No `<style>` blocks, no `style=""` attributes, no new `.css` files.
- No inline `<script>`; page JS goes in `static/js/pages/<page>.js` (you may write these) and uses existing
  classes only. Never restyle anything from JS.
- Colours for categories always come from the swatch order `ui.swatch(1..8)` (same as chart series), so a
  bed, a crop or a sensor keeps its colour everywhere.
- Status colours: ok = good, info = neutral, warn = attention, bad = act now, off = inactive. Urgency
  uses `ui.chip(text, urgency="low|normal|high|critical")`.
- Every page needs an empty state (`ui.empty`) and must work at 360 px wide.

If a page needs something that does not exist, use the closest component and write in `PROGRESS.md`
what you were missing. The human adds components; you never add CSS.
