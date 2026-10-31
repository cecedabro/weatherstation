# Design brief — Frutiger Aero (your call)

Visual design is yours to own. The brief is the *aesthetic*, not pixel specs.
Make deliberate choices and keep them consistent across the site.

## Starting point: `index.html`
The repo root has `index.html`, a landing-page mock that Cédric already approved.
Reuse its palette, glass cards, fonts and spacing as your design tokens in T11
(copy the CSS into `static/`, don't link to the file). Don't edit `index.html`.

## The look: Frutiger Aero
The optimistic mid-2000s "clean tech + nature" aesthetic. Think: glossy but
clean, translucent glass surfaces, soft gradients, water and greenery, bright
skies, rounded shapes, a sense of calm and abundance. It fits a garden weather
station well.

Pull it off with, for example:
- Palette: sky blues and fresh greens, white, with glass/translucent panels over
  a soft gradient or a subtle nature background. Good contrast for text, always.
- Surfaces: frosted-glass cards (backdrop blur), soft shadows, generous rounding,
  a subtle gloss/highlight on primary elements — without burying the data.
- Typography: a clean humanist sans (e.g. the Frutiger-adjacent free fonts); large,
  confident numbers for current conditions.
- Motion: gentle, optional, never blocking. Respect `prefers-reduced-motion`.
- Imagery/icons: simple weather and plant motifs; keep them light so the page
  stays fast and legible.

## Non-negotiables (these beat the aesthetic)
- Readability and contrast (WCAG AA) win over gloss. The numbers are the point.
- Fast and self-contained: vendor fonts/CSS/JS locally, no third-party CDNs, no
  heavy image payloads. The site runs on the homelab for a handful of viewers.
- Responsive to 360px; the glass/gradient must not cause horizontal scroll or
  unreadable text on a phone in sunlight.
- Accessible: semantic HTML, focus states, alt text, reduced-motion support.

## What to keep consistent
Pick a small set of design tokens (colours, radius, blur, spacing, type scale),
put them in CSS custom properties in one stylesheet, and reuse them. Record the
palette and font choice in PROGRESS.md so later tasks stay consistent. The admin
page can be plainer; the public page carries the aesthetic.
