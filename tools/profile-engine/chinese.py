"""
Chinese astrology — Layers 1, 2, 3.

  Layer 1: Year pillar (Animal + Element + Yin/Yang polarity).
    - Animal = Earthly Branch (12-year cycle): Rat, Ox, Tiger, Rabbit, Dragon,
      Snake, Horse, Goat, Monkey, Rooster, Dog, Pig.
    - Element = Heavenly Stem element (10-stem / 5-element / 2-polarity cycle):
      Wood, Fire, Earth, Metal, Water — each as Yang then Yin.
    - Year boundary = Chinese New Year (lunar — first new moon at or after
      ~Jan 21 of the Gregorian year). A birth before CNY belongs to the
      previous Chinese year.

  Layer 2: Inner Animal (Month pillar). Determined by which solar term
    (jieqi) the Sun has just crossed. Solar terms fall at 15° tropical
    longitude intervals starting from 315° (Lichun, Sun at 15° Aquarius)
    which is the start of the Tiger month.

  Layer 3: Secret Animal (Hour pillar). Determined by the 12 traditional
    double-hours; each is a 2-hour block in local civil time at the
    birthplace. Needs precision 1.

  Layer 4 (BaZi Four Pillars — full Stems & Branches for Year/Month/Day/Hour,
    with Day Master analysis) is DEFERRED to a future engine version. When
    that version is built, the engine should surface this deferral up front.

Sources used for verification: standard CNY dates per Wikipedia
(1976-01-31, 1985-02-20, 2024-02-10), and the canonical 1984 anchor as
year 1 of the current sexagenary cycle (Wood Rat).
"""
from __future__ import annotations

import swisseph as swe

EPHEMERIS_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

# Branch (Earthly Branch / Animal) — 12-cycle, indexed 0=Rat by sexagenary convention.
ANIMALS = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
           "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]

# Stem (Heavenly Stem) — 10-cycle. Elements pair as (Yang, Yin).
ELEMENTS = ["Wood", "Fire", "Earth", "Metal", "Water"]
POLARITIES = ["Yang", "Yin"]

# Anchor: 1984 Chinese New Year = first day of the current 60-year (sexagenary) cycle.
# At CNY 1984: Stem index 0 (Wood-Yang = Jia), Branch index 0 (Rat = Zi).
SEXAGENARY_ANCHOR_YEAR = 1984

# Solar terms for the 12 Chinese astrological months. Each begins when the Sun
# reaches the listed tropical longitude. Tiger month = the month containing
# the Chinese New Year, beginning at Lichun (Sun = 315°).
SOLAR_TERMS = [
    (315, "Lichun",     "Beginning of Spring", "Tiger"),
    (345, "Jingzhe",    "Awakening of Insects", "Rabbit"),
    ( 15, "Qingming",   "Pure Brightness",     "Dragon"),
    ( 45, "Lixia",      "Beginning of Summer", "Snake"),
    ( 75, "Mangzhong",  "Grain in Ear",        "Horse"),
    (105, "Xiaoshu",    "Lesser Heat",         "Goat"),
    (135, "Liqiu",      "Beginning of Autumn", "Monkey"),
    (165, "Bailu",      "White Dew",           "Rooster"),
    (195, "Hanlu",      "Cold Dew",            "Dog"),
    (225, "Lidong",     "Beginning of Winter", "Pig"),
    (255, "Daxue",      "Greater Snow",        "Rat"),
    (285, "Xiaohan",    "Lesser Cold",         "Ox"),
]

# Hour boundaries for the 12 double-hours (Earthly Branches mapped to local
# civil time). Each animal owns a 2-hour block starting at the listed hour.
# Note: Rat hour spans 23:00–01:00 (straddles midnight) — handled below.
HOUR_BRANCHES = [
    ( 1, "Ox"),       ( 3, "Tiger"),    ( 5, "Rabbit"),  ( 7, "Dragon"),
    ( 9, "Snake"),    (11, "Horse"),    (13, "Goat"),    (15, "Monkey"),
    (17, "Rooster"),  (19, "Dog"),      (21, "Pig"),     (23, "Rat"),
]


# Chinese New Year dates (Gregorian, Beijing time) 1900–2050.
# Precomputed because the rigorous algorithm requires leap-month-placement logic
# (principal-term containment per Chinese astronomical calendar). Hong-Kong-
# Observatory-grade reliable; doesn't change. Replace with a full astronomical
# implementation in a later engine version if needed.
_CNY_DATES: dict[int, tuple[int, int]] = {
    1900: (1, 31), 1901: (2, 19), 1902: (2, 8), 1903: (1, 29), 1904: (2, 16),
    1905: (2, 4), 1906: (1, 25), 1907: (2, 13), 1908: (2, 2), 1909: (1, 22),
    1910: (2, 10), 1911: (1, 30), 1912: (2, 18), 1913: (2, 6), 1914: (1, 26),
    1915: (2, 14), 1916: (2, 3), 1917: (1, 23), 1918: (2, 11), 1919: (2, 1),
    1920: (2, 20), 1921: (2, 8), 1922: (1, 28), 1923: (2, 16), 1924: (2, 5),
    1925: (1, 24), 1926: (2, 13), 1927: (2, 2), 1928: (1, 23), 1929: (2, 10),
    1930: (1, 30), 1931: (2, 17), 1932: (2, 6), 1933: (1, 26), 1934: (2, 14),
    1935: (2, 4), 1936: (1, 24), 1937: (2, 11), 1938: (1, 31), 1939: (2, 19),
    1940: (2, 8), 1941: (1, 27), 1942: (2, 15), 1943: (2, 5), 1944: (1, 25),
    1945: (2, 13), 1946: (2, 2), 1947: (1, 22), 1948: (2, 10), 1949: (1, 29),
    1950: (2, 17), 1951: (2, 6), 1952: (1, 27), 1953: (2, 14), 1954: (2, 3),
    1955: (1, 24), 1956: (2, 12), 1957: (1, 31), 1958: (2, 18), 1959: (2, 8),
    1960: (1, 28), 1961: (2, 15), 1962: (2, 5), 1963: (1, 25), 1964: (2, 13),
    1965: (2, 2), 1966: (1, 21), 1967: (2, 9), 1968: (1, 30), 1969: (2, 17),
    1970: (2, 6), 1971: (1, 27), 1972: (2, 15), 1973: (2, 3), 1974: (1, 23),
    1975: (2, 11), 1976: (1, 31), 1977: (2, 18), 1978: (2, 7), 1979: (1, 28),
    1980: (2, 16), 1981: (2, 5), 1982: (1, 25), 1983: (2, 13), 1984: (2, 2),
    1985: (2, 20), 1986: (2, 9), 1987: (1, 29), 1988: (2, 17), 1989: (2, 6),
    1990: (1, 27), 1991: (2, 15), 1992: (2, 4), 1993: (1, 23), 1994: (2, 10),
    1995: (1, 31), 1996: (2, 19), 1997: (2, 7), 1998: (1, 28), 1999: (2, 16),
    2000: (2, 5), 2001: (1, 24), 2002: (2, 12), 2003: (2, 1), 2004: (1, 22),
    2005: (2, 9), 2006: (1, 29), 2007: (2, 18), 2008: (2, 7), 2009: (1, 26),
    2010: (2, 14), 2011: (2, 3), 2012: (1, 23), 2013: (2, 10), 2014: (1, 31),
    2015: (2, 19), 2016: (2, 8), 2017: (1, 28), 2018: (2, 16), 2019: (2, 5),
    2020: (1, 25), 2021: (2, 12), 2022: (2, 1), 2023: (1, 22), 2024: (2, 10),
    2025: (1, 29), 2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13),
    2030: (2, 3), 2031: (1, 23), 2032: (2, 11), 2033: (1, 31), 2034: (2, 19),
    2035: (2, 8), 2036: (1, 28), 2037: (2, 15), 2038: (2, 4), 2039: (1, 24),
    2040: (2, 12), 2041: (2, 1), 2042: (1, 22), 2043: (2, 10), 2044: (1, 30),
    2045: (2, 17), 2046: (2, 6), 2047: (1, 26), 2048: (2, 14), 2049: (2, 2),
    2050: (1, 23),
}


def chinese_new_year_date(year: int) -> tuple[int, int, int]:
    """Chinese New Year for a Gregorian `year`. Returns (year, month, day).
    Coverage: 1900–2050 (table-based, Beijing-time-accurate). Out-of-range
    years raise — a proper astronomical implementation with leap-month logic
    can replace this lookup when needed."""
    if year in _CNY_DATES:
        m, d = _CNY_DATES[year]
        return year, m, d
    raise ValueError(
        f"Chinese New Year date not in the precomputed table for year {year}. "
        f"Coverage is 1900–2050. Extend the table or implement the full "
        f"astronomical algorithm to support this year."
    )


def year_pillar(chinese_year: int) -> dict:
    """For a Chinese year (post-CNY Gregorian year), return the year pillar."""
    branch_idx = (chinese_year - SEXAGENARY_ANCHOR_YEAR) % 12
    stem_idx = (chinese_year - SEXAGENARY_ANCHOR_YEAR) % 10
    element = ELEMENTS[stem_idx // 2]
    polarity = POLARITIES[stem_idx % 2]
    animal = ANIMALS[branch_idx]
    return {
        "animal": animal,
        "element": element,
        "polarity": polarity,
        "name": f"{element} {animal}",
        "name_with_polarity": f"{polarity} {element} {animal}",
        "stem_index": stem_idx,
        "branch_index": branch_idx,
        "sexagenary_index": (stem_idx * 6 + branch_idx * 5) % 60,  # ganzhi position
        "chinese_year_gregorian": chinese_year,
    }


def month_animal_from_sun_longitude(sun_longitude: float) -> dict:
    """Determine Inner Animal (Month) from the Sun's tropical longitude.
    Each solar term begins a 30°-wide month."""
    # Shift so that Lichun (315°) is the zero point.
    shifted = (sun_longitude - 315.0) % 360.0
    idx = int(shifted // 30)
    term = SOLAR_TERMS[idx]
    return {
        "animal": term[3],
        "solar_term_pinyin": term[1],
        "solar_term_english": term[2],
        "solar_term_start_longitude": term[0],
    }


def hour_animal(time_str: str) -> dict:
    """Determine Secret Animal (Hour) from local civil time 'HH:MM'."""
    hh, _mm = map(int, time_str.split(":"))
    if hh in (23, 0) or (hh == 0 and _mm == 0):
        animal = "Rat"
        block = "23:00–01:00"
    else:
        # Find the largest start_hour <= hh
        animal = None
        block = None
        for start_hour, a in HOUR_BRANCHES:
            if hh >= start_hour:
                animal = a
                block = f"{start_hour:02d}:00–{(start_hour + 2) % 24:02d}:00"
        if animal is None:
            animal = "Rat"
            block = "23:00–01:00"
    return {"animal": animal, "time_range": block}


def full_chinese(birth: dict) -> dict:
    """Compute the Chinese horoscope block from a `birth:` dict.

    Layer 1 (Year): requires birth.date only.
    Layer 2 (Inner / Month): requires birth.date (uses Sun longitude at noon
        UTC of birth date — for hour-of-day boundary cases, precision 1 with
        time would refine, but date-only is reliable to within ~24h since
        solar terms are 15-day apart).
    Layer 3 (Secret / Hour): requires birth.time (precision 1)."""
    date_str = str(birth["date"])
    y, m, d = map(int, date_str.split("-"))

    # Layer 1: determine which Chinese year this Gregorian date belongs to.
    cny_y, cny_m, cny_d = chinese_new_year_date(y)
    if (m, d) < (cny_m, cny_d):
        chinese_year = y - 1
        cny_for_chinese_year = chinese_new_year_date(chinese_year)
    else:
        chinese_year = y
        cny_for_chinese_year = (cny_y, cny_m, cny_d)
    year_p = year_pillar(chinese_year)
    year_p["chinese_new_year"] = (
        f"{cny_for_chinese_year[0]:04d}-{cny_for_chinese_year[1]:02d}-"
        f"{cny_for_chinese_year[2]:02d}"
    )

    # Layer 2: Inner Animal from Sun longitude at the birth moment.
    # Compute at noon UTC of birth date; refine if precision-1 time is available.
    jd_for_sun = swe.julday(y, m, d, 12.0)
    if birth.get("time") and birth.get("tz"):
        from western import birth_to_julian_day_ut
        try:
            jd_for_sun = birth_to_julian_day_ut(birth)
        except Exception:
            pass
    sun_lon = swe.calc_ut(jd_for_sun, swe.SUN, EPHEMERIS_FLAGS)[0][0]
    month_p = month_animal_from_sun_longitude(sun_lon)

    # Layer 3: Secret Animal from local civil time. Requires precision 1.
    hour_p = None
    if birth.get("time"):
        hour_p = hour_animal(birth["time"])

    triple = " / ".join(filter(None, [
        year_p["animal"], month_p["animal"], hour_p["animal"] if hour_p else None,
    ]))

    return {
        "year": year_p,
        "month": month_p,
        "hour": hour_p,
        "triple_animals": triple,  # popular "outer / inner / secret" summary
    }


def essentials_from_full(full: dict) -> dict:
    """Frontmatter-friendly subset."""
    y = full["year"]
    out = {
        "year_animal": y["animal"],
        "year_element": y["element"],
        "year_polarity": y["polarity"],
        "year_pillar": y["name_with_polarity"],
        "inner_animal": full["month"]["animal"],
    }
    if full["hour"]:
        out["secret_animal"] = full["hour"]["animal"]
    out["triple_animals"] = full["triple_animals"]
    return out
