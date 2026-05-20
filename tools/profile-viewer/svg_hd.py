"""
Render a canonical HD bodygraph as SVG, themed via CSS variables.

v0.7 rewrite — matches the canonical Jovian-Archive-style chart:
  - 64 gate positions encoded within their centers (canonical groupings)
  - All 36 channels rendered as structural lines (faint when inactive)
  - Gate numbers written inside each center
  - Activation circles around gates activated by Personality / Design / both
  - Channel halves split-colored by activation source (P = red, D = green)
  - Hanging gates get a short emanation half-line
  - Body silhouette as a subtle ghost behind everything
  - Sci-fi treatment: defined centers glow, active channels glow

viewBox: 460x680.
"""
from __future__ import annotations

import secrets


def _uid() -> str:
    """Short unique suffix to keep SVG <filter>/<pattern> IDs unique per render.

    Why: when two bodygraphs share a page (e.g. the standalone bodygraph plus
    the one nested inside the mandala), duplicate IDs make Firefox resolve
    `filter: url(#hd-defined-glow)` to the first matching element in document
    order — which, on desktop, is inside the standalone bodygraph (hidden
    via display:none). Firefox then refuses to apply the filter and the
    nested-bodygraph centers render without their lineage colors / glow.
    Chrome/Brave are forgiving and pick a same-SVG match. Per-render uids
    eliminate the collision."""
    return secrets.token_hex(3)


# --------------------------------------------------------------------
# Center geometry (vertices for shape rendering, anchor for fallback)
# --------------------------------------------------------------------
CENTERS = {
    "head":         {"var": "--hd-head",         "label": "Head"},
    "ajna":         {"var": "--hd-ajna",         "label": "Ajna"},
    "throat":       {"var": "--hd-throat",       "label": "Throat"},
    "g":            {"var": "--hd-g",            "label": "G"},
    "heart":        {"var": "--hd-heart",        "label": "Heart"},
    "solar_plexus": {"var": "--hd-solar_plexus", "label": "Solar Plexus"},
    "sacral":       {"var": "--hd-sacral",       "label": "Sacral"},
    "spleen":       {"var": "--hd-spleen",       "label": "Spleen"},
    "root":         {"var": "--hd-root",         "label": "Root"},
}

# Canonical bodygraph layout — Head AND Ajna both apex-down (Jovian Archive
# standard). Coordinates in viewBox 460x680.
LAYOUT = {
    "head":   {"shape": "triangle_down", "vertices": [(180, 30), (280, 30), (230, 110)]},
    "ajna":   {"shape": "triangle_down", "vertices": [(180, 130), (280, 130), (230, 210)]},
    "throat": {"shape": "rect",          "bounds":   (165, 230, 295, 310)},
    "g":      {"shape": "diamond",       "vertices": [(230, 330), (295, 400), (230, 470), (165, 400)]},
    "heart":  {"shape": "triangle_left", "vertices": [(360, 340), (360, 400), (300, 370)]},
    "solar_plexus": {"shape": "triangle_left", "vertices": [(390, 430), (390, 580), (280, 505)]},
    "sacral": {"shape": "rect",          "bounds":   (165, 485, 295, 565)},
    "spleen": {"shape": "triangle_right","vertices": [(50, 430), (50, 580), (165, 505)]},
    "root":   {"shape": "rect",          "bounds":   (165, 600, 295, 670)},
}

# --------------------------------------------------------------------
# 64 gate positions inside their centers (canonical groupings)
# --------------------------------------------------------------------
GATE_POSITIONS: dict[int, tuple[float, float]] = {
    # HEAD — single row across top of inverted triangle
    64: (203, 58),
    61: (230, 58),
    63: (257, 58),

    # AJNA — 3 / 2 / 1 row layout, all inside inverted triangle
    47: (200, 152),
    24: (230, 152),
     4: (260, 152),
    17: (215, 175),
    11: (245, 175),
    43: (230, 196),

    # THROAT — 3 / 2-wide / 2-wide / 4 rows
    62: (185, 248),
    23: (230, 248),
    56: (275, 248),
    16: (180, 266),
    35: (280, 266),
    20: (180, 284),
    12: (280, 284),
    31: (180, 302),
     8: (210, 302),
    33: (250, 302),
    45: (280, 302),

    # G — diamond, 5 row arrangement
     1: (230, 348),
     7: (215, 374),
    13: (245, 374),
    10: (190, 400),
    25: (270, 400),
    15: (215, 425),
    46: (245, 425),
     2: (230, 452),

    # HEART — small triangle, 4 gates
    21: (340, 358),
    51: (343, 372),
    26: (313, 372),
    40: (343, 388),

    # SOLAR PLEXUS — 7 gates along the long edge (apex-left)
    36: (375, 455),
    22: (368, 480),
    37: (300, 505),
     6: (360, 505),
    49: (360, 530),
    55: (350, 555),
    30: (370, 568),

    # SACRAL — 4 rows
     5: (185, 502),
    14: (230, 502),
    29: (275, 502),
    34: (230, 522),
    27: (200, 542),
    59: (260, 542),
    42: (185, 558),
     3: (230, 558),
     9: (275, 558),

    # SPLEEN — back column + interior 3
    48: (70, 450),
    57: (80, 478),
    44: (90, 503),
    50: (95, 528),
    32: (118, 487),
    28: (132, 510),
    18: (115, 547),

    # ROOT — 3 / 2 / 2 / 2 rows
    53: (185, 614),
    60: (230, 614),
    52: (275, 614),
    54: (200, 632),
    19: (260, 632),
    38: (200, 648),
    39: (260, 648),
    58: (215, 663),
    41: (245, 663),
}
assert len(GATE_POSITIONS) == 64, f"expected 64 gate positions, got {len(GATE_POSITIONS)}"

CENTER_OF_GATE: dict[int, str] = {}
def _reg(center: str, gates: list[int]) -> None:
    for g in gates:
        CENTER_OF_GATE[g] = center
_reg("head",         [64, 61, 63])
_reg("ajna",         [47, 24, 4, 17, 43, 11])
_reg("throat",       [62, 23, 56, 35, 12, 45, 33, 8, 31, 20, 16])
_reg("g",            [1, 13, 25, 46, 2, 15, 10, 7])
_reg("heart",        [21, 40, 26, 51])
_reg("solar_plexus", [36, 22, 37, 6, 49, 55, 30])
_reg("sacral",       [5, 14, 29, 59, 9, 3, 42, 27, 34])
_reg("spleen",       [48, 57, 44, 50, 32, 28, 18])
_reg("root",         [53, 60, 52, 19, 39, 41, 58, 38, 54])

# All 36 channels (gate pairs)
ALL_CHANNELS: list[tuple[int, int]] = [
    (1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31),
    (9, 52), (10, 20), (10, 34), (10, 57), (11, 56), (12, 22),
    (13, 33), (16, 48), (17, 62), (18, 58), (19, 49), (20, 34),
    (20, 57), (21, 45), (23, 43), (24, 61), (25, 51), (26, 44),
    (27, 50), (28, 38), (29, 46), (30, 41), (32, 54), (34, 57),
    (35, 36), (37, 40), (39, 55), (42, 53), (47, 64),
]


def _shape_open(layout: dict) -> str:
    if layout["shape"] == "rect":
        x1, y1, x2, y2 = layout["bounds"]
        return f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" rx="2"'
    elif layout["shape"] in ("triangle_down", "triangle_up", "triangle_left", "triangle_right", "diamond"):
        pts = " ".join(f"{x},{y}" for x, y in layout["vertices"])
        return f'<polygon points="{pts}"'
    return ""


# Body silhouette path — subtle ghost: head + neck + tapered torso.
BODY_SILHOUETTE = (
    "M 230 18 "
    "C 195 18 175 48 175 86 "
    "C 175 124 195 142 230 142 "
    "C 265 142 285 124 285 86 "
    "C 285 48 265 18 230 18 Z "
    "M 200 148 L 260 148 L 270 178 L 410 318 L 450 670 L 10 670 L 50 318 L 190 178 Z"
)


def render_bodygraph_combined(charts_hd: list[dict | None], entity_colors: list[str], entity_names: list[str]) -> str:
    """Render a combined bodygraph overlay for N entities.

    Each center:
      - Defined by no one      → undefined (white)
      - Defined by one entity  → filled with that entity's color
      - Defined by 2+ entities → striped fill (alternating entity colors)
    Each gate:
      - Activated by 1 entity  → solid circle in that entity's color
      - Activated by 2+        → striped circle (using same patterns)
    Channels:
      - Active in 1 entity     → line in that entity's color
      - Active in 2+           → gradient between entity colors
    """
    # Per-render unique suffix for filter / pattern IDs (see _uid()).
    uid = _uid()
    f_def = f'hdc-defined-glow-{uid}'
    f_chn = f'hdc-channel-glow-{uid}'
    p_both = f'hdc-both-pattern-{uid}'
    out: list[str] = [
        f'<svg viewBox="0 0 460 680" xmlns="http://www.w3.org/2000/svg" class="bodygraph">',
        '<defs>',
        f'  <filter id="{f_def}" x="-30%" y="-30%" width="160%" height="160%">',
        '    <feGaussianBlur stdDeviation="3" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        f'  <filter id="{f_chn}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.5" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
    ]
    # One stripe pattern per pair-of-entities combination we need (for 2 entities,
    # we need one "both" pattern). For more entities, more patterns.
    if len(entity_colors) >= 2:
        out.append(
            f'  <pattern id="{p_both}" patternUnits="userSpaceOnUse" '
            f'width="6" height="6" patternTransform="rotate(45)">'
            f'<rect x="0" y="0" width="3" height="6" fill="{entity_colors[0]}"/>'
            f'<rect x="3" y="0" width="3" height="6" fill="{entity_colors[1]}"/>'
            f'</pattern>'
        )
    out.extend([
        '  <style>',
        '    .body-silhouette { fill: var(--text); opacity: 0.05; }',
        '    .center-stroke { stroke: var(--hd-stroke); stroke-width: 1.2; }',
        '    .center-undef-fill { fill: var(--hd-undef-bg); }',
        '    .channel-structure { stroke: var(--hd-stroke-weak); stroke-width: 1.4; stroke-linecap: round; opacity: 0.45; }',
        f'    .channel-overlay-line {{ stroke-width: 4; stroke-linecap: round; filter: url(#{f_chn}); }}',
        '    .gate-num { font-family: "JetBrains Mono", monospace; font-size: 8.5px; font-weight: 600; }',
        '    .gate-num-undefined { fill: var(--text-dim); }',
        '    .gate-num-activated { fill: #ffffff; }',
        '    .center-label-text { font-family: "JetBrains Mono", monospace; font-size: 7px; letter-spacing: 0.08em; text-transform: uppercase; }',
        '    .center-label-defined { fill: rgba(0, 0, 0, 0.6); }',
        '    .center-label-undefined { fill: var(--text-faint); }',
        '    .overlay-legend-text { font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.04em; }',
        '  </style>',
        '</defs>',
    ])

    # Body silhouette
    out.append(f'<path d="{BODY_SILHOUETTE}" class="body-silhouette"/>')

    # Per-entity activation sets
    per_entity_p = []
    per_entity_d = []
    per_entity_activated = []
    per_entity_defined = []
    per_entity_channels_active = []
    for chart in charts_hd:
        if chart is None or "skipped" in (chart or {}):
            per_entity_p.append(set())
            per_entity_d.append(set())
            per_entity_activated.append(set())
            per_entity_defined.append(set())
            per_entity_channels_active.append(set())
            continue
        p_g = {a["gate"] for a in chart.get("personality_activations", [])}
        d_g = {a["gate"] for a in chart.get("design_activations", [])}
        per_entity_p.append(p_g)
        per_entity_d.append(d_g)
        per_entity_activated.append(p_g | d_g)
        per_entity_defined.append(set(chart.get("defined_centers", [])))
        per_entity_channels_active.append(
            {tuple(sorted(c["gates"])) for c in chart.get("channels", [])}
        )

    def entities_defining(center: str) -> list[int]:
        return [i for i, defs in enumerate(per_entity_defined) if center in defs]

    def entities_activating_gate(gate: int) -> list[int]:
        return [i for i, act in enumerate(per_entity_activated) if gate in act]

    def entities_with_channel(a: int, b: int) -> list[int]:
        pair = tuple(sorted((a, b)))
        return [i for i, chs in enumerate(per_entity_channels_active) if pair in chs]

    # 1. Structural channel lines (all 36 faint)
    for a, b in ALL_CHANNELS:
        ax, ay = GATE_POSITIONS[a]
        bx, by = GATE_POSITIONS[b]
        out.append(
            f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" class="channel-structure" '
            f'data-tip-type="channel" data-tip-id="{a}-{b}"/>'
        )

    # 2. Active channels (entity-colored)
    for a, b in ALL_CHANNELS:
        actives = entities_with_channel(a, b)
        if not actives:
            continue
        ax, ay = GATE_POSITIONS[a]
        bx, by = GATE_POSITIONS[b]
        if len(actives) == 1:
            stroke = entity_colors[actives[0]]
            out.append(
                f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" '
                f'class="channel-overlay-line" stroke="{stroke}"/>'
            )
        else:
            # Multi-entity active: use gradient between first two entity colors
            grad_id = f"hdc_grad_{a}_{b}"
            out.append(
                f'<defs><linearGradient id="{grad_id}" x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0%" stop-color="{entity_colors[actives[0]]}"/>'
                f'<stop offset="100%" stop-color="{entity_colors[actives[1]]}"/>'
                f'</linearGradient></defs>'
            )
            out.append(
                f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" '
                f'class="channel-overlay-line" stroke="url(#{grad_id})"/>'
            )

    # 3. Centers
    for cname, ldata in LAYOUT.items():
        definers = entities_defining(cname)
        if not definers:
            fill_attr = ' class="center-undef-fill center-stroke"'
        elif len(definers) == 1:
            color = entity_colors[definers[0]]
            fill_attr = f' fill="{color}" filter="url(#{f_def})" class="center-stroke"'
        else:
            fill_attr = f' fill="url(#{p_both})" filter="url(#{f_def})" class="center-stroke"'
        out.append(
            f'{_shape_open(ldata)}{fill_attr} '
            f'data-tip-type="center" data-tip-id="{cname}"/>'
        )

    # 4. Center labels
    for cname, ldata in LAYOUT.items():
        x, y = (200, 305)  # placeholder, overridden below
        # Use the canonical label positions from the regular renderer
    label_offsets = {
        "head":          (230, 22),
        "ajna":          (230, 220),
        "throat":        (230, 322),
        "g":             (230, 482),
        "heart":         (330, 405),
        "solar_plexus":  (335, 593),
        "sacral":        (230, 577),
        "spleen":        (107, 593),
        "root":          (230, 682),
    }
    for cname, (lx, ly) in label_offsets.items():
        is_defined = bool(entities_defining(cname))
        cls = "center-label-text center-label-defined" if is_defined else "center-label-text center-label-undefined"
        out.append(
            f'<text x="{lx}" y="{ly}" class="{cls}" '
            f'text-anchor="middle">{CENTERS[cname]["label"]}</text>'
        )

    # 5. Gates with activation circles
    for gate, (gx, gy) in GATE_POSITIONS.items():
        activators = entities_activating_gate(gate)
        # Invisible hover target
        out.append(
            f'<circle cx="{gx}" cy="{gy}" r="9" fill="transparent" '
            f'data-tip-type="gate" data-tip-id="{gate}"/>'
        )
        if activators:
            r = 6.5
            if len(activators) == 1:
                color = entity_colors[activators[0]]
                out.append(f'<circle cx="{gx}" cy="{gy}" r="{r}" fill="{color}" stroke="{color}" stroke-width="1.2"/>')
            else:
                out.append(f'<circle cx="{gx}" cy="{gy}" r="{r}" fill="url(#{p_both})" stroke="{entity_colors[activators[0]]}" stroke-width="1.2"/>')
            text_cls = "gate-num gate-num-activated"
        else:
            text_cls = "gate-num gate-num-undefined"
        out.append(
            f'<text x="{gx}" y="{gy}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'style="pointer-events: none">{gate}</text>'
        )

    # 6. Legend (top-left corner)
    for i, name in enumerate(entity_names):
        y = 16 + i * 14
        out.append(f'<circle cx="14" cy="{y}" r="5" fill="{entity_colors[i]}" filter="url(#{f_def})"/>')
        out.append(f'<text x="24" y="{y}" class="overlay-legend-text" fill="{entity_colors[i]}" dominant-baseline="central">{name}</text>')

    out.append('</svg>')
    return "\n".join(out)


def render_bodygraph(chart_hd: dict | None, size: int = 460) -> str:
    # Per-render unique suffix for filter / pattern IDs. See _uid() docstring.
    uid = _uid()
    f_def = f'hd-defined-glow-{uid}'
    f_chn = f'hd-channel-glow-{uid}'
    f_act = f'hd-activation-glow-{uid}'
    p_str = f'stripe-pattern-{uid}'
    out: list[str] = [
        f'<svg viewBox="0 0 460 680" xmlns="http://www.w3.org/2000/svg" class="bodygraph">',
        '<defs>',
        # Filters
        f'  <filter id="{f_def}" x="-30%" y="-30%" width="160%" height="160%">',
        '    <feGaussianBlur stdDeviation="3" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        f'  <filter id="{f_chn}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.5" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        f'  <filter id="{f_act}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.5" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <style>',
        '    .body-silhouette { fill: var(--text); opacity: 0.05; }',
        '    .center-stroke { stroke: var(--hd-stroke); stroke-width: 1.2; }',
        '    .center-undef-fill { fill: var(--hd-undef-bg); }',
        f'    .center-head-fill         {{ fill: var(--hd-head); filter: url(#{f_def}); }}',
        f'    .center-ajna-fill         {{ fill: var(--hd-ajna); filter: url(#{f_def}); }}',
        f'    .center-throat-fill       {{ fill: var(--hd-throat); filter: url(#{f_def}); }}',
        f'    .center-g-fill            {{ fill: var(--hd-g); filter: url(#{f_def}); }}',
        f'    .center-heart-fill        {{ fill: var(--hd-heart); filter: url(#{f_def}); }}',
        f'    .center-solar_plexus-fill {{ fill: var(--hd-solar_plexus); filter: url(#{f_def}); }}',
        f'    .center-sacral-fill       {{ fill: var(--hd-sacral); filter: url(#{f_def}); }}',
        f'    .center-spleen-fill       {{ fill: var(--hd-spleen); filter: url(#{f_def}); }}',
        f'    .center-root-fill         {{ fill: var(--hd-root); filter: url(#{f_def}); }}',
        # Channel layers
        '    .channel-structure { stroke: var(--hd-stroke-weak); stroke-width: 1.4; stroke-linecap: round; opacity: 0.45; }',
        f'    .channel-personality {{ stroke: var(--hd-personality); stroke-width: 4; stroke-linecap: round; filter: url(#{f_chn}); }}',
        f'    .channel-design      {{ stroke: var(--hd-design);      stroke-width: 4; stroke-linecap: round; filter: url(#{f_chn}); }}',
        '    .channel-both-base   { stroke: var(--hd-personality); stroke-width: 4; stroke-linecap: butt; }',
        '    .channel-both-over   { stroke: var(--hd-design); stroke-width: 4; stroke-linecap: butt; stroke-dasharray: 7 7; }',
        # Gate numbers + activation badges
        '    .gate-num { font-family: "JetBrains Mono", monospace; font-size: 8.5px; font-weight: 600; letter-spacing: 0.02em; }',
        '    .gate-num-defined { fill: rgba(0, 0, 0, 0.82); }',
        '    .gate-num-undefined { fill: var(--text-dim); }',
        '    .gate-num-activated { fill: #ffffff; }',
        f'    .activation-circle-personality {{ fill: var(--hd-personality); stroke: var(--hd-personality); stroke-width: 1.2; filter: url(#{f_act}); }}',
        f'    .activation-circle-design      {{ fill: var(--hd-design); stroke: var(--hd-design); stroke-width: 1.2; filter: url(#{f_act}); }}',
        f'    .activation-circle-both        {{ fill: url(#{p_str}); stroke: var(--hd-personality); stroke-width: 1.2; filter: url(#{f_act}); }}',
        # Center labels
        '    .center-label-text { font-family: "JetBrains Mono", monospace; font-size: 7px; letter-spacing: 0.08em; text-transform: uppercase; }',
        '    .center-label-defined { fill: rgba(0, 0, 0, 0.55); }',
        '    .center-label-undefined { fill: var(--text-faint); }',
        '    .skipped-note { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--text-faint); letter-spacing: 0.04em; }',
        '  </style>',
        # Stripe pattern for "both" activations (P + D on same gate)
        f'  <pattern id="{p_str}" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">',
        '    <rect x="0" y="0" width="3" height="6" fill="var(--hd-personality)"/>',
        '    <rect x="3" y="0" width="3" height="6" fill="var(--hd-design)"/>',
        '  </pattern>',
        '</defs>',
    ]

    # 0. Body silhouette (subtle ghost behind everything)
    out.append(f'<path d="{BODY_SILHOUETTE}" class="body-silhouette"/>')

    if chart_hd is None or "skipped" in (chart_hd or {}):
        # Render skeleton only.
        for cname, ldata in LAYOUT.items():
            out.append(f'{_shape_open(ldata)} class="center-undef-fill center-stroke"/>')
        # Gate numbers in undefined state
        for gate, (gx, gy) in GATE_POSITIONS.items():
            out.append(f'<text x="{gx}" y="{gy}" class="gate-num gate-num-undefined" text-anchor="middle" dominant-baseline="central">{gate}</text>')
        out.append('<text x="230" y="675" text-anchor="middle" class="skipped-note">HD REQUIRES PRECISION 1 (DATE + TIME + PLACE)</text>')
        out.append('</svg>')
        return "\n".join(out)

    defined = set(chart_hd.get("defined_centers", []))
    p_gates = {a["gate"] for a in chart_hd.get("personality_activations", [])}
    d_gates = {a["gate"] for a in chart_hd.get("design_activations", [])}
    activated = p_gates | d_gates
    active_channels_set = {tuple(sorted(c["gates"])) for c in chart_hd.get("channels", [])}

    def gate_state(g: int) -> str:
        """'both' | 'personality' | 'design' | 'none'"""
        in_p = g in p_gates
        in_d = g in d_gates
        if in_p and in_d: return "both"
        if in_p: return "personality"
        if in_d: return "design"
        return "none"

    # 1. STRUCTURE — all 36 channel lines as faint guides (with tooltips)
    for a, b in ALL_CHANNELS:
        ax, ay = GATE_POSITIONS[a]
        bx, by = GATE_POSITIONS[b]
        ch_id = f"{a}-{b}"
        out.append(
            f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" class="channel-structure" '
            f'data-tip-type="channel" data-tip-id="{ch_id}"/>'
        )

    # 2. ACTIVE CHANNEL HALVES — split-colored by source gate's activation
    for a, b in ALL_CHANNELS:
        if tuple(sorted((a, b))) not in active_channels_set:
            continue
        ax, ay = GATE_POSITIONS[a]
        bx, by = GATE_POSITIONS[b]
        mx, my = (ax + bx) / 2, (ay + by) / 2

        def render_half(x1: float, y1: float, x2: float, y2: float, state: str) -> None:
            if state == "personality":
                out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="channel-personality"/>')
            elif state == "design":
                out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="channel-design"/>')
            elif state == "both":
                # Striped: solid red base + dashed dark overlay
                out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="channel-both-base"/>')
                out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="channel-both-over"/>')

        render_half(ax, ay, mx, my, gate_state(a))
        render_half(mx, my, bx, by, gate_state(b))

    # 2b. HANGING GATES — short emanation half-line from the gate
    hanging = set(chart_hd.get("hanging_gates", []) or [])
    for a, b in ALL_CHANNELS:
        if a in hanging and b not in activated:
            ax, ay = GATE_POSITIONS[a]
            bx, by = GATE_POSITIONS[b]
            # Short stub: 20% of the channel toward partner
            sx, sy = ax + (bx - ax) * 0.25, ay + (by - ay) * 0.25
            state = gate_state(a)
            if state == "personality":
                out.append(f'<line x1="{ax}" y1="{ay}" x2="{sx}" y2="{sy}" class="channel-personality"/>')
            elif state == "design":
                out.append(f'<line x1="{ax}" y1="{ay}" x2="{sx}" y2="{sy}" class="channel-design"/>')
            elif state == "both":
                out.append(f'<line x1="{ax}" y1="{ay}" x2="{sx}" y2="{sy}" class="channel-both-base"/>')
                out.append(f'<line x1="{ax}" y1="{ay}" x2="{sx}" y2="{sy}" class="channel-both-over"/>')
        if b in hanging and a not in activated:
            ax, ay = GATE_POSITIONS[a]
            bx, by = GATE_POSITIONS[b]
            sx, sy = bx + (ax - bx) * 0.25, by + (ay - by) * 0.25
            state = gate_state(b)
            if state == "personality":
                out.append(f'<line x1="{bx}" y1="{by}" x2="{sx}" y2="{sy}" class="channel-personality"/>')
            elif state == "design":
                out.append(f'<line x1="{bx}" y1="{by}" x2="{sx}" y2="{sy}" class="channel-design"/>')
            elif state == "both":
                out.append(f'<line x1="{bx}" y1="{by}" x2="{sx}" y2="{sy}" class="channel-both-base"/>')
                out.append(f'<line x1="{bx}" y1="{by}" x2="{sx}" y2="{sy}" class="channel-both-over"/>')

    # 3. CENTERS — drawn after channels so the lines pass behind the center fills
    for cname, ldata in LAYOUT.items():
        is_defined = cname in defined
        cls = f"center-{cname}-fill" if is_defined else "center-undef-fill"
        out.append(
            f'{_shape_open(ldata)} class="{cls} center-stroke" '
            f'data-tip-type="center" data-tip-id="{cname}"/>'
        )

    # 4. CHANNELS — re-render the active halves ON TOP of the center fills,
    #    so the colored channel edges show inside the centers too.
    #    Already drawn above before centers; the visible portion outside centers
    #    is enough. (Drawing them again here would create double-stroke.)

    # 5. GATES — number text + activation circle for each of 64 gates
    for gate, (gx, gy) in GATE_POSITIONS.items():
        state = gate_state(gate)
        in_defined_center = CENTER_OF_GATE[gate] in defined
        # Invisible hover target — a generous circle so the cursor doesn't have
        # to land exactly on the 8.5px number.
        out.append(
            f'<circle cx="{gx}" cy="{gy}" r="9" fill="transparent" '
            f'data-tip-type="gate" data-tip-id="{gate}"/>'
        )
        if state != "none":
            r = 6.5
            out.append(
                f'<circle cx="{gx}" cy="{gy}" r="{r}" class="activation-circle-{state}" '
                f'data-tip-type="gate" data-tip-id="{gate}"/>'
            )
            text_cls = "gate-num gate-num-activated"
        else:
            text_cls = "gate-num gate-num-defined" if in_defined_center else "gate-num gate-num-undefined"
        out.append(
            f'<text x="{gx}" y="{gy}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="gate" data-tip-id="{gate}" '
            f'style="pointer-events: none">{gate}</text>'
        )

    # 6. CENTER LABELS — tiny text below or beside each center
    label_offsets = {
        "head":          (230, 22),
        "ajna":          (230, 220),
        "throat":        (230, 322),
        "g":             (230, 482),
        "heart":         (330, 405),
        "solar_plexus":  (335, 593),
        "sacral":        (230, 577),
        "spleen":        (107, 593),
        "root":          (230, 682),
    }
    for cname, (lx, ly) in label_offsets.items():
        is_defined = cname in defined
        cls = "center-label-text center-label-defined" if is_defined else "center-label-text center-label-undefined"
        out.append(
            f'<text x="{lx}" y="{ly}" class="{cls}" '
            f'text-anchor="middle">{CENTERS[cname]["label"]}</text>'
        )

    out.append('</svg>')
    return "\n".join(out)
