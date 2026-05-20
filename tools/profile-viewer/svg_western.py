"""
Render a Western natal chart wheel as SVG, themed via CSS variables.

Layout: viewBox 800x800, center 400/400. Asc fixed at 9 o'clock. Zodiac
longitudes increase counter-clockwise in math-angle space, which — because
SVG y is inverted — visually means clockwise from the Ascendant: down to
IC at bottom, right to DSC, up to MC at top, back to Asc.

All colors are CSS variables (--chart-*, --aspect-*) set per theme by the
main stylesheet, so the SVG re-skins instantly on theme switch.
"""
from __future__ import annotations

import math

SIGN_GLYPHS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
}
SIGN_ORDER = list(SIGN_GLYPHS.keys())

PLANET_GLYPHS = {
    "sun": "☉", "moon": "☽", "mercury": "☿", "venus": "♀",
    "mars": "♂", "jupiter": "♃", "saturn": "♄", "uranus": "♅",
    "neptune": "♆", "pluto": "♇", "north_node": "☊", "chiron": "⚷",
}

ELEMENT_BY_SIGN = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

ASPECT_DASH = {
    "quincunx": "3 2",
    "semi_sextile": "2 2",
}

ASPECT_STROKE = {
    "conjunction": 1.2,
    "opposition": 1.7,
    "trine": 1.4,
    "square": 1.5,
    "sextile": 1.1,
    "quincunx": 0.9,
    "semi_sextile": 0.9,
}


def _polar(cx: float, cy: float, r: float, math_angle_deg: float) -> tuple[float, float]:
    rad = math.radians(math_angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def render_chart_wheel_combined(charts_western: list[dict], entity_colors: list[str], entity_names: list[str], size: int = 800) -> str:
    """Render a combined Western chart overlay for N entities.

    Zodiac is fixed in neutral orientation (Aries at 9 o'clock); no houses
    (each entity has different cusps). Each entity's planets are rendered at
    their tropical longitudes, color-coded by entity. Aspects omitted —
    cross-aspect (synastry) math lives in a separate pass.
    """
    cx = cy = size / 2
    R_ZODIAC_OUT = size * 0.475
    R_ZODIAC_IN = size * 0.4
    R_PLANET_OUTER = size * 0.355
    R_PLANET_INNER = size * 0.18

    def lon_to_math(lon: float) -> float:
        return (180.0 + lon) % 360.0

    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="chart-wheel">',
        '<defs>',
        '  <filter id="overlay-planet-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="2.4" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <style>',
        '    .sign-label { font-family: "JetBrains Mono", "Segoe UI Symbol", monospace; font-size: 22px; }',
        '    .planet-glyph-overlay { font-family: "Segoe UI Symbol", "Apple Symbols", serif; font-size: 24px; filter: url(#overlay-planet-glow); }',
        '    .planet-degree-overlay { font-family: "JetBrains Mono", monospace; font-size: 9px; letter-spacing: 0.04em; }',
        '    .planet-tick-overlay { stroke-width: 1.3; }',
        '    .chart-ring { fill: none; stroke: var(--chart-ring); stroke-width: 0.8; }',
        '    .chart-ring-strong { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.4; }',
        '    .zodiac-wedge-fire  { fill: var(--chart-fire);  }',
        '    .zodiac-wedge-earth { fill: var(--chart-earth); }',
        '    .zodiac-wedge-air   { fill: var(--chart-air);   }',
        '    .zodiac-wedge-water { fill: var(--chart-water); }',
        '    .sign-glyph-fire    { fill: var(--chart-fire-glyph); }',
        '    .sign-glyph-earth   { fill: var(--chart-earth-glyph); }',
        '    .sign-glyph-air     { fill: var(--chart-air-glyph); }',
        '    .sign-glyph-water   { fill: var(--chart-water-glyph); }',
        '    .overlay-legend-name { font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }',
        '  </style>',
        '</defs>',
    ]

    # 1. Zodiac wedges
    for i, sign in enumerate(SIGN_ORDER):
        start_lon = i * 30
        end_lon = start_lon + 30
        a1 = lon_to_math(start_lon)
        a2 = lon_to_math(end_lon)
        x1_out, y1_out = _polar(cx, cy, R_ZODIAC_OUT, a1)
        x2_out, y2_out = _polar(cx, cy, R_ZODIAC_OUT, a2)
        x1_in, y1_in = _polar(cx, cy, R_ZODIAC_IN, a1)
        x2_in, y2_in = _polar(cx, cy, R_ZODIAC_IN, a2)
        large = 0
        d = (
            f"M {x1_out:.2f} {y1_out:.2f} "
            f"A {R_ZODIAC_OUT:.2f} {R_ZODIAC_OUT:.2f} 0 {large} 0 {x2_out:.2f} {y2_out:.2f} "
            f"L {x2_in:.2f} {y2_in:.2f} "
            f"A {R_ZODIAC_IN:.2f} {R_ZODIAC_IN:.2f} 0 {large} 1 {x1_in:.2f} {y1_in:.2f} "
            f"Z"
        )
        elem = ELEMENT_BY_SIGN[sign]
        out.append(
            f'<path d="{d}" class="zodiac-wedge-{elem}" stroke="var(--chart-ring)" stroke-width="0.5" '
            f'data-tip-type="sign" data-tip-id="{sign}"/>'
        )
        mid_angle = lon_to_math(start_lon + 15)
        gx, gy = _polar(cx, cy, (R_ZODIAC_OUT + R_ZODIAC_IN) / 2, mid_angle)
        out.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" class="sign-label sign-glyph-{elem}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="sign" data-tip-id="{sign}">{SIGN_GLYPHS[sign]}</text>'
        )

    # 2. Ring outlines
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_OUT}" class="chart-ring-strong"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_IN}" class="chart-ring-strong"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_PLANET_INNER}" class="chart-ring"/>')

    # 3. Per-entity planet rings (each entity gets its own concentric ring inside the zodiac)
    n_entities = len(charts_western)
    ring_band = R_ZODIAC_IN - R_PLANET_INNER  # available radial space
    band_per_entity = min(60, ring_band / max(n_entities, 1))
    for ent_idx, chart in enumerate(charts_western):
        color = entity_colors[ent_idx]
        # Each entity gets a ring at its own radius
        ring_r = R_ZODIAC_IN - 24 - ent_idx * band_per_entity
        planets = chart.get("planets") or []
        # Place planets, collision-avoiding within this entity's band
        placed: list[tuple[float, float]] = []
        for p in sorted(planets, key=lambda x: x["longitude"]):
            lon = p["longitude"]
            ang = lon_to_math(lon)
            r = ring_r
            for prev_ang, prev_r in placed:
                arc_dist = min(abs(ang - prev_ang), 360 - abs(ang - prev_ang))
                if arc_dist < 8 and abs(r - prev_r) < 18:
                    r = max(R_PLANET_INNER + 12, prev_r - 20)
            placed.append((ang, r))

            px, py = _polar(cx, cy, r, ang)
            glyph = PLANET_GLYPHS.get(p["body"], "?")
            out.append(
                f'<text x="{px:.2f}" y="{py:.2f}" class="planet-glyph-overlay" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="{color}" '
                f'data-tip-type="planet" data-tip-id="{p["body"]}">{glyph}</text>'
            )
            # Degree just inside
            dx, dy = _polar(cx, cy, r - 16, ang)
            out.append(
                f'<text x="{dx:.2f}" y="{dy:.2f}" class="planet-degree-overlay" '
                f'fill="{color}" opacity="0.7" '
                f'text-anchor="middle" dominant-baseline="central">{p["degree_in_sign"]:.1f}°</text>'
            )
            # Tick on inner zodiac ring
            tx1, ty1 = _polar(cx, cy, R_ZODIAC_IN, ang)
            tx2, ty2 = _polar(cx, cy, R_ZODIAC_IN - 7, ang)
            out.append(
                f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}" '
                f'class="planet-tick-overlay" stroke="{color}"/>'
            )

    # 4. Legend in center
    center_y_offset = -(n_entities - 1) * 11
    for ent_idx, name in enumerate(entity_names):
        color = entity_colors[ent_idx]
        y = cy + center_y_offset + ent_idx * 22
        out.append(
            f'<circle cx="{cx - 60}" cy="{y}" r="4" fill="{color}" filter="url(#overlay-planet-glow)"/>'
        )
        out.append(
            f'<text x="{cx - 48}" y="{y}" class="overlay-legend-name" '
            f'fill="{color}" dominant-baseline="central">{name}</text>'
        )

    out.append('</svg>')
    return "\n".join(out)


def render_chart_wheel(chart_western: dict, size: int = 800) -> str:
    cx = cy = size / 2
    R_ZODIAC_OUT = size * 0.475
    R_ZODIAC_IN = size * 0.4
    R_HOUSE_IN = size * 0.3
    R_PLANET_OUT = size * 0.3
    R_PLANET_IN = size * 0.15

    asc_lon = (chart_western.get("ascendant") or {}).get("longitude")
    rotating = asc_lon is not None

    def lon_to_math_angle(lon: float) -> float:
        if rotating:
            return (180.0 + lon - asc_lon) % 360.0
        return (180.0 + lon) % 360.0

    # SVG-internal stylesheet uses CSS variables from the main theme.
    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="chart-wheel">',
        '<defs>',
        '  <filter id="planet-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="2.4" result="blur"/>',
        '    <feMerge>',
        '      <feMergeNode in="blur"/>',
        '      <feMergeNode in="SourceGraphic"/>',
        '    </feMerge>',
        '  </filter>',
        '  <filter id="aspect-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="1.2" result="blur"/>',
        '    <feMerge>',
        '      <feMergeNode in="blur"/>',
        '      <feMergeNode in="SourceGraphic"/>',
        '    </feMerge>',
        '  </filter>',
        '  <style>',
        '    .sign-label { font-family: "JetBrains Mono", "Segoe UI Symbol", monospace; font-size: 22px; }',
        '    .planet-glyph { font-family: "Segoe UI Symbol", "Apple Symbols", serif; font-size: 26px; fill: var(--chart-planet-text); filter: url(#planet-glow); }',
        '    .planet-degree { font-family: "JetBrains Mono", monospace; font-size: 9.5px; fill: var(--chart-planet-degree); letter-spacing: 0.04em; }',
        '    .house-num { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--chart-house-num); letter-spacing: 0.06em; }',
        '    .axis-label { font-family: "JetBrains Mono", monospace; font-size: 10.5px; font-weight: 600; fill: var(--chart-axis-text); letter-spacing: 0.08em; }',
        '    .chart-ring { fill: none; stroke: var(--chart-ring); stroke-width: 0.8; }',
        '    .chart-ring-strong { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.4; }',
        '    .house-cusp { stroke: var(--chart-ring); stroke-width: 0.6; }',
        '    .house-cusp-axis { stroke: var(--chart-axis); stroke-width: 1.4; opacity: 0.85; }',
        '    .planet-tick { stroke: var(--chart-planet-tick); stroke-width: 1.3; }',
        '    .zodiac-wedge-fire  { fill: var(--chart-fire);  }',
        '    .zodiac-wedge-earth { fill: var(--chart-earth); }',
        '    .zodiac-wedge-air   { fill: var(--chart-air);   }',
        '    .zodiac-wedge-water { fill: var(--chart-water); }',
        '    .sign-glyph-fire    { fill: var(--chart-fire-glyph); }',
        '    .sign-glyph-earth   { fill: var(--chart-earth-glyph); }',
        '    .sign-glyph-air     { fill: var(--chart-air-glyph); }',
        '    .sign-glyph-water   { fill: var(--chart-water-glyph); }',
        '    .aspect-line { fill: none; opacity: 0.85; filter: url(#aspect-glow); }',
        '    .aspect-conjunction  { stroke: var(--aspect-conjunction); }',
        '    .aspect-opposition   { stroke: var(--aspect-opposition); }',
        '    .aspect-square       { stroke: var(--aspect-square); }',
        '    .aspect-trine        { stroke: var(--aspect-trine); }',
        '    .aspect-sextile      { stroke: var(--aspect-sextile); }',
        '    .aspect-quincunx     { stroke: var(--aspect-quincunx); }',
        '    .aspect-semi_sextile { stroke: var(--aspect-semi_sextile); }',
        '  </style>',
        '</defs>',
    ]

    # 1. Zodiac sector backgrounds (element-colored wedges).
    # With the fixed direction (lon ↑ ⇒ math_angle ↑), sweep-flag 0 traces the
    # arc the short way visually because SVG y is inverted.
    for i, sign in enumerate(SIGN_ORDER):
        start_lon = i * 30
        end_lon = (i + 1) * 30
        a1 = lon_to_math_angle(start_lon)
        a2 = lon_to_math_angle(end_lon)
        x1_out, y1_out = _polar(cx, cy, R_ZODIAC_OUT, a1)
        x2_out, y2_out = _polar(cx, cy, R_ZODIAC_OUT, a2)
        x1_in, y1_in = _polar(cx, cy, R_ZODIAC_IN, a1)
        x2_in, y2_in = _polar(cx, cy, R_ZODIAC_IN, a2)
        large = 0
        d = (
            f"M {x1_out:.2f} {y1_out:.2f} "
            f"A {R_ZODIAC_OUT:.2f} {R_ZODIAC_OUT:.2f} 0 {large} 0 {x2_out:.2f} {y2_out:.2f} "
            f"L {x2_in:.2f} {y2_in:.2f} "
            f"A {R_ZODIAC_IN:.2f} {R_ZODIAC_IN:.2f} 0 {large} 1 {x1_in:.2f} {y1_in:.2f} "
            f"Z"
        )
        elem = ELEMENT_BY_SIGN[sign]
        out.append(
            f'<path d="{d}" class="zodiac-wedge-{elem}" stroke="var(--chart-ring)" stroke-width="0.5" '
            f'data-tip-type="sign" data-tip-id="{sign}"/>'
        )

        # Sign glyph at the mid-angle on the zodiac ring
        mid_angle = lon_to_math_angle(start_lon + 15)
        gx, gy = _polar(cx, cy, (R_ZODIAC_OUT + R_ZODIAC_IN) / 2, mid_angle)
        out.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" class="sign-label sign-glyph-{elem}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="sign" data-tip-id="{sign}">{SIGN_GLYPHS[sign]}</text>'
        )

    # 2. House lines + numbers
    houses = chart_western.get("houses") or []
    if houses:
        for h in houses:
            cusp_lon = h["cusp_longitude"]
            ang = lon_to_math_angle(cusp_lon)
            x1, y1 = _polar(cx, cy, R_HOUSE_IN, ang)
            x2, y2 = _polar(cx, cy, R_ZODIAC_IN, ang)
            cls = "house-cusp-axis" if h["number"] in (1, 4, 7, 10) else "house-cusp"
            out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{cls}"/>')

            # House number, mid-house
            next_idx = h["number"] % 12
            next_cusp = houses[next_idx]["cusp_longitude"]
            span = (next_cusp - cusp_lon) % 360
            mid_lon = (cusp_lon + span / 2) % 360
            num_ang = lon_to_math_angle(mid_lon)
            nx, ny = _polar(cx, cy, R_HOUSE_IN + (R_ZODIAC_IN - R_HOUSE_IN) * 0.3, num_ang)
            out.append(
                f'<text x="{nx:.2f}" y="{ny:.2f}" class="house-num" text-anchor="middle" dominant-baseline="central" '
                f'data-tip-type="house" data-tip-id="{h["number"]}">{h["number"]}</text>'
            )

        # ASC/MC/DSC/IC labels
        asc_ang = lon_to_math_angle(houses[0]["cusp_longitude"])
        mc_ang = lon_to_math_angle(houses[9]["cusp_longitude"])
        dc_ang = lon_to_math_angle(houses[6]["cusp_longitude"])
        ic_ang = lon_to_math_angle(houses[3]["cusp_longitude"])
        for label, ang in [("ASC", asc_ang), ("MC", mc_ang), ("DSC", dc_ang), ("IC", ic_ang)]:
            lx, ly = _polar(cx, cy, R_ZODIAC_OUT + 16, ang)
            out.append(f'<text x="{lx:.2f}" y="{ly:.2f}" class="axis-label" text-anchor="middle" dominant-baseline="central">{label}</text>')

    # 3. Ring outlines
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_OUT}" class="chart-ring-strong"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ZODIAC_IN}" class="chart-ring-strong"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_HOUSE_IN}" class="chart-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_PLANET_IN}" class="chart-ring"/>')

    # 4. Planets — sorted by longitude so we can stagger close conjunctions inward
    planets = chart_western.get("planets") or []
    placed: list[tuple[float, float, str]] = []
    sorted_planets = sorted(planets, key=lambda p: p["longitude"])
    for p in sorted_planets:
        lon = p["longitude"]
        ang = lon_to_math_angle(lon)
        r = (R_PLANET_OUT + R_PLANET_IN) / 2
        for prev_ang, prev_r, _ in placed:
            arc_dist = min(abs(ang - prev_ang), 360 - abs(ang - prev_ang))
            if arc_dist < 8 and abs(r - prev_r) < 18:
                r = max(R_PLANET_IN + 14, prev_r - 22)
        placed.append((ang, r, p["body"]))

        px, py = _polar(cx, cy, r, ang)
        glyph = PLANET_GLYPHS.get(p["body"], "?")
        out.append(
            f'<text x="{px:.2f}" y="{py:.2f}" class="planet-glyph" text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="planet" data-tip-id="{p["body"]}">{glyph}</text>'
        )
        dx, dy = _polar(cx, cy, r - 18, ang)
        retro_mark = "℞" if p.get("retrograde") else ""
        out.append(f'<text x="{dx:.2f}" y="{dy:.2f}" class="planet-degree" text-anchor="middle" dominant-baseline="central">{p["degree_in_sign"]:.1f}°{retro_mark}</text>')

        # Tick mark on the inner zodiac ring at the exact degree
        tx1, ty1 = _polar(cx, cy, R_ZODIAC_IN, ang)
        tx2, ty2 = _polar(cx, cy, R_ZODIAC_IN - 8, ang)
        out.append(f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}" class="planet-tick"/>')

    # 5. Aspect lines
    aspects = chart_western.get("aspects") or []
    by_body = {p["body"]: p for p in planets}
    for a in aspects:
        fp = by_body.get(a["from"])
        tp = by_body.get(a["to"])
        if not fp or not tp:
            continue
        ang_f = lon_to_math_angle(fp["longitude"])
        ang_t = lon_to_math_angle(tp["longitude"])
        x1, y1 = _polar(cx, cy, R_PLANET_IN - 4, ang_f)
        x2, y2 = _polar(cx, cy, R_PLANET_IN - 4, ang_t)
        stroke = ASPECT_STROKE.get(a["type"], 1.0)
        dash = ASPECT_DASH.get(a["type"])
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'class="aspect-line aspect-{a["type"]}" stroke-width="{stroke}"{dash_attr} '
            f'data-tip-type="aspect" data-tip-id="{a["type"]}"/>'
        )

    out.append('</svg>')
    return "\n".join(out)
