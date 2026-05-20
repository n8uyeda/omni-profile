"""Anthropic Messages API client — stdlib-only urllib version. Used by both
the chat and add-entity serverless functions."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

MODEL_CHAT = os.environ.get("OMNI_MODEL_CHAT", "claude-sonnet-4-6")
MODEL_AUTHORING = os.environ.get("OMNI_MODEL_AUTHORING", "claude-sonnet-4-6")

MAX_TOKENS_CHAT = 1500
MAX_TOKENS_AUTHORING = 4000


def messages_call(model: str, system: str, messages: list[dict],
                   max_tokens: int) -> dict:
    """Single Messages API call. Returns the parsed response dict, or raises
    RuntimeError with a user-friendly message on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set in the Vercel environment. "
            "Add it under Settings → Environment Variables in the Vercel dashboard."
        )

    body = json.dumps({
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:500]
        except Exception:
            detail = e.reason
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"Anthropic API request failed: {e}")


def extract_text(payload: dict) -> str:
    """Pull the assistant's text from a Messages API response."""
    out = []
    for p in (payload.get("content") or []):
        if isinstance(p, dict) and p.get("type") == "text":
            out.append(p.get("text") or "")
    return "".join(out).strip()


def usage_from(payload: dict) -> dict:
    """Return {input_tokens, output_tokens} for the call (or zeros if missing)."""
    u = payload.get("usage") or {}
    return {
        "input_tokens": int(u.get("input_tokens") or 0),
        "output_tokens": int(u.get("output_tokens") or 0),
    }
