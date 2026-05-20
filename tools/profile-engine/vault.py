"""
Vault adapter: walk the canon, find pages with a populated `birth:` block.

Returns dicts (not classes) to keep the pipeline simple.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import yaml

ENTITY_TYPES = {"person", "influence", "mentor", "project", "holdco_asset"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def vault_root_from_here() -> Path:
    """Resolve the vault root assuming this file lives at tools/profile-engine/."""
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


def is_populated_birth(birth: dict | None) -> bool:
    """A birth block is considered populated if it at least has a date set."""
    if not isinstance(birth, dict):
        return False
    return bool(birth.get("date"))


def precision_of(birth: dict) -> int:
    """Read the declared precision tier (1/2/3). Default 3 if missing."""
    p = birth.get("precision")
    if isinstance(p, int) and p in (1, 2, 3):
        return p
    return 3


def iter_entities_with_birth(vault: Path) -> Iterator[dict]:
    """Yield {path, name, type, birth} for every canon page with a populated birth: block."""
    canon = vault / "04_CANON"
    if not canon.is_dir():
        return
    for md in sorted(canon.rglob("*.md")):
        fm = read_frontmatter(md)
        if not fm:
            continue
        if fm.get("type") not in ENTITY_TYPES:
            continue
        birth = fm.get("birth")
        if not is_populated_birth(birth):
            continue
        yield {
            "path": md,
            "name": md.stem,
            "type": fm.get("type"),
            "birth": birth,
            "precision": precision_of(birth),
        }
