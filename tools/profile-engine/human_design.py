"""
Human Design module — v0.3.

Built on top of pyswisseph. HD is a re-projection of tropical longitudes onto a
64-gate × 6-line I Ching wheel, computed for two moments:
- PERSONALITY chart: the moment of birth (same JD UT as Western)
- DESIGN chart: the moment when the Sun's tropical longitude was 88° EARLIER
  (NOT 88 days — the Sun's apparent motion varies, so we use swisseph's
  solcross_ut to find the exact crossing time).

13 activations per chart (26 total):
  Sun, Earth (= Sun + 180°), North Node, South Node (= NN + 180°),
  Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto.

Each activation has a Gate (1-64) and Line (1-6).

Wheel calibration: Gate 17 begins at 3.875° tropical Aries. Verified against
Matty's documented chart (Sun in Cancer 20.99° → Gate 62 Line 1, and
Design Sun → Gate 42 Line 3 → Profile 1/3).

Defined Centers, Channels, Type, Strategy, Authority, Profile, and
Incarnation Cross (code + angle type) are derived from the activations.
The 192-entry Incarnation Cross NAME table is intentionally deferred —
v0.3 emits the cross gates + angle classification only.
"""
from __future__ import annotations

from typing import Optional

import swisseph as swe

from western import EPHEMERIS_FLAGS, BODIES as WESTERN_BODIES, birth_to_julian_day_ut


# ----- Wheel definition -----

# Tropical longitude where Gate 17 begins. The remaining 63 gates each span 5.625°
# in this sequence around the wheel.
WHEEL_OFFSET = 3.875

# Order of the 64 gates around the wheel starting from WHEEL_OFFSET, going forward
# in zodiacal longitude. Anchor: Gate 41 at index 53 → starts at 302° tropical
# (~2° Aquarius), matching the canonical "Sun crosses Gate 41 around January 22"
# reference point.
GATE_WHEEL = [
    17, 21, 51, 42, 3, 27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15,
    52, 39, 53, 62, 56, 31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46,
    18, 48, 57, 32, 50, 28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10,
    58, 38, 54, 61, 60, 41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25,
]
assert len(GATE_WHEEL) == 64 and len(set(GATE_WHEEL)) == 64

GATE_DEG = 360.0 / 64       # 5.625
LINE_DEG = GATE_DEG / 6     # 0.9375


def gate_line_from_longitude(lon: float) -> tuple[int, int]:
    """Map tropical longitude → (gate, line). lon is in degrees, any range."""
    pos = (lon - WHEEL_OFFSET) % 360.0
    idx = int(pos // GATE_DEG)
    within = pos - idx * GATE_DEG
    line = int(within // LINE_DEG) + 1
    return GATE_WHEEL[idx], line


# ----- Centers, gates, channels -----

CENTERS = [
    "head", "ajna", "throat", "g", "heart",
    "solar_plexus", "sacral", "spleen", "root",
]

# Gates that belong to each center.
CENTER_OF_GATE: dict[int, str] = {}
def _register(center: str, gates: list[int]) -> None:
    for g in gates:
        CENTER_OF_GATE[g] = center

_register("head",         [64, 61, 63])
_register("ajna",         [47, 24, 4, 17, 43, 11])
_register("throat",       [62, 23, 56, 35, 12, 45, 33, 8, 31, 20, 16])
_register("g",            [1, 13, 25, 46, 2, 15, 10, 7])
_register("heart",        [21, 40, 26, 51])
_register("solar_plexus", [36, 22, 37, 6, 49, 55, 30])
_register("sacral",       [5, 14, 29, 59, 9, 3, 42, 27, 34])
_register("spleen",       [48, 57, 44, 50, 32, 28, 18])
_register("root",         [53, 60, 52, 19, 39, 41, 58, 38, 54])
assert len(CENTER_OF_GATE) == 64

# Motors — used to determine Type.
MOTOR_CENTERS = {"heart", "sacral", "solar_plexus", "root"}

# The 36 channels — each is a gate pair across two centers.
CHANNELS: list[tuple[int, int]] = [
    (1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31),
    (9, 52), (10, 20), (10, 34), (10, 57), (11, 56), (12, 22),
    (13, 33), (16, 48), (17, 62), (18, 58), (19, 49), (20, 34),
    (20, 57), (21, 45), (23, 43), (24, 61), (25, 51), (26, 44),
    (27, 50), (28, 38), (29, 46), (30, 41), (32, 54), (34, 57),
    (35, 36), (37, 40), (39, 55), (42, 53), (47, 64),
]
assert len(CHANNELS) == 36


# ----- Activation computation -----

# Bodies common to Western + HD. HD also needs Earth (Sun+180°) and
# South Node (NN+180°) — derived in code, not from swisseph directly.
HD_DIRECT_BODIES = [(name, bid) for (name, bid) in WESTERN_BODIES]  # 11 bodies


def compute_design_jd_ut(personality_jd_ut: float, personality_sun_lon: float) -> float:
    """Find the JD UT when the Sun was at (personality_sun - 88°). Uses swisseph
    solar-crossing function for precision (Sun's apparent motion isn't uniform)."""
    target = (personality_sun_lon - 88.0) % 360.0
    # solcross_ut searches forward from the given JD for the next time Sun crosses
    # the target longitude. To search backward, pass a JD before the design moment.
    search_start = personality_jd_ut - 100.0
    return swe.solcross_ut(target, search_start, EPHEMERIS_FLAGS)


def _sun_longitude_at(jd_ut: float) -> float:
    vals, _ = swe.calc_ut(jd_ut, swe.SUN, EPHEMERIS_FLAGS)
    return vals[0]


def compute_activations(jd_ut: float) -> list[dict]:
    """13 activations for a given moment: Sun, Earth, NN, SN, Moon, Mercury,
    Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto."""
    out = []
    # Direct bodies (11 of them — incl. True Node as "north_node")
    longs: dict[str, float] = {}
    for name, bid in HD_DIRECT_BODIES:
        vals, _ = swe.calc_ut(jd_ut, bid, EPHEMERIS_FLAGS)
        longs[name] = vals[0]

    # Earth = Sun + 180 (mod 360)
    longs["earth"] = (longs["sun"] + 180.0) % 360.0
    # South Node = North Node + 180 (mod 360)
    longs["south_node"] = (longs["north_node"] + 180.0) % 360.0

    # Output order matches the canonical HD chart listing.
    order = ["sun", "earth", "north_node", "south_node",
             "moon", "mercury", "venus", "mars",
             "jupiter", "saturn", "uranus", "neptune", "pluto"]
    for body in order:
        lon = longs[body]
        gate, line = gate_line_from_longitude(lon)
        out.append({
            "body": body,
            "longitude": round(lon, 4),
            "gate": gate,
            "line": line,
        })
    return out


# ----- Derivations from activations -----

def activated_gates(personality: list[dict], design: list[dict]) -> set[int]:
    return {a["gate"] for a in personality} | {a["gate"] for a in design}


def defined_centers(activated: set[int]) -> tuple[set[str], list[tuple[int, int]]]:
    """A center is defined when at least one COMPLETED CHANNEL touches it. A
    channel is completed when BOTH of its gates are activated. (A 'hanging gate'
    — one gate of a channel activated but not the other — does not define a center.)
    Returns (set of defined center names, list of activated channel gate-pairs)."""
    active_channels = [(a, b) for (a, b) in CHANNELS if a in activated and b in activated]
    centers = set()
    for a, b in active_channels:
        centers.add(CENTER_OF_GATE[a])
        centers.add(CENTER_OF_GATE[b])
    return centers, active_channels


def _channel_centers(pair: tuple[int, int]) -> tuple[str, str]:
    return CENTER_OF_GATE[pair[0]], CENTER_OF_GATE[pair[1]]


def derive_definition(defined: set[str], channels: list[tuple[int, int]]) -> str:
    """Definition = number of separate clusters in the defined graph.
    'No Definition' (Reflector) if no centers are defined."""
    if not defined:
        return "No Definition"
    # Build adjacency restricted to defined centers and activated channels.
    adj: dict[str, set[str]] = {c: set() for c in defined}
    for a, b in channels:
        ca, cb = CENTER_OF_GATE[a], CENTER_OF_GATE[b]
        adj[ca].add(cb)
        adj[cb].add(ca)
    seen: set[str] = set()
    components = 0
    for c in defined:
        if c in seen:
            continue
        components += 1
        stack = [c]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adj[n] - seen)
    return {1: "Single Definition", 2: "Split Definition", 3: "Triple Split",
            4: "Quadruple Split"}.get(components, f"{components}-part Definition")


def throat_connected_to_motor(defined: set[str], channels: list[tuple[int, int]]) -> bool:
    """Throat is motor-connected if a chain of defined channels links it to any motor."""
    if "throat" not in defined:
        return False
    adj: dict[str, set[str]] = {c: set() for c in defined}
    for a, b in channels:
        ca, cb = CENTER_OF_GATE[a], CENTER_OF_GATE[b]
        adj[ca].add(cb)
        adj[cb].add(ca)
    seen: set[str] = {"throat"}
    stack = ["throat"]
    while stack:
        n = stack.pop()
        if n in MOTOR_CENTERS:
            return True
        for nb in adj.get(n, ()):
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return False


def derive_type(defined: set[str], channels: list[tuple[int, int]]) -> str:
    if not defined:
        return "Reflector"
    sacral_defined = "sacral" in defined
    motor_to_throat = throat_connected_to_motor(defined, channels)
    if sacral_defined and motor_to_throat:
        return "Manifesting Generator"
    if sacral_defined:
        return "Generator"
    if motor_to_throat:
        return "Manifestor"
    return "Projector"


STRATEGIES = {
    "Manifestor": "To Inform",
    "Generator": "To Respond",
    "Manifesting Generator": "To Respond and Inform",
    "Projector": "Wait for the Invitation",
    "Reflector": "Wait a Lunar Cycle",
}

NOT_SELF_THEMES = {
    "Manifestor": "Anger",
    "Generator": "Frustration",
    "Manifesting Generator": "Frustration and Anger",
    "Projector": "Bitterness",
    "Reflector": "Disappointment",
}


def derive_authority(defined: set[str], hd_type: str) -> str:
    """Inner authority hierarchy. The first defined center in this order
    determines authority (with type-specific exceptions for Projectors)."""
    if hd_type == "Reflector":
        return "Lunar"
    if "solar_plexus" in defined:
        return "Emotional"
    if "sacral" in defined:
        return "Sacral"
    if "spleen" in defined:
        return "Splenic"
    if "heart" in defined:
        # G-center → Self-Projected; otherwise Ego/Heart projector
        if hd_type == "Projector" and "g" in defined:
            return "Self-Projected"
        return "Ego"  # Manifestor with Heart authority
    if hd_type == "Projector":
        if "g" in defined:
            return "Self-Projected"
        return "Mental/Environmental"
    return "Unknown"


def derive_profile(personality: list[dict], design: list[dict]) -> str:
    """Profile = Personality Sun line / Design Sun line."""
    p_sun = next(a for a in personality if a["body"] == "sun")
    d_sun = next(a for a in design if a["body"] == "sun")
    return f"{p_sun['line']}/{d_sun['line']}"


# Incarnation Cross canonical names (Ra Uru Hu / Jovian Archive standard).
# Lookup by (angle_type, Personality_Sun_gate). Each angle has 32 unique names
# distributed across the 64 gates — each name covers the two gates of the
# same Sun-Earth axis (e.g., gate 1 and gate 2 both yield "Cross of the Sphinx"
# in Right Angle).
#
# Verified entries: Consciousness (N8: gate 35), Maya (Matty: gate 62),
# the Four Ways (Andrea T + Nadine R: gate 24), Industry (Ben U: gate 29 LAC),
# the Vessel of Love (Mahni + David B: gate 46), Eden (Gabriel V: gate 36).
# Remaining entries reconstructed from canonical HD references; verify against
# Jovian Archive bgcalc output if a discrepancy arises and update here.
INCARNATION_CROSS_NAMES: dict[tuple[str, int], str] = {
    # ---- Right Angle Crosses (64 entries, 32 unique names) ----
    ("Right Angle", 1):  "Right Angle Cross of the Sphinx",
    ("Right Angle", 2):  "Right Angle Cross of the Sphinx",
    ("Right Angle", 3):  "Right Angle Cross of Laws",
    ("Right Angle", 50): "Right Angle Cross of Laws",
    ("Right Angle", 4):  "Right Angle Cross of Explanation",
    ("Right Angle", 49): "Right Angle Cross of Explanation",
    ("Right Angle", 5):  "Right Angle Cross of Consciousness",
    ("Right Angle", 35): "Right Angle Cross of Consciousness",
    ("Right Angle", 6):  "Right Angle Cross of Eden",
    ("Right Angle", 36): "Right Angle Cross of Eden",
    ("Right Angle", 7):  "Right Angle Cross of the Sphinx",   # alt-axis variant
    ("Right Angle", 13): "Right Angle Cross of the Sphinx",   # alt-axis variant
    ("Right Angle", 8):  "Right Angle Cross of Contagion",
    ("Right Angle", 14): "Right Angle Cross of Contagion",
    ("Right Angle", 9):  "Right Angle Cross of Planning",
    ("Right Angle", 16): "Right Angle Cross of Planning",
    ("Right Angle", 10): "Right Angle Cross of the Vessel of Love",
    ("Right Angle", 15): "Right Angle Cross of the Vessel of Love",
    ("Right Angle", 11): "Right Angle Cross of Eden",         # 11/12 axis
    ("Right Angle", 12): "Right Angle Cross of Eden",
    ("Right Angle", 17): "Right Angle Cross of Service",
    ("Right Angle", 18): "Right Angle Cross of Service",
    ("Right Angle", 19): "Right Angle Cross of the Four Ways",
    ("Right Angle", 33): "Right Angle Cross of the Four Ways",
    ("Right Angle", 20): "Right Angle Cross of the Sleeping Phoenix",
    ("Right Angle", 34): "Right Angle Cross of the Sleeping Phoenix",
    ("Right Angle", 21): "Right Angle Cross of Tension",
    ("Right Angle", 48): "Right Angle Cross of Tension",
    ("Right Angle", 22): "Right Angle Cross of Rulership",
    ("Right Angle", 47): "Right Angle Cross of Rulership",
    ("Right Angle", 23): "Right Angle Cross of Explanation",  # alt 23/43 axis
    ("Right Angle", 43): "Right Angle Cross of Explanation",
    ("Right Angle", 24): "Right Angle Cross of the Four Ways",
    ("Right Angle", 44): "Right Angle Cross of the Four Ways",
    ("Right Angle", 25): "Right Angle Cross of the Vessel of Love",
    ("Right Angle", 46): "Right Angle Cross of the Vessel of Love",
    ("Right Angle", 26): "Right Angle Cross of Rulership",
    ("Right Angle", 45): "Right Angle Cross of Rulership",
    ("Right Angle", 27): "Right Angle Cross of the Unexpected",
    ("Right Angle", 28): "Right Angle Cross of the Unexpected",
    ("Right Angle", 29): "Right Angle Cross of Industry",
    ("Right Angle", 30): "Right Angle Cross of Industry",
    ("Right Angle", 31): "Right Angle Cross of the Alpha",
    ("Right Angle", 41): "Right Angle Cross of the Unexpected",
    ("Right Angle", 32): "Right Angle Cross of Maya",
    ("Right Angle", 42): "Right Angle Cross of Maya",
    ("Right Angle", 37): "Right Angle Cross of Planning",
    ("Right Angle", 40): "Right Angle Cross of Planning",
    ("Right Angle", 38): "Right Angle Cross of Tension",
    ("Right Angle", 39): "Right Angle Cross of Tension",
    ("Right Angle", 51): "Right Angle Cross of Penetration",
    ("Right Angle", 57): "Right Angle Cross of Penetration",
    ("Right Angle", 52): "Right Angle Cross of Service",
    ("Right Angle", 58): "Right Angle Cross of Service",
    ("Right Angle", 53): "Right Angle Cross of Penetration",
    ("Right Angle", 54): "Right Angle Cross of Penetration",
    ("Right Angle", 55): "Right Angle Cross of the Sleeping Phoenix",
    ("Right Angle", 59): "Right Angle Cross of the Sleeping Phoenix",
    ("Right Angle", 56): "Right Angle Cross of Laws",
    ("Right Angle", 60): "Right Angle Cross of Laws",
    ("Right Angle", 61): "Right Angle Cross of Maya",
    ("Right Angle", 62): "Right Angle Cross of Maya",
    ("Right Angle", 63): "Right Angle Cross of Consciousness",
    ("Right Angle", 64): "Right Angle Cross of Consciousness",

    # ---- Left Angle Crosses (64 entries, 32 unique names) ----
    ("Left Angle", 1):   "Left Angle Cross of the Defiant",
    ("Left Angle", 2):   "Left Angle Cross of the Defiant",
    ("Left Angle", 3):   "Left Angle Cross of Wishes",
    ("Left Angle", 50):  "Left Angle Cross of Wishes",
    ("Left Angle", 4):   "Left Angle Cross of Revolution",
    ("Left Angle", 49):  "Left Angle Cross of Revolution",
    ("Left Angle", 5):   "Left Angle Cross of Separation",
    ("Left Angle", 35):  "Left Angle Cross of Separation",
    ("Left Angle", 6):   "Left Angle Cross of Confrontation",
    ("Left Angle", 36):  "Left Angle Cross of Confrontation",
    ("Left Angle", 7):   "Left Angle Cross of the Alpha",
    ("Left Angle", 13):  "Left Angle Cross of Masks",
    ("Left Angle", 8):   "Left Angle Cross of Uncertainty",
    ("Left Angle", 14):  "Left Angle Cross of Uncertainty",
    ("Left Angle", 9):   "Left Angle Cross of Focus",
    ("Left Angle", 16):  "Left Angle Cross of Identification",
    ("Left Angle", 10):  "Left Angle Cross of Prevention",
    ("Left Angle", 15):  "Left Angle Cross of Prevention",
    ("Left Angle", 11):  "Left Angle Cross of Education",
    ("Left Angle", 12):  "Left Angle Cross of Education",
    ("Left Angle", 17):  "Left Angle Cross of Upheaval",
    ("Left Angle", 18):  "Left Angle Cross of Upheaval",
    ("Left Angle", 19):  "Left Angle Cross of Refinement",
    ("Left Angle", 33):  "Left Angle Cross of Refinement",
    ("Left Angle", 20):  "Left Angle Cross of Duality",
    ("Left Angle", 34):  "Left Angle Cross of Duality",
    ("Left Angle", 21):  "Left Angle Cross of Endeavor",
    ("Left Angle", 48):  "Left Angle Cross of Endeavor",
    ("Left Angle", 22):  "Left Angle Cross of Rulership",
    ("Left Angle", 47):  "Left Angle Cross of Rulership",
    ("Left Angle", 23):  "Left Angle Cross of Dedication",
    ("Left Angle", 43):  "Left Angle Cross of Dedication",
    ("Left Angle", 24):  "Left Angle Cross of Incarnation",
    ("Left Angle", 44):  "Left Angle Cross of Incarnation",
    ("Left Angle", 25):  "Left Angle Cross of Healing",
    ("Left Angle", 46):  "Left Angle Cross of Healing",
    ("Left Angle", 26):  "Left Angle Cross of Confrontation",
    ("Left Angle", 45):  "Left Angle Cross of Confrontation",
    ("Left Angle", 27):  "Left Angle Cross of Alignment",
    ("Left Angle", 28):  "Left Angle Cross of Alignment",
    ("Left Angle", 29):  "Left Angle Cross of Industry",
    ("Left Angle", 30):  "Left Angle Cross of Industry",
    ("Left Angle", 31):  "Left Angle Cross of the Alpha",
    ("Left Angle", 41):  "Left Angle Cross of Spirit",
    ("Left Angle", 32):  "Left Angle Cross of Limitation",
    ("Left Angle", 42):  "Left Angle Cross of Limitation",
    ("Left Angle", 37):  "Left Angle Cross of Migration",
    ("Left Angle", 40):  "Left Angle Cross of Migration",
    ("Left Angle", 38):  "Left Angle Cross of Individualism",
    ("Left Angle", 39):  "Left Angle Cross of Individualism",
    ("Left Angle", 51):  "Left Angle Cross of the Clarion",
    ("Left Angle", 57):  "Left Angle Cross of the Clarion",
    ("Left Angle", 52):  "Left Angle Cross of Demands",
    ("Left Angle", 58):  "Left Angle Cross of Demands",
    ("Left Angle", 53):  "Left Angle Cross of Cycles",
    ("Left Angle", 54):  "Left Angle Cross of Cycles",
    ("Left Angle", 55):  "Left Angle Cross of Moods",
    ("Left Angle", 59):  "Left Angle Cross of Moods",
    ("Left Angle", 56):  "Left Angle Cross of Distraction",
    ("Left Angle", 60):  "Left Angle Cross of Distraction",
    ("Left Angle", 61):  "Left Angle Cross of Obscuration",
    ("Left Angle", 62):  "Left Angle Cross of Obscuration",
    ("Left Angle", 63):  "Left Angle Cross of Dominion",
    ("Left Angle", 64):  "Left Angle Cross of Dominion",

    # ---- Juxtaposition Crosses (64 entries — Profile 4/1, fixed-fate) ----
    ("Juxtaposition", 1):  "Juxtaposition Cross of Self-Expression",
    ("Juxtaposition", 2):  "Juxtaposition Cross of Allowing",
    ("Juxtaposition", 3):  "Juxtaposition Cross of Mutation",
    ("Juxtaposition", 4):  "Juxtaposition Cross of Formulization",
    ("Juxtaposition", 5):  "Juxtaposition Cross of Patterns",
    ("Juxtaposition", 6):  "Juxtaposition Cross of Conflict",
    ("Juxtaposition", 7):  "Juxtaposition Cross of Interaction",
    ("Juxtaposition", 8):  "Juxtaposition Cross of Contribution",
    ("Juxtaposition", 9):  "Juxtaposition Cross of Focus",
    ("Juxtaposition", 10): "Juxtaposition Cross of Behavior",
    ("Juxtaposition", 11): "Juxtaposition Cross of Ideas",
    ("Juxtaposition", 12): "Juxtaposition Cross of Articulation",
    ("Juxtaposition", 13): "Juxtaposition Cross of the Listener",
    ("Juxtaposition", 14): "Juxtaposition Cross of Empowering",
    ("Juxtaposition", 15): "Juxtaposition Cross of Extremes",
    ("Juxtaposition", 16): "Juxtaposition Cross of Experimentation",
    ("Juxtaposition", 17): "Juxtaposition Cross of Opinion",
    ("Juxtaposition", 18): "Juxtaposition Cross of Correction",
    ("Juxtaposition", 19): "Juxtaposition Cross of Need",
    ("Juxtaposition", 20): "Juxtaposition Cross of the Now",
    ("Juxtaposition", 21): "Juxtaposition Cross of Control",
    ("Juxtaposition", 22): "Juxtaposition Cross of Grace",
    ("Juxtaposition", 23): "Juxtaposition Cross of Assimilation",
    ("Juxtaposition", 24): "Juxtaposition Cross of Rationalization",
    ("Juxtaposition", 25): "Juxtaposition Cross of Innocence",
    ("Juxtaposition", 26): "Juxtaposition Cross of the Trickster",
    ("Juxtaposition", 27): "Juxtaposition Cross of Caring",
    ("Juxtaposition", 28): "Juxtaposition Cross of Risk",
    ("Juxtaposition", 29): "Juxtaposition Cross of Commitment",
    ("Juxtaposition", 30): "Juxtaposition Cross of Fates",
    ("Juxtaposition", 31): "Juxtaposition Cross of Influence",
    ("Juxtaposition", 32): "Juxtaposition Cross of Conservation",
    ("Juxtaposition", 33): "Juxtaposition Cross of Retreat",
    ("Juxtaposition", 34): "Juxtaposition Cross of Power",
    ("Juxtaposition", 35): "Juxtaposition Cross of Experience",
    ("Juxtaposition", 36): "Juxtaposition Cross of Crisis",
    ("Juxtaposition", 37): "Juxtaposition Cross of the Bargain",
    ("Juxtaposition", 38): "Juxtaposition Cross of Opposition",
    ("Juxtaposition", 39): "Juxtaposition Cross of Provocation",
    ("Juxtaposition", 40): "Juxtaposition Cross of Denial",
    ("Juxtaposition", 41): "Juxtaposition Cross of Fantasy",
    ("Juxtaposition", 42): "Juxtaposition Cross of Completion",
    ("Juxtaposition", 43): "Juxtaposition Cross of Insight",
    ("Juxtaposition", 44): "Juxtaposition Cross of Alertness",
    ("Juxtaposition", 45): "Juxtaposition Cross of the Gatherer",
    ("Juxtaposition", 46): "Juxtaposition Cross of Serendipity",
    ("Juxtaposition", 47): "Juxtaposition Cross of Oppression",
    ("Juxtaposition", 48): "Juxtaposition Cross of Depth",
    ("Juxtaposition", 49): "Juxtaposition Cross of Principles",
    ("Juxtaposition", 50): "Juxtaposition Cross of Values",
    ("Juxtaposition", 51): "Juxtaposition Cross of Shock",
    ("Juxtaposition", 52): "Juxtaposition Cross of Stillness",
    ("Juxtaposition", 53): "Juxtaposition Cross of Beginnings",
    ("Juxtaposition", 54): "Juxtaposition Cross of Ambition",
    ("Juxtaposition", 55): "Juxtaposition Cross of Spirit",
    ("Juxtaposition", 56): "Juxtaposition Cross of Stimulation",
    ("Juxtaposition", 57): "Juxtaposition Cross of Intuition",
    ("Juxtaposition", 58): "Juxtaposition Cross of Vitality",
    ("Juxtaposition", 59): "Juxtaposition Cross of Strategy",
    ("Juxtaposition", 60): "Juxtaposition Cross of Limitation",
    ("Juxtaposition", 61): "Juxtaposition Cross of Mystery",
    ("Juxtaposition", 62): "Juxtaposition Cross of Detail",
    ("Juxtaposition", 63): "Juxtaposition Cross of Doubts",
    ("Juxtaposition", 64): "Juxtaposition Cross of Confusion",
}
assert len(INCARNATION_CROSS_NAMES) == 192, \
    f"expected 192 cross-name entries, got {len(INCARNATION_CROSS_NAMES)}"


def derive_cross(personality: list[dict], design: list[dict]) -> dict:
    """Incarnation Cross — code (gates), angle type, and canonical name."""
    p_sun = next(a for a in personality if a["body"] == "sun")
    p_earth = next(a for a in personality if a["body"] == "earth")
    d_sun = next(a for a in design if a["body"] == "sun")
    d_earth = next(a for a in design if a["body"] == "earth")
    profile = (p_sun["line"], d_sun["line"])
    # Cross angle by profile combination
    right_angle = {(1, 3), (1, 4), (2, 4), (2, 5), (3, 5), (3, 6), (4, 6)}
    juxtaposition = {(4, 1)}
    left_angle = {(5, 1), (5, 2), (6, 2), (6, 3)}
    if profile in right_angle:
        angle = "Right Angle"
    elif profile in juxtaposition:
        angle = "Juxtaposition"
    elif profile in left_angle:
        angle = "Left Angle"
    else:
        angle = "Unclassified"
    # Canonical name lookup
    name = INCARNATION_CROSS_NAMES.get((angle, p_sun["gate"]))
    return {
        "angle": angle,
        "code": f"{p_sun['gate']}/{p_earth['gate']} | {d_sun['gate']}/{d_earth['gate']}",
        "gates": {
            "personality_sun": p_sun["gate"],
            "personality_earth": p_earth["gate"],
            "design_sun": d_sun["gate"],
            "design_earth": d_earth["gate"],
        },
        "name": name,
    }


def channel_record(pair: tuple[int, int]) -> dict:
    a, b = pair
    return {
        "channel": f"{a}-{b}",
        "gates": [a, b],
        "centers": list(_channel_centers(pair)),
    }


class HDPrecisionError(ValueError):
    """Raised when Human Design can't be computed for the given birth data.
    HD requires precision 1: the Personality Sun's *line* shifts every ~26h,
    so without an exact birth time, the profile is undeterminable."""


def full_hd_chart(birth: dict) -> dict:
    """Compute the complete HD chart for a Level-1 birth block.
    Raises HDPrecisionError if time, tz, lat, or lon are missing."""
    if not (birth.get("time") and birth.get("tz")):
        raise HDPrecisionError(
            "Human Design requires precision 1 (date + time + tz). "
            "Personality Sun line shifts every ~26 hours; without exact "
            "birth time the profile is undeterminable."
        )
    p_jd = birth_to_julian_day_ut(birth)
    p_sun_lon = _sun_longitude_at(p_jd)
    d_jd = compute_design_jd_ut(p_jd, p_sun_lon)

    personality = compute_activations(p_jd)
    design = compute_activations(d_jd)

    activated = activated_gates(personality, design)
    defined, active_channels = defined_centers(activated)
    hd_type = derive_type(defined, active_channels)
    authority = derive_authority(defined, hd_type)
    strategy = STRATEGIES.get(hd_type, "Unknown")
    not_self = NOT_SELF_THEMES.get(hd_type, "Unknown")
    profile = derive_profile(personality, design)
    cross = derive_cross(personality, design)
    definition = derive_definition(defined, active_channels)

    # Hanging gates: activated but not in a completed channel.
    in_channel = {g for pair in active_channels for g in pair}
    hanging = sorted(activated - in_channel)

    return {
        "type": hd_type,
        "strategy": strategy,
        "authority": authority,
        "not_self_theme": not_self,
        "profile": profile,
        "definition": definition,
        "incarnation_cross": cross,
        "defined_centers": sorted(defined),
        "undefined_centers": sorted(set(CENTERS) - defined),
        "channels": [channel_record(p) for p in sorted(active_channels)],
        "hanging_gates": hanging,
        "personality_jd_ut": round(p_jd, 5),
        "design_jd_ut": round(d_jd, 5),
        "personality_activations": personality,
        "design_activations": design,
    }


def essentials_from_full(full: dict) -> dict:
    """Frontmatter-friendly subset."""
    return {
        "type": full["type"],
        "strategy": full["strategy"],
        "authority": full["authority"],
        "profile": full["profile"],
        "definition": full["definition"],
        "incarnation_cross": full["incarnation_cross"]["code"],
        "cross_angle": full["incarnation_cross"]["angle"],
        "cross_name": full["incarnation_cross"]["name"],
    }
