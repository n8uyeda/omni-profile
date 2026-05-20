# Profile Viewer

Static-site generator for the Omni-Profile system. Reads canon-page frontmatter (`profile:` essentials) and sibling `<Name>.profile.yaml` files, renders a browser-viewable interactive network at `site/` (repo root, gitignored).

Spec: [`Master_Profile_System_Architecture.md`](../../Master_Profile_System_Architecture.md). Pairs with [`tools/profile-engine/`](../profile-engine/).

## Install

```bash
pip3 install --user -r tools/profile-viewer/requirements.txt
```

Dependencies: `Jinja2`, `PyYAML`. Cytoscape.js is loaded via CDN at view time — no JS build step.

## Run

```bash
python3 tools/profile-viewer/build.py
open site/index.html
```

The site is static — no dev server required. Re-run after birth-data changes or engine recomputations.

## What's rendered (v0.6)

- **`site/index.html`** — Cytoscape network graph (entities as nodes, surfaced relational connections as edges) + entity cards with KPI chips
- **`site/people/<Name>.html`** — Per-person Dashboard:
  - KPI cards (Western · HD · Mayan · Chinese)
  - Western chart wheel SVG (zodiac ring + 12 houses + planets + aspect lines)
  - HD bodygraph SVG (9 canonical shapes + active channels + hanging gates)
  - Detail tables (planets, aspects, channels, birth data)
  - Network connections to other entities
- **`site/pair/<A>--<B>.html`** — Synastry pair view (shared profile / channels / element / animal etc.)
- **`site/assets/data.json`** — Network graph data for the Cytoscape JS

## Connection types surfaced in the network (v0.6)

| Kind | Weight | Source |
|---|---|---|
| HD channel (shared activation) | 2.5 each | full chart |
| Mayan day-sign match | 2.0 | essentials |
| Sun sign match | 1.5 | essentials |
| HD profile match | 1.5 | essentials |
| Chinese year animal match | 1.5 | essentials |
| Dominant element match | 1.0 | essentials |
| Mayan tone match | 1.0 | essentials |
| Chinese year element / inner animal match | 1.0 | essentials |
| HD cross angle / 2+ shared defined centers | 0.5 | full chart |

Edge weight is the sum across surfaced connections. Edge thickness scales with weight.

## Files

- `data.py` — load entities from `04_CANON/` (frontmatter + sibling `.profile.yaml`).
- `synastry.py` — compute pattern-match connections between entity pairs.
- `svg_western.py` — render the Western chart wheel SVG (zodiac, houses, planets, aspects).
- `svg_hd.py` — render the HD bodygraph SVG (centers, channels, hanging gates).
- `templates/` — Jinja2 templates: `base`, `index`, `person`, `pair`.
- `static/css/style.css` — single stylesheet, no preprocessor.
- `build.py` — CLI entrypoint.

## Roadmap

### v0.8 (current) — what landed
- Three runtime themes (Deep Space / Cosmic Glass / Planetarium) with toggle
- Western chart upside-down bug fixed
- Canonical HD bodygraph: 64 gates in centers, all 36 channels, activation circles, split-color channel halves, hanging-gate stubs, body silhouette
- Plain hover tooltips on all chart elements (~153 canonical descriptions)
- **Design / Personality activation columns** flanking the bodygraph (13 planet glyphs + gate.line per side, themed with `--hd-personality` red for Design, `--text` for Personality)
- **Index page redesign**: selector checkboxes next to each entity, dynamic dashboards panel above the selector with Stacked / Overlaid toggle. Each mini-dashboard renders KPI cards + Western wheel + bodygraph + activation columns
- **The Mandala chart** — new chart type combining the zodiac wheel (12 sign sectors) + 64 HD gate sectors at tropical longitudes + Unicode I Ching hexagrams (☰..☷ block) outermost + planet placements + nested bodygraph at the center. Aries fixed at 9 o'clock, longitude CCW visually (so Capricorn at top matches the canonical Jovian Archive mandala orientation)

### v0.9 — explicit deferrals (surface these first when work resumes)

When the next viewer version is started, the model should remind N8 of these explicit deferrals up front:

- **🔔 Structured tooltips** — Replace the v0.7 plain tooltips (name + 1-sentence description) with structured ones: glyph + canonical reference (e.g., for HD gate 17: "Gate 17 ☉ — The Following / Hexagram 17"; for planets: "☉ Sun — Core identity"). N8 said *"don't forget!"* when deferring this.
- **🔔 Placement-specific tooltip interpretations** — Add a "read deeper" link/click on each tooltip that opens an LLM-generated placement-specific reading (e.g., "Sun in Gemini in 7th house" interpretations, gate.line interpretations). Currently generic-only.
- **🔔 Detailed readings** — LLM-generated multi-section reading per person. Originally planned for v0.8 but bumped because the visual rebuild took the slot. Requires Anthropic API key.
- **🔔 True synastry overlay math** — The current "overlaid" view-mode just stacks dashboards with hue-rotate filters as a visual distinguisher. Real synastry overlay needs both Western wheels rendered in the same SVG with Asc-anchored alignment and planets color-coded by entity; both bodygraphs in one with defined centers blended; cross-aspects computed between the two charts (planet of A vs planet of B).
- **🔔 Mandala in mini-dashboards** — The mandala currently renders only on the per-person page. v0.9 could add it to the mini-dashboards too (toggle: Western / Bodygraph / Mandala).
- **🔔 Mandala: activated-gate highlighting refinement** — Right now active gates get an accent-color stroke + glow. Could also color the wedge fill by activation state (P red / D dark / both striped) to match the bodygraph treatment.

### Other deferrals

- Precise per-gate positioning refinement on the HD bodygraph (current positions are approximate canonical).
- Proper Western synastry math: cross-aspects between two charts, composite midpoints, house overlays.
- Search / filter on the index; node clustering by domain or HD type.
- Narrative view (View C from the spec): prose synthesis per person.
- Hosting (static, deploy to any HTTP server or Pages provider).

## Conventions

- Pure static output. No dev server. Open `site/index.html` in any browser.
- `site/` is regenerated on every build and is gitignored.
- Cytoscape.js is loaded from CDN. If you ship offline, vendor it into `static/js/`.
- The viewer never modifies vault data. One-way: vault → site.
