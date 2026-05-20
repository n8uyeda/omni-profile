"""Per-IP rate limiting for add-entity submissions.

Vercel serverless functions are stateless — there's no shared in-memory store
across instances. For V1, we accept best-effort limiting:
  - Within a single instance, an in-memory dict tracks counts per IP per day.
  - Across instances (cold starts), the counter resets — so the actual cap is
    a *soft* upper bound, not a hard one.
  - For a hard cap, we'd need Vercel KV / Upstash Redis. Out of scope for V1.

The Anthropic monthly spend cap on console.anthropic.com remains the absolute
backstop — nothing can charge more than the cap allows.
"""
from __future__ import annotations

import time

# Per-instance state. Wiped on cold start.
# Keyed by bucket_name → ip → list[timestamps]. Separate buckets let us
# enforce different per-IP caps on different actions (e.g. 3/day for
# add-entity submissions, 1/day for readings-authoring).
_BUCKETS: dict[str, dict[str, list[float]]] = {}

# Window: seconds. 86400 = 1 day.
DEFAULT_WINDOW_SECONDS = 86400
DEFAULT_MAX_REQUESTS = 3


def check_and_increment(ip: str, bucket: str = "default",
                          max_requests: int = DEFAULT_MAX_REQUESTS,
                          window_seconds: int = DEFAULT_WINDOW_SECONDS) -> tuple[bool, int, int]:
    """Returns (allowed, remaining, reset_in_seconds).

    If allowed=False, the caller should respond 429 (or skip the action)."""
    now = time.time()
    cutoff = now - window_seconds
    bucket_map = _BUCKETS.setdefault(bucket, {})
    history = [t for t in bucket_map.get(ip, []) if t > cutoff]
    if len(history) >= max_requests:
        oldest = history[0]
        reset_in = int(window_seconds - (now - oldest))
        bucket_map[ip] = history
        return False, 0, max(reset_in, 0)
    history.append(now)
    bucket_map[ip] = history
    remaining = max(max_requests - len(history), 0)
    return True, remaining, window_seconds


def check_without_increment(ip: str, bucket: str = "default",
                              max_requests: int = DEFAULT_MAX_REQUESTS,
                              window_seconds: int = DEFAULT_WINDOW_SECONDS) -> bool:
    """Like check_and_increment but read-only — doesn't consume a slot.
    Returns True if a fresh call would be allowed."""
    now = time.time()
    cutoff = now - window_seconds
    history = [t for t in _BUCKETS.get(bucket, {}).get(ip, []) if t > cutoff]
    return len(history) < max_requests
