# Profile Engine

Local-first calculator for the Omni-Profile system. Reads `birth:` blocks from canon pages and computes structured chart data across four esoteric systems. Pure Python on top of Swiss Ephemeris.

Spec: `Master_Profile_System_Architecture.md` (in `~/Downloads/`). Schema: `vault/10_META/AGENTS.md` → "Birth data — the `birth:` block".

## Install

```bash
pip3 install --user -r tools/profile-engine/requirements.txt
```

Dependencies: `pyswisseph` (Swiss Ephemeris bindings) and `PyYAML`. Uses the bundled Moshier analytical ephemeris — no external data files required.

## Current state: v0.5

For every canon page with a populated `birth:` block (precision 1, 2, or 3), computes whatever each system can given the available data:

- **Western astrology** — 11 bodies (Sun, Moon, Mercury–Pluto, True Node) · 12 Placidus houses · ASC/MC · major + minor aspects · element + modality balance
- **Mayan calendar** (GMT-584283 correlation) — day-sign (K'iche' + Yucatec) · tone (1–13) · trecena start · full Long Count
- **Human Design** — Type · Strategy · Authority · Profile · Definition · Defined Centers · Activated Channels · Hanging Gates · Incarnation Cross (gates + angle type). Wheel calibrated at 3.875° tropical Aries; verified against Jovian Archive output for N8 and Matty
- **Chinese astrology** (Layers 1, 2, 3) — Year pillar (Animal + Element + Yin/Yang polarity) · Inner Animal (Month, by solar term) · Secret Animal (Hour, by 2-hour block)

Precision tiers (set via `birth.precision` in the canon page frontmatter):
- **1** (date + time + place) — all systems compute fully
- **2** (date + place, no time) — Western planets + aspects + balance (Moon ±6°); Mayan full; Chinese Year + Inner; HD skipped (needs time); no houses / Rising
- **3** (date only) — same as L2; place is reserved for future Astro-Geography

Essentials go to canon-page frontmatter as `profile:`. Full chart goes to a sibling `<Name>.profile.yaml`.

```bash
python3 tools/profile-engine/compute.py                              # dry-run for all entities
python3 tools/profile-engine/compute.py --path "04_CANON/Personal/N8.md"
python3 tools/profile-engine/compute.py --write                      # persist to frontmatter + sibling files
```

## Files

- `vault.py` — walk `04_CANON/`, parse frontmatter, yield entities with a populated `birth:` block.
- `western.py` — pyswisseph wrappers. Local civil time + IANA tz → JD UT → planet positions and house cusps. Tropical zodiac; Placidus houses.
- `mayan.py` — GMT correlation, K'iche' + Yucatec day-sign names, tone, trecena, Long Count.
- `human_design.py` — Personality + Design activations (sun-88° via swisseph `solcross_ut`), gate-line projection, center / channel / type / authority / profile / cross derivation.
- `chinese.py` — Year / Month / Hour pillars. CNY date table for 1900–2050 (precomputed for accuracy across leap years).
- `writer.py` — two-target write: essentials → canon page frontmatter; full chart → sibling `.profile.yaml`. Uses an `IndentedDumper` for 2-space list indentation (vault convention).
- `compute.py` — CLI entrypoint.

## Roadmap

### Next version — surface these deferrals first when work resumes

When the next engine version is started, the model should remind N8 of these explicit deferrals up front rather than burying them in the roadmap:

- **🔔 Chinese astrology Layer 4 — BaZi Four Pillars.** Year/Month/Day/Hour each with full Stem + Branch (8 characters total). Includes Day Master analysis, Useful God / favorable element identification, ten gods (shi shen), and full BaZi pillar interpretation. Explicitly deferred by N8 during the v0.4 build with the instruction: *"we will add the fourth layer later. When we work on the next version, you're automatically going to remind me that we're adding the next layer."* This is the loudest deferral on the roadmap.

### Other deferrals

- **Astro-Geography** — AstroCartography lines, Parans, Local Space. Map rendering is heavier than ephemeris math; needs a tile renderer or SVG world map.
- **Asteroids (Chiron, Ceres, Pallas, Juno, Vesta, Eris)** — require the external `seas_*.se1` ephemeris files from astro.com.
- **Western minor aspects** — currently has conjunction/sextile/square/trine/opposition + quincunx + semi-sextile. Could add septile/quintile/biquintile.
- **Western: Whole-Sign houses option** alongside Placidus.
- **HD Variables** — Color / Tone / Base layers beneath line.
- ~~**HD Incarnation Cross *names*** — 192-entry table~~ — shipped 2026-05-18. `INCARNATION_CROSS_NAMES` in `human_design.py` maps `(angle, P_Sun_gate)` → canonical name (e.g., "Right Angle Cross of Consciousness"). Names confirmed against the 14 entities in the network; remaining gates use canonical recall and may need verification against Jovian Archive output for edge cases.
- **Mayan 5-sign cross + year-bearer** — the directional cross construction varies across K'iche' / Yucatec / Aztec sources; needs a deliberate lineage choice.
- ~~**Level 2 / Level 3 graceful fallback**~~ — shipped in v0.5.
- **Animals** — same `birth:` schema; engine just needs to be allowed to process `type: animal`. Currently skipped per v1 scope decision.

### Viewer (separate from the engine)

- **Static HTML site** — read sibling `.profile.yaml` files → emit per-person chart cards, a relational network graph, synastry pair views. Not yet started.

## Conventions

- Calculations are reproducible: local civil time + IANA timezone are the inputs; `zoneinfo` handles DST and historical zone changes.
- `precision` is human-set in the `birth:` block. The engine refuses to compute houses or HD without it.
- All output is structured data. Interpretation (narrative, "what this means") is the viewer's job, not the engine's.
- Engine version bumps with each new system or breaking schema change. Current: 0.5.
