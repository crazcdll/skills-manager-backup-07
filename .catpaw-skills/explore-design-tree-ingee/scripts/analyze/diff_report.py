#!/usr/bin/env python3
"""
D2C Annotator Report - 生成模块标注的 HTML 可视化报告

用法:
    python diff_report.py <before.json> <after.json> [--before-img X.png] [--after-img Y.png] [-o report.html]

使用纯标注风格（matched / before_only / after_only），不做行动判断。
"""

import json
import argparse
import sys
import os
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import load_json
from match_nodes import annotate_modules


STATUS_COLORS = {
    "matched":     ("#1a2a1a", "#4ade80"),
    "after_only":  ("#1a1a2a", "#60a5fa"),
    "before_only": ("#2a1a1a", "#f87171"),
    "absorbed":    ("#1a2a2a", "#2dd4bf"),
}


def fact_chips(facts: dict) -> str:
    """Render fact annotations as small chips"""
    chips = []

    if facts.get("structure_same"):
        chips.append(('<span class="chip chip-ok">structure same</span>'))
    else:
        chips.append('<span class="chip chip-warn">structure changed</span>')

    d = facts.get("descendants", {})
    if d.get("before") and d.get("after"):
        if d["before"] == d["after"]:
            chips.append(f'<span class="chip chip-ok">{d["before"]} nodes</span>')
        else:
            chips.append(f'<span class="chip chip-warn">{d["before"]} → {d["after"]} nodes</span>')

    cc = facts.get("children_count")
    if cc:
        chips.append(f'<span class="chip chip-warn">children {cc["before"]} → {cc["after"]}</span>')

    if facts.get("layout_changed"):
        lc = facts["layout_changed"]
        chips.append(f'<span class="chip chip-warn">layout: {escape(lc["before"] or "none")} → {escape(lc["after"] or "none")}</span>')

    ts = facts.get("texts_shared", 0)
    tb = facts.get("texts_total_before", 0)
    ta = facts.get("texts_total_after", 0)
    if tb > 0 or ta > 0:
        chips.append(f'<span class="chip chip-info">texts: {ts} shared / {tb} before / {ta} after</span>')

    return " ".join(chips)


def render_matched_card(entry: dict) -> str:
    b = entry["before"]
    a = entry["after"]
    sim = entry["similarity"]
    facts = entry["facts"]

    sim_pct = int(sim * 100)
    if sim >= 0.9:
        sim_class = "sim-high"
    elif sim >= 0.5:
        sim_class = "sim-mid"
    else:
        sim_class = "sim-low"

    name_line = escape(a["name"])
    if facts.get("name_changed"):
        name_line = f'{escape(facts["name_changed"]["before"])} → {escape(facts["name_changed"]["after"])}'

    parts = [f'<div class="module-card">']
    parts.append(f'  <div class="name">')
    parts.append(f'    <span class="badge badge-matched">matched</span>')
    parts.append(f'    {name_line}')
    parts.append(f'    <span class="similarity {sim_class}">{sim_pct}%</span>')
    parts.append(f'  </div>')
    parts.append(f'  <div class="meta">{b["id"]} ↔ {a["id"]}</div>')
    parts.append(f'  <div class="facts">{fact_chips(facts)}</div>')

    # Text changes
    if facts.get("texts_added"):
        added = ", ".join(f'"{escape(t)}"' for t in facts["texts_added"][:5])
        parts.append(f'  <div class="texts-change texts-added">+ {added}</div>')
    if facts.get("texts_removed"):
        removed = ", ".join(f'"{escape(t)}"' for t in facts["texts_removed"][:5])
        parts.append(f'  <div class="texts-change texts-removed">- {removed}</div>')

    parts.append('</div>')
    return "\n".join(parts)


def render_side_card(entry: dict, side: str) -> str:
    status = entry["status"]
    bg, fg = STATUS_COLORS[status]
    name = escape(entry["name"])

    parts = [f'<div class="module-card">']
    parts.append(f'  <div class="name"><span class="badge" style="background:{bg};color:{fg}">{status}</span> {name}</div>')

    meta_parts = [f'{entry["descendants"]} nodes', f'id: {entry["id"]}']
    parts.append(f'  <div class="meta">{" &middot; ".join(meta_parts)}</div>')

    if entry.get("texts_preview"):
        preview = " ".join(f'"{escape(t)}"' for t in entry["texts_preview"][:4])
        parts.append(f'  <div class="texts-preview">{preview}</div>')

    # Text absorption annotation
    absorbed = entry.get("text_absorbed")
    if absorbed:
        cov = int(absorbed["coverage"] * 100)
        parts.append(f'  <div class="absorbed-info">texts found in <strong>{escape(absorbed["absorbed_by_name"])}</strong> ({cov}% coverage)</div>')
        if absorbed.get("absorbed_texts"):
            texts = ", ".join(f'"{escape(t)}"' for t in absorbed["absorbed_texts"][:5])
            parts.append(f'  <div class="absorbed-texts">{texts}</div>')

    parts.append('</div>')
    return "\n".join(parts)


def render_html(result: dict, before_img: str, after_img: str,
                before_name: str, after_name: str) -> str:
    summary = result["summary"]
    matched = result["matched"]
    after_only = result["after_only"]
    before_only = result["before_only"]

    # Stats
    stats = [
        (summary["matched"], "Matched", "#1a2a1a", "#4ade80"),
        (summary["after_only"], "After Only", "#1a1a2a", "#60a5fa"),
        (summary["before_only"], "Before Only", "#2a1a1a", "#f87171"),
    ]
    if summary.get("text_absorbed", 0) > 0:
        stats.append((summary["text_absorbed"], "Text Absorbed", "#1a2a2a", "#2dd4bf"))

    stats_html = "\n".join(
        f'<span class="stat" style="background:{bg};color:{fg}">{count} {label}</span>'
        for count, label, bg, fg in stats if count > 0
    )

    # Sidebar sections
    sidebar_parts = []

    # Matched
    if matched:
        sidebar_parts.append('<div class="module-group">')
        sidebar_parts.append('  <div class="module-group-title">Matched Modules</div>')
        # Sort: low similarity first (more interesting)
        for entry in sorted(matched, key=lambda e: e["similarity"]):
            sidebar_parts.append(render_matched_card(entry))
        sidebar_parts.append('</div>')
        sidebar_parts.append('<div class="divider"></div>')

    # After only
    if after_only:
        sidebar_parts.append('<div class="module-group">')
        sidebar_parts.append('  <div class="module-group-title">After Only (new in after)</div>')
        for entry in after_only:
            sidebar_parts.append(render_side_card(entry, "after"))
        sidebar_parts.append('</div>')
        sidebar_parts.append('<div class="divider"></div>')

    # Before only
    if before_only:
        sidebar_parts.append('<div class="module-group">')
        sidebar_parts.append('  <div class="module-group-title">Before Only (gone in after)</div>')
        for entry in before_only:
            sidebar_parts.append(render_side_card(entry, "before"))
        sidebar_parts.append('</div>')

    sidebar_html = "\n".join(sidebar_parts)

    # Bbox overlays
    def make_overlays(entries_with_bbox, color):
        ovs = []
        for e in entries_with_bbox:
            bbox = e.get("bbox")
            if not bbox or bbox.get("height", 0) <= 0:
                continue
            name = e.get("name", "")[:20]
            bg_c, fg_c = color
            ovs.append(
                f'<div class="bbox-overlay" style="top:{bbox["top"]}px;height:{bbox["height"]}px;'
                f'border-color:{fg_c};--label-bg:{bg_c};--label-fg:{fg_c}"'
                f' data-label="{escape(name)}"></div>'
            )
        return "\n".join(ovs)

    # Before overlays: matched (before side) + before_only
    before_overlays_list = [m["before"] for m in matched if m["before"].get("bbox")]
    before_only_with_bbox = [e for e in before_only if e.get("bbox")]
    before_ov = make_overlays(before_overlays_list, STATUS_COLORS["matched"])
    before_ov += "\n" + make_overlays(before_only_with_bbox, STATUS_COLORS["before_only"])

    # After overlays: matched (after side) + after_only
    after_overlays_list = [m["after"] for m in matched if m["after"].get("bbox")]
    after_only_with_bbox = [e for e in after_only if e.get("bbox")]
    after_ov = make_overlays(after_overlays_list, STATUS_COLORS["matched"])
    after_ov += "\n" + make_overlays(after_only_with_bbox, STATUS_COLORS["after_only"])

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Module Annotator: {escape(before_name)} → {escape(after_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; }}

  .header {{ padding: 20px 32px; border-bottom: 1px solid #222; display: flex; align-items: center; gap: 16px; }}
  .header h1 {{ font-size: 18px; font-weight: 600; }}
  .header .arrow {{ color: #555; font-size: 14px; }}
  .header .subtitle {{ font-size: 12px; color: #666; margin-left: auto; }}

  .stats {{ display: flex; gap: 10px; padding: 14px 32px; border-bottom: 1px solid #222; flex-wrap: wrap; }}
  .stat {{ padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 500; }}

  .main {{ display: flex; height: calc(100vh - 110px); }}

  .screenshots {{ display: flex; flex: 1; overflow: auto; }}
  .screenshot-panel {{ flex: 1; padding: 12px; display: flex; flex-direction: column; align-items: center; border-right: 1px solid #222; min-width: 0; }}
  .screenshot-panel:last-child {{ border-right: none; }}
  .screenshot-panel h3 {{ font-size: 11px; color: #666; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1.5px; flex-shrink: 0; }}
  .img-container {{ position: relative; width: 100%; }}
  .img-container img {{ width: 100%; height: auto; border-radius: 10px; box-shadow: 0 2px 16px rgba(0,0,0,0.5); display: block; }}

  .bbox-overlay {{
    position: absolute; left: 1%; width: 98%;
    border: 1.5px solid; border-radius: 3px;
    pointer-events: none; opacity: 0.5;
    transition: opacity 0.2s;
  }}
  .bbox-overlay:hover {{ opacity: 1; }}
  .bbox-overlay::after {{
    content: attr(data-label);
    position: absolute; top: -1px; right: -1px;
    font-size: 8px; padding: 1px 4px; border-radius: 0 3px 0 3px;
    background: var(--label-bg); color: var(--label-fg);
    font-weight: 600; white-space: nowrap; opacity: 0.9;
  }}

  .sidebar {{ width: 440px; overflow-y: auto; border-left: 1px solid #222; flex-shrink: 0; }}

  .module-group {{ padding: 10px 14px 4px; }}
  .module-group-title {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #555; margin-bottom: 6px; }}

  .module-card {{ padding: 10px 12px; margin: 0 0 4px; border-radius: 8px; cursor: default; transition: background 0.15s; border-left: 3px solid transparent; }}
  .module-card:hover {{ background: #151515; }}
  .module-card .name {{ font-size: 13px; font-weight: 500; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
  .module-card .meta {{ font-size: 11px; color: #555; font-family: 'SF Mono', monospace; }}
  .module-card .badge {{ font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.5px; }}

  .badge-matched {{ background: #1a2a1a; color: #4ade80; }}

  .facts {{ margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px; }}
  .chip {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; font-weight: 500; }}
  .chip-ok {{ background: #1a2a1a; color: #4ade80; }}
  .chip-warn {{ background: #2a2a1a; color: #facc15; }}
  .chip-info {{ background: #1a1a2a; color: #93c5fd; }}

  .texts-preview {{ margin-top: 4px; font-size: 11px; color: #666; font-style: italic; }}
  .texts-change {{ font-size: 10px; margin-top: 2px; }}
  .texts-added {{ color: #4ade80; }}
  .texts-removed {{ color: #f87171; }}

  .absorbed-info {{ font-size: 11px; color: #2dd4bf; margin-top: 4px; }}
  .absorbed-info strong {{ color: #5eead4; }}
  .absorbed-texts {{ font-size: 10px; color: #2dd4bf; opacity: 0.7; margin-top: 2px; }}

  .similarity {{ font-size: 11px; margin-left: auto; font-weight: 600; }}
  .sim-high {{ color: #4ade80; }}
  .sim-mid {{ color: #facc15; }}
  .sim-low {{ color: #fb923c; }}

  .divider {{ height: 1px; background: #1a1a1a; margin: 6px 14px; }}
</style>
</head>
<body>

<div class="header">
  <h1>{escape(before_name)}</h1>
  <span class="arrow">&rarr;</span>
  <h1>{escape(after_name)}</h1>
  <span class="subtitle">Module Annotator &mdash; facts only, no action judgement</span>
</div>

<div class="stats">
  {stats_html}
</div>

<div class="main">
  <div class="screenshots">
    <div class="screenshot-panel">
      <h3>Before</h3>
      <div class="img-container">
        <img src="{escape(before_img)}" alt="Before">
        {before_ov}
      </div>
    </div>
    <div class="screenshot-panel">
      <h3>After</h3>
      <div class="img-container">
        <img src="{escape(after_img)}" alt="After">
        {after_ov}
      </div>
    </div>
  </div>

  <div class="sidebar">
    {sidebar_html}
  </div>
</div>

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="生成模块标注 HTML 报告")
    parser.add_argument("before_json", help="旧版设计稿 JSON")
    parser.add_argument("after_json", help="新版设计稿 JSON")
    parser.add_argument("--before-img", help="旧版截图路径（默认同名 .png）")
    parser.add_argument("--after-img", help="新版截图路径（默认同名 .png）")
    parser.add_argument("-o", "--output", help="输出 HTML 路径")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    before = load_json(args.before_json)
    after = load_json(args.after_json)

    before_img = args.before_img or args.before_json.replace(".json", ".png")
    after_img = args.after_img or args.after_json.replace(".json", ".png")

    before_name = os.path.splitext(os.path.basename(args.before_json))[0]
    after_name = os.path.splitext(os.path.basename(args.after_json))[0]

    output_path = args.output or os.path.join(os.path.dirname(args.before_json), "diff-report.html")
    output_dir = os.path.dirname(os.path.abspath(output_path))
    before_img_rel = os.path.relpath(before_img, output_dir)
    after_img_rel = os.path.relpath(after_img, output_dir)

    result = annotate_modules(before, after, module_depth=args.depth, verbose=args.verbose)
    html = render_html(result, before_img_rel, after_img_rel, before_name, after_name)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(json.dumps({"ok": True, "report": output_path, "summary": result["summary"]},
                      ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
