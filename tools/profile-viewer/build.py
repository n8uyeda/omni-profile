#!/usr/bin/env python3
"""
Profile Viewer — v0.6 first slice.

Reads canon pages + their `.profile.yaml` sibling files, renders Jinja2
templates, emits a static HTML site at ../../site/ (repo-root-relative).

Usage:
    python3 tools/profile-viewer/build.py
    open site/index.html
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from data import load_entities, vault_root_from_here, slugify
from synastry import compute_edges, synastry_summary, rank_pairs, compute_outliers, compute_demographics
from itertools import combinations

from svg_western import render_chart_wheel, render_chart_wheel_combined
from svg_hd import render_bodygraph, render_bodygraph_combined
from svg_mandala import render_mandala, render_mandala_combined
from svg_tzolkin import render_tzolkin
from svg_chinese import render_chinese_wheel
from tooltips_data import all_meanings


HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
REPO_ROOT = HERE.parent.parent
DEFAULT_OUT = REPO_ROOT / "site"
VIEWER_VERSION = "0.9"


def now_human() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env


def engine_version_from_entities(entities: list[dict]) -> str:
    for e in entities:
        ess = e.get("essentials") or {}
        if ess.get("engine_version"):
            return ess["engine_version"]
    return "?"


def write(out_path: Path, content: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


def copy_static(out_dir: Path) -> None:
    target = out_dir / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(STATIC_DIR, target)


def pair_slug(a: dict, b: dict) -> str:
    return f"{a['slug']}--{b['slug']}"


def build_network_json(entities: list[dict], edges: list[dict]) -> dict:
    return {
        "nodes": [
            {"id": e["slug"], "label": e["name"], "type": e["type"]}
            for e in entities
        ],
        "edges": [
            {
                "source": ed["source"],
                "target": ed["target"],
                "weight": ed["weight"],
                "count": ed["count"],
                "tooltip": ed["tooltip"],
                "connections": ed["connections"],
            }
            for ed in edges
        ],
    }


def related_for(entity: dict, edges: list[dict], entities_by_slug: dict[str, dict]) -> list[dict]:
    rels = []
    for ed in edges:
        other_slug = None
        if ed["source"] == entity["slug"]:
            other_slug = ed["target"]
        elif ed["target"] == entity["slug"]:
            other_slug = ed["source"]
        if not other_slug:
            continue
        other = entities_by_slug.get(other_slug)
        if not other:
            continue
        # Pair slug uses alphabetical ordering for deterministic file names
        a, b = sorted([entity, other], key=lambda x: x["slug"])
        rels.append({
            "slug": other_slug,
            "name": other["name"],
            "tooltip": ed["tooltip"],
            "pair_slug": pair_slug(a, b),
        })
    return rels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile Viewer v0.6 — build static HTML site.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output site directory (default: repo-root/site/)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    vault = vault_root_from_here()

    print(f"vault:  {vault}")
    print(f"output: {out_dir}")

    entities = load_entities(vault)
    if not entities:
        print("no entities with populated birth: blocks found", )
        return 1
    print(f"loaded {len(entities)} entities with profiles")

    edges = compute_edges(entities)
    print(f"surfaced {len(edges)} edges between entities")

    engine_version = engine_version_from_entities(entities)
    generated_at = now_human()
    env = jinja_env()
    entities_by_slug = {e["slug"]: e for e in entities}

    # Common template context — includes the canonical tooltip data as JSON
    meanings_json = json.dumps(all_meanings(), ensure_ascii=False)
    network_data_json = json.dumps(build_network_json(entities, edges), ensure_ascii=False)
    # Planet glyph map for activation columns and any template that needs symbols
    planet_glyphs = {
        "sun": "☉", "earth": "⊕", "moon": "☽",
        "north_node": "☊", "south_node": "☋",
        "mercury": "☿", "venus": "♀", "mars": "♂",
        "jupiter": "♃", "saturn": "♄",
        "uranus": "♅", "neptune": "♆", "pluto": "♇",
        "chiron": "⚷",
    }
    base_ctx = {
        "generated_at": generated_at,
        "engine_version": engine_version,
        "viewer_version": VIEWER_VERSION,
        "meanings_json": meanings_json,
        "network_data_json": network_data_json,
        "planet_glyphs": planet_glyphs,
    }

    # 1. Index page
    pair_pages = []
    for ed in edges:
        a = entities_by_slug[ed["source"]]
        b = entities_by_slug[ed["target"]]
        a_, b_ = sorted([a, b], key=lambda x: x["slug"])
        pair_pages.append({
            "slug": pair_slug(a_, b_),
            "a": a_["name"],
            "b": b_["name"],
            "count": ed["count"],
        })

    # Pre-render mini-dashboard pool: each entity gets its SVGs rendered now
    # and dropped into the hidden pool on the index page.
    pool = []
    for e in entities:
        chart = e.get("chart") or {}
        w_full = chart.get("western") or {}
        hd_full = chart.get("human_design") or {}
        pool.append({
            "entity": e,
            "western_svg": render_chart_wheel(w_full) if w_full.get("planets") else "",
            "hd_svg": render_bodygraph(hd_full),
            "mandala_svg": render_mandala(
                w_full,
                hd_full if hd_full and "skipped" not in hd_full else None,
            ) if w_full.get("planets") else "",
        })

    # Pre-render combined overlay dashboards for each pair of entities
    # Entity colors: theme-aware via CSS variables (re-tint automatically when
    # the user switches themes). entity 1 = --accent-western, entity 2 = --accent-chinese.
    OVERLAY_COLORS = ["var(--accent-western)", "var(--accent-chinese)"]
    combined_pool = []
    for a, b in combinations(entities, 2):
        a_chart = a.get("chart") or {}
        b_chart = b.get("chart") or {}
        a_w = a_chart.get("western") or {}
        b_w = b_chart.get("western") or {}
        a_hd = a_chart.get("human_design") or {}
        b_hd = b_chart.get("human_design") or {}

        if not (a_w.get("planets") and b_w.get("planets")):
            # Skip pairs missing chart data on either side
            continue

        a_hd_for_combined = a_hd if a_hd and "skipped" not in a_hd else None
        b_hd_for_combined = b_hd if b_hd and "skipped" not in b_hd else None

        # Pair slug uses alphabetical ordering for deterministic file names
        a_, b_ = sorted([a, b], key=lambda x: x["slug"])
        pslug = pair_slug(a_, b_)

        # Render the pair in the alphabetical order so colors are deterministic
        names_in_order = [a_["name"], b_["name"]]
        w_in_order = [
            (a_chart.get("western") or {}) if a is a_ else (b_chart.get("western") or {}),
            (b_chart.get("western") or {}) if b is b_ else (a_chart.get("western") or {}),
        ]
        hd_in_order = [
            a_hd_for_combined if a is a_ else b_hd_for_combined,
            b_hd_for_combined if b is b_ else a_hd_for_combined,
        ]

        combined_pool.append({
            "entity_a": a_,
            "entity_b": b_,
            "pair_slug": pslug,
            "western_svg": render_chart_wheel_combined(w_in_order, OVERLAY_COLORS, names_in_order),
            "mandala_svg": render_mandala_combined(w_in_order, hd_in_order, OVERLAY_COLORS, names_in_order),
        })

    # Recommendation rankings — top harmonious / friction pairs + outliers
    rankings = rank_pairs(entities)
    outliers = compute_outliers(entities)
    demographics = compute_demographics(entities)

    # Add synastry summary to each combined pool entry for the overlay panel
    pair_summary_by_slug: dict[str, dict] = {
        r["pair_slug"]: r["summary"] for r in rankings["all"]
    }
    for c in combined_pool:
        c["synastry"] = pair_summary_by_slug.get(c["pair_slug"])

    index_html = env.get_template("index.html").render(
        title="Network",
        asset_prefix="",
        entities=entities,
        edges=edges,
        pair_pages=pair_pages,
        pool=pool,
        combined_pool=combined_pool,
        rankings=rankings,
        outliers=outliers,
        demographics=demographics,
        n_entities=len(entities),
        **base_ctx,
    )
    write(out_dir / "index.html", index_html)
    print(f"  wrote: index.html ({len(combined_pool)} combined pair dashboards)")

    # 2. Per-person pages
    person_tpl = env.get_template("person.html")
    for e in entities:
        chart = e.get("chart") or {}
        western_full = chart.get("western") or {}
        hd_full = chart.get("human_design") or {}

        western_svg = ""
        if western_full.get("planets"):
            western_svg = render_chart_wheel(western_full)

        hd_svg = render_bodygraph(hd_full)

        # Mandala only when we have Western planet data — it's the combined chart
        mandala_svg = ""
        if western_full.get("planets"):
            mandala_svg = render_mandala(western_full, hd_full if hd_full and "skipped" not in hd_full else None)

        mayan_full = chart.get("mayan") or {}
        chinese_full = chart.get("chinese") or {}
        tzolkin_svg = render_tzolkin(mayan_full) if mayan_full else ""
        chinese_svg = render_chinese_wheel(chinese_full) if chinese_full else ""

        related = related_for(e, edges, entities_by_slug)

        person_html = person_tpl.render(
            title=e["name"],
            asset_prefix="../",
            entity=e,
            western_svg=western_svg,
            hd_svg=hd_svg,
            mandala_svg=mandala_svg,
            tzolkin_svg=tzolkin_svg,
            chinese_svg=chinese_svg,
            related=related,
            **base_ctx,
        )
        write(out_dir / "people" / f"{e['slug']}.html", person_html)
        print(f"  wrote: people/{e['slug']}.html")

    # 3. Pair pages — one per edge, now with full synastry summary
    pair_tpl = env.get_template("pair.html")
    for ed in edges:
        a = entities_by_slug[ed["source"]]
        b = entities_by_slug[ed["target"]]
        a_, b_ = sorted([a, b], key=lambda x: x["slug"])
        slug = pair_slug(a_, b_)
        summary = synastry_summary(a_, b_)
        pair_html = pair_tpl.render(
            title=f"{a_['name']} ↔ {b_['name']}",
            asset_prefix="../",
            a=a_,
            b=b_,
            edge=ed,
            synastry=summary,
            **base_ctx,
        )
        write(out_dir / "pair" / f"{slug}.html", pair_html)
        print(f"  wrote: pair/{slug}.html")

    # 4. JSON data + static assets
    copy_static(out_dir)
    (out_dir / "assets" / "data.json").write_text(
        json.dumps(build_network_json(entities, edges), indent=2),
        encoding="utf-8",
    )
    print(f"  wrote: assets/ (css, js, data.json)")

    # 5. Build manifest
    (out_dir / "assets" / "build.json").write_text(
        json.dumps({
            "viewer_version": VIEWER_VERSION,
            "engine_version": engine_version,
            "generated_at": generated_at,
            "entity_count": len(entities),
            "edge_count": len(edges),
        }, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"done. open: file://{out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
