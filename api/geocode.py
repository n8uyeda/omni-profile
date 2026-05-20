"""Vercel serverless function: POST /api/geocode

Nominatim place-name lookup + timezone derivation from lat/lon."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

USER_AGENT = "OmniProfileServerless/0.1 (https://github.com/)"

try:
    from timezonefinder import TimezoneFinder  # type: ignore
    _TZ = TimezoneFinder()
except ImportError:
    _TZ = None


def _send_json(req, status, body):
    payload = json.dumps(body).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    req.send_header("Content-Length", str(len(payload)))
    req.send_header("Access-Control-Allow-Origin", "*")
    req.end_headers()
    req.wfile.write(payload)


def _tz_from_coords(lat, lon):
    if _TZ is None or lat is None or lon is None:
        return None
    try:
        return _TZ.timezone_at(lat=float(lat), lng=float(lon))
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 10_000:
            return _send_json(self, 400, {"ok": False, "error": "missing body"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _send_json(self, 400, {"ok": False, "error": "invalid JSON"})

        query = (body.get("query") or "").strip()
        if not query:
            return _send_json(self, 400, {"ok": False, "error": "query is required"})

        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        })
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return _send_json(self, 502, {"ok": False, "error": f"geocoder failed: {e}"})

        if not data:
            return _send_json(self, 200, {"ok": True, "found": False})

        hit = data[0]
        try:
            lat = float(hit["lat"])
            lon = float(hit["lon"])
        except (KeyError, ValueError):
            return _send_json(self, 200, {"ok": True, "found": False})

        return _send_json(self, 200, {
            "ok": True,
            "found": True,
            "result": {
                "display_name": hit.get("display_name"),
                "lat": lat,
                "lon": lon,
                "tz": _tz_from_coords(lat, lon),
                "type": hit.get("type"),
            },
        })
