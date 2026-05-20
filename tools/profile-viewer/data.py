"""
Load entities + computed profiles from the vault for the viewer.

Reads the canon page frontmatter (essentials) and the sibling `<Name>.profile.yaml`
(full chart). Returns a list of Entity dicts shaped for templates and the
network graph.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ENTITY_TYPES = {"person", "influence", "mentor", "project", "holdco_asset"}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def vault_root_from_here() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "vault"


def read_frontmatter(md_path: Path) -> dict | None:
    text = md_path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def slugify(name: str) -> str:
    """Filename-safe slug. Keeps original capitalization, swaps spaces for underscores."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# Map H2 headings inside .profile.system_readings.md to the canonical system key
# used by the template. Keys are case-insensitive; aliases are forgiving.
SYSTEM_HEADING_MAP = {
    "western": "western",
    "western astrology": "western",
    "natal": "western",
    "natal chart": "western",
    "human design": "human_design",
    "hd": "human_design",
    "mandala": "human_design",
    "mayan": "mayan",
    "tzolkin": "mayan",
    "tzolk'in": "mayan",
    "chinese": "chinese",
    "chinese astrology": "chinese",
    "chinese zodiac": "chinese",
}


def load_reading(md_path: Path) -> dict | None:
    """Load a sibling `<Name>.profile.reading.md` if present.

    Returns {
      'frontmatter': dict,       # YAML metadata
      'sections': [               # markdown sections, split on H2 headers
        {'heading': str, 'body': str}, ...
      ],
    } or None if no file.
    """
    reading_path = md_path.with_name(md_path.stem + ".profile.reading.md")
    if not reading_path.exists():
        return None
    text = reading_path.read_text(encoding="utf-8")
    fm: dict = {}
    body = text
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = text[fm_match.end():]
    # Split body on H2 headers
    parts = SECTION_RE.split(body)
    # parts = [prefix, heading_1, body_1, heading_2, body_2, ...]
    sections = []
    if len(parts) > 1:
        # First chunk is any pre-heading content; skip if empty
        prefix = parts[0].strip()
        if prefix:
            sections.append({"heading": None, "body": prefix})
        for i in range(1, len(parts), 2):
            sections.append({
                "heading": parts[i].strip(),
                "body": parts[i + 1].strip() if i + 1 < len(parts) else "",
            })
    else:
        # No H2 headers — single section
        if body.strip():
            sections.append({"heading": None, "body": body.strip()})
    return {"frontmatter": fm, "sections": sections}


def load_system_readings(md_path: Path) -> dict | None:
    """Load a sibling `<Name>.profile.system_readings.md` if present.

    File is expected to have one H2 section per chart system (`## Western`,
    `## Human Design`, `## Mayan`, `## Chinese`). Returns:

        {
          'frontmatter': dict,
          'systems': {
            'western':      {'heading': 'Western',      'body': str},
            'human_design': {'heading': 'Human Design', 'body': str},
            'mayan':        {'heading': 'Mayan',        'body': str},
            'chinese':      {'heading': 'Chinese',      'body': str},
          }
        }

    Missing systems are simply absent from the `systems` dict. Returns None
    if the file does not exist.
    """
    sysreads_path = md_path.with_name(md_path.stem + ".profile.system_readings.md")
    if not sysreads_path.exists():
        return None
    text = sysreads_path.read_text(encoding="utf-8")
    fm: dict = {}
    body = text
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = text[fm_match.end():]
    parts = SECTION_RE.split(body)
    systems: dict[str, dict] = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            heading = parts[i].strip()
            key = SYSTEM_HEADING_MAP.get(heading.lower())
            if not key:
                continue  # unrecognized heading — skip silently
            section_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            systems[key] = {"heading": heading, "body": section_body}
    return {"frontmatter": fm, "systems": systems}


def load_entities(vault: Path) -> list[dict]:
    """Yield entities that have at least a populated birth: block (i.e., an
    entity the engine has produced or could produce a profile for)."""
    canon = vault / "04_CANON"
    out: list[dict] = []
    if not canon.is_dir():
        return out
    for md in sorted(canon.rglob("*.md")):
        fm = read_frontmatter(md)
        if not fm:
            continue
        if fm.get("type") not in ENTITY_TYPES:
            continue
        birth = fm.get("birth")
        if not (isinstance(birth, dict) and birth.get("date")):
            continue

        # Sibling .profile.yaml (full chart) — present if engine has run on this entity.
        sibling = md.with_name(md.stem + ".profile.yaml")
        full_chart = None
        if sibling.exists():
            try:
                full_chart = yaml.safe_load(sibling.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                full_chart = None

        reading = load_reading(md)
        system_readings = load_system_readings(md)

        # Psychometric data (MBTI / Enneagram / OCEAN) — user-provided
        psych = fm.get("psychometrics")
        if isinstance(psych, dict):
            # Drop entries that are entirely None/empty
            psych = _prune_psychometrics(psych)
        else:
            psych = None

        # Operational tags — user-defined free-form labels
        tags_raw = fm.get("operational_tags") or []
        tags = [t for t in tags_raw if t and str(t).strip()] if isinstance(tags_raw, list) else []

        out.append({
            "name": md.stem,
            "slug": slugify(md.stem),
            "type": fm.get("type"),
            "domain": fm.get("domain") or "",
            "canon_path": str(md.relative_to(vault)),
            "frontmatter": fm,
            "birth": birth,
            "essentials": fm.get("profile"),   # None if engine hasn't run
            "chart": full_chart,                # None if no sibling file
            "reading": reading,                  # None if no .profile.reading.md
            "system_readings": system_readings,   # None if no .profile.system_readings.md
            "psychometrics": psych,              # None if all fields empty
            "operational_tags": tags,            # always a list, possibly empty
        })
    return out


def _prune_psychometrics(psych: dict) -> dict | None:
    """Remove None / empty values; return None if nothing left."""
    out: dict = {}
    if psych.get("mbti"):
        out["mbti"] = str(psych["mbti"]).strip()
    enn = psych.get("enneagram")
    if isinstance(enn, dict):
        enn_clean = {k: v for k, v in enn.items() if v not in (None, "")}
        if enn_clean:
            out["enneagram"] = enn_clean
    ocean = psych.get("ocean")
    if isinstance(ocean, dict):
        ocean_clean = {k: v for k, v in ocean.items() if isinstance(v, (int, float))}
        if ocean_clean:
            out["ocean"] = ocean_clean
    return out or None
