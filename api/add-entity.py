"""Vercel serverless function: POST /api/add-entity

Public visitor adds a new person to the network. The function:
  1. Validates input (with 3-per-IP-per-day soft cap)
  2. Computes the chart in-memory via the engine modules
  3. Builds canon .md + profile .yaml content
  4. Commits both files to the GitHub repo via the GitHub API
  5. Returns the file paths + person URL

GitHub commit triggers a Vercel auto-rebuild. The new entity appears in the
live network ~30-60s after submission. Readings are NOT auto-authored on the
public version — the site owner runs the local backfill_readings.py CLI
periodically to publish readings.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date as _date
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "profile-engine"))

from lib.entities import sanitize_name
from lib.github_client import put_file
from lib.rate_limit import check_and_increment


def _send_json(req, status, body):
    payload = json.dumps(body).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    req.send_header("Content-Length", str(len(payload)))
    req.send_header("Access-Control-Allow-Origin", "*")
    req.end_headers()
    req.wfile.write(payload)


def _derive_precision(time_str, lat, lon):
    if time_str and lat is not None and lon is not None:
        return 1
    if lat is not None and lon is not None:
        return 2
    return 3


def _client_ip(req: BaseHTTPRequestHandler) -> str:
    """Best-effort client IP. Vercel sets x-forwarded-for and x-real-ip."""
    for header in ("x-forwarded-for", "x-real-ip"):
        v = req.headers.get(header)
        if v:
            # x-forwarded-for can be a comma list — take the first
            return v.split(",")[0].strip()
    return req.client_address[0]


def _build_canon_md(name: str, payload: dict, precision: int, essentials: dict) -> str:
    today = _date.today().isoformat()
    pronouns = (payload.get("pronouns") or "they/them").strip()
    lines = ["---", "type: person", f"pronouns: {pronouns}", "status: working",
             "domain: Shared", f"last_updated: {today}"]
    if payload.get("relationship"):
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
    lines.append(f"  source: Submitted via public add-entity form on {today}")

    # Essentials block (computed) — embed as YAML
    import yaml as _yaml  # local import
    ess_yaml = _yaml.safe_dump({"profile": essentials}, sort_keys=False, allow_unicode=True).strip()
    lines.append(ess_yaml)
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")
    lines.append("Public submission. Chart data is computed; biographical content "
                 "will be authored later by the vault owner.")
    lines.append("")
    return "\n".join(lines)


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_POST(self):  # noqa: N802
        # Rate limit per IP (3/day, soft)
        ip = _client_ip(self)
        allowed, remaining, reset_in = check_and_increment(ip, max_requests=3)
        if not allowed:
            hours = max(reset_in // 3600, 1)
            return _send_json(self, 429, {
                "ok": False,
                "error": f"Submission limit reached for this IP. Try again in ~{hours}h. "
                         f"(Soft cap of 3 submissions per IP per 24h to protect against spam.)",
            })

        # Parse JSON body
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 100_000:
            return _send_json(self, 400, {"ok": False, "error": "missing body"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _send_json(self, 400, {"ok": False, "error": "invalid JSON"})

        # Validate
        name = sanitize_name(body.get("name") or "")
        if not name:
            return _send_json(self, 400, {"ok": False, "error":
                "Name is required. Allowed: letters, digits, spaces, apostrophes, hyphens, periods."})

        date_str = (body.get("date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return _send_json(self, 400, {"ok": False, "error": "Birth date is required (YYYY-MM-DD)."})

        time_str = (body.get("time") or "").strip() or None
        if time_str and not re.match(r"^\d{2}:\d{2}$", time_str):
            return _send_json(self, 400, {"ok": False, "error": "Birth time must be HH:MM if provided."})

        try:
            lat = float(body["lat"]) if body.get("lat") not in (None, "") else None
            lon = float(body["lon"]) if body.get("lon") not in (None, "") else None
        except (TypeError, ValueError):
            return _send_json(self, 400, {"ok": False, "error": "lat/lon must be numbers."})

        # Derive timezone from coords if not provided
        tz = (body.get("tz") or "").strip() or None
        if not tz and lat is not None and lon is not None:
            try:
                from timezonefinder import TimezoneFinder  # type: ignore
                tz = TimezoneFinder().timezone_at(lat=lat, lng=lon)
            except Exception:
                pass

        precision = _derive_precision(time_str, lat, lon)
        if precision == 1 and not tz:
            return _send_json(self, 400, {"ok": False, "error":
                "Couldn't determine timezone. Please enter the IANA timezone (e.g. America/Los_Angeles)."})

        place = (body.get("place") or "").strip() or None

        # Build birth dict for the engine
        birth = {"date": date_str, "precision": precision}
        if time_str: birth["time"] = time_str
        if tz: birth["tz"] = tz
        if place: birth["place"] = place
        if lat is not None: birth["lat"] = lat
        if lon is not None: birth["lon"] = lon

        # Compute the chart by calling the engine modules directly. Each system
        # is wrapped separately so one system's failure (e.g. Chinese calendar
        # out-of-range for very old / future birth dates) doesn't abort the
        # entire submission — the chart computes for whatever systems work.
        skipped = []
        try:
            from western import chart as western_chart, essentials_from_full as western_ess
            from mayan import full_mayan, essentials_from_full as mayan_ess
            from chinese import full_chinese, essentials_from_full as chinese_ess
            from writer import build_essentials, build_full_chart
            try:
                from human_design import full_hd_chart, essentials_from_full as hd_ess
            except ImportError:
                full_hd_chart = None
                hd_ess = None

            try:
                w_full = western_chart(birth, precision)
            except Exception as e:
                # Western is foundational — failure here is fatal.
                return _send_json(self, 500, {"ok": False, "error":
                    f"Western chart compute failed: {e}"})

            try:
                m_full = full_mayan(birth)
            except Exception as e:
                m_full = None
                skipped.append(f"mayan ({e})")

            try:
                c_full = full_chinese(birth)
            except Exception as e:
                c_full = None
                skipped.append(f"chinese ({e})")

            hd_full = None
            if precision == 1 and full_hd_chart is not None:
                try:
                    hd_full = full_hd_chart(birth)
                except Exception as e:
                    skipped.append(f"human_design ({e})")

            essentials = build_essentials(
                western_ess(w_full),
                mayan_ess(m_full) if m_full else None,
                hd_ess(hd_full) if (hd_full and hd_ess) else None,
                chinese_ess(c_full) if c_full else None,
                precision=precision,
            )
            full_chart = build_full_chart(birth, w_full, m_full, hd_full, c_full)
            full_chart["entity"] = name
            full_chart["canon_path"] = f"04_CANON/People/{name}.md"
        except Exception as e:
            return _send_json(self, 500, {"ok": False, "error": f"Engine failed: {e}"})

        # Build the file contents
        try:
            canon_md = _build_canon_md(name, {
                **body, "date": date_str, "time": time_str, "tz": tz,
                "lat": lat, "lon": lon, "place": place,
            }, precision, essentials)

            import yaml as _yaml
            profile_yaml = _yaml.safe_dump(full_chart, sort_keys=False, allow_unicode=True)
        except Exception as e:
            return _send_json(self, 500, {"ok": False, "error": f"Building file contents failed: {e}"})

        # Commit to GitHub
        try:
            canon_repo_path = f"vault/04_CANON/People/{name}.md"
            yaml_repo_path = f"vault/04_CANON/People/{name}.profile.yaml"
            commit_msg = f"Add {name} via public form ({date_str})"
            put_file(canon_repo_path, canon_md, commit_msg, update_existing=False)
            put_file(yaml_repo_path, profile_yaml, commit_msg, update_existing=False)
        except RuntimeError as e:
            return _send_json(self, 502, {"ok": False, "error": f"GitHub commit failed: {e}"})

        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
        return _send_json(self, 200, {
            "ok": True,
            "name": name,
            "slug": slug,
            "precision": precision,
            "person_url": f"people/{slug}.html",
            "canon_md": canon_md,
            "profile_yaml": profile_yaml,
            "remaining_submissions_today": remaining,
            "note": "Your entity is committed to the repo. Vercel will rebuild "
                    "the site in ~30-60s and your page will be live.",
        })
