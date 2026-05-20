#!/usr/bin/env python3
"""
Local Omni-Profile dev server. Serves the built static site and accepts new
entity submissions from the add-entity form on the homepage.

Usage:
    python3 tools/profile-viewer/serve.py
    python3 tools/profile-viewer/serve.py --port 9000
    python3 tools/profile-viewer/serve.py --no-rebuild   # skip viewer build after add

Endpoints:
    GET  /<path>              static files from <repo>/site/
    POST /api/geocode         { "query": "Santa Barbara, CA" } -> Nominatim lookup
    POST /api/add-entity      see API below

POST /api/add-entity body (JSON):
    {
      "name":      "Jane Doe",                 # required
      "date":      "1986-04-12",               # required, YYYY-MM-DD
      "time":      "13:30",                    # optional, HH:MM (24h)
      "place":     "San Francisco, CA, USA",   # optional human-readable
      "lat":       37.7749,                    # required if precision 1 or 2
      "lon":      -122.4194,                   # required if precision 1 or 2
      "tz":        "America/Los_Angeles",      # required if precision 1
      "domain":    "Shared",                   # optional, defaults to "Shared"
      "relationship": ""                       # optional human label
    }

Response (success): { "ok": true, "slug": "Jane_Doe", "canon_path": "..." }
Response (failure): { "ok": false, "error": "<message>" }  with non-200 status
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date as _date
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VAULT_ROOT = REPO_ROOT / "vault"
PEOPLE_DIR = VAULT_ROOT / "04_CANON" / "Shared" / "People"
PERSONAL_DIR = VAULT_ROOT / "04_CANON" / "Personal"

# Defer importing the data + synastry modules until first use; they're heavy
# and only needed for pair-chat (2-entity mode). data.py is a sibling module
# already on this directory's path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
SITE_DIR = REPO_ROOT / "site"
ENGINE_COMPUTE = REPO_ROOT / "tools" / "profile-engine" / "compute.py"
VIEWER_BUILD = REPO_ROOT / "tools" / "profile-viewer" / "build.py"

# Reference template — the authoring rule + structure all generated readings
# must follow. Loaded once at startup.
REFERENCE_READING = PERSONAL_DIR / "N8.profile.system_readings.md"

# ============================================================================
# Anthropic API — keys, cost tracking, safety caps
# ============================================================================

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# Default models. Sonnet for one-shot authoring (quality + reasoning matters);
# Haiku for chat (many short turns, latency-sensitive).
MODEL_AUTHORING = os.environ.get("OMNI_MODEL_AUTHORING", "claude-sonnet-4-6")
MODEL_CHAT      = os.environ.get("OMNI_MODEL_CHAT", "claude-sonnet-4-6")

# Hard token cap per request — prevents runaway responses.
MAX_TOKENS_AUTHORING = 4000
MAX_TOKENS_CHAT      = 1500

# Per-session spend cap (USD). Server refuses further LLM calls once exceeded
# until restart. Configurable via OMNI_SPEND_CAP env var.
SESSION_SPEND_CAP_USD = float(os.environ.get("OMNI_SPEND_CAP", "1.0"))

# Pricing per million tokens (USD). Approximate published rates; updated rarely.
PRICING = {
    "claude-sonnet-4-6":  {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5":   {"input": 1.0,  "output": 5.0},
    "claude-opus-4-7":    {"input": 15.0, "output": 75.0},
}

# Running spend tally for this server session.
_SPEND_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "calls": 0,
    "estimated_usd": 0.0,
}


def estimate_call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]


def anthropic_messages_call(model: str, system: str, messages: list[dict],
                             max_tokens: int) -> dict:
    """Single Messages API call. Returns the parsed JSON response, or raises
    a RuntimeError with a user-friendly message on failure.

    Tracks token usage + estimated cost in _SPEND_USAGE. Refuses the call if
    the per-session spend cap would be exceeded (estimated post-call).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Get one at https://console.anthropic.com/ "
            "and export it before starting the server: "
            "`export ANTHROPIC_API_KEY=sk-ant-...`"
        )
    if _SPEND_USAGE["estimated_usd"] >= SESSION_SPEND_CAP_USD:
        raise RuntimeError(
            f"Per-session API spend cap reached "
            f"(${_SPEND_USAGE['estimated_usd']:.4f} / ${SESSION_SPEND_CAP_USD:.2f}). "
            f"Restart the server to reset, or raise the cap with `OMNI_SPEND_CAP=5.0`."
        )

    body = json.dumps({
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {detail or e.reason}")
    except Exception as e:
        raise RuntimeError(f"Anthropic API request failed: {e}")

    usage = payload.get("usage") or {}
    in_tok  = int(usage.get("input_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or 0)
    cost = estimate_call_cost(model, in_tok, out_tok)
    _SPEND_USAGE["input_tokens"]  += in_tok
    _SPEND_USAGE["output_tokens"] += out_tok
    _SPEND_USAGE["calls"]         += 1
    _SPEND_USAGE["estimated_usd"] += cost
    sys.stderr.write(
        f"[anthropic] {model} · in={in_tok} out={out_tok} "
        f"call_cost=${cost:.4f} session_total=${_SPEND_USAGE['estimated_usd']:.4f} "
        f"(cap=${SESSION_SPEND_CAP_USD:.2f})\n"
    )
    return payload


def anthropic_extract_text(payload: dict) -> str:
    """Pull the assistant's text from a Messages API response."""
    parts = payload.get("content") or []
    out = []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == "text":
            out.append(p.get("text") or "")
    return "".join(out).strip()

# Nominatim usage policy requires identifying the application. Be polite.
# Keep ASCII-only — HTTP header values default to latin-1, so the em dash
# I had here originally would crash urlopen() with an encoding error.
USER_AGENT = "OmniProfileLocalServer/0.1 (local dev - Personal Intelligence System vault)"

# Local IANA timezone lookup by lat/lon — used by the geocoder to fill in the
# timezone field automatically, and by add-entity as a fallback when the client
# didn't supply a tz but did supply coordinates.
try:
    from timezonefinder import TimezoneFinder  # type: ignore
    _TZ_FINDER = TimezoneFinder()
except ImportError:
    _TZ_FINDER = None  # geocoder will skip the tz field; add-entity will require manual tz


def tz_from_coords(lat: float | None, lon: float | None) -> str | None:
    """Resolve an IANA timezone from coordinates. Returns None on any failure
    (missing input, edge cases like polar regions, library not installed)."""
    if _TZ_FINDER is None or lat is None or lon is None:
        return None
    try:
        return _TZ_FINDER.timezone_at(lat=lat, lng=lon)
    except Exception:
        return None

# Strict allowlist for entity names so a malicious payload can't traverse paths.
# Letters, digits, spaces, apostrophes, hyphens, periods. Reject everything else.
NAME_SAFE_RE = re.compile(r"^[A-Za-z0-9 .'-]{1,80}$")


def sanitize_name(name: str) -> str | None:
    name = (name or "").strip()
    if not NAME_SAFE_RE.match(name):
        return None
    # Collapse internal whitespace
    return re.sub(r"\s+", " ", name)


def derive_precision(time: str | None, lat: float | None, lon: float | None) -> int:
    if time and lat is not None and lon is not None:
        return 1
    if lat is not None and lon is not None:
        return 2
    return 3


def build_canon_markdown(payload: dict, precision: int) -> str:
    """Render the new entity's canon .md file."""
    name = payload["name"]
    today = _date.today().isoformat()
    lines = ["---"]
    lines.append("type: person")
    pronouns = (payload.get("pronouns") or "they/them").strip()
    lines.append(f"pronouns: {pronouns}")
    lines.append("status: working")
    lines.append(f"domain: {payload.get('domain') or 'Shared'}")
    lines.append(f"last_updated: {today}")
    if payload.get("relationship"):
        # Free-form; user-provided. Keep as a single line.
        rel = payload["relationship"].replace("\n", " ").strip()
        lines.append(f"relationship_to_n8: {rel}")
    lines.append("birth:")
    lines.append(f"  date: {payload['date']}")
    if payload.get("time"):
        lines.append(f"  time: '{payload['time']}'")
    if payload.get("tz"):
        lines.append(f"  tz: {payload['tz']}")
    if payload.get("place"):
        lines.append(f"  place: {payload['place']}")
    if payload.get("lat") is not None:
        lines.append(f"  lat: {payload['lat']}")
    if payload.get("lon") is not None:
        lines.append(f"  lon: {payload['lon']}")
    lines.append(f"  precision: {precision}")
    lines.append(f"  source: Entered via local add-entity form on {today}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")
    lines.append(
        "Canon page created via the local add-entity form. Replace this body "
        "with biographical content as you collect material. Profile data is "
        "computed automatically — see the sibling `.profile.yaml`."
    )
    lines.append("")
    return "\n".join(lines)


def run_engine_on_file(canon_path: Path) -> tuple[bool, str]:
    """Run `compute.py --path <rel> --write` to compute chart + write sibling."""
    rel = canon_path.relative_to(VAULT_ROOT).as_posix()
    cmd = [sys.executable, str(ENGINE_COMPUTE), "--path", rel, "--write"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "engine exited non-zero").strip()
    return True, proc.stdout.strip()


def run_viewer_build() -> tuple[bool, str]:
    cmd = [sys.executable, str(VIEWER_BUILD)]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "viewer build exited non-zero").strip()
    # build.py prints a lot; just confirm it completed
    return True, "viewer built"


def geocode_lookup(query: str) -> dict | None:
    """Hit Nominatim. Returns the top match (with IANA timezone derived from
    its coordinates) as a dict, or None on no-match. {'_error': msg} on failure."""
    if not query.strip():
        return None
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": f"geocoder failed: {e}"}
    if not data:
        return None
    hit = data[0]
    try:
        lat = float(hit["lat"])
        lon = float(hit["lon"])
        return {
            "display_name": hit.get("display_name"),
            "lat": lat,
            "lon": lon,
            "tz": tz_from_coords(lat, lon),   # IANA tz, or None if outside coverage
            "type": hit.get("type"),
        }
    except (KeyError, ValueError):
        return None


# ============================================================================
# Reply length controls — terse / standard / deep
# ============================================================================
#
# Appended to the system prompt to nudge reply length. Standard matches the
# current default ("2-4 short paragraphs typical"); terse compresses; deep
# expands toward the texture of the authored readings.

LENGTH_INSTRUCTIONS = {
    "terse":    (
        "LENGTH: Be terse. 1-3 sentences max. One vivid detail, no extra "
        "framing. No multi-paragraph answers."
    ),
    "standard": (
        "LENGTH: 2-4 short paragraphs typical. Specific but contained."
    ),
    "deep":     (
        "LENGTH: Go deeper. 4-6 paragraphs, the texture of an authored "
        "reading — declarative, layered, weaving multiple chart placements "
        "together. Quote real values; show the connections between gates / "
        "channels / aspects / day-sign that the question pulls on. Treat "
        "each reply as a small written piece, not a quick answer."
    ),
}


# ============================================================================
# Chat personas — quick re-framing lenses the user can toggle in the chat UI
# ============================================================================
#
# Each persona is an addendum to the base system prompt. The "general" persona
# adds nothing. The other three nudge the assistant's interpretive frame
# without changing the underlying chart data or voice register.

# A header injected before each non-general persona frame so the model
# treats lens-switches as a feature, not as a repeat of an earlier question.
_PERSONA_OVERRIDE_HEADER = (
    "YOU MUST APPLY THIS FRAMING to every reply in this conversation. "
    "Even if the user has asked a similar or identical question earlier in "
    "this conversation (perhaps under a different framing), RE-ANSWER through "
    "this framing fully and freshly. Do NOT say things like 'I already "
    "covered this' or 'the chart is still the same' — each framing produces "
    "a distinct reading and that's the whole design. Each lens deserves its "
    "own complete answer, even if the underlying chart data is identical.\n\n"
)

PERSONA_FRAMES = {
    "general": "",  # default — no extra framing
    "hero_journey": (
        _PERSONA_OVERRIDE_HEADER +
        "FRAMING — HERO'S JOURNEY:\n"
        "Read this chart through Joseph Campbell's monomyth. The chart is a "
        "soul's hero arc: Call to Adventure, Refusal, Threshold Crossing, "
        "Tests / Allies / Enemies, the Abyss, Transformation, the Ultimate "
        "Boon, the Return with the Elixir. Every placement is a stage or a "
        "tool on that arc.\n"
        "  - The Sun is the conscious quest.\n"
        "  - The Moon is what's brought from the ordinary world / the "
        "inherited home.\n"
        "  - Houses are the world-stages of the journey.\n"
        "  - The HD profile is the archetype the hero embodies.\n"
        "  - The HD incarnation cross is the soul's pattern across the arc.\n"
        "  - The Mayan day-sign is the seed-instruction the journey serves.\n"
        "  - The Chinese animal is the inner companion / shadow on the road.\n"
        "When the user asks about an element, locate it on the hero arc, "
        "name the stage, and show how it advances or stalls the journey. "
        "Use the language of myth and trial, but stay grounded in the actual "
        "chart values."
    ),
    "relationship": (
        _PERSONA_OVERRIDE_HEADER +
        "FRAMING — RELATIONSHIP / INTERPERSONAL:\n"
        "Read this chart through the lens of how this person joins, attaches, "
        "attracts, conflicts, repairs, and leaves. Every chart element gets "
        "read for its implication on connection.\n"
        "  - The 7th house is partnership; the 5th is courtship / play; "
        "the 8th is shared depth and resources.\n"
        "  - The Moon is emotional inheritance brought to relating.\n"
        "  - Defined HD centers are what consistently radiates onto others; "
        "undefined centers are what gets absorbed from them.\n"
        "  - HD channels formed BETWEEN people are electromagnetic; gates "
        "without partners (hanging gates) are doorways looking for someone "
        "to complete them.\n"
        "  - The Mayan day-sign is the relational gift offered.\n"
        "  - The Chinese inner animal is the private temperament a close "
        "partner eventually sees.\n"
        "When the user asks about an element, surface its relational "
        "implication — what this means for how this person loves, fights, "
        "trusts, withdraws, returns."
    ),
    "creative_practice": (
        _PERSONA_OVERRIDE_HEADER +
        "FRAMING — CREATIVE PRACTICE:\n"
        "Read this chart through the lens of artistic and creative work. "
        "Every chart element gets read for what it says about how this "
        "person makes things, what materials they work in, what their "
        "creative rhythm looks like, what blocks them, and what their voice "
        "is.\n"
        "  - The 5th house is play, performance, what brings joy in making.\n"
        "  - The Sun is the conscious creative impulse; the Moon is the "
        "emotional source the work draws from; Venus is taste and what's "
        "found beautiful; Mars is creative drive and how/when it pushes.\n"
        "  - The dominant element points to native medium (fire = "
        "performance, motion; earth = building, material; air = ideas, "
        "language; water = depth, music, image).\n"
        "  - The HD type sets the creative work-rhythm — Generators sustain "
        "long flow, Manifestors initiate then withdraw, Projectors guide + "
        "see, Reflectors mirror, Manifesting Generators do many things at "
        "once.\n"
        "  - The HD throat tells whether the work demands speaking or "
        "showing, and whether to wait or initiate.\n"
        "  - The Mayan day-sign is the creative gift; the Chinese inner "
        "animal is the private artistic temperament that emerges in flow.\n"
        "When the user asks about an element, surface its implication for "
        "creative practice — what to make, when to make, what to wait for, "
        "what to abandon, what voice this chart wants to speak in."
    ),
    "business": (
        _PERSONA_OVERRIDE_HEADER +
        "FRAMING — BUSINESS / WORK / ENTERPRISE:\n"
        "Read this chart through the lens of work, career, leadership, and "
        "money. Every chart element gets read for its implication on "
        "decision-making, sustainable energy, and the right kind of "
        "professional life.\n"
        "  - HD Strategy + Authority is the decision rule — answer "
        "professional questions through that frame first.\n"
        "  - The 10th house is public reputation / vocation; the 2nd is "
        "resource patterns and money flow; the 6th is daily work and "
        "service.\n"
        "  - The dominant element is the kind of value this person creates "
        "(fire = vision, earth = build, air = ideas, water = depth).\n"
        "  - Defined Throat = ready to be the voice; undefined Throat = "
        "shouldn't initiate without invitation.\n"
        "  - The Mayan day-sign is the gift this person can offer (and sell); "
        "the Chinese animal is leadership archetype.\n"
        "When the user asks about an element, surface its entrepreneurial / "
        "professional implication, with concrete actionable guidance for "
        "how to use it at work or in business."
    ),
}


def read_pronouns_from_canon(canon_path: Path) -> str | None:
    """Pull the `pronouns:` line out of the canon page's frontmatter, if set.
    Returns the value as a string (e.g. 'he/him') or None if absent."""
    try:
        text = canon_path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return None
    m = re.search(r"^pronouns:\s*(\S.*?)\s*$", fm_match.group(1), re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("'\"")


def find_entity_files(name: str) -> tuple[Path, Path, Path, Path] | None:
    """Locate canon .md + .profile.yaml + .profile.reading.md + .profile.system_readings.md
    for the named entity. Searches Personal/ then Shared/People/. Returns paths
    (some of which may not exist yet) or None if the canon .md is missing."""
    for folder in (PERSONAL_DIR, PEOPLE_DIR):
        canon = folder / f"{name}.md"
        if canon.exists():
            return (
                canon,
                folder / f"{name}.profile.yaml",
                folder / f"{name}.profile.reading.md",
                folder / f"{name}.profile.system_readings.md",
            )
    return None


# ============================================================================
# Reading authoring prompts
# ============================================================================

def system_prompt_for_system_readings() -> str:
    """The role + voice + AUTHORING RULE for the 4 per-chart readings."""
    return (
        "You are an expert chart reader trained in Western astrology, "
        "Human Design, the Mayan Tzolk'in calendar, and Chinese astrology.\n"
        "\n"
        "Voice: warm-grounded, declarative, dense, layered. Sentences are "
        "statements (not questions, not exhortations, not second-person life "
        "advice). Pull SPECIFIC values from the chart data (degrees, signs, "
        "houses, gates, channels, tones, animals). Roughly 250-400 words per "
        "section.\n"
        "\n"
        "CRITICAL AUTHORING RULE — each section must stay STRICTLY within "
        "its system. No cross-system labels:\n"
        "  - Western section: Sun / Moon / Rising / planets / houses / "
        "aspects / elements / modalities only.\n"
        "  - Human Design section: Type / Strategy / Authority / Profile / "
        "Definition / Centers / Channels / Gates / Cross only.\n"
        "  - Mayan section: day-sign (Q'anil/Lamat etc.) / tone / trecena / "
        "Long Count / bak'tun only.\n"
        "  - Chinese section: year pillar (animal + element + polarity) / "
        "Inner Animal / Secret Animal / Triple Animals only.\n"
        "\n"
        "Forbidden cross-system tokens:\n"
        "  - No 'Yang Fire Dragon' in Mayan.\n"
        "  - No 'Projector' / 'Generator' / center names in Western.\n"
        "  - No 'Cancer Sun' / planet names in Chinese.\n"
        "  - No Mayan day-signs in HD.\n"
        "Cross-system synthesis is a separate file (.profile.reading.md), "
        "not these per-chart sections.\n"
        "\n"
        "Precision handling — check the entity's birth.precision in the YAML:\n"
        "  - precision 1: write all four sections at full depth.\n"
        "  - precision 2 (no time): in the HD section, write briefly: "
        "'Human Design requires birth time — without it, no Type / Authority "
        "/ Profile can be computed for this chart.' Western at precision 2 "
        "lacks houses + Rising; write about Sun, Moon, planets, aspects, "
        "element balance only.\n"
        "  - precision 3 (date only): same as precision 2 plus no "
        "place-dependent calculations.\n"
        "\n"
        "Output: a complete markdown file. Start with the frontmatter exactly "
        "as shown in the reference, then four H2 sections. Do not add any "
        "explanatory text outside the markdown."
    )


def system_prompt_for_thematic_reading() -> str:
    """The role + voice for the cross-system thematic synthesis."""
    return (
        "You are an expert chart reader trained in Western astrology, Human "
        "Design, the Mayan Tzolk'in calendar, and Chinese astrology.\n"
        "\n"
        "Voice: warm-grounded, declarative, dense, layered. The same register "
        "as the per-chart readings, but this file is the OPPOSITE structural "
        "move — instead of one section per system, you weave all four systems "
        "together by theme.\n"
        "\n"
        "Standard themes (use these exact H2 headings, in this order):\n"
        "  ## Threshold — the opening 'who they are' framing, often a single "
        "line that telescopes all four systems together\n"
        "  ## Mind & Self\n"
        "  ## Emotional Field\n"
        "  ## Drive & Direction\n"
        "  ## Lineage & Inheritance\n"
        "  ## Where it goes\n"
        "\n"
        "Each section weaves Western placements + HD architecture + Mayan "
        "day-sign + Chinese animal where naturally relevant. Pull specific "
        "chart values. Roughly 150-250 words per section.\n"
        "\n"
        "Output: a complete markdown file. Frontmatter (type: profile_reading, "
        "entity: <name>, voice: warm-grounded, etc.), then the six H2 "
        "sections. Do not add any explanatory text outside the markdown."
    )


def author_system_readings(name: str, yaml_text: str) -> str:
    """Call the Anthropic API to write the 4 per-chart readings. Returns the
    full markdown file content."""
    reference = REFERENCE_READING.read_text(encoding="utf-8") if REFERENCE_READING.exists() else ""
    user_msg = (
        f"Author a complete .profile.system_readings.md file for the entity "
        f"named '{name}'.\n\n"
        f"Here is their computed chart data (YAML — read all of it for "
        f"specifics):\n\n"
        f"```yaml\n{yaml_text}\n```\n\n"
        f"For reference, here is N8's file — match this structure exactly, "
        f"including the frontmatter shape and the AUTHORING RULE comment "
        f"verbatim:\n\n"
        f"```markdown\n{reference}\n```\n\n"
        f"Return ONLY the new markdown file content. Start with `---` "
        f"(frontmatter). Update the `entity:` field to '{name}'. Update "
        f"`generated_at:` to the current ISO 8601 timestamp."
    )
    payload = anthropic_messages_call(
        model=MODEL_AUTHORING,
        system=system_prompt_for_system_readings(),
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=MAX_TOKENS_AUTHORING,
    )
    return anthropic_extract_text(payload)


def system_prompt_for_chat(name: str, yaml_text: str,
                            system_readings_text: str | None,
                            thematic_reading_text: str | None,
                            pronouns: str | None = None) -> str:
    """Build the system prompt for chatting about a specific entity's chart.
    The chart data + any existing readings are baked in so the assistant
    grounds every answer in this specific person, not generic astrology.

    The `pronouns` arg is read but intentionally NOT inserted as a pronoun
    instruction — readings flow better when you refer to the person by name
    or by 'the chart' instead of he/she/they. Kept in the signature for
    future use and so the canon-page field still has a server-side reader.
    """
    parts = [
        f"You are an expert chart reader who knows {name}'s Omni-Profile chart "
        f"intimately. You read in a warm-grounded voice: declarative, dense, "
        f"layered, grounded in {name}'s specific chart data.",
        "",
        f"The person chatting with you may not be {name} themselves — they "
        f"could be a friend, family member, or collaborator asking about "
        f"{name}'s chart. Speak about {name} by NAME — call them \"{name}\" "
        f"or refer to \"the chart\" / \"this chart\". Do NOT use pronouns "
        f"(he / she / they / his / her / their / them). Names are unambiguous "
        f"and read more deliberate than pronouns in chart writing.",
        "",
        "Rules:",
        f"- Stay grounded in {name}'s actual chart values. Never give generic "
        "astrology / HD / Mayan / Chinese answers. If the user asks something "
        "the chart doesn't address, say so plainly — don't invent.",
        "- When asked about a specific system, use only that system's "
        "vocabulary (no 'Yang Fire Dragon' in a Mayan answer, no 'Projector' "
        "in a Western answer) — unless the user explicitly asks for "
        "cross-system synthesis.",
        "- Be concise but specific. 2-4 short paragraphs typical. Quote real "
        "values (degrees, signs, houses, gates, channels, tones, animals).",
        "- Your replies are rendered as markdown in the browser. Use `**bold**` "
        "and `*italics*` sparingly for emphasis; don't use headings inside "
        "replies (the chat bubbles already provide structure).",
        "",
        "================================================================",
        f"{name}'s computed chart (raw YAML — every placement, every gate, "
        f"every aspect):",
        "================================================================",
        "",
        yaml_text.strip(),
    ]
    if system_readings_text:
        parts.extend([
            "",
            "================================================================",
            f"{name}'s authored per-chart readings (use as the established "
            f"voice + interpretive ground when answering):",
            "================================================================",
            "",
            system_readings_text.strip(),
        ])
    if thematic_reading_text:
        parts.extend([
            "",
            "================================================================",
            f"{name}'s cross-system thematic synthesis (use as overall "
            f"framing):",
            "================================================================",
            "",
            thematic_reading_text.strip(),
        ])
    return "\n".join(parts)


def load_entity_dict(name: str) -> dict | None:
    """Load a single entity's full dict (chart + essentials + readings) using
    the viewer's data module. Returns None if not found."""
    from data import load_entities  # local import — heavy module
    entities = load_entities(VAULT_ROOT)
    for e in entities:
        if e.get("name") == name:
            return e
    return None


def format_synastry_for_prompt(name_a: str, name_b: str, summary: dict) -> str:
    """Render the synastry_summary dict as readable prose the LLM can use.
    Lists each system's top events with their weights + labels."""
    lines = []
    lines.append(f"Synastry between {name_a} and {name_b}:")
    lines.append(f"  Total harmony score: +{summary.get('total_harmony', 0)}")
    lines.append(f"  Total friction score: -{summary.get('total_friction', 0)}")
    lines.append(f"  Net: {summary.get('net', 0)}")
    lines.append(f"  Total surfaced events: {summary.get('total_events', 0)}")
    lines.append("")
    systems = summary.get("systems") or {}
    sys_labels = {
        "western":      "Western (cross-aspects between charts)",
        "hd":           "Human Design (electromagnetics, companion channels, open/defined pressure)",
        "chinese":      "Chinese (animal harmony / conflict, element generating / destroying)",
        "mayan":        "Mayan (day-sign + tone resonance)",
        "psychometric": "Psychometric / Tags",
    }
    for key, label in sys_labels.items():
        sys = systems.get(key) or {}
        events = sys.get("events_sorted") or sys.get("events") or []
        if not events:
            continue
        lines.append(f"{label}:")
        lines.append(f"  harmony +{sys.get('harmony', 0)} · friction -{sys.get('friction', 0)} · {len(events)} events")
        for ev in events[:8]:  # top 8 per system to keep prompt size sane
            weight = ev.get("weight", 0)
            sign = "+" if weight > 0 else ("" if weight == 0 else "")
            label_ev = ev.get("label", "")
            detail = ev.get("detail", "")
            line = f"  {sign}{weight:+.2f}  {label_ev}"
            if detail:
                line += f"  ({detail})"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)


def system_prompt_for_pair_chat(entity_a: dict, entity_b: dict, synastry: dict,
                                  pronouns_a: str | None = None,
                                  pronouns_b: str | None = None) -> str:
    """Build the system prompt for chatting about TWO entities — both charts,
    their readings (when present), and the pre-computed synastry data."""
    name_a = entity_a["name"]
    name_b = entity_b["name"]
    pronouns_a = pronouns_a or "they/them (no pronouns set; mirror the user if they use specifics)"
    pronouns_b = pronouns_b or "they/them (no pronouns set; mirror the user if they use specifics)"

    def load_text(path_str: str) -> str | None:
        if not path_str:
            return None
        p = VAULT_ROOT / path_str
        return p.read_text(encoding="utf-8") if p.exists() else None

    # Load the .profile.yaml for each entity (raw chart data)
    yaml_a = (Path(VAULT_ROOT) / entity_a["canon_path"]).with_suffix("")
    yaml_a = yaml_a.parent / (yaml_a.name + ".profile.yaml")
    yaml_b = (Path(VAULT_ROOT) / entity_b["canon_path"]).with_suffix("")
    yaml_b = yaml_b.parent / (yaml_b.name + ".profile.yaml")
    yaml_a_text = yaml_a.read_text(encoding="utf-8") if yaml_a.exists() else ""
    yaml_b_text = yaml_b.read_text(encoding="utf-8") if yaml_b.exists() else ""

    # Optional: readings for each entity (give the assistant the voice + ground)
    def readings_for(canon_path_str: str) -> tuple[str | None, str | None]:
        canon = VAULT_ROOT / canon_path_str
        sys_r = canon.parent / (canon.stem + ".profile.system_readings.md")
        the_r = canon.parent / (canon.stem + ".profile.reading.md")
        return (
            sys_r.read_text(encoding="utf-8") if sys_r.exists() else None,
            the_r.read_text(encoding="utf-8") if the_r.exists() else None,
        )
    sys_a, the_a = readings_for(entity_a["canon_path"])
    sys_b, the_b = readings_for(entity_b["canon_path"])

    synastry_text = format_synastry_for_prompt(name_a, name_b, synastry)

    parts = [
        f"You are an expert chart reader who knows BOTH {name_a} and {name_b}'s "
        f"Omni-Profile charts intimately, AND the relational dynamics between "
        f"them. You read in a warm-grounded voice: declarative, dense, layered, "
        f"grounded in their actual chart values and the pre-computed synastry "
        f"data below.",
        "",
        f"The person chatting with you may be {name_a}, {name_b}, both, or "
        f"someone else asking about the pair. Speak about them in third person "
        f"by default unless the user explicitly says which one they are.",
        "",
        f"Refer to both people by NAME — \"{name_a}\" and \"{name_b}\". Do "
        f"NOT use pronouns (he/she/they/his/her/their/them). Use names + "
        f"phrases like \"{name_a}'s chart\", \"the connection between them\", "
        f"\"this pair\". Names are unambiguous, especially with two people "
        f"in play at once.",
        "",
        "Rules:",
        "- The conversation is about the relationship / dynamic between the "
        "two charts. Anchor your answers in the synastry events listed below.",
        "- When the user asks about a single person's placement, you can "
        "answer about just that person — but proactively connect it to how "
        "the other chart relates when relevant.",
        "- Use only a single system's vocabulary when the user asks about "
        "that system (no 'Yang Fire Dragon' in a Mayan answer, etc.) — unless "
        "they explicitly ask for cross-system synthesis.",
        "- Be specific. Quote real values from the YAML (degrees, signs, gates, "
        "channels, tones, animals). Quote real synastry events with their weight.",
        "- 2-4 short paragraphs typical. Markdown for `**bold**` and `*italic*` "
        "is fine; no headings inside replies.",
        "",
        "================================================================",
        f"{name_a}'s computed chart:",
        "================================================================",
        "",
        yaml_a_text.strip(),
    ]
    if sys_a:
        parts.extend([
            "",
            "================================================================",
            f"{name_a}'s authored per-chart readings:",
            "================================================================",
            "",
            sys_a.strip(),
        ])
    if the_a:
        parts.extend([
            "",
            "================================================================",
            f"{name_a}'s cross-system thematic synthesis:",
            "================================================================",
            "",
            the_a.strip(),
        ])
    parts.extend([
        "",
        "================================================================",
        f"{name_b}'s computed chart:",
        "================================================================",
        "",
        yaml_b_text.strip(),
    ])
    if sys_b:
        parts.extend([
            "",
            "================================================================",
            f"{name_b}'s authored per-chart readings:",
            "================================================================",
            "",
            sys_b.strip(),
        ])
    if the_b:
        parts.extend([
            "",
            "================================================================",
            f"{name_b}'s cross-system thematic synthesis:",
            "================================================================",
            "",
            the_b.strip(),
        ])
    parts.extend([
        "",
        "================================================================",
        f"PRE-COMPUTED SYNASTRY between {name_a} and {name_b}:",
        "================================================================",
        "",
        synastry_text,
    ])
    return "\n".join(parts)


def author_thematic_reading(name: str, yaml_text: str, system_readings_text: str) -> str:
    """Call the Anthropic API to write the cross-system thematic reading.
    Receives the just-authored system_readings as additional context so the
    thematic narrative is consistent with the per-chart prose."""
    # Try to use N8's existing thematic reading as a voice reference.
    n8_thematic = PERSONAL_DIR / "N8.profile.reading.md"
    reference = n8_thematic.read_text(encoding="utf-8") if n8_thematic.exists() else ""
    user_msg = (
        f"Author a complete .profile.reading.md file (cross-system thematic "
        f"synthesis) for the entity named '{name}'.\n\n"
        f"Chart data (YAML):\n\n```yaml\n{yaml_text}\n```\n\n"
        f"The per-chart readings I just authored for this entity (use as the "
        f"voice + interpretive ground; the thematic file should layer above "
        f"them, weaving the systems together):\n\n"
        f"```markdown\n{system_readings_text}\n```\n\n"
        f"For voice reference, here is N8's thematic reading — match its "
        f"register, frontmatter shape, and theme-by-theme structure:\n\n"
        f"```markdown\n{reference}\n```\n\n"
        f"Return ONLY the new markdown file content. Start with `---` "
        f"(frontmatter). Update `entity:` to '{name}' and `generated_at:` to "
        f"the current ISO 8601 timestamp."
    )
    payload = anthropic_messages_call(
        model=MODEL_AUTHORING,
        system=system_prompt_for_thematic_reading(),
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=MAX_TOKENS_AUTHORING,
    )
    return anthropic_extract_text(payload)


class Handler(SimpleHTTPRequestHandler):
    """Static-file handler with two POST endpoints layered on top."""

    # Suppress noisy default logging; keep only POSTs and errors.
    # `args[0]` is normally the HTTP request line (string), but on error paths
    # it can be an HTTPStatus enum (no startswith) — guard for both.
    def log_message(self, format, *args):  # noqa: A002
        first = str(args[0]) if args else ""
        if first.startswith("POST"):
            sys.stderr.write("[serve] %s - %s\n" % (self.address_string(), format % args))

    # Serve from <repo>/site/ regardless of cwd.
    def translate_path(self, path):
        # Path is /-rooted. Map to SITE_DIR.
        # Use SimpleHTTPRequestHandler's logic but rebased to SITE_DIR.
        path = path.split("?", 1)[0].split("#", 1)[0]
        # Decode + normalize
        path = urllib.parse.unquote(path)
        parts = [p for p in path.split("/") if p and p != ".."]
        return str(SITE_DIR.joinpath(*parts))

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 100_000:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # Same-origin only — but be permissive for dev (the form is served from
        # this same origin, so this is harmless and avoids surprise CORS issues).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802 — http.server naming convention
        if self.path == "/api/geocode":
            self.handle_geocode()
        elif self.path == "/api/add-entity":
            self.handle_add_entity()
        elif self.path == "/api/author-readings":
            self.handle_author_readings()
        elif self.path == "/api/chat":
            self.handle_chat()
        else:
            self._send_json(404, {"ok": False, "error": f"no endpoint at {self.path}"})

    def do_GET(self):  # noqa: N802
        if self.path == "/api/spend":
            self._send_json(200, {
                "ok": True,
                "usage": dict(_SPEND_USAGE),
                "cap_usd": SESSION_SPEND_CAP_USD,
                "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            })
            return
        super().do_GET()

    # --- /api/geocode -------------------------------------------------------
    def handle_geocode(self):
        body = self._read_json()
        if not body or not isinstance(body.get("query"), str):
            self._send_json(400, {"ok": False, "error": "JSON body must have a 'query' string."})
            return
        result = geocode_lookup(body["query"])
        if result is None:
            self._send_json(200, {"ok": True, "found": False})
            return
        if "_error" in result:
            self._send_json(502, {"ok": False, "error": result["_error"]})
            return
        self._send_json(200, {"ok": True, "found": True, "result": result})

    # --- /api/add-entity ----------------------------------------------------
    def handle_add_entity(self):
        body = self._read_json()
        if not body:
            self._send_json(400, {"ok": False, "error": "Invalid or missing JSON body."})
            return

        name = sanitize_name(body.get("name") or "")
        if not name:
            self._send_json(400, {"ok": False, "error":
                "Name is required. Allowed: letters, digits, spaces, apostrophes, hyphens, periods."})
            return

        # Date is required and must match YYYY-MM-DD.
        date_str = (body.get("date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            self._send_json(400, {"ok": False, "error":
                "Birth date is required and must be YYYY-MM-DD."})
            return

        # Optional fields
        time_str = (body.get("time") or "").strip() or None
        if time_str and not re.match(r"^\d{2}:\d{2}$", time_str):
            self._send_json(400, {"ok": False, "error":
                "Birth time must be HH:MM (24h) if provided."})
            return
        place = (body.get("place") or "").strip() or None
        tz = (body.get("tz") or "").strip() or None

        try:
            lat = float(body["lat"]) if body.get("lat") not in (None, "") else None
            lon = float(body["lon"]) if body.get("lon") not in (None, "") else None
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error":
                "Latitude and longitude must be numbers if provided."})
            return

        precision = derive_precision(time_str, lat, lon)
        # If no timezone was supplied but we have coordinates, derive one from
        # them. Keeps the form one field lighter when the user already geocoded.
        if not tz and lat is not None and lon is not None:
            tz = tz_from_coords(lat, lon)
        if precision == 1 and not tz:
            self._send_json(400, {"ok": False, "error":
                "Could not determine the timezone for this location. Please enter it manually (IANA format, e.g. America/Los_Angeles)."})
            return

        canon_path = PEOPLE_DIR / f"{name}.md"
        if canon_path.exists():
            self._send_json(409, {"ok": False, "error":
                f"A canon page already exists for '{name}' at {canon_path.relative_to(VAULT_ROOT)}."})
            return

        # Compose canonical payload for markdown generation
        payload = {
            "name": name,
            "date": date_str,
            "time": time_str,
            "place": place,
            "tz": tz,
            "lat": lat,
            "lon": lon,
            "pronouns": (body.get("pronouns") or "").strip() or None,
            "domain": (body.get("domain") or "").strip() or "Shared",
            "relationship": (body.get("relationship") or "").strip() or None,
        }

        # Write the canon page
        try:
            PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
            canon_path.write_text(build_canon_markdown(payload, precision), encoding="utf-8")
        except OSError as e:
            self._send_json(500, {"ok": False, "error": f"Failed to write canon page: {e}"})
            return

        # Run the engine on this file. If the engine fails, leave the canon page
        # in place (so the user can edit and re-run manually) but report the
        # error.
        ok, msg = run_engine_on_file(canon_path)
        if not ok:
            self._send_json(500, {
                "ok": False,
                "error": f"Engine failed for {name}. The canon page was written, but no chart was computed.\n\n{msg}",
                "canon_path": str(canon_path.relative_to(REPO_ROOT)),
            })
            return

        # Run the viewer build so the new entity appears on next reload.
        ok, msg = run_viewer_build()
        if not ok:
            self._send_json(500, {
                "ok": False,
                "error": f"Engine succeeded but viewer build failed.\n\n{msg}",
            })
            return

        # Optional: auto-author readings inline. Default ON so newly-added
        # entities arrive fully fleshed out (chart + 4 system readings + 1
        # thematic synthesis). Costs ~$0.05-0.10 and adds 60-120s.
        # Pass auto_readings=false in the body to opt out.
        auto_readings_flag = body.get("auto_readings")
        auto_readings = True if auto_readings_flag is None else bool(auto_readings_flag)
        yaml_path_local = canon_path.parent / f"{name}.profile.yaml"
        readings_status = None
        if auto_readings and yaml_path_local.exists():
            try:
                yaml_text = yaml_path_local.read_text(encoding="utf-8")
                sys_text = author_system_readings(name, yaml_text)
                system_readings_path = canon_path.parent / f"{name}.profile.system_readings.md"
                system_readings_path.write_text(sys_text, encoding="utf-8")

                thematic_text = author_thematic_reading(name, yaml_text, sys_text)
                reading_path_local = canon_path.parent / f"{name}.profile.reading.md"
                reading_path_local.write_text(thematic_text, encoding="utf-8")

                # Rebuild again so the readings appear in the rendered page
                ok2, msg2 = run_viewer_build()
                if not ok2:
                    readings_status = f"authored but rebuild failed: {msg2}"
                else:
                    readings_status = "authored"
            except RuntimeError as e:
                readings_status = f"failed: {e}"
            except OSError as e:
                readings_status = f"failed (file io): {e}"

        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")

        # Include the post-engine file contents in the response so the browser
        # can build a download link without needing a separate endpoint. The
        # .md now contains the computed `profile:` essentials in frontmatter;
        # the .yaml has the full chart (every house cusp, every aspect, every
        # gate activation).
        canon_md_content = None
        yaml_content = None
        try:
            canon_md_content = canon_path.read_text(encoding="utf-8")
            yaml_path = canon_path.parent / f"{name}.profile.yaml"
            if yaml_path.exists():
                yaml_content = yaml_path.read_text(encoding="utf-8")
        except OSError:
            pass  # download just won't appear in the response — submission still succeeded

        self._send_json(200, {
            "ok": True,
            "name": name,
            "slug": slug,
            "precision": precision,
            "canon_path": str(canon_path.relative_to(REPO_ROOT)),
            "person_url": f"people/{slug}.html",
            "canon_md": canon_md_content,
            "profile_yaml": yaml_content,
            "readings_status": readings_status,
            "session_spend_usd": round(_SPEND_USAGE["estimated_usd"], 4),
            "session_spend_cap_usd": SESSION_SPEND_CAP_USD,
        })

    # --- /api/author-readings -----------------------------------------------
    def handle_author_readings(self):
        body = self._read_json()
        if not body:
            self._send_json(400, {"ok": False, "error": "Invalid or missing JSON body."})
            return
        name = sanitize_name(body.get("name") or "")
        if not name:
            self._send_json(400, {"ok": False, "error":
                "Name is required (must match an existing canon page)."})
            return

        files = find_entity_files(name)
        if not files:
            self._send_json(404, {"ok": False, "error":
                f"No canon page found for '{name}' in either Personal/ or Shared/People/."})
            return
        canon_path, yaml_path, reading_path, system_readings_path = files
        if not yaml_path.exists():
            self._send_json(409, {"ok": False, "error":
                f"'{name}' has no computed profile yet. Run the engine first."})
            return

        # Default behavior: only generate readings that don't exist.
        # Pass `?overwrite=1` (or {"overwrite": true} in body) to regenerate.
        overwrite = bool(body.get("overwrite"))
        will_write_system    = overwrite or not system_readings_path.exists()
        will_write_thematic  = overwrite or not reading_path.exists()
        if not (will_write_system or will_write_thematic):
            self._send_json(200, {
                "ok": True,
                "skipped": True,
                "message": "Both reading files already exist. Pass overwrite=true to regenerate.",
            })
            return

        try:
            yaml_text = yaml_path.read_text(encoding="utf-8")
        except OSError as e:
            self._send_json(500, {"ok": False, "error": f"Could not read profile.yaml: {e}"})
            return

        try:
            sys_text = None
            if will_write_system:
                sys_text = author_system_readings(name, yaml_text)
                system_readings_path.write_text(sys_text, encoding="utf-8")
            elif will_write_thematic:
                # Thematic step needs the system readings as context — read them.
                sys_text = system_readings_path.read_text(encoding="utf-8") if system_readings_path.exists() else ""

            thematic_text = None
            if will_write_thematic:
                thematic_text = author_thematic_reading(name, yaml_text, sys_text or "")
                reading_path.write_text(thematic_text, encoding="utf-8")
        except RuntimeError as e:
            self._send_json(502, {"ok": False, "error": str(e)})
            return
        except OSError as e:
            self._send_json(500, {"ok": False, "error": f"Failed to write reading file: {e}"})
            return

        # Rebuild so the new readings appear in the rendered site.
        ok, msg = run_viewer_build()
        if not ok:
            self._send_json(500, {"ok": False, "error":
                f"Readings written but viewer build failed: {msg}"})
            return

        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
        self._send_json(200, {
            "ok": True,
            "name": name,
            "slug": slug,
            "person_url": f"people/{slug}.html",
            "wrote_system_readings": bool(will_write_system),
            "wrote_thematic_reading": bool(will_write_thematic),
            "session_spend_usd":  round(_SPEND_USAGE["estimated_usd"], 4),
            "session_spend_cap_usd": SESSION_SPEND_CAP_USD,
        })

    # --- /api/chat ----------------------------------------------------------
    def handle_chat(self):
        body = self._read_json()
        if not body:
            self._send_json(400, {"ok": False, "error": "Invalid or missing JSON body."})
            return

        # Accept either `name` (single, backward compat) or `names` (array of 1 or 2).
        # 3+ names is rejected — chat is currently single-or-pair.
        raw_names = body.get("names")
        if raw_names is None:
            single = body.get("name")
            raw_names = [single] if single else []
        if not isinstance(raw_names, list):
            self._send_json(400, {"ok": False, "error":
                "`names` must be a list. Use [name] for single chat or [a, b] for pair chat."})
            return

        names = []
        for n in raw_names:
            clean = sanitize_name(n or "")
            if not clean:
                self._send_json(400, {"ok": False, "error":
                    f"Invalid name: {n!r}. Allowed: letters, digits, spaces, apostrophes, hyphens, periods."})
                return
            names.append(clean)

        if len(names) == 0:
            self._send_json(400, {"ok": False, "error":
                "Provide 1 entity name for single-person chat, or 2 for pair chat."})
            return
        if len(names) > 2:
            self._send_json(400, {"ok": False, "error":
                f"Chat supports 1 or 2 entities. Got {len(names)}."})
            return

        # Persona — one of the framing lenses, defaults to general.
        persona = (body.get("persona") or "general").strip().lower()
        if persona not in PERSONA_FRAMES:
            self._send_json(400, {"ok": False, "error":
                f"Unknown persona '{persona}'. Allowed: {sorted(PERSONA_FRAMES)}"})
            return

        # Length — terse / standard / deep, defaults to standard.
        length = (body.get("length") or "standard").strip().lower()
        if length not in LENGTH_INSTRUCTIONS:
            self._send_json(400, {"ok": False, "error":
                f"Unknown length '{length}'. Allowed: {sorted(LENGTH_INSTRUCTIONS)}"})
            return

        messages = body.get("messages") or []
        if not isinstance(messages, list) or not messages:
            self._send_json(400, {"ok": False, "error":
                "messages must be a non-empty list of {role, content} turns."})
            return
        for i, m in enumerate(messages):
            if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
                self._send_json(400, {"ok": False, "error":
                    f"messages[{i}] must have role 'user' or 'assistant'."})
                return
            if not isinstance(m.get("content"), str):
                self._send_json(400, {"ok": False, "error":
                    f"messages[{i}].content must be a string."})
                return

        # Truncate history if it's gotten huge
        if len(messages) > 20:
            messages = messages[-20:]

        # ----- Build the system prompt based on mode -----
        try:
            if len(names) == 1:
                # Single-entity mode (original behavior)
                name = names[0]
                files = find_entity_files(name)
                if not files:
                    self._send_json(404, {"ok": False, "error":
                        f"No canon page found for '{name}'."})
                    return
                canon_path, yaml_path, reading_path, system_readings_path = files
                if not yaml_path.exists():
                    self._send_json(409, {"ok": False, "error":
                        f"'{name}' has no computed profile yet."})
                    return
                yaml_text = yaml_path.read_text(encoding="utf-8")
                sys_readings = system_readings_path.read_text(encoding="utf-8") if system_readings_path.exists() else None
                thematic = reading_path.read_text(encoding="utf-8") if reading_path.exists() else None
                pronouns = read_pronouns_from_canon(canon_path)
                system_prompt = system_prompt_for_chat(name, yaml_text, sys_readings, thematic, pronouns=pronouns)
            else:
                # Pair mode — load both entities + pre-computed synastry
                name_a, name_b = names
                if name_a == name_b:
                    self._send_json(400, {"ok": False, "error":
                        "Pair chat needs two different entities."})
                    return
                entity_a = load_entity_dict(name_a)
                entity_b = load_entity_dict(name_b)
                if entity_a is None:
                    self._send_json(404, {"ok": False, "error":
                        f"No computed entity found for '{name_a}'."})
                    return
                if entity_b is None:
                    self._send_json(404, {"ok": False, "error":
                        f"No computed entity found for '{name_b}'."})
                    return
                from synastry import synastry_summary  # local import — heavy
                summary = synastry_summary(entity_a, entity_b)
                # Read pronouns from each canon page
                canon_a = VAULT_ROOT / entity_a["canon_path"]
                canon_b = VAULT_ROOT / entity_b["canon_path"]
                pronouns_a = read_pronouns_from_canon(canon_a)
                pronouns_b = read_pronouns_from_canon(canon_b)
                system_prompt = system_prompt_for_pair_chat(
                    entity_a, entity_b, summary,
                    pronouns_a=pronouns_a, pronouns_b=pronouns_b,
                )

            # Append the persona frame (if any). The framing comes AFTER the
            # chart data + readings so it's the last instruction the model
            # reads before responding — it tends to weight late context heavily.
            frame = PERSONA_FRAMES.get(persona, "")
            if frame:
                system_prompt = system_prompt + "\n\n================================================================\n" + frame

            # Append the length instruction. Comes LAST so it's the most
            # immediate context the model reads.
            length_instr = LENGTH_INSTRUCTIONS.get(length, "")
            if length_instr:
                system_prompt = system_prompt + "\n\n================================================================\n" + length_instr
        except OSError as e:
            self._send_json(500, {"ok": False, "error":
                f"Could not read entity files: {e}"})
            return

        # Tag the LATEST user turn with the current persona lens so the lens
        # transition is visible in the immediate context, not just buried in
        # the system prompt. Critical when the user asks the same question
        # under different lenses in one conversation — without this, the model
        # tends to recognize the repeat and respond "I already covered this."
        # The tag is added at request time only; the client never sees it.
        if messages and messages[-1].get("role") == "user" and persona != "general":
            persona_labels = {
                "hero_journey":  "Hero's Journey",
                "relationship":  "Relationship",
                "business":      "Business",
            }
            label = persona_labels.get(persona, persona)
            tagged_messages = list(messages)
            last = dict(tagged_messages[-1])
            last["content"] = (
                f"[Lens: {label} — apply this framing fully, even if I've "
                f"asked something similar in a different lens earlier in "
                f"this conversation]\n\n{last['content']}"
            )
            tagged_messages[-1] = last
            messages = tagged_messages

        # ----- Call the model -----
        # Bump max_tokens for "deep" length so 4-6 paragraph replies aren't truncated.
        per_request_tokens = {
            "terse":    600,
            "standard": MAX_TOKENS_CHAT,  # 1500
            "deep":     3500,
        }.get(length, MAX_TOKENS_CHAT)
        try:
            payload = anthropic_messages_call(
                model=MODEL_CHAT,
                system=system_prompt,
                messages=messages,
                max_tokens=per_request_tokens,
            )
            reply = anthropic_extract_text(payload)
        except RuntimeError as e:
            self._send_json(502, {"ok": False, "error": str(e)})
            return

        self._send_json(200, {
            "ok": True,
            "reply": reply,
            "mode": "pair" if len(names) == 2 else "single",
            "names": names,
            "persona": persona,
            "length": length,
            "session_spend_usd": round(_SPEND_USAGE["estimated_usd"], 4),
            "session_spend_cap_usd": SESSION_SPEND_CAP_USD,
        })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to bind (default 8765)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind (default 127.0.0.1 — local only)")
    args = parser.parse_args()

    if not SITE_DIR.is_dir():
        print(f"error: built site missing at {SITE_DIR}", file=sys.stderr)
        print(f"       run: python3 tools/profile-viewer/build.py", file=sys.stderr)
        return 1

    # SO_REUSEADDR lets us rebind to the port immediately after Ctrl+C — avoids
    # the "Address already in use" error during the ~30s TCP TIME_WAIT window.
    HTTPServer.allow_reuse_address = True
    server = HTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/index.html"
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"Omni-Profile local server")
    print(f"  serving:    {SITE_DIR}")
    print(f"  vault:      {VAULT_ROOT}")
    print(f"  open:       {url}")
    print(f"  endpoints:  POST /api/add-entity, /api/geocode, /api/author-readings, /api/chat")
    print(f"              GET  /api/spend")
    print(f"  anthropic:  {'API key set ✓' if api_key_set else 'API key NOT set — readings + chat will fail until ANTHROPIC_API_KEY is exported'}")
    print(f"  spend cap:  ${SESSION_SPEND_CAP_USD:.2f} per server session (raise with OMNI_SPEND_CAP=5.0)")
    print(f"  models:     authoring={MODEL_AUTHORING}  chat={MODEL_CHAT}")
    print(f"  stop:       Ctrl+C")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down.")
        server.server_close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
