"""
Relational analysis between entities.

Two-layer system:
  1. Lightweight pattern-match connections (existing v0.6 work):
     - Shared HD channels, profiles, animals, day-signs, etc.
     - Used for the network graph edges.
  2. Real synastry math (added v0.9):
     - Western cross-aspects between two charts (planet of A vs planet of B)
     - HD electromagnetic channels + open/defined center pressure
     - Chinese Three-Harmony / Six-Conflict / element generating/destroying
     - Mayan day-sign + tone resonance
     - Per-system harmony/friction scores

Both layers feed:
  - Network graph (layer 1)
  - Pair-page synastry boxes (layer 2)
  - Combined-overlay dashboard summary (layer 2)
  - Top-N recommendation lists on the index (rollup of layer 2)
"""
from __future__ import annotations

import math
from itertools import combinations


# ----------------------------------------------------------------------
# Layer 1: pattern-match connections (existing — drives network graph)
# ----------------------------------------------------------------------

def dominant_element(essentials_western: dict) -> str | None:
    eb = (essentials_western or {}).get("elements")
    if not isinstance(eb, dict) or not eb:
        return None
    return max(eb, key=eb.get)


def shared_hd_channels(a_chart: dict, b_chart: dict) -> list[str]:
    a_ch = {c["channel"] for c in (a_chart.get("human_design") or {}).get("channels", [])}
    b_ch = {c["channel"] for c in (b_chart.get("human_design") or {}).get("channels", [])}
    return sorted(a_ch & b_ch)


def shared_defined_centers(a_chart: dict, b_chart: dict) -> list[str]:
    a_c = set((a_chart.get("human_design") or {}).get("defined_centers", []))
    b_c = set((b_chart.get("human_design") or {}).get("defined_centers", []))
    return sorted(a_c & b_c)


def compute_edges(entities: list[dict]) -> list[dict]:
    """Network-graph edges. One per pair where at least one connection-rule fires."""
    edges: list[dict] = []
    for a, b in combinations(entities, 2):
        a_e = a.get("essentials") or {}
        b_e = b.get("essentials") or {}
        a_c = a.get("chart") or {}
        b_c = b.get("chart") or {}

        connections: list[dict] = []

        a_sun = (a_e.get("western") or {}).get("sun") or {}
        b_sun = (b_e.get("western") or {}).get("sun") or {}
        if a_sun.get("sign") and a_sun.get("sign") == b_sun.get("sign"):
            connections.append({"kind": "sun_sign", "label": f"Both Sun in {a_sun['sign']}", "weight": 1.5})

        a_dom = dominant_element(a_e.get("western") or {})
        b_dom = dominant_element(b_e.get("western") or {})
        if a_dom and a_dom == b_dom:
            connections.append({"kind": "dominant_element", "label": f"Both {a_dom}-dominant", "weight": 1.0})

        a_hd = a_e.get("human_design") or {}
        b_hd = b_e.get("human_design") or {}
        if a_hd.get("profile") and a_hd.get("profile") == b_hd.get("profile"):
            connections.append({"kind": "hd_profile", "label": f"Both Profile {a_hd['profile']}", "weight": 1.5})

        if a_hd.get("cross_angle") and a_hd.get("cross_angle") == b_hd.get("cross_angle"):
            connections.append({"kind": "hd_cross_angle", "label": f"Both {a_hd['cross_angle']} Cross", "weight": 0.5})

        if a_c and b_c:
            shared = shared_hd_channels(a_c, b_c)
            for ch in shared:
                connections.append({"kind": "hd_channel", "label": f"Channel {ch}", "weight": 2.5})
            shared_centers = shared_defined_centers(a_c, b_c)
            if len(shared_centers) >= 2:
                connections.append({"kind": "hd_centers", "label": f"{len(shared_centers)} shared defined centers", "weight": 0.5})

        a_m = (a_e.get("mayan") or {}).get("day_sign") or {}
        b_m = (b_e.get("mayan") or {}).get("day_sign") or {}
        if a_m.get("kiche") and a_m.get("kiche") == b_m.get("kiche"):
            connections.append({"kind": "mayan_day_sign", "label": f"Both {a_m['kiche']}", "weight": 2.0})
        a_t = (a_e.get("mayan") or {}).get("tone")
        b_t = (b_e.get("mayan") or {}).get("tone")
        if a_t is not None and a_t == b_t:
            connections.append({"kind": "mayan_tone", "label": f"Both tone {a_t}", "weight": 1.0})

        a_ch = a_e.get("chinese") or {}
        b_ch = b_e.get("chinese") or {}
        if a_ch.get("year_animal") and a_ch.get("year_animal") == b_ch.get("year_animal"):
            connections.append({"kind": "chinese_year_animal", "label": f"Both {a_ch['year_animal']}", "weight": 1.5})
        if a_ch.get("year_element") and a_ch.get("year_element") == b_ch.get("year_element"):
            connections.append({"kind": "chinese_year_element", "label": f"Both {a_ch['year_element']}", "weight": 1.0})
        if a_ch.get("inner_animal") and a_ch.get("inner_animal") == b_ch.get("inner_animal"):
            connections.append({"kind": "chinese_inner_animal", "label": f"Both Inner {a_ch['inner_animal']}", "weight": 1.0})

        if connections:
            total_weight = sum(c["weight"] for c in connections)
            edges.append({
                "source": a["slug"],
                "target": b["slug"],
                "weight": round(total_weight, 2),
                "count": len(connections),
                "connections": connections,
                "tooltip": " · ".join(c["label"] for c in connections),
            })
    return edges


# ----------------------------------------------------------------------
# Layer 2: real synastry math (added v0.9)
# ----------------------------------------------------------------------

# Western cross-aspect definitions: (name, exact_angle, orb, harmony_sign)
SYNASTRY_ASPECTS = [
    ("conjunction",  0,   6.0, +1.0),   # fused; default harmonious (varies by planet)
    ("opposition",   180, 6.0, -1.0),   # tension across an axis
    ("trine",        120, 5.0, +1.0),   # harmonious flow
    ("square",       90,  5.0, -1.0),   # friction → growth
    ("sextile",      60,  3.0, +0.7),   # easy opportunity
    ("quincunx",     150, 2.0, -0.5),   # awkward adjustment
]

# Pair multipliers — these planetary pairs carry extra weight in synastry tradition.
PAIR_MULTIPLIERS = {
    frozenset({"sun", "moon"}): 1.8,
    frozenset({"venus", "mars"}): 1.6,
    frozenset({"moon", "moon"}): 1.5,
    frozenset({"sun", "sun"}): 1.4,
    frozenset({"sun", "venus"}): 1.3,
    frozenset({"sun", "mars"}): 1.2,
    frozenset({"moon", "venus"}): 1.3,
    frozenset({"moon", "mars"}): 1.2,
    frozenset({"saturn", "sun"}): 1.3,
    frozenset({"saturn", "moon"}): 1.3,
    frozenset({"saturn", "venus"}): 1.2,
    frozenset({"saturn", "mars"}): 1.1,
    frozenset({"mercury", "mercury"}): 0.9,
    frozenset({"mercury", "sun"}): 0.9,
    frozenset({"mercury", "moon"}): 0.9,
}

# Outer-planet aspects (Uranus, Neptune, Pluto, Node) are generational; lower
# weight unless aspecting the personal planets (Sun/Moon/Mercury/Venus/Mars).
OUTER_PLANETS = {"uranus", "neptune", "pluto", "north_node"}


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _orb_max_for(aspect_name: str) -> float:
    for name, _, orb, _ in SYNASTRY_ASPECTS:
        if name == aspect_name:
            return orb
    return 1.0


def compute_western_synastry(chart_a: dict | None, chart_b: dict | None) -> list[dict]:
    """Cross-aspects between two natal charts. Each event has weight (signed)."""
    events: list[dict] = []
    if not chart_a or not chart_b:
        return events
    planets_a = chart_a.get("planets") or []
    planets_b = chart_b.get("planets") or []
    for p_a in planets_a:
        for p_b in planets_b:
            sep = _angular_diff(p_a["longitude"], p_b["longitude"])
            for name, exact, orb, sign in SYNASTRY_ASPECTS:
                diff = abs(sep - exact)
                if diff <= orb:
                    body_a, body_b = p_a["body"], p_b["body"]
                    pair_mult = PAIR_MULTIPLIERS.get(frozenset({body_a, body_b}), 1.0)
                    # Outer-outer aspects are weakened (generational)
                    if body_a in OUTER_PLANETS and body_b in OUTER_PLANETS:
                        pair_mult *= 0.3
                    # Tightness: tight orbs are stronger
                    tightness = max(0.25, 1 - (diff / orb))
                    weight = sign * pair_mult * tightness
                    events.append({
                        "kind": "western_aspect",
                        "aspect": name,
                        "from": body_a,
                        "to": body_b,
                        "orb_deg": round(diff, 2),
                        "weight": round(weight, 3),
                        "label": f"A's {body_a.replace('_', ' ').title()} {name} B's {body_b.replace('_', ' ').title()}",
                        "detail": f"{diff:.1f}° orb",
                    })
                    break  # one aspect per planet-pair
    return events


# HD: list of all 36 canonical channels (gate pairs)
ALL_HD_CHANNELS = [
    (1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31),
    (9, 52), (10, 20), (10, 34), (10, 57), (11, 56), (12, 22),
    (13, 33), (16, 48), (17, 62), (18, 58), (19, 49), (20, 34),
    (20, 57), (21, 45), (23, 43), (24, 61), (25, 51), (26, 44),
    (27, 50), (28, 38), (29, 46), (30, 41), (32, 54), (34, 57),
    (35, 36), (37, 40), (39, 55), (42, 53), (47, 64),
]


def _gate_set(chart_hd: dict | None) -> set[int]:
    if not chart_hd:
        return set()
    p = {a["gate"] for a in chart_hd.get("personality_activations", []) or []}
    d = {a["gate"] for a in chart_hd.get("design_activations", []) or []}
    return p | d


def compute_hd_synastry(hd_a: dict | None, hd_b: dict | None) -> list[dict]:
    """HD synastry events:
      - Electromagnetic channels: channel completed across the pair (A has one
        gate, B has the partner — strong attraction/completion).
      - Open/defined center pressure: A feels B's defined center in their own
        open center (and vice versa) — amplification.
      - Companionship channels: both have the same channel fully defined.
    """
    events: list[dict] = []
    if not (hd_a and "skipped" not in (hd_a or {}) and hd_b and "skipped" not in (hd_b or {})):
        return events

    a_gates = _gate_set(hd_a)
    b_gates = _gate_set(hd_b)
    a_defined = set(hd_a.get("defined_centers", []))
    b_defined = set(hd_b.get("defined_centers", []))
    a_channels = {tuple(sorted(c["gates"])) for c in hd_a.get("channels", [])}
    b_channels = {tuple(sorted(c["gates"])) for c in hd_b.get("channels", [])}

    # 1. Electromagnetic channels — channel newly-completed when combined,
    # not already complete in either A or B alone.
    for g1, g2 in ALL_HD_CHANNELS:
        pair = tuple(sorted((g1, g2)))
        already_complete = pair in a_channels or pair in b_channels
        if already_complete:
            continue
        # Need A and B to between them activate both gates
        a_has = ({g1, g2} & a_gates)
        b_has = ({g1, g2} & b_gates)
        if not a_has or not b_has:
            continue
        # Combined coverage = both gates activated across the pair
        if (a_has | b_has) >= {g1, g2}:
            # Identify who carries which
            a_carries = sorted(a_has - b_has)
            b_carries = sorted(b_has - a_has)
            if a_carries and b_carries:
                events.append({
                    "kind": "hd_electromagnetic",
                    "channel": f"{g1}-{g2}",
                    "a_gate": a_carries[0] if a_carries else None,
                    "b_gate": b_carries[0] if b_carries else None,
                    "weight": 2.2,  # strong harmony
                    "label": f"Channel {g1}-{g2} — electromagnetic completion",
                    "detail": f"A carries gate {a_carries[0] if a_carries else '—'}, B carries gate {b_carries[0] if b_carries else '—'}",
                })

    # 2. Companionship channels — both have the same channel defined.
    for ch in sorted(a_channels & b_channels):
        events.append({
            "kind": "hd_companion_channel",
            "channel": f"{ch[0]}-{ch[1]}",
            "weight": 1.5,
            "label": f"Channel {ch[0]}-{ch[1]} — both define it",
            "detail": "shared definition — same energy access",
        })

    # 3. Open-vs-defined center pressure (both directions, lighter weight,
    # categorized as friction-with-growth since open centers amplify+distort).
    all_centers = {"head", "ajna", "throat", "g", "heart", "solar_plexus",
                   "sacral", "spleen", "root"}
    a_open = all_centers - a_defined
    b_open = all_centers - b_defined
    for c in sorted(b_defined & a_open):
        events.append({
            "kind": "hd_open_pressure",
            "center": c,
            "direction": "B→A",
            "weight": -0.4,
            "label": f"B's defined {c} pressures A's open {c}",
            "detail": "amplification + distortion in A's open center",
        })
    for c in sorted(a_defined & b_open):
        events.append({
            "kind": "hd_open_pressure",
            "center": c,
            "direction": "A→B",
            "weight": -0.4,
            "label": f"A's defined {c} pressures B's open {c}",
            "detail": "amplification + distortion in B's open center",
        })

    return events


# Chinese compatibility lookups
THREE_HARMONIES = {
    frozenset({"Rat", "Dragon", "Monkey"}),
    frozenset({"Ox", "Snake", "Rooster"}),
    frozenset({"Tiger", "Horse", "Dog"}),
    frozenset({"Rabbit", "Goat", "Pig"}),
}
SIX_HARMONIES = {
    frozenset({"Rat", "Ox"}), frozenset({"Tiger", "Pig"}),
    frozenset({"Rabbit", "Dog"}), frozenset({"Dragon", "Rooster"}),
    frozenset({"Snake", "Monkey"}), frozenset({"Horse", "Goat"}),
}
SIX_CONFLICTS = {
    frozenset({"Rat", "Horse"}), frozenset({"Ox", "Goat"}),
    frozenset({"Tiger", "Monkey"}), frozenset({"Rabbit", "Rooster"}),
    frozenset({"Dragon", "Dog"}), frozenset({"Snake", "Pig"}),
}
ELEMENT_GENERATES = {  # A generates B → harmony
    "Wood": "Fire", "Fire": "Earth", "Earth": "Metal",
    "Metal": "Water", "Water": "Wood",
}
ELEMENT_DESTROYS = {  # A destroys B → friction
    "Wood": "Earth", "Earth": "Water", "Water": "Fire",
    "Fire": "Metal", "Metal": "Wood",
}


def compute_chinese_synastry(c_a: dict | None, c_b: dict | None) -> list[dict]:
    events: list[dict] = []
    if not c_a or not c_b:
        return events
    a_animal = c_a.get("year_animal")
    b_animal = c_b.get("year_animal")
    a_elem = c_a.get("year_element")
    b_elem = c_b.get("year_element")

    if a_animal and b_animal:
        if a_animal == b_animal:
            events.append({
                "kind": "chinese_same_animal",
                "weight": 1.0,
                "label": f"Both {a_animal} year — mirror dynamic",
                "detail": "same archetype; harmony in shared traits, friction in shared blind spots",
            })
        elif frozenset({a_animal, b_animal}) in THREE_HARMONIES:
            events.append({
                "kind": "chinese_three_harmony",
                "weight": 2.0,
                "label": f"Three Harmonies: {a_animal} ↔ {b_animal}",
                "detail": "strong natural compatibility — same trine",
            })
        elif frozenset({a_animal, b_animal}) in SIX_HARMONIES:
            events.append({
                "kind": "chinese_six_harmony",
                "weight": 1.5,
                "label": f"Six Harmonies pair: {a_animal} ↔ {b_animal}",
                "detail": "complementary opposites — supportive",
            })
        elif frozenset({a_animal, b_animal}) in SIX_CONFLICTS:
            events.append({
                "kind": "chinese_conflict",
                "weight": -1.8,
                "label": f"Six Conflicts: {a_animal} ↔ {b_animal}",
                "detail": "directly opposing energies — tension",
            })

    if a_elem and b_elem:
        if a_elem == b_elem:
            events.append({
                "kind": "chinese_same_element",
                "weight": 0.5,
                "label": f"Both {a_elem} element",
                "detail": "shared elemental nature",
            })
        elif ELEMENT_GENERATES.get(a_elem) == b_elem:
            events.append({
                "kind": "chinese_element_generating",
                "weight": 1.2,
                "label": f"{a_elem} generates {b_elem}",
                "detail": "A's element feeds B's — supportive flow",
            })
        elif ELEMENT_GENERATES.get(b_elem) == a_elem:
            events.append({
                "kind": "chinese_element_generating",
                "weight": 1.2,
                "label": f"{b_elem} generates {a_elem}",
                "detail": "B's element feeds A's — supportive flow",
            })
        elif ELEMENT_DESTROYS.get(a_elem) == b_elem:
            events.append({
                "kind": "chinese_element_destroying",
                "weight": -1.0,
                "label": f"{a_elem} overcomes {b_elem}",
                "detail": "A's element dominates B's — friction",
            })
        elif ELEMENT_DESTROYS.get(b_elem) == a_elem:
            events.append({
                "kind": "chinese_element_destroying",
                "weight": -1.0,
                "label": f"{b_elem} overcomes {a_elem}",
                "detail": "B's element dominates A's — friction",
            })

    a_inner = c_a.get("inner_animal")
    b_inner = c_b.get("inner_animal")
    if a_inner and b_inner and a_inner == b_inner:
        events.append({
            "kind": "chinese_same_inner",
            "weight": 0.7,
            "label": f"Both Inner Animal {a_inner}",
            "detail": "matching seasonal / monthly archetype",
        })

    return events


def compute_mayan_synastry(m_a: dict | None, m_b: dict | None) -> list[dict]:
    events: list[dict] = []
    if not m_a or not m_b:
        return events
    a_sign = (m_a.get("day_sign") or {}).get("kiche") if isinstance(m_a.get("day_sign"), dict) else None
    b_sign = (m_b.get("day_sign") or {}).get("kiche") if isinstance(m_b.get("day_sign"), dict) else None
    a_tone = m_a.get("tone")
    b_tone = m_b.get("tone")

    # Same day-sign — strong resonance
    if a_sign and b_sign and a_sign == b_sign:
        events.append({
            "kind": "mayan_same_day_sign",
            "weight": 2.0,
            "label": f"Both {a_sign} day-sign",
            "detail": "same Nawal — twin archetype",
        })

    # Same tone
    if a_tone is not None and b_tone is not None and a_tone == b_tone:
        events.append({
            "kind": "mayan_same_tone",
            "weight": 1.5,
            "label": f"Both tone {a_tone}",
            "detail": "same numeric energy — shared rhythm",
        })
    # Complementary tones (1+13, 2+12, etc. — sum to 14)
    elif a_tone is not None and b_tone is not None and a_tone + b_tone == 14:
        events.append({
            "kind": "mayan_complementary_tone",
            "weight": 0.8,
            "label": f"Complementary tones {a_tone} + {b_tone} = 14",
            "detail": "balancing opposite numeric energies",
        })

    return events


def compute_psychometric_synastry(psych_a: dict | None, psych_b: dict | None,
                                  tags_a: list | None, tags_b: list | None) -> list[dict]:
    """Psychometric & operational-tag overlap events."""
    events: list[dict] = []
    psych_a = psych_a or {}
    psych_b = psych_b or {}
    tags_a = tags_a or []
    tags_b = tags_b or []

    # Same MBTI type
    mbti_a, mbti_b = psych_a.get("mbti"), psych_b.get("mbti")
    if mbti_a and mbti_b:
        if mbti_a == mbti_b:
            events.append({
                "kind": "mbti_match",
                "weight": 1.5,
                "label": f"Both MBTI {mbti_a}",
                "detail": "shared cognitive function stack",
            })
        elif len(mbti_a) == 4 and len(mbti_b) == 4:
            # Count shared dichotomies (E/I, S/N, T/F, J/P)
            shared = sum(1 for i in range(4) if mbti_a[i] == mbti_b[i])
            if shared == 3:
                events.append({
                    "kind": "mbti_close",
                    "weight": 0.7,
                    "label": f"MBTI {mbti_a} ↔ {mbti_b} share 3 of 4 letters",
                    "detail": "adjacent cognitive type",
                })

    # Same Enneagram type
    e_a = (psych_a.get("enneagram") or {}).get("type")
    e_b = (psych_b.get("enneagram") or {}).get("type")
    if e_a is not None and e_b is not None:
        if e_a == e_b:
            events.append({
                "kind": "enneagram_match",
                "weight": 1.5,
                "label": f"Both Enneagram {e_a}",
                "detail": "same core motivational structure",
            })

    # Shared operational tags
    shared_tags = set(tags_a) & set(tags_b)
    for tag in sorted(shared_tags):
        events.append({
            "kind": "tag_match",
            "weight": 0.8,
            "label": f"Both tagged '{tag}'",
            "detail": "shared operational category",
        })

    return events


def synastry_summary(entity_a: dict, entity_b: dict) -> dict:
    """Full synastry breakdown: per-system events + scores + overall totals."""
    a_chart = entity_a.get("chart") or {}
    b_chart = entity_b.get("chart") or {}

    western_events = compute_western_synastry(a_chart.get("western"), b_chart.get("western"))
    hd_events = compute_hd_synastry(a_chart.get("human_design"), b_chart.get("human_design"))
    chinese_events = compute_chinese_synastry(a_chart.get("chinese"), b_chart.get("chinese"))
    mayan_events = compute_mayan_synastry(a_chart.get("mayan"), b_chart.get("mayan"))
    psychometric_events = compute_psychometric_synastry(
        entity_a.get("psychometrics"), entity_b.get("psychometrics"),
        entity_a.get("operational_tags"), entity_b.get("operational_tags"),
    )

    def categorize(events: list[dict]) -> dict:
        harmony = sum(e["weight"] for e in events if e["weight"] > 0)
        friction = sum(-e["weight"] for e in events if e["weight"] < 0)
        return {
            "harmony": round(harmony, 2),
            "friction": round(friction, 2),
            "net": round(harmony - friction, 2),
            "count": len(events),
            "events_sorted": sorted(events, key=lambda e: abs(e["weight"]), reverse=True),
        }

    systems = {
        "western":      categorize(western_events),
        "hd":           categorize(hd_events),
        "chinese":      categorize(chinese_events),
        "mayan":        categorize(mayan_events),
        "psychometric": categorize(psychometric_events),
    }
    total_harmony = round(sum(s["harmony"] for s in systems.values()), 2)
    total_friction = round(sum(s["friction"] for s in systems.values()), 2)
    return {
        "systems": systems,
        "total_harmony": total_harmony,
        "total_friction": total_friction,
        "net": round(total_harmony - total_friction, 2),
        "total_events": sum(s["count"] for s in systems.values()),
    }


# ----------------------------------------------------------------------
# Recommendations — top harmony / friction / outliers (active at N ≥ 3)
# ----------------------------------------------------------------------

def rank_pairs(entities: list[dict]) -> dict:
    """For every pair: compute synastry summary, return sorted lists."""
    pair_records = []
    for a, b in combinations(entities, 2):
        a_, b_ = sorted([a, b], key=lambda e: e["slug"])
        summary = synastry_summary(a_, b_)
        pair_records.append({
            "entity_a": a_,
            "entity_b": b_,
            "pair_slug": f"{a_['slug']}--{b_['slug']}",
            "summary": summary,
        })
    by_harmony = sorted(pair_records, key=lambda r: r["summary"]["total_harmony"], reverse=True)
    by_friction = sorted(pair_records, key=lambda r: r["summary"]["total_friction"], reverse=True)
    by_net = sorted(pair_records, key=lambda r: r["summary"]["net"], reverse=True)
    return {
        "by_harmony": by_harmony,
        "by_friction": by_friction,
        "by_net": by_net,
        "all": pair_records,
    }


def compute_demographics(entities: list[dict]) -> list[dict]:
    """Frequency counts for categorical fields across the entity group.

    Returns a list of category dicts, each shaped:
        {
          'system': 'human_design',
          'label': 'HD Type',
          'buckets': [{'value': 'Projector', 'count': 8, 'slugs': [...]}, ...]
        }
    Buckets are sorted by count desc. Empty fields excluded entirely.
    """
    from collections import Counter, defaultdict

    def get_from_essentials(e, *path):
        v = e.get("essentials") or {}
        for p in path:
            if not isinstance(v, dict):
                return None
            v = v.get(p)
        return v

    def get_psych(e, *path):
        v = e.get("psychometrics") or {}
        for p in path:
            if not isinstance(v, dict):
                return None
            v = v.get(p)
        return v

    # (field_path, label, system_tag, source) — source is which entity attr to walk
    fields = [
        # Human Design
        (("human_design", "type"),         "HD Type",         "hd",          "essentials"),
        (("human_design", "profile"),      "HD Profile",      "hd",          "essentials"),
        (("human_design", "authority"),    "HD Authority",    "hd",          "essentials"),
        (("human_design", "definition"),   "HD Definition",   "hd",          "essentials"),
        (("human_design", "cross_angle"),  "HD Cross Angle",  "hd",          "essentials"),
        # Western
        (("western", "sun", "sign"),       "Sun sign",        "western",     "essentials"),
        (("western", "moon", "sign"),      "Moon sign",       "western",     "essentials"),
        (("western", "rising", "sign"),    "Rising sign",     "western",     "essentials"),
        # Mayan
        (("mayan", "day_sign", "kiche"),   "Mayan day-sign",  "mayan",       "essentials"),
        (("mayan", "tone"),                "Mayan tone",      "mayan",       "essentials"),
        # Chinese
        (("chinese", "year_animal"),       "Chinese animal",  "chinese",     "essentials"),
        (("chinese", "year_element"),      "Chinese element", "chinese",     "essentials"),
        (("chinese", "year_polarity"),     "Yin / Yang",      "chinese",     "essentials"),
        (("chinese", "inner_animal"),      "Inner animal",    "chinese",     "essentials"),
        (("chinese", "secret_animal"),     "Secret animal",   "chinese",     "essentials"),
        # Psychometric — user-provided, may be sparse
        (("mbti",),                        "MBTI",            "psychometric", "psychometrics"),
        (("enneagram", "type"),            "Enneagram type",  "psychometric", "psychometrics"),
    ]

    categories: list[dict] = []
    for path, label, system, source in fields:
        counts: Counter = Counter()
        slugs_by_value: dict[str, list[str]] = defaultdict(list)
        for e in entities:
            v = get_psych(e, *path) if source == "psychometrics" else get_from_essentials(e, *path)
            if v is None or v == "":
                continue
            v_str = str(v)
            counts[v_str] += 1
            slugs_by_value[v_str].append(e["slug"])
        if not counts:
            continue
        buckets = [
            {"value": v, "count": c, "slugs": slugs_by_value[v]}
            for v, c in counts.most_common()
        ]
        categories.append({
            "system": system,
            "label": label,
            "buckets": buckets,
            "total": sum(counts.values()),
            "unique": len(counts),
        })

    # Operational tags — multi-value field, count occurrences across all entities
    tag_counts: Counter = Counter()
    tag_slugs: dict[str, list[str]] = defaultdict(list)
    for e in entities:
        for tag in e.get("operational_tags") or []:
            tag_counts[tag] += 1
            tag_slugs[tag].append(e["slug"])
    if tag_counts:
        buckets = [
            {"value": v, "count": c, "slugs": tag_slugs[v]}
            for v, c in tag_counts.most_common()
        ]
        categories.append({
            "system": "psychometric",
            "label": "Operational tags",
            "buckets": buckets,
            "total": sum(tag_counts.values()),
            "unique": len(tag_counts),
        })
    return categories


def compute_outliers(entities: list[dict]) -> list[dict]:
    """Surface entities with statistically unusual placements relative to the
    group: lone Sun-element, lone HD type, lone Chinese animal, etc.

    Active only when N ≥ 3 (a group of 2 has no 'group mean' to deviate from).
    """
    if len(entities) < 3:
        return []
    outliers = []

    # Helper: extract from essentials
    def get(e, *path):
        v = e.get("essentials") or {}
        for p in path:
            if not isinstance(v, dict):
                return None
            v = v.get(p)
        return v

    def lone_field(field_path, label_template):
        """An entity is an outlier on this field if (a) its value is unique in
        the group AND (b) some other value has 2+ entities clustered on it.
        Without (b), 'all-unique' fields would falsely flag everyone."""
        values = {e["slug"]: get(e, *field_path) for e in entities}
        from collections import Counter
        counts = Counter([v for v in values.values() if v is not None])
        has_cluster = any(c >= 2 for c in counts.values())
        if not has_cluster:
            return
        for slug, v in values.items():
            if v is None:
                continue
            if counts[v] == 1:
                outliers.append({
                    "slug": slug,
                    "kind": "lone_" + "_".join(field_path),
                    "label": label_template.format(v),
                    "value": v,
                })

    # The fields to scan for solitary values
    lone_field(("western", "sun", "sign"),         "lone Sun in {0}")
    lone_field(("human_design", "type"),           "lone {0} HD type")
    lone_field(("human_design", "profile"),        "lone Profile {0}")
    lone_field(("chinese", "year_animal"),         "lone Chinese {0}")
    lone_field(("chinese", "year_element"),        "lone {0} element")
    lone_field(("mayan", "tone"),                  "lone tone {0}")

    return outliers
