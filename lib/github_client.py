"""Minimal GitHub API client for committing new entity files back to the
public repo on visitor submission. Uses urllib only — no PyGithub dep needed.

Auth via the GITHUB_TOKEN env var (a Personal Access Token with `repo` scope
or a fine-grained token with Contents: Read+Write on the target repo).
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"


def _get_repo_config() -> tuple[str, str, str, str]:
    """Pull GITHUB_TOKEN + GITHUB_REPO_OWNER + GITHUB_REPO_NAME + GITHUB_REPO_BRANCH
    from env. Default branch is `main`."""
    token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("GITHUB_REPO_OWNER")
    repo = os.environ.get("GITHUB_REPO_NAME")
    branch = os.environ.get("GITHUB_REPO_BRANCH", "main")
    missing = [k for k, v in [("GITHUB_TOKEN", token), ("GITHUB_REPO_OWNER", owner), ("GITHUB_REPO_NAME", repo)] if not v]
    if missing:
        raise RuntimeError(
            "GitHub config missing: " + ", ".join(missing) +
            ". Set these in Vercel → Settings → Environment Variables."
        )
    return token, owner, repo, branch


def _request(method: str, path: str, body: dict | None = None) -> dict:
    token, owner, repo, _branch = _get_repo_config()
    url = f"{API}/repos/{owner}/{repo}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "OmniProfileServerless/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:500]
        except Exception:
            detail = e.reason
        raise RuntimeError(f"GitHub API HTTP {e.code} on {method} {path}: {detail}")


def get_file_sha(repo_path: str) -> str | None:
    """Return the SHA of an existing file at `repo_path` (e.g.
    'vault/04_CANON/People/Foo.md'), or None if it doesn't exist."""
    _t, _o, _r, branch = _get_repo_config()
    try:
        data = _request("GET", f"/contents/{repo_path}?ref={branch}")
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return None
        raise
    return data.get("sha")


def put_file(repo_path: str, content: str, commit_message: str,
              update_existing: bool = False) -> dict:
    """Create (or update if update_existing=True) a file in the repo.
    Returns the GitHub API response (which includes the new commit SHA)."""
    _t, _o, _r, branch = _get_repo_config()
    body = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if update_existing:
        sha = get_file_sha(repo_path)
        if sha:
            body["sha"] = sha
    return _request("PUT", f"/contents/{repo_path}", body)
