"""
Render the Chinese Zodiac Wheel — 12 animals + 5-element pentagon.

Layout:
  - Outermost rim: yin/yang banding (alternating animals)
  - Animal ring: 12 sectors, each with the Chinese character + English name
  - Center: pentagon of the 5 elements (Wood / Fire / Earth / Metal / Water),
    with directional arrows for the generation cycle
  - Markers for Inner Animal (month) + Secret Animal (hour) on the outer ring
  - Year-animal sector + Year-element pentagon vertex highlighted in the
    person's accent color
"""
from __future__ import annotations

import math

# 12 animals in canonical Chinese zodiac order
ANIMALS = [
    ("Rat",     "鼠", "yang"),
    ("Ox",      "牛", "yin"),
    ("Tiger",   "虎", "yang"),
    ("Rabbit",  "兔", "yin"),
    ("Dragon",  "龍", "yang"),
    ("Snake",   "蛇", "yin"),
    ("Horse",   "馬", "yang"),
    ("Goat",    "羊", "yin"),
    ("Monkey",  "猴", "yang"),
    ("Rooster", "雞", "yin"),
    ("Dog",     "狗", "yang"),
    ("Pig",     "豬", "yin"),
]

# 5 elements in generation cycle order (Wood → Fire → Earth → Metal → Water → Wood)
ELEMENTS = ["Wood", "Fire", "Earth", "Metal", "Water"]


def _polar(cx: float, cy: float, r: float, math_angle_deg: float) -> tuple[float, float]:
    rad = math.radians(math_angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def _wedge_path(cx: float, cy: float, r_out: float, r_in: float,
                math_start: float, math_end: float) -> str:
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


def render_chinese_wheel(chinese_chart: dict | None, size: int = 800) -> str:
    cx = cy = size / 2
    R_YIN_YANG_OUT = size * 0.49
    R_YIN_YANG_IN = size * 0.465
    R_ANIMAL_OUT = R_YIN_YANG_IN
    R_ANIMAL_IN = size * 0.32
    R_PENTAGON_OUT = size * 0.27
    R_PENTAGON_IN = size * 0.08

    # Person's data
    user_year_animal = None
    user_year_element = None
    user_year_polarity = None
    user_inner_animal = None
    user_secret_animal = None
    if chinese_chart:
        user_year_animal = chinese_chart.get("year_animal")
        user_year_element = chinese_chart.get("year_element")
        user_year_polarity = chinese_chart.get("year_polarity")
        user_inner_animal = chinese_chart.get("inner_animal")
        user_secret_animal = chinese_chart.get("secret_animal")

    def animal_index(name: str | None) -> int | None:
        if not name:
            return None
        for i, (n, _, _) in enumerate(ANIMALS):
            if n == name:
                return i
        return None

    user_year_idx = animal_index(user_year_animal)
    user_inner_idx = animal_index(user_inner_animal)
    user_secret_idx = animal_index(user_secret_animal)
    user_element_idx = ELEMENTS.index(user_year_element) if user_year_element in ELEMENTS else None

    # Animals progress clockwise from 12 o'clock — Rat at top
    def animal_math_angle(i: float) -> float:
        return (90 - i * 30) % 360

    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="chinese-wheel">',
        '<defs>',
        '  <filter id="cn-active-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="3" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <filter id="cn-stamp-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="4" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <style>',
        '    .cn-yin { fill: var(--bg-page); }',
        '    .cn-yang { fill: var(--bg-card-elevated); }',
        '    .cn-rim-stroke { stroke: var(--chart-ring); stroke-width: 0.6; }',
        '    .cn-animal-sector { fill: var(--bg-card); stroke: var(--chart-ring); stroke-width: 0.8; }',
        '    .cn-animal-sector-active { fill: var(--accent-soft); stroke: var(--accent-chinese); stroke-width: 2; filter: url(#cn-active-glow); }',
        '    .cn-animal-name { font-family: "JetBrains Mono", monospace; font-size: 11px; fill: var(--text); letter-spacing: 0.04em; }',
        '    .cn-animal-name-active { fill: var(--accent-chinese); font-weight: 700; }',
        '    .cn-animal-glyph { font-family: "Noto Sans CJK SC", "Source Han Sans", "PingFang SC", "Hiragino Sans", serif; font-size: 28px; fill: var(--text); }',
        '    .cn-animal-glyph-active { fill: var(--accent-chinese); filter: url(#cn-active-glow); }',
        '    .cn-element-line { stroke: var(--chart-ring); stroke-width: 1; fill: none; }',
        '    .cn-element-fill-wood  { fill: #6FA286; }',
        '    .cn-element-fill-fire  { fill: #C44545; }',
        '    .cn-element-fill-earth { fill: #C49B45; }',
        '    .cn-element-fill-metal { fill: #C9D1E3; }',
        '    .cn-element-fill-water { fill: #4A6FA5; }',
        '    .cn-element-stroke { stroke: var(--chart-ring); stroke-width: 1; }',
        '    .cn-element-active { stroke: var(--accent-chinese); stroke-width: 2.5; filter: url(#cn-active-glow); }',
        '    .cn-element-label { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--text); letter-spacing: 0.04em; text-transform: uppercase; }',
        '    .cn-marker-inner { fill: var(--accent-mayan); stroke: var(--bg-page); stroke-width: 1.5; filter: url(#cn-active-glow); }',
        '    .cn-marker-secret { fill: var(--accent-western); stroke: var(--bg-page); stroke-width: 1.5; filter: url(#cn-active-glow); }',
        '    .cn-marker-legend { font-family: "JetBrains Mono", monospace; font-size: 9px; fill: var(--text-dim); letter-spacing: 0.04em; text-transform: uppercase; }',
        '    .cn-stamp-pillar { font-family: "Inter", -apple-system, system-ui, sans-serif; font-size: 18px; fill: var(--accent-chinese); font-weight: 600; filter: url(#cn-stamp-glow); }',
        '    .cn-stamp-sub { font-family: "JetBrains Mono", monospace; font-size: 10px; fill: var(--text-faint); letter-spacing: 0.06em; text-transform: uppercase; }',
        '    .cn-ring { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.2; }',
        '  </style>',
        '</defs>',
    ]

    # 1. Yin/Yang rim
    for i, (animal, _, polarity) in enumerate(ANIMALS):
        start_ang = animal_math_angle(i + 1)
        end_ang = animal_math_angle(i)
        wedge_d = _wedge_path(cx, cy, R_YIN_YANG_OUT, R_YIN_YANG_IN, start_ang, end_ang)
        cls = f"cn-{polarity} cn-rim-stroke"
        out.append(f'<path d="{wedge_d}" class="{cls}"/>')

    # 2. Animal sectors
    for i, (animal, glyph, polarity) in enumerate(ANIMALS):
        start_ang = animal_math_angle(i + 1)
        end_ang = animal_math_angle(i)
        wedge_d = _wedge_path(cx, cy, R_ANIMAL_OUT, R_ANIMAL_IN, start_ang, end_ang)
        is_active = (user_year_idx == i)
        cls = "cn-animal-sector-active" if is_active else "cn-animal-sector"
        out.append(
            f'<path d="{wedge_d}" class="{cls}" '
            f'data-tip-type="chinese_animal" data-tip-id="{animal}"/>'
        )
        # Chinese character glyph
        mid_ang = animal_math_angle(i + 0.5)
        glyph_r = (R_ANIMAL_OUT * 0.62 + R_ANIMAL_IN * 0.38)
        gx, gy = _polar(cx, cy, glyph_r, mid_ang)
        glyph_cls = "cn-animal-glyph cn-animal-glyph-active" if is_active else "cn-animal-glyph"
        out.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" class="{glyph_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="chinese_animal" data-tip-id="{animal}">{glyph}</text>'
        )
        # English name below the glyph
        name_r = R_ANIMAL_IN + (R_ANIMAL_OUT - R_ANIMAL_IN) * 0.22
        nx, ny = _polar(cx, cy, name_r, mid_ang)
        name_cls = "cn-animal-name cn-animal-name-active" if is_active else "cn-animal-name"
        out.append(
            f'<text x="{nx:.2f}" y="{ny:.2f}" class="{name_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="chinese_animal" data-tip-id="{animal}">{animal.upper()}</text>'
        )

    # 3. Inner/Secret animal markers (small dots on the outer rim)
    if user_inner_idx is not None:
        ang = animal_math_angle(user_inner_idx + 0.5)
        mx, my = _polar(cx, cy, R_YIN_YANG_OUT + 14, ang)
        out.append(f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="6" class="cn-marker-inner"/>')
    if user_secret_idx is not None:
        ang = animal_math_angle(user_secret_idx + 0.5)
        mx, my = _polar(cx, cy, R_YIN_YANG_OUT + 28, ang)
        out.append(f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="6" class="cn-marker-secret"/>')

    # Marker legend (bottom-left corner)
    out.append('<g class="cn-marker-legend-group">')
    out.append(f'<circle cx="22" cy="{size - 38}" r="5" class="cn-marker-inner"/>')
    out.append(f'<text x="34" y="{size - 38}" class="cn-marker-legend" dominant-baseline="central">Inner (month)</text>')
    out.append(f'<circle cx="22" cy="{size - 20}" r="5" class="cn-marker-secret"/>')
    out.append(f'<text x="34" y="{size - 20}" class="cn-marker-legend" dominant-baseline="central">Secret (hour)</text>')
    out.append('</g>')

    # 4. Ring outline
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ANIMAL_OUT}" class="cn-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_ANIMAL_IN}" class="cn-ring"/>')

    # 5. Five-element pentagon in the center.
    # Pentagon vertices at top + 4 around. Order: Wood (top), Fire (upper-right),
    # Earth (lower-right), Metal (lower-left), Water (upper-left) — generation
    # cycle goes clockwise around the pentagon.
    pentagon_angles = [90 - i * 72 for i in range(5)]  # math angles
    pentagon_vertices = [
        _polar(cx, cy, R_PENTAGON_OUT, a) for a in pentagon_angles
    ]

    # Generation cycle: Wood → Fire → Earth → Metal → Water → Wood
    for i in range(5):
        x1, y1 = pentagon_vertices[i]
        x2, y2 = pentagon_vertices[(i + 1) % 5]
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="cn-element-line"/>')

    # Element circles at each vertex
    for i, elem in enumerate(ELEMENTS):
        x, y = pentagon_vertices[i]
        is_active = (user_element_idx == i)
        fill_cls = f"cn-element-fill-{elem.lower()}"
        stroke_cls = "cn-element-active" if is_active else "cn-element-stroke"
        out.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="22" '
            f'class="{fill_cls} {stroke_cls}" '
            f'data-tip-type="chinese_element" data-tip-id="{elem}"/>'
        )
        # Element label below the circle
        label_offset_y = 38 if pentagon_angles[i] <= 90 and pentagon_angles[i] >= -90 else -38
        # Actually, place label radially outward from pentagon center
        label_angle = pentagon_angles[i]
        lx, ly = _polar(cx, cy, R_PENTAGON_OUT + 38, label_angle)
        out.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" class="cn-element-label" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="chinese_element" data-tip-id="{elem}">{elem}</text>'
        )

    # 6. Center stamp — Year pillar
    if user_year_animal and user_year_element:
        pillar_text = f"{user_year_polarity or ''} {user_year_element} {user_year_animal}".strip()
        out.append(
            f'<rect x="{cx - 75}" y="{cy - 14}" width="150" height="28" rx="4" '
            f'fill="var(--bg-page)" stroke="var(--accent-chinese)" stroke-width="1.4" opacity="0.92"/>'
        )
        out.append(
            f'<text x="{cx}" y="{cy}" class="cn-stamp-pillar" '
            f'text-anchor="middle" dominant-baseline="central">{pillar_text}</text>'
        )

    out.append('</svg>')
    return "\n".join(out)
