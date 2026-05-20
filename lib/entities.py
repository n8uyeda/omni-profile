"""Entity file lookups + frontmatter helpers for the serverless functions.
The public bundle puts all entity files under vault/04_CANON/People/."""
from __future__ import annotations

import re
from pathlib import Path

# Resolved at import time. lib/ lives at the repo root; canon is two levels down.
REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = REPO_ROOT / "vault"
PEOPLE_DIR = VAULT_ROOT / "04_CANON" / "People"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
NAME_SAFE_RE = re.compile(r"^[A-Za-z0-9 .'-]{1,80}$")


def sanitize_name(name: str) -> str | None:
    name = (name or "").strip()
    if not NAME_SAFE_RE.match(name):
        return None
    return re.sub(r"\s+", " ", name)


def find_entity_files(name: str) -> tuple[Path, Path, Path, Path] | None:
    """Return (canon_md, profile_yaml, profile_reading, profile_system_readings)
    paths for the named entity, or None if the canon page doesn't exist."""
    canon = PEOPLE_DIR / f"{name}.md"
    if not canon.exists():
        return None
    return (
        canon,
        PEOPLE_DIR / f"{name}.profile.yaml",
        PEOPLE_DIR / f"{name}.profile.reading.md",
        PEOPLE_DIR / f"{name}.profile.system_readings.md",
    )


def read_pronouns_from_canon(canon_path: Path) -> str | None:
    """Pull the `pronouns:` line out of a canon page's frontmatter, if set."""
    try:
        text = canon_path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    m = re.search(r"^pronouns:\s*(\S.*?)\s*$", fm_match.group(1), re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else None
