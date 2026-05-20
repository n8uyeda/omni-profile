"""
Traditional Mayan calendar — Tzolk'in day-sign + tone + trecena + Long Count.

Uses the GMT 584283 correlation per the spec ("Strictly utilizes the GMT 584283
Correlation (The Traditional Count)"). All inputs are calendar dates only;
this calendar is date-of-birth based, not time-of-birth.

Day-sign names are given in both Highland K'iche' and Classical Yucatec forms.
K'iche' is the lineage referenced by Jaguar Wisdom / Ken Johnson in the spec.

Day 0 of Long Count (0.0.0.0.0) = 4 Ajpu/Ahau = JDN 584283
(Aug 11, 3114 BCE proleptic Gregorian).
"""
from __future__ import annotations

from typing import Optional

import swisseph as swe

GMT_CORRELATION = 584283

# Index 0..19 in canonical sequence. Day 0 (JDN 584283) is 4 Ajpu (= last index, 19).
DAY_SIGNS = [
    {"kiche": "Imox",     "yucatec": "Imix"},
    {"kiche": "Iq'",      "yucatec": "Ik"},
    {"kiche": "Aq'ab'al", "yucatec": "Akbal"},
    {"kiche": "K'at",     "yucatec": "Kan"},
    {"kiche": "Kan",      "yucatec": "Chicchan"},
    {"kiche": "Kame",     "yucatec": "Cimi"},
    {"kiche": "Kej",      "yucatec": "Manik"},
    {"kiche": "Q'anil",   "yucatec": "Lamat"},
    {"kiche": "Toj",      "yucatec": "Muluc"},
    {"kiche": "Tz'i'",    "yucatec": "Oc"},
    {"kiche": "B'atz'",   "yucatec": "Chuen"},
    {"kiche": "E",        "yucatec": "Eb"},
    {"kiche": "Aj",       "yucatec": "Ben"},
    {"kiche": "I'x",      "yucatec": "Ix"},
    {"kiche": "Tz'ikin",  "yucatec": "Men"},
    {"kiche": "Ajmaq",    "yucatec": "Cib"},
    {"kiche": "No'j",     "yucatec": "Caban"},
    {"kiche": "Tijax",    "yucatec": "Etznab"},
    {"kiche": "Kawoq",    "yucatec": "Cauac"},
    {"kiche": "Ajpu",     "yucatec": "Ahau"},
]


def julian_day_number_for_date(year: int, month: int, day: int) -> int:
    """Return the integer JDN for the given proleptic Gregorian/Julian calendar date,
    using the same calendar-switch logic swisseph uses (Gregorian after 1582-10-15)."""
    # swe.julday at noon gives JD with .5 fractional. Floor to get JDN.
    jd = swe.julday(year, month, day, 12.0)
    return int(jd)  # Python int() truncates toward zero; JDN at noon is integer


def long_count(jdn: int) -> dict:
    """Compute classic Long Count baktun.katun.tun.winal.kin."""
    offset = jdn - GMT_CORRELATION
    if offset < 0:
        # supportable, just preserves sign — but birth dates are post-3114 BCE so this shouldn't fire
        return {"signed_offset_days": offset}
    baktun, r = divmod(offset, 144000)
    katun, r = divmod(r, 7200)
    tun, r = divmod(r, 360)
    winal, kin = divmod(r, 20)
    return {
        "baktun": baktun,
        "katun": katun,
        "tun": tun,
        "winal": winal,
        "kin": kin,
        "notation": f"{baktun}.{katun}.{tun}.{winal}.{kin}",
    }


def tzolkin(jdn: int) -> dict:
    """Day-sign, tone (1-13), and trecena start for the given JDN."""
    offset = jdn - GMT_CORRELATION
    tone_idx = (3 + offset) % 13   # day 0 → 4 (tone 4 → index 3)
    tone = tone_idx + 1
    sign_idx = (19 + offset) % 20  # day 0 → index 19 (Ajpu/Ahau)
    day_sign = DAY_SIGNS[sign_idx]

    # Trecena: walk back to the start of the current 13-day run (tone 1).
    trecena_start_offset = offset - tone_idx
    trecena_start_sign_idx = (19 + trecena_start_offset) % 20
    trecena_start = DAY_SIGNS[trecena_start_sign_idx]

    return {
        "day_sign": day_sign,
        "sign_index": sign_idx,
        "tone": tone,
        "trecena_start": trecena_start,
    }


def full_mayan(birth: dict) -> dict:
    """Compute the Mayan block from a birth: block. Date-only; tz/time ignored.

    The Tzolkin day boundary at local midnight is the K'iche' tradition. For
    a precision-1 birth right around midnight, this could pick the 'wrong'
    day vs. UTC-noon conventions. We use the local civil date as recorded —
    consistent with how N8 + Matty have it stored."""
    date_str = str(birth["date"])
    y, m, d = map(int, date_str.split("-"))
    jdn = julian_day_number_for_date(y, m, d)

    tz = tzolkin(jdn)
    lc = long_count(jdn)

    return {
        "correlation": f"GMT-{GMT_CORRELATION}",
        "long_count": lc.get("notation"),
        "day_sign": tz["day_sign"],
        "tone": tz["tone"],
        "trecena_start": tz["trecena_start"],
    }


def essentials_from_full(full: dict) -> dict:
    """Frontmatter-friendly subset."""
    return {
        "day_sign": full["day_sign"],
        "tone": full["tone"],
    }
