"""
Western astrology calculations.

Pure functions on top of pyswisseph. Local civil time + IANA timezone in,
structured chart data out. All angles are tropical zodiac longitudes in degrees.

Conventions:
- Tropical zodiac.
- Placidus houses (configurable).
- True Node (not Mean Node) for the lunar nodes — modern default.
- Aspects: conservative orbs (8° conjunction/opposition, 7° square/trine,
  5° sextile, 3° quincunx, 2° semi-sextile).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import swisseph as swe

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

ELEMENT_BY_SIGN = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

MODALITY_BY_SIGN = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}

EPHEMERIS_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

# Body name → swisseph constant. Order matters: used as the canonical output order.
BODIES = [
    ("sun", swe.SUN),
    ("moon", swe.MOON),
    ("mercury", swe.MERCURY),
    ("venus", swe.VENUS),
    ("mars", swe.MARS),
    ("jupiter", swe.JUPITER),
    ("saturn", swe.SATURN),
    ("uranus", swe.URANUS),
    ("neptune", swe.NEPTUNE),
    ("pluto", swe.PLUTO),
    ("north_node", swe.TRUE_NODE),
    # Note: Chiron and other asteroids require an external `seas_*.se1` ephemeris file
    # from astro.com; skipped in v0.2. Re-enable once the file is provisioned.
]

# (aspect name, exact angle, orb degrees)
ASPECTS = [
    ("conjunction", 0.0, 8.0),
    ("opposition", 180.0, 8.0),
    ("trine", 120.0, 7.0),
    ("square", 90.0, 7.0),
    ("sextile", 60.0, 5.0),
    ("quincunx", 150.0, 3.0),
    ("semi_sextile", 30.0, 2.0),
]


@dataclass
class Placement:
    body: str
    longitude: float       # tropical longitude, 0-360
    sign: str
    degree_in_sign: float  # 0-30
    speed: float           # deg/day; negative = retrograde

    def to_dict(self) -> dict:
        return {
            "body": self.body,
            "longitude": round(self.longitude, 4),
            "sign": self.sign,
            "degree_in_sign": round(self.degree_in_sign, 4),
            "retrograde": self.speed < 0,
        }


def sign_from_longitude(lon: float) -> tuple[str, float]:
    lon = lon % 360
    idx = int(lon // 30)
    return SIGNS[idx], lon - idx * 30


def birth_to_julian_day_ut(birth: dict) -> float:
    """Convert a `birth:` block (local civil date+time+tz) to JD UT."""
    date_str = str(birth["date"])
    time_str = birth.get("time")
    tz_name = birth.get("tz")

    if not (date_str and time_str and tz_name):
        raise ValueError(
            "birth_to_julian_day_ut requires date + time + tz (precision 1). "
            f"got date={date_str!r} time={time_str!r} tz={tz_name!r}"
        )

    y, m, d = map(int, str(date_str).split("-"))
    hh, mm = map(int, time_str.split(":"))
    dt_local = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))

    hour_decimal = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_decimal)


def birth_to_julian_day_ut_noon(birth: dict) -> float:
    """Fallback for precision 2/3: JD at 12:00 UT of the birth date. The Moon's
    position at this moment is the best date-only proxy (±6° due to ~13°/day
    lunar motion). Sun is reliable to within ~1° regardless."""
    y, m, d = map(int, str(birth["date"]).split("-"))
    return swe.julday(y, m, d, 12.0)


def compute_placement(jd_ut: float, body_name: str, body_id: int) -> Placement:
    vals, _retflag = swe.calc_ut(jd_ut, body_id, EPHEMERIS_FLAGS)
    lon = vals[0]
    speed = vals[3]
    sign, deg_in_sign = sign_from_longitude(lon)
    return Placement(body=body_name, longitude=lon, sign=sign, degree_in_sign=deg_in_sign, speed=speed)


def compute_ascendant(jd_ut: float, lat: float, lon: float, hsys: bytes = b"P") -> dict:
    """Return Asc, MC, and all 12 cusps for the given house system (Placidus default)."""
    cusps, ascmc = swe.houses(jd_ut, lat, lon, hsys)
    asc_lon = ascmc[0]
    mc_lon = ascmc[1]
    asc_sign, asc_deg = sign_from_longitude(asc_lon)
    mc_sign, mc_deg = sign_from_longitude(mc_lon)
    houses_out = []
    for i, c in enumerate(cusps[:12], start=1):
        s, d = sign_from_longitude(c)
        houses_out.append({
            "number": i,
            "cusp_longitude": round(c % 360, 4),
            "sign": s,
            "degree_in_sign": round(d, 4),
        })
    return {
        "ascendant": {"longitude": round(asc_lon, 4), "sign": asc_sign, "degree_in_sign": round(asc_deg, 4)},
        "midheaven": {"longitude": round(mc_lon, 4), "sign": mc_sign, "degree_in_sign": round(mc_deg, 4)},
        "houses": houses_out,
    }


def assign_house(planet_longitude: float, houses: list[dict]) -> int:
    """Return house number 1..12 the planet falls in, by cusps."""
    cusps = [h["cusp_longitude"] for h in houses]
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        L = planet_longitude % 360
        if start <= end:
            if start <= L < end:
                return i + 1
        else:  # wraps past 360
            if L >= start or L < end:
                return i + 1
    return 1  # unreachable


def shortest_arc(a: float, b: float) -> float:
    """Smallest absolute separation between two longitudes, 0..180."""
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def compute_aspects(placements: list[Placement]) -> list[dict]:
    out = []
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            sep = shortest_arc(a.longitude, b.longitude)
            for name, exact, orb in ASPECTS:
                if abs(sep - exact) <= orb:
                    out.append({
                        "from": a.body,
                        "to": b.body,
                        "type": name,
                        "separation": round(sep, 4),
                        "orb": round(abs(sep - exact), 4),
                    })
                    break  # one aspect per pair (first/tightest in our priority order)
    return out


def element_modality_balance(placements: list[Placement]) -> tuple[dict, dict]:
    """Count personal/social/outer-planet placements by element and modality.
    Includes Sun, Moon, Mercury, Venus, Mars (the inner/personal). Caller can
    extend; this is the conventional 'count' used for chart balance overviews."""
    inner = {"sun", "moon", "mercury", "venus", "mars"}
    elements = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modalities = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for p in placements:
        if p.body not in inner:
            continue
        elements[ELEMENT_BY_SIGN[p.sign]] += 1
        modalities[MODALITY_BY_SIGN[p.sign]] += 1
    return elements, modalities


def chart(birth: dict, precision: int, house_system: bytes = b"P") -> dict:
    """Compute the Western chart for any precision tier.

    Precision 1: full chart (planets + houses + aspects + ASC/MC).
    Precision 2/3: planet positions + aspects + balance only; houses/ASC/MC
        omitted (require precision 1). Moon flagged as date-only-approximate."""
    if precision == 1:
        jd_ut = birth_to_julian_day_ut(birth)
        lat = birth.get("lat")
        lon = birth.get("lon")
        if lat is None or lon is None:
            raise ValueError(
                "Western chart at precision 1 requires lat + lon. "
                "Either populate them or lower the precision tier."
            )
        placements = [compute_placement(jd_ut, name, bid) for name, bid in BODIES]
        angles = compute_ascendant(jd_ut, float(lat), float(lon), house_system)
        planets_out = []
        for p in placements:
            d = p.to_dict()
            d["house"] = assign_house(p.longitude, angles["houses"])
            planets_out.append(d)
        elements, modalities = element_modality_balance(placements)
        return {
            "zodiac": "tropical",
            "house_system": {b"P": "Placidus", b"W": "Whole Sign", b"K": "Koch"}.get(house_system, "unknown"),
            "precision_note": None,
            "ascendant": angles["ascendant"],
            "midheaven": angles["midheaven"],
            "houses": angles["houses"],
            "planets": planets_out,
            "aspects": compute_aspects(placements),
            "element_balance": elements,
            "modality_balance": modalities,
        }

    # Precision 2 or 3: compute at solar-noon UT of the birth date.
    jd_ut = birth_to_julian_day_ut_noon(birth)
    placements = [compute_placement(jd_ut, name, bid) for name, bid in BODIES]
    planets_out = [p.to_dict() for p in placements]  # no house field at L2/3
    elements, modalities = element_modality_balance(placements)
    note = (
        "Computed at 12:00 UT of birth date (no birth time on file). "
        "Sun reliable to ±1°; Moon ±6° (date-only). "
        "Houses, Ascendant, and Midheaven omitted — require precision 1."
    )
    return {
        "zodiac": "tropical",
        "house_system": None,
        "precision_note": note,
        "ascendant": None,
        "midheaven": None,
        "houses": None,
        "planets": planets_out,
        "aspects": compute_aspects(placements),
        "element_balance": elements,
        "modality_balance": modalities,
    }


# Back-compat alias.
def full_chart(birth: dict, house_system: bytes = b"P") -> dict:
    return chart(birth, precision=1, house_system=house_system)


def essentials_from_full(full: dict) -> dict:
    """Extract the small frontmatter-friendly subset of a chart at any precision."""
    by_body = {p["body"]: p for p in full["planets"]}
    out = {
        "sun": {"sign": by_body["sun"]["sign"], "degree": by_body["sun"]["degree_in_sign"]},
        "moon": {"sign": by_body["moon"]["sign"], "degree": by_body["moon"]["degree_in_sign"]},
        "elements": full["element_balance"],
        "modalities": full["modality_balance"],
    }
    if full.get("ascendant"):
        out["rising"] = {"sign": full["ascendant"]["sign"], "degree": full["ascendant"]["degree_in_sign"]}
    if full.get("precision_note"):
        out["note"] = "Sun reliable to ±1°, Moon ±6° (no birth time on file)"
    return out


def sun_moon_rising(birth: dict) -> dict:
    return essentials_from_full(chart(birth, precision=1))
