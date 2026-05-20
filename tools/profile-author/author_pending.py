#!/usr/bin/env python3
"""Author readings for entities that have a pending-readings marker file.

Runs in a GitHub Action triggered on push to main. The /api/add-entity
serverless function writes `pending-readings/<name>.flag` when a visitor
opts in to auto-readings AND is within the 1-per-IP-per-day cap.

This script:
  1. Scans `pending-readings/` for marker files
  2. For each marker, authors the 4 system readings + thematic synthesis
     via the Anthropic API (using the ANTHROPIC_API_KEY env var)
  3. Writes the readings files alongside the existing chart files
  4. Deletes the marker
  5. Caller (the workflow) commits + pushes the changes

Usage:
    ANTHROPIC_API_KEY=sk-ant-... python3 tools/profile-author/author_pending.py
    python3 tools/profile-author/author_pending.py --dry-run

Failure mode: if a marker can't be authored (API failure etc), the marker
stays in place and gets retried on the next workflow run.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.anthropic_client import messages_call, extract_text, MODEL_AUTHORING, MAX_TOKENS_AUTHORING
from lib.prompts import (
    system_prompt_for_chat,
)

PENDING_DIR = ROOT / "pending-readings"
PEOPLE_DIR = ROOT / "vault" / "04_CANON" / "People"


# ============================================================================
# Reading prompt builders (mirrors local serve.py logic)
# ============================================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def system_prompt_for_system_readings_author() -> str:
    return (
        "You are an expert chart reader trained in Western astrology, Human "
        "Design, the Mayan Tzolk'in calendar, and Chinese astrology.\n\n"
        "Voice: warm-grounded, declarative, dense, layered. Sentences are "
        "statements. Use chart-specific values (degrees, signs, houses, gates, "
        "channels, tones, animals). 250-400 words per section.\n\n"
        "CRITICAL AUTHORING RULE — each section must stay STRICTLY within its "
        "system. No 'Yang Fire Dragon' in Mayan. No 'Projector' in Western. "
        "No 'Cancer Sun' in Chinese. No Mayan day-signs in HD.\n\n"
        "Precision handling: if precision: 2, HD reads 'Human Design requires "
        "birth time — without it, no Type / Authority / Profile can be computed.' "
        "If precision: 3, Western lacks houses + Rising.\n\n"
        "Output: a complete markdown file. Frontmatter (type: profile_system_readings, "
        "entity: <name>, generated_at, voice: warm-grounded, engine_version: '0.5', "
        "viewer_version: '0.9.3') + four H2 sections in this order: "
        "## Western, ## Human Design, ## Mayan, ## Chinese."
    )


def system_prompt_for_thematic_author() -> str:
    return (
        "You are an expert chart reader writing a cross-system thematic synthesis "
        "in warm-grounded voice: declarative, dense, layered.\n\n"
        "Output: a complete markdown file. Frontmatter (type: profile_reading, "
        "entity: <name>, generated_at, voice: warm-grounded, engine_version: '0.5', "
        "viewer_version: '0.9.3') + six H2 sections weaving all four systems:\n"
        "  ## Threshold\n  ## Mind & Self\n  ## Emotional Field\n"
        "  ## Drive & Direction\n  ## Lineage & Inheritance\n  ## Where it goes\n\n"
        "Each section weaves Western + HD + Mayan + Chinese where naturally "
        "relevant. ~150-250 words per section."
    )


def author_for_entity(name: str, dry_run: bool = False) -> tuple[bool, str]:
    """Author both reading files for one entity. Returns (success, message)."""
    canon = PEOPLE_DIR / f"{name}.md"
    yaml_p = PEOPLE_DIR / f"{name}.profile.yaml"
    sys_path = PEOPLE_DIR / f"{name}.profile.system_readings.md"
    the_path = PEOPLE_DIR / f"{name}.profile.reading.md"

    if not canon.exists() or not yaml_p.exists():
        return False, f"missing chart data for {name}"

    if dry_run:
        bits = []
        if not sys_path.exists(): bits.append("system_readings")
        if not the_path.exists(): bits.append("thematic")
        return True, f"would author: {', '.join(bits) if bits else '(nothing — already complete)'}"

    yaml_text = yaml_p.read_text(encoding="utf-8")

    # 1. System readings (4 sections)
    if not sys_path.exists():
        user_msg = (
            f"Author a complete .profile.system_readings.md file for the entity "
            f"named '{name}'.\n\n"
            f"Chart data (YAML):\n\n```yaml\n{yaml_text}\n```\n\n"
            f"Return ONLY the new markdown file content. Start with `---` "
            f"(frontmatter). Set `entity: {name}` and `generated_at: {_now_iso()}`."
        )
        payload = messages_call(
            model=MODEL_AUTHORING,
            system=system_prompt_for_system_readings_author(),
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=MAX_TOKENS_AUTHORING,
        )
        sys_text = extract_text(payload)
        sys_path.write_text(sys_text, encoding="utf-8")
    else:
        sys_text = sys_path.read_text(encoding="utf-8")

    # 2. Thematic synthesis (6 sections)
    if not the_path.exists():
        user_msg = (
            f"Author a complete .profile.reading.md file (cross-system thematic "
            f"synthesis) for the entity named '{name}'.\n\n"
            f"Chart data (YAML):\n\n```yaml\n{yaml_text}\n```\n\n"
            f"For voice + interpretive ground, here are the per-chart readings "
            f"just authored for this entity:\n\n```markdown\n{sys_text}\n```\n\n"
            f"Return ONLY the new markdown file content. Start with `---`. "
            f"Set `entity: {name}` and `generated_at: {_now_iso()}`."
        )
        payload = messages_call(
            model=MODEL_AUTHORING,
            system=system_prompt_for_thematic_author(),
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=MAX_TOKENS_AUTHORING,
        )
        the_text = extract_text(payload)
        the_path.write_text(the_text, encoding="utf-8")

    return True, f"authored readings for {name}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    p.add_argument("--dry-run", action="store_true", help="List pending markers; don't call API")
    p.add_argument("--limit", type=int, default=None, help="Process at most N markers")
    args = p.parse_args()

    if not PENDING_DIR.exists():
        print(f"no pending-readings/ directory at {PENDING_DIR}; nothing to do.")
        return 0

    flags = sorted(PENDING_DIR.glob("*.flag"))
    if not flags:
        print("no pending markers; nothing to do.")
        return 0

    print(f"found {len(flags)} pending marker{'' if len(flags) == 1 else 's'}:")
    for f in flags:
        print(f"  - {f.name}")
    print()

    if args.limit:
        flags = flags[:args.limit]

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY not set in environment.", file=sys.stderr)
        return 2

    failures = []
    for flag in flags:
        name = flag.stem  # e.g. "Jane Doe" from "Jane Doe.flag"
        print(f"processing {name}…")
        try:
            ok, msg = author_for_entity(name, dry_run=args.dry_run)
            print(f"  {msg}")
            if ok and not args.dry_run:
                flag.unlink()
                print(f"  deleted marker {flag.name}")
            elif not ok:
                failures.append(name)
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            failures.append(name)

    if failures:
        print(f"\n{len(failures)} marker{'s' if len(failures) != 1 else ''} failed; "
              f"will retry on next workflow run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
