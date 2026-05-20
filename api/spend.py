"""Vercel serverless function: GET /api/spend

Reports config for diagnostic purposes. Serverless functions are stateless,
so this doesn't track running totals — for live spend, check the Anthropic
console at https://console.anthropic.com/settings/billing."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler


def _send_json(req, status, body):
    payload = json.dumps(body).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    req.send_header("Content-Length", str(len(payload)))
    req.send_header("Access-Control-Allow-Origin", "*")
    req.end_headers()
    req.wfile.write(payload)


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_GET(self):  # noqa: N802
        return _send_json(self, 200, {
            "ok": True,
            "environment": "vercel-serverless",
            "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "github_token_set": bool(os.environ.get("GITHUB_TOKEN")),
            "model_chat":      os.environ.get("OMNI_MODEL_CHAT", "claude-sonnet-4-6"),
            "model_authoring": os.environ.get("OMNI_MODEL_AUTHORING", "claude-sonnet-4-6"),
            "note": "Serverless functions don't share state. Track live spend at "
                    "https://console.anthropic.com/settings/billing.",
        })
