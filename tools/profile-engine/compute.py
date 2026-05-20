#!/usr/bin/env python3
"""
Profile Engine — v0.2.

For every canon page with a Level-1 `birth:` block:
  - computes the full Western chart (all planets + houses + aspects)
  - computes Mayan day-sign + tone + Long Count
  - (with --write) writes the essentials to canon-page frontmatter as `profile:`
    and the full chart to a sibling `<Name>.profile.yaml`

Usage:
    python3 tools/profile-engine/compute.py
    python3 tools/profile-engine/compute.py --path "04_CANON/Personal/N8.md"
    python3 tools/profile-engine/compute.py --write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vault import (
    iter_entities_with_birth,
    vault_root_from_here,
    read_frontmatter,
    is_populated_birth,
    precision_of,
)
from western import chart as western_chart, essentials_from_full as western_essentials
from mayan import full_mayan, essentials_from_full as mayan_essentials
from human_design import full_hd_chart, essentials_from_full as hd_essentials, HDPrecisionError
from chinese import full_chinese, essentials_from_full as chinese_essentials
from writer import (
    build_essentials,
    build_full_chart,
    write_essentials_to_canon,
    write_full_chart_sibling,
)


def fmt_placement_short(p: dict) -> str:
    retro = " R" if p.get("retrograde") else ""
    return f"{p['sign']:>12} {p['degree_in_sign']:6.2f}°{retro}"


def print_chart_summary(name: str, birth: dict, precision: int, w_full: dict, m_full: dict, hd_full: dict | None, c_full: dict) -> None:
    print(f"\n  {name}  (precision {precision})")
    print(f"    born   {birth.get('date')} {birth.get('time', '')} {birth.get('tz', '')}  in  {birth.get('place', '')}")

    by_body = {p["body"]: p for p in w_full["planets"]}
    sun_house = f"    house {by_body['sun']['house']}" if "house" in by_body["sun"] else ""
    moon_house = f"    house {by_body['moon']['house']}" if "house" in by_body["moon"] else ""
    print(f"    Sun     {fmt_placement_short(by_body['sun'])}{sun_house}")
    print(f"    Moon    {fmt_placement_short(by_body['moon'])}{moon_house}")
    if w_full.get("ascendant"):
        asc = w_full["ascendant"]
        print(f"    Rising  {asc['sign']:>12} {asc['degree_in_sign']:6.2f}°")
    else:
        print(f"    Rising            —  (precision 2/3: no birth time)")
    eb = w_full["element_balance"]
    mb = w_full["modality_balance"]
    print(f"    elements:    fire {eb['fire']} · earth {eb['earth']} · air {eb['air']} · water {eb['water']}")
    print(f"    modalities:  cardinal {mb['cardinal']} · fixed {mb['fixed']} · mutable {mb['mutable']}")
    print(f"    aspects:     {len(w_full['aspects'])} found (full list in sibling file)")
    if w_full.get("precision_note"):
        print(f"    note:        Moon position ±6° (no birth time on file)")

    ds = m_full["day_sign"]
    print(f"    Mayan:       tone {m_full['tone']}  {ds['kiche']:>10} / {ds['yucatec']}    Long Count {m_full['long_count']}")

    if hd_full is not None:
        cx = hd_full["incarnation_cross"]
        print(f"    HD:          {hd_full['type']}  ·  profile {hd_full['profile']}  ·  {hd_full['authority']} authority")
        print(f"                 {hd_full['definition']}  ·  defined: {', '.join(hd_full['defined_centers'])}")
        print(f"                 {cx['angle']} Cross  {cx['code']}")
        if hd_full["channels"]:
            print(f"                 channels: {', '.join(c['channel'] for c in hd_full['channels'])}")
    else:
        print(f"    HD:          — skipped (needs precision 1: date + time + place)")

    cy = c_full["year"]
    secret = c_full["hour"]["animal"] if c_full["hour"] else "—"
    print(f"    Chinese:     {cy['name_with_polarity']}  ·  Inner: {c_full['month']['animal']}  ·  Secret: {secret}")
    print(f"                 triple: {c_full['triple_animals']}")


def compute_one(name: str, birth: dict, precision: int, canon_path: Path | None, write: bool, vault_root: Path | None = None) -> bool:
    if precision not in (1, 2, 3):
        print(f"\n  {name}: skipping — invalid precision tier {precision}. Set birth.precision to 1, 2, or 3.")
        return False
    try:
        w_full = western_chart(birth, precision)
        m_full = full_mayan(birth)
        c_full = full_chinese(birth)
    except Exception as e:
        print(f"\n  {name}: compute error — {e}")
        return False

    hd_full = None
    if precision == 1:
        try:
            hd_full = full_hd_chart(birth)
        except HDPrecisionError as e:
            print(f"\n  {name}: HD precision-1 attempt failed despite precision=1; {e}")

    print_chart_summary(name, birth, precision, w_full, m_full, hd_full, c_full)

    if write and canon_path is not None:
        essentials = build_essentials(
            western_essentials(w_full),
            mayan_essentials(m_full),
            hd_essentials(hd_full) if hd_full else None,
            chinese_essentials(c_full),
            precision=precision,
        )
        full = build_full_chart(birth, w_full, m_full, hd_full, c_full)
        write_essentials_to_canon(canon_path, essentials)
        sibling = write_full_chart_sibling(canon_path, full, vault_root=vault_root)
        print(f"    wrote: essentials → {canon_path.name} frontmatter")
        print(f"    wrote: full chart → {sibling.name}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile Engine v0.5 — Western + Mayan + HD + Chinese with Level-2/3 fallback.")
    parser.add_argument("--path", help="Restrict to one canon .md file (relative to vault/ or absolute).")
    parser.add_argument("--write", action="store_true", help="Persist: write profile: to canon frontmatter AND full chart to sibling .profile.yaml.")
    args = parser.parse_args(argv)

    vault = vault_root_from_here()
    print(f"vault root: {vault}")
    print(f"mode: {'WRITE' if args.write else 'dry-run (use --write to persist)'}")

    if args.path:
        md = Path(args.path)
        if not md.is_absolute():
            md = vault / md
        if not md.exists():
            print(f"file not found: {md}", file=sys.stderr)
            return 2
        fm = read_frontmatter(md)
        birth = (fm or {}).get("birth")
        if not is_populated_birth(birth):
            print(f"{md.name}: no populated birth: block", file=sys.stderr)
            return 1
        compute_one(md.stem, birth, precision_of(birth), md, args.write, vault_root=vault)
        return 0

    entities = list(iter_entities_with_birth(vault))
    if not entities:
        print("no entities with populated birth: blocks found under 04_CANON/", file=sys.stderr)
        return 1

    print(f"found {len(entities)} entit{'y' if len(entities) == 1 else 'ies'} with birth data")
    print("-" * 60)
    for e in entities:
        compute_one(e["name"], e["birth"], e["precision"], e["path"], args.write, vault_root=vault)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
