"""
Render the Omni-Profile Mandala — zodiac wheel + 64 HD gates + bodygraph.

Per the reference Image 1: concentric rings encoding tropical longitude.

Outer → inner:
  - Hexagram glyphs (U+4DC0..U+4DFF) at each gate's mid-longitude
  - 64 gate sectors (each 5.625° wide) with gate numbers, tinted by element
    of the containing zodiac sign; activated gates highlighted
  - 12 zodiac sectors (30° each) with element-tinted fills + sign glyphs
  - Planet placements (small glyphs on a ring inside the zodiac)
  - HD bodygraph at the center (nested SVG)

Orientation: 0° Aries fixed at left (9 o'clock). Zodiac longitude increases
counter-clockwise visually → Capricorn at top, Cancer at bottom (matches
the Image-1 reference exactly).
"""
from __future__ import annotations

import math
import re
from typing import Optional

from svg_western import PLANET_GLYPHS, SIGN_GLYPHS, SIGN_ORDER, ELEMENT_BY_SIGN
from svg_hd import render_bodygraph, render_bodygraph_combined


# HD gate wheel — order around the zodiac starting from 3.875° tropical Aries.
GATE_WHEEL = [
    17, 21, 51, 42, 3, 27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15,
    52, 39, 53, 62, 56, 31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46,
    18, 48, 57, 32, 50, 28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10,
    58, 38, 54, 61, 60, 41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25,
]
WHEEL_OFFSET = 3.875
GATE_DEG = 360.0 / 64  # 5.625

# Hexagram glyphs: gate N corresponds to hexagram N (Unicode U+4DC0 + N - 1).
def hexagram_glyph(gate: int) -> str:
    return chr(0x4DBF + gate)


def _polar(cx: float, cy: float, r: float, math_angle_deg: float) -> tuple[float, float]:
    rad = math.radians(math_angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def _arc_path(cx: float, cy: float, r: float, math_start: float, math_end: float, sweep: int) -> str:
    """Single arc from math_start to math_end at radius r."""
    x1, y1 = _polar(cx, cy, r, math_start)
    x2, y2 = _polar(cx, cy, r, math_end)
    return f"M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 0 {sweep} {x2:.2f} {y2:.2f}"


def _wedge_path(cx: float, cy: float, r_out: float, r_in: float,
                math_start: float, math_end: float) -> str:
    """Closed wedge between two radii. math_end > math_start (mod 360 normalized)."""
    x1_out, y1_out = _polar(cx, cy, r_out, math_start)
    x2_out, y2_out = _polar(cx, cy, r_out, math_end)
    x1_in, y1_in = _polar(cx, cy, r_in, math_start)
    x2_in, y2_in = _polar(cx, cy, r_in, math_end)
    return (
        f"M {x1_out:.2f} {y1_out:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 0 0 {x2_out:.2f} {y2_out:.2f} "
        f"L {x2_in:.2f} {y2_in:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 0 1 {x1_in:.2f} {y1_in:.2f} "
        f"Z"
    )


def lon_to_math(lon: float) -> float:
    """Fixed mandala orientation: Aries at 9 o'clock, longitude CCW visually."""
    return (180.0 + lon) % 360.0


def _sign_for_longitude(lon: float) -> str:
    return SIGN_ORDER[int((lon % 360) // 30)]


def _strip_outer_svg(svg_str: str) -> str:
    """Pull the inner content out of a complete SVG document so we can nest it."""
    m = re.match(r'^\s*<svg[^>]*>(.*)</svg>\s*$', svg_str, re.DOTALL)
    return m.group(1) if m else svg_str


def render_mandala_combined(charts_western: list[dict], charts_hd: list[dict | None],
                            entity_colors: list[str], entity_names: list[str],
                            size: int = 1000) -> str:
    """Combined mandala overlay for N entities.

    Outer rings (zodiac + hexagrams + gate sectors) are shared. Each entity's
    planet placements are color-coded on the planet ring. Gate sectors are
    highlighted by which entities have them activated. The bodygraph at
    the center is the combined bodygraph from render_bodygraph_combined.
    """
    cx = cy = size / 2
    R_HEX = size * 0.490
    R_GATE_OUT = size * 0.455
    R_GATE_IN = size * 0.405
    R_ZODIAC_OUT = R_GATE_IN
    R_ZODIAC_IN = size * 0.355
    R_PLANET = size * 0.335

    BODY_W = size * 0.40
    BODY_H = size * 0.58
    BODY_X = (size - BODY_W) / 2
    BODY_Y = (size - BODY_H) / 2

    # Per-entity activated gate sets
    per_entity_active: list[set[int]] = []
    for chart in charts_hd:
        if chart is None:
            per_entity_active.append(set())
            continue
        p_g = {a["gate"] for a in chart.get("personality_activations", []) or []}
        d_g = {a["gate"] for a in chart.get("design_activations", []) or []}
        per_entity_active.append(p_g | d_g)

    def gate_activators(gate: int) -> list[int]:
        return [i for i, act in enumerate(per_entity_active) if gate in act]

    # Per-render unique suffix (see svg_hd._uid docstring).
    import secrets as _secrets
    uid = _secrets.token_hex(3)
    f_act = f'mc-active-glow-{uid}'
    f_pla = f'mc-planet-glow-{uid}'
    p_both = f'mc-both-pattern-{uid}'
    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="mandala">',
        '<defs>',
        f'  <filter id="{f_act}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="2.4" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        f'  <filter id="{f_pla}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.6" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
    ]
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
        '    .mc-hexagram { font-family: serif; font-size: 16px; fill: var(--text-faint); opacity: 0.85; }',
        f'    .mc-hexagram-active {{ fill: var(--text); opacity: 1; filter: url(#{f_act}); }}',
        '    .mc-gate-text { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--text); font-weight: 600; }',
        f'    .mc-gate-text-active {{ fill: #ffffff; filter: url(#{f_act}); }}',
        '    .mc-zodiac-wedge-fire  { fill: var(--chart-fire); opacity: 0.75; }',
        '    .mc-zodiac-wedge-earth { fill: var(--chart-earth); opacity: 0.75; }',
        '    .mc-zodiac-wedge-air   { fill: var(--chart-air); opacity: 0.75; }',
        '    .mc-zodiac-wedge-water { fill: var(--chart-water); opacity: 0.75; }',
        '    .mc-sign-glyph-fire   { fill: var(--chart-fire-glyph); }',
        '    .mc-sign-glyph-earth  { fill: var(--chart-earth-glyph); }',
        '    .mc-sign-glyph-air    { fill: var(--chart-air-glyph); }',
        '    .mc-sign-glyph-water  { fill: var(--chart-water-glyph); }',
        '    .mc-sign-glyph { font-family: "JetBrains Mono", "Segoe UI Symbol", monospace; font-size: 24px; }',
        f'    .mc-planet-glyph {{ font-family: "Segoe UI Symbol", "Apple Symbols", serif; font-size: 22px; filter: url(#{f_pla}); }}',
        '    .mc-ring { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.2; }',
        '    .mc-ring-thin { fill: none; stroke: var(--chart-ring); stroke-width: 0.7; }',
        '    .mc-gate-wedge-fire  { fill: var(--chart-fire); }',
        '    .mc-gate-wedge-earth { fill: var(--chart-earth); }',
        '    .mc-gate-wedge-air   { fill: var(--chart-air); }',
        '    .mc-gate-wedge-water { fill: var(--chart-water); }',
        # Activated gates: lighter base fill alongside the entity-color stroke + glow.
        '    .mc-gate-wedge-fire.mc-gate-wedge-active   { fill: color-mix(in srgb, var(--chart-fire), white 22%); }',
        '    .mc-gate-wedge-earth.mc-gate-wedge-active  { fill: color-mix(in srgb, var(--chart-earth), white 22%); }',
        '    .mc-gate-wedge-air.mc-gate-wedge-active    { fill: color-mix(in srgb, var(--chart-air), white 22%); }',
        '    .mc-gate-wedge-water.mc-gate-wedge-active  { fill: color-mix(in srgb, var(--chart-water), white 22%); }',
        '    .mc-overlay-legend { font-family: "JetBrains Mono", monospace; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }',
        '  </style>',
        '</defs>',
    ])

    # Gate-ring wedges with multi-entity activation strokes
    for i in range(64):
        gate = GATE_WHEEL[i]
        start_lon = WHEEL_OFFSET + i * GATE_DEG
        end_lon = start_lon + GATE_DEG
        a1 = lon_to_math(start_lon)
        a2 = lon_to_math(end_lon)
        sign = _sign_for_longitude((start_lon + end_lon) / 2)
        elem = ELEMENT_BY_SIGN[sign]
        activators = gate_activators(gate)
        wedge_d = _wedge_path(cx, cy, R_GATE_OUT, R_GATE_IN, a1, a2)
        if len(activators) == 1:
            stroke = entity_colors[activators[0]]
            stroke_attr = f' stroke="{stroke}" stroke-width="2" filter="url(#{f_act})"'
        elif len(activators) >= 2:
            stroke = f"url(#{p_both})"
            stroke_attr = f' stroke="url(#{p_both})" stroke-width="2.5" filter="url(#{f_act})"'
        else:
            stroke_attr = ""
        active_cls = " mc-gate-wedge-active" if activators else ""
        out.append(
            f'<path d="{wedge_d}" class="mc-gate-wedge-{elem}{active_cls}"{stroke_attr} '
            f'data-tip-type="gate" data-tip-id="{gate}"/>'
        )
        mid_angle = lon_to_math((start_lon + end_lon) / 2)
        nx, ny = _polar(cx, cy, (R_GATE_OUT + R_GATE_IN) / 2, mid_angle)
        text_cls = "mc-gate-text mc-gate-text-active" if activators else "mc-gate-text"
        out.append(
            f'<text x="{nx:.2f}" y="{ny:.2f}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="gate" data-tip-id="{gate}">{gate}</text>'
        )

    # Zodiac sectors
    for i, sign in enumerate(SIGN_ORDER):
        start_lon = i * 30
        end_lon = start_lon + 30
        a1 = lon_to_math(start_lon)
        a2 = lon_to_math(end_lon)
        elem = ELEMENT_BY_SIGN[sign]
        wedge_d = _wedge_path(cx, cy, R_ZODIAC_OUT, R_ZODIAC_IN, a1, a2)
        out.append(
            f'<path d="{wedge_d}" class="mc-zodiac-wedge-{elem}" '
            f'data-tip-type="sign" data-tip-id="{sign}"/>'
        )
        mid_angle = lon_to_math(start_lon + 15)
        gx, gy = _polar(cx, cy, (R_ZODIAC_OUT + R_ZODIAC_IN) / 2, mid_angle)
        out.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" class="mc-sign-glyph mc-sign-glyph-{elem}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="sign" data-tip-id="{sign}">{SIGN_GLYPHS[sign]}</text>'
        )

    # Hexagrams
    for i in range(64):
        gate = GATE_WHEEL[i]
        start_lon = WHEEL_OFFSET + i * GATE_DEG
        mid_angle = lon_to_math(start_lon + GATE_DEG / 2)
        x, y = _polar(cx, cy, R_HEX, mid_angle)
        cls = "mc-hexagram mc-hexagram-active" if gate_activators(gate) else "mc-hexagram"
        out.append(
            f'<text x="{x:.2f}" y="{y:.2f}" class="{cls}" '
            f'text-anchor="middle" dominant-baseline="central">{hexagram_glyph(gate)}</text>'
        )

    # Ring outlines
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_GATE_OUT}" class="mc-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_GATE_IN}" class="mc-ring-thin"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_IN}" class="mc-ring"/>')

    # Per-entity planet rings
    n_entities = len(charts_western)
    for ent_idx, chart in enumerate(charts_western):
        color = entity_colors[ent_idx]
        ring_r = R_PLANET - ent_idx * 24
        planets = chart.get("planets") or []
        placed: list[tuple[float, float]] = []
        for p in sorted(planets, key=lambda x: x["longitude"]):
            lon = p["longitude"]
            ang = lon_to_math(lon)
            r = ring_r
            for prev_ang, prev_r in placed:
                arc_dist = min(abs(ang - prev_ang), 360 - abs(ang - prev_ang))
                if arc_dist < 4 and abs(r - prev_r) < 16:
                    r = max(R_PLANET - 60, prev_r - 18)
            placed.append((ang, r))
            px, py = _polar(cx, cy, r, ang)
            glyph = PLANET_GLYPHS.get(p["body"], "?")
            out.append(
                f'<text x="{px:.2f}" y="{py:.2f}" class="mc-planet-glyph" '
                f'fill="{color}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'data-tip-type="planet" data-tip-id="{p["body"]}">{glyph}</text>'
            )
            # Tick on zodiac inner ring
            tx1, ty1 = _polar(cx, cy, R_ZODIAC_IN, ang)
            tx2, ty2 = _polar(cx, cy, R_ZODIAC_IN - 7, ang)
            out.append(
                f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}" '
                f'stroke="{color}" stroke-width="1.4"/>'
            )

    # Center intentionally empty — see render_mandala() for the rationale.
    # (Pair-page combined dashboards are a separate design problem; the
    # combined bodygraph view will move to its own block when we revisit
    # those pages.)

    # Top-of-mandala legend
    for i, name in enumerate(entity_names):
        x = 20 + i * 240
        out.append(
            f'<circle cx="{x}" cy="20" r="7" fill="{entity_colors[i]}" filter="url(#{f_act})"/>'
        )
        out.append(
            f'<text x="{x + 14}" y="20" class="mc-overlay-legend" fill="{entity_colors[i]}" dominant-baseline="central">{name}</text>'
        )

    out.append('</svg>')
    return "\n".join(out)


def render_mandala(chart_western: dict, chart_hd: dict | None, size: int = 1000) -> str:
    cx = cy = size / 2
    # Ring radii (proportional to size)
    R_HEX = size * 0.490
    R_GATE_OUT = size * 0.455
    R_GATE_IN = size * 0.405
    R_ZODIAC_OUT = R_GATE_IN
    R_ZODIAC_IN = size * 0.355
    R_PLANET = size * 0.335
    R_PLANET_TICK = size * 0.355

    # Bodygraph nested in center
    BODY_W = size * 0.40
    BODY_H = size * 0.58
    BODY_X = (size - BODY_W) / 2
    BODY_Y = (size - BODY_H) / 2

    # Personality + design gate activations (for highlighting active gates)
    p_gates: set[int] = set()
    d_gates: set[int] = set()
    if chart_hd:
        p_gates = {a["gate"] for a in chart_hd.get("personality_activations", []) or []}
        d_gates = {a["gate"] for a in chart_hd.get("design_activations", []) or []}
    active_gates = p_gates | d_gates

    # Per-render unique suffix for filter IDs so the same mandala can appear
    # multiple times on a page without Firefox cross-resolving url(#…) refs
    # (see svg_hd._uid docstring for full context).
    import secrets as _secrets
    uid = _secrets.token_hex(3)
    f_act = f'mandala-active-glow-{uid}'
    f_pla = f'mandala-planet-glow-{uid}'
    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="mandala">',
        '<defs>',
        f'  <filter id="{f_act}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="2.4" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        f'  <filter id="{f_pla}" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.6" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <style>',
        '    .mandala-hexagram { font-family: serif; font-size: 16px; fill: var(--text-faint); opacity: 0.85; }',
        f'    .mandala-hexagram-active {{ fill: var(--text); opacity: 1; filter: url(#{f_act}); }}',
        '    .mandala-gate-text { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--text); font-weight: 600; letter-spacing: 0.02em; }',
        f'    .mandala-gate-text-active {{ fill: #ffffff; filter: url(#{f_act}); }}',
        '    .mandala-gate-divider { stroke: var(--chart-ring); stroke-width: 0.5; }',
        '    .mandala-gate-wedge-fire   { fill: var(--chart-fire); }',
        '    .mandala-gate-wedge-earth  { fill: var(--chart-earth); }',
        '    .mandala-gate-wedge-air    { fill: var(--chart-air); }',
        '    .mandala-gate-wedge-water  { fill: var(--chart-water); }',
        # Activated gates: keep the accent stroke + glow emphasis AND lighten
        # the element-tinted base fill so the activation reads even on a
        # cluttered chart. color-mix mixes 22% white into the base color.
        '    .mandala-gate-wedge-fire.mandala-gate-wedge-active   { fill: color-mix(in srgb, var(--chart-fire), white 22%); }',
        '    .mandala-gate-wedge-earth.mandala-gate-wedge-active  { fill: color-mix(in srgb, var(--chart-earth), white 22%); }',
        '    .mandala-gate-wedge-air.mandala-gate-wedge-active    { fill: color-mix(in srgb, var(--chart-air), white 22%); }',
        '    .mandala-gate-wedge-water.mandala-gate-wedge-active  { fill: color-mix(in srgb, var(--chart-water), white 22%); }',
        f'    .mandala-gate-wedge-active {{ stroke: var(--accent); stroke-width: 1.5; filter: url(#{f_act}); }}',
        '    .mandala-zodiac-wedge-fire  { fill: var(--chart-fire); opacity: 0.75; }',
        '    .mandala-zodiac-wedge-earth { fill: var(--chart-earth); opacity: 0.75; }',
        '    .mandala-zodiac-wedge-air   { fill: var(--chart-air); opacity: 0.75; }',
        '    .mandala-zodiac-wedge-water { fill: var(--chart-water); opacity: 0.75; }',
        '    .mandala-sign-glyph-fire   { fill: var(--chart-fire-glyph); }',
        '    .mandala-sign-glyph-earth  { fill: var(--chart-earth-glyph); }',
        '    .mandala-sign-glyph-air    { fill: var(--chart-air-glyph); }',
        '    .mandala-sign-glyph-water  { fill: var(--chart-water-glyph); }',
        '    .mandala-sign-glyph        { font-family: "JetBrains Mono", "Segoe UI Symbol", monospace; font-size: 24px; }',
        f'    .mandala-planet-glyph      {{ font-family: "Segoe UI Symbol", "Apple Symbols", serif; font-size: 22px; fill: var(--chart-planet-text); filter: url(#{f_pla}); }}',
        '    .mandala-planet-tick { stroke: var(--chart-planet-tick); stroke-width: 1.4; }',
        '    .mandala-ring { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.2; }',
        '    .mandala-ring-thin { fill: none; stroke: var(--chart-ring); stroke-width: 0.7; }',
        '  </style>',
        '</defs>',
    ]

    # 1. Gate-ring wedges (64 sectors)
    for i in range(64):
        gate = GATE_WHEEL[i]
        start_lon = WHEEL_OFFSET + i * GATE_DEG
        end_lon = start_lon + GATE_DEG
        a1 = lon_to_math(start_lon)
        a2 = lon_to_math(end_lon)
        sign = _sign_for_longitude((start_lon + end_lon) / 2)
        elem = ELEMENT_BY_SIGN[sign]
        is_active = gate in active_gates
        wedge_d = _wedge_path(cx, cy, R_GATE_OUT, R_GATE_IN, a1, a2)
        active_attr = ' mandala-gate-wedge-active' if is_active else ''
        out.append(
            f'<path d="{wedge_d}" class="mandala-gate-wedge-{elem}{active_attr}" '
            f'data-tip-type="gate" data-tip-id="{gate}"/>'
        )
        # Gate number at the mid-radius / mid-angle
        mid_angle = lon_to_math((start_lon + end_lon) / 2)
        nx, ny = _polar(cx, cy, (R_GATE_OUT + R_GATE_IN) / 2, mid_angle)
        text_cls = "mandala-gate-text mandala-gate-text-active" if is_active else "mandala-gate-text"
        out.append(
            f'<text x="{nx:.2f}" y="{ny:.2f}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="gate" data-tip-id="{gate}">{gate}</text>'
        )

    # 2. Zodiac-ring sectors (12 × 30°)
    for i, sign in enumerate(SIGN_ORDER):
        start_lon = i * 30
        end_lon = start_lon + 30
        a1 = lon_to_math(start_lon)
        a2 = lon_to_math(end_lon)
        elem = ELEMENT_BY_SIGN[sign]
        wedge_d = _wedge_path(cx, cy, R_ZODIAC_OUT, R_ZODIAC_IN, a1, a2)
        out.append(
            f'<path d="{wedge_d}" class="mandala-zodiac-wedge-{elem}" '
            f'data-tip-type="sign" data-tip-id="{sign}"/>'
        )
        # Sign glyph
        mid_angle = lon_to_math(start_lon + 15)
        gx, gy = _polar(cx, cy, (R_ZODIAC_OUT + R_ZODIAC_IN) / 2, mid_angle)
        out.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" class="mandala-sign-glyph mandala-sign-glyph-{elem}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="sign" data-tip-id="{sign}">{SIGN_GLYPHS[sign]}</text>'
        )

    # 3. Hexagram glyphs outermost
    for i in range(64):
        gate = GATE_WHEEL[i]
        start_lon = WHEEL_OFFSET + i * GATE_DEG
        mid_angle = lon_to_math(start_lon + GATE_DEG / 2)
        x, y = _polar(cx, cy, R_HEX, mid_angle)
        is_active = gate in active_gates
        cls = "mandala-hexagram mandala-hexagram-active" if is_active else "mandala-hexagram"
        out.append(
            f'<text x="{x:.2f}" y="{y:.2f}" class="{cls}" '
            f'text-anchor="middle" dominant-baseline="central">{hexagram_glyph(gate)}</text>'
        )

    # 4. Ring outlines
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_GATE_OUT}" class="mandala-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_GATE_IN}" class="mandala-ring-thin"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_IN}" class="mandala-ring"/>')

    # 5. Planet placements (just inside the zodiac ring)
    planets = (chart_western or {}).get("planets") or []
    placed: list[tuple[float, float]] = []  # (angle, radius) for collision-avoid
    sorted_planets = sorted(planets, key=lambda p: p["longitude"])
    for p in sorted_planets:
        lon = p["longitude"]
        ang = lon_to_math(lon)
        r = R_PLANET
        for prev_ang, prev_r in placed:
            arc_dist = min(abs(ang - prev_ang), 360 - abs(ang - prev_ang))
            if arc_dist < 4 and abs(r - prev_r) < 16:
                r = max(R_PLANET - 24, prev_r - 18)
        placed.append((ang, r))
        px, py = _polar(cx, cy, r, ang)
        glyph = PLANET_GLYPHS.get(p["body"], "?")
        out.append(
            f'<text x="{px:.2f}" y="{py:.2f}" class="mandala-planet-glyph" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="planet" data-tip-id="{p["body"]}">{glyph}</text>'
        )
        # Tick mark on the inner zodiac ring at the exact degree
        tx1, ty1 = _polar(cx, cy, R_ZODIAC_IN, ang)
        tx2, ty2 = _polar(cx, cy, R_ZODIAC_IN - 7, ang)
        out.append(f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}" class="mandala-planet-tick"/>')

    # The center is intentionally empty. The Design + Personality activation
    # columns are overlaid in that space via HTML (see _mandala_panel.html).
    # Nesting the bodygraph here used to be the layout — that produced a
    # whole class of cross-browser bugs (Firefox nested-SVG filter resolution,
    # CSS variable leak across viewport, duplicate-ID collisions). We now
    # keep the bodygraph as a wholly separate top-level chart.

    out.append('</svg>')
    return "\n".join(out)
