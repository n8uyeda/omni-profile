# Omni-Profile

A four-system esoteric profile engine (Western astrology, Mayan calendar,
Human Design, Chinese astrology) with a relational network view across a
consented seed group, a chat interface that grounds every answer in the
specific chart being asked about, and a public form for visitors to submit
their own birth data and join the network.

Live at: **(set after first Vercel deploy)**

## What's in this repo

- `tools/profile-engine/` — local-first chart computation. Pure Python on top of Swiss Ephemeris. Computes Western (planets, houses, aspects), Mayan (Tzolk'in day-sign + tone + Long Count), Human Design (type, profile, channels, gates, cross), and Chinese (year pillar + Inner Animal + Secret Animal) charts.
- `tools/profile-viewer/` — static-site generator (Jinja2). Reads canon pages + computed `.profile.yaml` siblings, emits HTML for the per-person dashboards, pair-synastry pages, network graph, and the floating chat panel.
- `vault/04_CANON/People/` — birth data + computed chart + (where available) the per-chart readings and cross-system thematic synthesis for each entity.
- `api/` — Vercel Python serverless functions: `chat`, `geocode`, `add-entity`, `spend`.
- `lib/` — shared helpers used by the serverless functions.

## How it works

```
Visitor visits the site
  → static HTML (built by tools/profile-viewer/build.py at deploy time)
  → chat with any chart via POST /api/chat (Anthropic API)
  → add their own chart via POST /api/add-entity
       which commits a new canon page + .profile.yaml back to this repo
       which triggers Vercel to rebuild
       which makes the new entity appear in the network ~30-60s later
```

## Build locally

```bash
pip install -r requirements.txt
python3 tools/profile-viewer/build.py
open site/index.html
```

For the local development server (form, chat, all API endpoints):

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
python3 tools/profile-viewer/serve.py
```

Then open `http://127.0.0.1:8765/`.

## Vercel deployment

This repo is configured to deploy to Vercel out of the box.

**Required environment variables** (set in Vercel → Settings → Environment Variables):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Powers the chat endpoint + any reading authoring. Required. |
| `GITHUB_TOKEN` | Personal Access Token with `repo` scope (or fine-grained: Contents → Read+Write). Used by `/api/add-entity` to commit new submissions back to this repo. Required if you want the public submission form to work. |
| `GITHUB_REPO_OWNER` | Your GitHub username or org that owns this repo. |
| `GITHUB_REPO_NAME` | The repo name (e.g. `omni-profile`). |
| `GITHUB_REPO_BRANCH` | Optional. Defaults to `main`. |
| `OMNI_MODEL_CHAT` | Optional. Defaults to `claude-sonnet-4-6`. |
| `OMNI_MODEL_AUTHORING` | Optional. Defaults to `claude-sonnet-4-6`. |

**Anthropic spend cap**: set a monthly spend ceiling at https://console.anthropic.com/settings/billing. This is the hardest backstop on API costs.

**Rate limits**: the public add-entity endpoint enforces a soft 3-submissions-per-IP-per-day cap to discourage spam. Chat is unthrottled — the Anthropic spend cap is the only backstop.

## License

Code under `tools/`, `lib/`, and `api/` is MIT — see `LICENSE`. `pyswisseph`
wraps the Swiss Ephemeris (Astrodienst AG), distributed under AGPL-3.0 with
a paid commercial alternative; the combined network-served form must comply
with the AGPL disclosure requirement, which is satisfied by publishing the
engine source in this public repo. See `NOTICE.md` for the third-party chain.
