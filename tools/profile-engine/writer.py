"""
Write derived profile data to (a) the canon page's frontmatter (essentials)
and (b) a sibling `<Name>.profile.yaml` file (full chart).

Approach for the canon-page write:
- Parse frontmatter via PyYAML, set `profile:` key, dump back.
- Preserves field order (Python 3.7+ dict insertion order + sort_keys=False).
- Will lose YAML comments if any exist. Current vault canon pages have none.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml


class IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequence items under their parent key
    (matches the vault's 2-space convention: `aliases:\\n  - Nate`)."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
ENGINE_VERSION = "0.5"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_essentials_to_canon(canon_path: Path, essentials: dict) -> None:
    """Add or replace a top-level `profile:` block in the canon page frontmatter."""
    text = canon_path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"no frontmatter found in {canon_path}")

    fm_text = m.group(1)
    body = text[m.end():]

    data = yaml.safe_load(fm_text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter in {canon_path} did not parse as a mapping")

    data["profile"] = essentials

    new_fm = yaml.dump(
        data,
        Dumper=IndentedDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,  # avoid line-wrapping long URLs or sentences
    )
    canon_path.write_text(f"---\n{new_fm}---\n{body}", encoding="utf-8")


def write_full_chart_sibling(canon_path: Path, full_chart: dict, vault_root: Path | None = None) -> Path:
    """Write the full computed chart as `<Name>.profile.yaml` next to the canon page."""
    out_path = canon_path.with_suffix("").with_name(canon_path.stem + ".profile.yaml")
    if vault_root is not None:
        try:
            rel_canon = str(canon_path.resolve().relative_to(vault_root.resolve()))
        except ValueError:
            rel_canon = str(canon_path)
    else:
        rel_canon = str(canon_path)
    payload = {
        "generated_at": _now_iso(),
        "engine_version": ENGINE_VERSION,
        "entity": canon_path.stem,
        "canon_path": rel_canon,
        **full_chart,
    }
    out_path.write_text(
        yaml.dump(
            payload,
            Dumper=IndentedDumper,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=1000,
        ),
        encoding="utf-8",
    )
    return out_path


def build_essentials(western_essentials: dict, mayan_essentials: dict,
                     hd_essentials: dict | None, chinese_essentials: dict,
                     precision: int) -> dict:
    """Compose the small frontmatter `profile:` block. Per-system blocks
    are omitted when the system couldn't compute at the given precision."""
    out = {
        "generated_at": _now_iso(),
        "engine_version": ENGINE_VERSION,
        "precision": precision,
        "western": western_essentials,
        "mayan": mayan_essentials,
        "chinese": chinese_essentials,
    }
    if hd_essentials is not None:
        out["human_design"] = hd_essentials
    else:
        out["human_design"] = {"skipped": "requires precision 1 (date + time + place)"}
    return out


def build_full_chart(birth: dict, western_full: dict, mayan_full: dict,
                     hd_full: dict | None, chinese_full: dict) -> dict:
    """Compose the sibling-file payload from per-system full computations.
    Missing systems are represented as a `skipped:` placeholder."""
    return {
        "birth": birth,
        "western": western_full,
        "mayan": mayan_full,
        "human_design": hd_full if hd_full is not None else {
            "skipped": "requires precision 1 (date + time + place)"
        },
        "chinese": chinese_full,
    }
