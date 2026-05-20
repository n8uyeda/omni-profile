"""
Render the Tzolk'in — Maya 260-day sacred calendar.

Two concentric "gears":
  - Outer ring: 20 day-signs (K'iche' names primary, Yucatec for tooltip)
  - Inner ring: 13 tones (1–13)

The person's day-sign and tone are highlighted in the entity accent color
with a soft glow. Center carries the resulting "[tone] [day-sign]" stamp.

Visual treatment: clean concentric rings with cog-tooth bumps on the outer
edges so the "gear" metaphor reads instantly without being mechanical.
"""
from __future__ import annotations

import math

# 20 day-signs in canonical Tzolk'in order. K'iche' first (engine default),
# Yucatec second (tooltip / cross-reference).
DAY_SIGNS = [
    ("Imox",     "Imix"),
    ("Iq'",      "Ik"),
    ("Aq'ab'al", "Akbal"),
    ("K'at",     "Kan"),
    ("Kan",      "Chicchan"),
    ("Kame",     "Cimi"),
    ("Kej",      "Manik"),
    ("Q'anil",   "Lamat"),
    ("Toj",      "Muluc"),
    ("Tz'i'",    "Oc"),
    ("B'atz'",   "Chuen"),
    ("E",        "Eb"),
    ("Aj",       "Ben"),
    ("I'x",      "Ix"),
    ("Tz'ikin",  "Men"),
    ("Ajmaq",    "Cib"),
    ("No'j",     "Caban"),
    ("Tijax",    "Etznab"),
    ("Kawoq",    "Cauac"),
    ("Ajpu",     "Ahau"),
]


def _polar(cx: float, cy: float, r: float, math_angle_deg: float) -> tuple[float, float]:
    rad = math.radians(math_angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def _wedge_path(cx: float, cy: float, r_out: float, r_in: float,
                math_start: float, math_end: float) -> str:
    """Closed wedge between two radii, sweep matching the mandala convention."""
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


def _cog_tooth_path(cx: float, cy: float, r_base: float, r_tip: float,
                    math_center: float, half_angular_width: float) -> str:
    """Trapezoid tooth path. The tooth is thinner at the tip than the base."""
    # Base corners (along inner radius)
    base_left = math_center + half_angular_width
    base_right = math_center - half_angular_width
    # Tip corners are narrower
    tip_half = half_angular_width * 0.55
    tip_left = math_center + tip_half
    tip_right = math_center - tip_half
    x1, y1 = _polar(cx, cy, r_base, base_left)
    x2, y2 = _polar(cx, cy, r_tip, tip_left)
    x3, y3 = _polar(cx, cy, r_tip, tip_right)
    x4, y4 = _polar(cx, cy, r_base, base_right)
    return f"M {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f} L {x3:.2f} {y3:.2f} L {x4:.2f} {y4:.2f} Z"


def render_tzolkin(mayan_chart: dict | None, size: int = 800) -> str:
    """Render the Tzolk'in gear chart highlighting the person's day-sign + tone."""
    cx = cy = size / 2

    # Outer day-sign ring
    R_DAY_TOOTH_TIP = size * 0.48
    R_DAY_TOOTH_BASE = size * 0.455
    R_DAY_OUT = R_DAY_TOOTH_BASE
    R_DAY_IN  = size * 0.345
    # Gap / intermesh zone
    R_GAP_OUT = R_DAY_IN
    R_GAP_IN  = size * 0.32
    # Inner tone ring
    R_TONE_TOOTH_TIP = R_GAP_IN
    R_TONE_TOOTH_BASE = size * 0.295
    R_TONE_OUT = R_TONE_TOOTH_BASE
    R_TONE_IN = size * 0.165

    # Person's position
    user_day_sign_kiche = None
    user_day_sign_yucatec = None
    user_tone = None
    if mayan_chart:
        ds = mayan_chart.get("day_sign") or {}
        if isinstance(ds, dict):
            user_day_sign_kiche = ds.get("kiche")
            user_day_sign_yucatec = ds.get("yucatec")
        user_tone = mayan_chart.get("tone")

    def find_day_sign_index() -> int | None:
        if not user_day_sign_kiche:
            return None
        for i, (kc, _) in enumerate(DAY_SIGNS):
            if kc == user_day_sign_kiche:
                return i
        return None

    user_ds_idx = find_day_sign_index()

    # Day-signs progress clockwise from 12 o'clock (math angle 90 → going down)
    # math_angle for index i = 90 - (i / 20) * 360 = 90 - i*18
    def ds_math_angle(i: int) -> float:
        return (90 - i * 18) % 360

    # Tones progress clockwise from 12 o'clock as well
    def tone_math_angle(t: int) -> float:
        # tone 1 at top, tone 13 just left of top
        return (90 - (t - 1) * (360 / 13)) % 360

    out: list[str] = [
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="tzolkin">',
        '<defs>',
        '  <filter id="tz-active-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="3" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <filter id="tz-stamp-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feGaussianBlur stdDeviation="4" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '  </filter>',
        '  <style>',
        '    .tz-tooth { fill: var(--bg-card-elevated); stroke: var(--chart-ring); stroke-width: 0.7; }',
        '    .tz-tooth-active { fill: var(--accent-mayan); filter: url(#tz-active-glow); }',
        '    .tz-day-sector { fill: var(--bg-card); stroke: var(--chart-ring); stroke-width: 0.8; }',
        '    .tz-tone-sector { fill: var(--bg-soft); stroke: var(--chart-ring); stroke-width: 0.8; }',
        '    .tz-sector-active { fill: var(--accent-soft); stroke: var(--accent-mayan); stroke-width: 2; filter: url(#tz-active-glow); }',
        '    .tz-day-label { font-family: "JetBrains Mono", monospace; font-size: 13px; fill: var(--text); font-weight: 600; letter-spacing: 0.03em; }',
        '    .tz-day-label-active { fill: var(--accent-mayan); }',
        '    .tz-tone-label { font-family: "JetBrains Mono", monospace; font-size: 22px; fill: var(--text); font-weight: 700; }',
        '    .tz-tone-label-active { fill: var(--accent-mayan); filter: url(#tz-active-glow); }',
        '    .tz-stamp-tone { font-family: "Inter", -apple-system, system-ui, sans-serif; font-size: 64px; fill: var(--accent-mayan); font-weight: 700; filter: url(#tz-stamp-glow); }',
        '    .tz-stamp-sign { font-family: "Inter", -apple-system, system-ui, sans-serif; font-size: 22px; fill: var(--text); font-weight: 600; letter-spacing: 0.04em; }',
        '    .tz-stamp-sub { font-family: "JetBrains Mono", monospace; font-size: 11px; fill: var(--text-faint); letter-spacing: 0.08em; text-transform: uppercase; }',
        '    .tz-ring { fill: none; stroke: var(--chart-ring-strong); stroke-width: 1.2; }',
        '    .tz-ring-thin { fill: none; stroke: var(--chart-ring); stroke-width: 0.6; }',
        '  </style>',
        '</defs>',
    ]

    # 1. Outer gear teeth (20 day-sign teeth)
    for i in range(20):
        ang = ds_math_angle(i + 0.5)  # tooth centered on its sector
        is_active = (user_ds_idx == i)
        tooth_d = _cog_tooth_path(cx, cy, R_DAY_TOOTH_BASE, R_DAY_TOOTH_TIP, ang, 6)
        cls = "tz-tooth tz-tooth-active" if is_active else "tz-tooth"
        out.append(f'<path d="{tooth_d}" class="{cls}"/>')

    # 2. Outer day-sign ring sectors
    for i, (kiche, yucatec) in enumerate(DAY_SIGNS):
        start_ang = ds_math_angle(i + 1)  # end-of-prev = start-of-this when iterating clockwise
        end_ang = ds_math_angle(i)
        wedge_d = _wedge_path(cx, cy, R_DAY_OUT, R_DAY_IN, start_ang, end_ang)
        is_active = (user_ds_idx == i)
        cls = "tz-day-sector tz-sector-active" if is_active else "tz-day-sector"
        out.append(
            f'<path d="{wedge_d}" class="{cls}" '
            f'data-tip-type="mayan_day_sign" data-tip-id="{kiche}"/>'
        )
        # Day-sign label, centered radially + angularly
        mid_ang = ds_math_angle(i + 0.5)
        lx, ly = _polar(cx, cy, (R_DAY_OUT + R_DAY_IN) / 2, mid_ang)
        # Rotate label so it reads outward
        rot = -(mid_ang - 90)  # SVG rotation, transforming math-angle into screen orientation
        text_cls = "tz-day-label tz-day-label-active" if is_active else "tz-day-label"
        out.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'transform="rotate({rot:.1f} {lx:.2f} {ly:.2f})" '
            f'data-tip-type="mayan_day_sign" data-tip-id="{kiche}">{kiche}</text>'
        )

    # 3. Inner tone gear teeth (13 teeth pointing outward into the gap)
    for t in range(1, 14):
        ang = tone_math_angle(t + 0.5)
        is_active = (user_tone == t)
        tooth_d = _cog_tooth_path(cx, cy, R_TONE_TOOTH_BASE, R_TONE_TOOTH_TIP, ang, 360 / 13 / 2 - 1)
        cls = "tz-tooth tz-tooth-active" if is_active else "tz-tooth"
        out.append(f'<path d="{tooth_d}" class="{cls}"/>')

    # 4. Inner tone ring sectors
    for t in range(1, 14):
        start_ang = tone_math_angle(t + 1)
        end_ang = tone_math_angle(t)
        wedge_d = _wedge_path(cx, cy, R_TONE_OUT, R_TONE_IN, start_ang, end_ang)
        is_active = (user_tone == t)
        cls = "tz-tone-sector tz-sector-active" if is_active else "tz-tone-sector"
        out.append(
            f'<path d="{wedge_d}" class="{cls}" '
            f'data-tip-type="mayan_tone" data-tip-id="{t}"/>'
        )
        mid_ang = tone_math_angle(t + 0.5)
        lx, ly = _polar(cx, cy, (R_TONE_OUT + R_TONE_IN) / 2, mid_ang)
        text_cls = "tz-tone-label tz-tone-label-active" if is_active else "tz-tone-label"
        out.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" class="{text_cls}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'data-tip-type="mayan_tone" data-tip-id="{t}">{t}</text>'
        )

    # 5. Ring outlines
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_DAY_OUT}" class="tz-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_DAY_IN}" class="tz-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_TONE_OUT}" class="tz-ring"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R_TONE_IN}" class="tz-ring-thin"/>')

    # 6. Center stamp — the person's tone + day-sign
    if user_tone is not None and user_day_sign_kiche:
        out.append(
            f'<text x="{cx}" y="{cy - 24}" class="tz-stamp-tone" '
            f'text-anchor="middle" dominant-baseline="central">{user_tone}</text>'
        )
        out.append(
            f'<text x="{cx}" y="{cy + 24}" class="tz-stamp-sign" '
            f'text-anchor="middle" dominant-baseline="central">{user_day_sign_kiche}</text>'
        )
        if user_day_sign_yucatec and user_day_sign_yucatec != user_day_sign_kiche:
            out.append(
                f'<text x="{cx}" y="{cy + 46}" class="tz-stamp-sub" '
                f'text-anchor="middle" dominant-baseline="central">{user_day_sign_yucatec}</text>'
            )
    else:
        out.append(
            f'<text x="{cx}" y="{cy}" class="tz-stamp-sub" '
            f'text-anchor="middle" dominant-baseline="central">no Mayan data</text>'
        )

    out.append('</svg>')
    return "\n".join(out)
