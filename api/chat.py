"""Vercel serverless function: POST /api/chat

Body shape:
  {
    "names":   ["N8"]            # 1 entity for single-mode, 2 for pair mode
    "messages":[{role, content}], # conversation history
    "persona": "general",         # general | hero_journey | relationship | business | creative_practice
    "length":  "standard"         # terse | standard | deep
  }

Returns {ok, reply, mode, names, persona, length}.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Vercel mounts each function with cwd at the repo root; resolve our shared lib.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.anthropic_client import messages_call, extract_text, MODEL_CHAT, MAX_TOKENS_CHAT
from lib.entities import sanitize_name, find_entity_files
from lib.prompts import (
    PERSONA_FRAMES, LENGTH_INSTRUCTIONS,
    system_prompt_for_chat, system_prompt_for_pair_chat,
    format_synastry_for_prompt,
)


def _read_json(req: BaseHTTPRequestHandler) -> dict | None:
    length = int(req.headers.get("Content-Length") or 0)
    if length <= 0 or length > 1_000_000:
        return None
    try:
        return json.loads(req.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _send_json(req: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    req.send_header("Content-Length", str(len(payload)))
    req.send_header("Access-Control-Allow-Origin", "*")
    req.end_headers()
    req.wfile.write(payload)


class handler(BaseHTTPRequestHandler):  # noqa: N801 — Vercel naming convention
    def do_POST(self):  # noqa: N802
        body = _read_json(self)
        if not body:
            return _send_json(self, 400, {"ok": False, "error": "Invalid or missing JSON body."})

        # Accept `names` (array) or `name` (single, backward compat)
        raw_names = body.get("names")
        if raw_names is None:
            single = body.get("name")
            raw_names = [single] if single else []
        if not isinstance(raw_names, list):
            return _send_json(self, 400, {"ok": False, "error": "`names` must be a list."})

        names = []
        for n in raw_names:
            clean = sanitize_name(n or "")
            if not clean:
                return _send_json(self, 400, {"ok": False, "error": f"Invalid name: {n!r}"})
            names.append(clean)
        if len(names) == 0:
            return _send_json(self, 400, {"ok": False, "error": "Provide 1 or 2 entity names."})
        if len(names) > 2:
            return _send_json(self, 400, {"ok": False, "error": f"Chat supports 1 or 2 entities. Got {len(names)}."})

        messages = body.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return _send_json(self, 400, {"ok": False, "error": "messages must be a non-empty list."})
        for i, m in enumerate(messages):
            if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
                return _send_json(self, 400, {"ok": False, "error": f"messages[{i}] needs role user|assistant"})
            if not isinstance(m.get("content"), str):
                return _send_json(self, 400, {"ok": False, "error": f"messages[{i}].content must be string"})

        persona = (body.get("persona") or "general").strip().lower()
        if persona not in PERSONA_FRAMES:
            return _send_json(self, 400, {"ok": False, "error": f"Unknown persona '{persona}'"})

        length_choice = (body.get("length") or "standard").strip().lower()
        if length_choice not in LENGTH_INSTRUCTIONS:
            return _send_json(self, 400, {"ok": False, "error": f"Unknown length '{length_choice}'"})

        if len(messages) > 20:
            messages = messages[-20:]

        try:
            if len(names) == 1:
                name = names[0]
                files = find_entity_files(name)
                if not files:
                    return _send_json(self, 404, {"ok": False, "error": f"No entity '{name}'"})
                _canon, yaml_p, reading_p, sys_p = files
                if not yaml_p.exists():
                    return _send_json(self, 409, {"ok": False, "error": f"'{name}' has no computed profile"})
                yaml_text = yaml_p.read_text(encoding="utf-8")
                sys_text = sys_p.read_text(encoding="utf-8") if sys_p.exists() else None
                the_text = reading_p.read_text(encoding="utf-8") if reading_p.exists() else None
                system_prompt = system_prompt_for_chat(name, yaml_text, sys_text, the_text)
            else:
                name_a, name_b = names
                if name_a == name_b:
                    return _send_json(self, 400, {"ok": False, "error": "Pair chat needs two different entities."})
                files_a = find_entity_files(name_a)
                files_b = find_entity_files(name_b)
                if not files_a or not files_a[1].exists():
                    return _send_json(self, 404, {"ok": False, "error": f"No computed profile for '{name_a}'"})
                if not files_b or not files_b[1].exists():
                    return _send_json(self, 404, {"ok": False, "error": f"No computed profile for '{name_b}'"})
                yaml_a = files_a[1].read_text(encoding="utf-8")
                yaml_b = files_b[1].read_text(encoding="utf-8")
                sys_a = files_a[3].read_text(encoding="utf-8") if files_a[3].exists() else None
                sys_b = files_b[3].read_text(encoding="utf-8") if files_b[3].exists() else None
                the_a = files_a[2].read_text(encoding="utf-8") if files_a[2].exists() else None
                the_b = files_b[2].read_text(encoding="utf-8") if files_b[2].exists() else None

                # Synastry — import lazily so the chat module doesn't load the
                # whole data + synastry pipeline unless we're in pair mode.
                sys.path.insert(0, str(ROOT / "tools" / "profile-viewer"))
                from data import load_entities
                from synastry import synastry_summary
                entities = load_entities(ROOT / "vault")
                ent_a = next((e for e in entities if e["name"] == name_a), None)
                ent_b = next((e for e in entities if e["name"] == name_b), None)
                if not ent_a or not ent_b:
                    return _send_json(self, 404, {"ok": False, "error": "Couldn't load entity dicts for synastry."})
                summary = synastry_summary(ent_a, ent_b)
                synastry_text = format_synastry_for_prompt(name_a, name_b, summary)
                system_prompt = system_prompt_for_pair_chat(
                    name_a, name_b, yaml_a, yaml_b, sys_a, sys_b, the_a, the_b, synastry_text,
                )

            # Append persona frame + length instruction at the END so the model
            # weights them heavily.
            frame = PERSONA_FRAMES.get(persona, "")
            if frame:
                system_prompt += "\n\n================================================================\n" + frame
            length_instr = LENGTH_INSTRUCTIONS.get(length_choice, "")
            if length_instr:
                system_prompt += "\n\n================================================================\n" + length_instr

            # Tag the latest user turn with the current lens (mirrors local server)
            if messages[-1].get("role") == "user" and persona != "general":
                persona_labels = {
                    "hero_journey":      "Hero's Journey",
                    "relationship":      "Relationship",
                    "creative_practice": "Creative Practice",
                    "business":          "Business",
                }
                label = persona_labels.get(persona, persona)
                tagged = list(messages)
                last = dict(tagged[-1])
                last["content"] = (
                    f"[Lens: {label} — apply this framing fully, even if I've asked something "
                    f"similar in a different lens earlier in this conversation]\n\n{last['content']}"
                )
                tagged[-1] = last
                messages = tagged

            per_request_tokens = {"terse": 600, "standard": MAX_TOKENS_CHAT, "deep": 3500}.get(length_choice, MAX_TOKENS_CHAT)
            payload_resp = messages_call(
                model=MODEL_CHAT,
                system=system_prompt,
                messages=messages,
                max_tokens=per_request_tokens,
            )
            reply = extract_text(payload_resp)
        except RuntimeError as e:
            return _send_json(self, 502, {"ok": False, "error": str(e)})
        except OSError as e:
            return _send_json(self, 500, {"ok": False, "error": f"File io: {e}"})

        return _send_json(self, 200, {
            "ok": True,
            "reply": reply,
            "mode": "pair" if len(names) == 2 else "single",
            "names": names,
            "persona": persona,
            "length": length_choice,
        })
