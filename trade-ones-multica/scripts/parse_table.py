#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析「任务创建结果」表格，输出结构化 JSON（按需求去重后的分组）。

输入（二选一）：
  --doc-json <file>  学城 getDocumentJson 导出的 ProseMirror JSON（推荐）
                     能同时拿到 mention 的 mis 和真实的 rowspan/colspan，合并单元格不会被误判成空
  --md <file>        直接粘贴的 Markdown / 竖线表格文本（无合并信息，空就是空，只有名字没有 mis）

输出：
  groups[]   按「需求 ones」去重的需求组（含所有 devTask 行、人员、PRD、页面、本周新增）
  orphans[]  没有需求 ones 链接的行（需要用户补链接，或本身不是需求行）
  records[]  逐行原始解析结果（含每格来源 own/merged）

用法：
  oa-skills citadel getDocumentJson --contentId 2792700866 --mis $MIS 2>/dev/null \
    | sed -n '/^{"type":"doc"/,$p' > /tmp/doc.json
  python3 parse_table.py --doc-json /tmp/doc.json --json /tmp/parsed.json
"""

import argparse
import json
import re
import sys

COL_ALIASES = {
    "person": ["开发人员", "人员", "负责人", "开发"],
    "title": ["任务标题", "标题"],
    "workload": ["工作量", "人天", "pd"],
    "date": ["日期", "排期"],
    "status": ["状态"],
    "labels": ["标签"],
    "devtask": ["任务id", "devtask", "任务"],
    "req": ["需求ones", "需求"],
    "prd": ["需求prd", "prd"],
    "pages": ["涉及页面", "涉及页面/模块", "页面"],
    "new": ["本周新增", "新增"],
}

REQUIRED = ["person", "req", "prd", "pages", "new"]
REQ_FIELDS = ("req", "prd", "pages", "new")


def norm(s):
    return re.sub(r"\s+", "", (s or "")).strip().lower()


def map_header(header_texts):
    mapping = {}
    normalized = [norm(h) for h in header_texts]
    for field, aliases in COL_ALIASES.items():
        for alias in aliases:
            if norm(alias) in normalized:
                mapping[field] = normalized.index(norm(alias))
                break
    return mapping


# ---------------- ProseMirror JSON ----------------

def collect_cell(cell_node):
    """把单元格节点拍平成 {text, mentions, links}。"""
    text_parts, mentions, links = [], [], []

    def walk(node):
        if not isinstance(node, dict):
            return
        ntype = node.get("type")
        attrs = node.get("attrs") or {}
        if ntype == "mention":
            mentions.append({"name": attrs.get("name", ""), "mis": attrs.get("uid", "")})
            if attrs.get("name"):
                text_parts.append(attrs["name"])
        elif ntype in ("open_link", "ones"):
            href = attrs.get("href") or node.get("href") or ""
            kind = attrs.get("type") or node.get("type_hint") or ""
            if href:
                links.append({"href": href, "kind": kind})
                text_parts.append(href)
        elif ntype == "link":
            href = attrs.get("href", "")
            if href:
                links.append({"href": href, "kind": attrs.get("type", "")})
        elif ntype == "text":
            text_parts.append(node.get("text", ""))
        elif ntype == "hard_break":
            text_parts.append(" ")
        for child in node.get("content") or []:
            walk(child)

    walk(cell_node)
    text = re.sub(r"\s+", " ", "".join(text_parts)).strip()
    return {"text": text, "mentions": mentions, "links": links}


def build_grid(table_node):
    """按 rowspan/colspan 还原网格：grid[row][col] = {cell, anchor_row}。"""
    rows = [r for r in table_node.get("content") or [] if r.get("type") == "table_row"]
    grid, occupied = [], []
    for r in range(len(rows)):
        grid.append({})
        occupied.append(set())

    for r, row in enumerate(rows):
        col = 0
        for cell in row.get("content") or []:
            if cell.get("type") not in ("table_cell", "table_header"):
                continue
            attrs = cell.get("attrs") or {}
            rowspan = int(attrs.get("rowspan") or 1)
            colspan = int(attrs.get("colspan") or 1)
            while col in occupied[r]:
                col += 1
            info = collect_cell(cell)
            info.update({"anchorRow": r, "type": cell.get("type"), "colspan": colspan})
            for dr in range(rowspan):
                rr = r + dr
                if rr >= len(rows):
                    break
                for dc in range(colspan):
                    grid[rr][col + dc] = info
                    occupied[rr].add(col + dc)
            col += colspan
    return rows, grid


def load_doc_json(path):
    content = open(path, encoding="utf-8").read()
    match = re.search(r'\{\s*"type"\s*:\s*"doc"', content)
    if not match:
        raise SystemExit("给出的文件里没有找到 ProseMirror JSON（应以 {\"type\":\"doc\" 开头）")
    idx = match.start()
    doc = json.loads(content[idx:])
    tables = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "table":
                tables.append(node)
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    parsed = []
    for t in tables:
        rows, grid = build_grid(t)
        parsed.append({"rows": rows, "grid": grid})
    return parsed


# ---------------- Markdown ----------------

MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
MD_MENTION = re.compile(r"@([^\s|]+)")


def load_md(path):
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8")]
    blocks, buf = [], []
    for line in lines:
        if line.strip().startswith("|"):
            buf.append(line)
        elif buf:
            blocks.append(buf)
            buf = []
    if buf:
        blocks.append(buf)

    tables = []
    for block in blocks:
        cells_rows = []
        for line in block:
            if re.match(r"^\s*\|[\s:\-\|]+\|\s*$", line):
                continue
            raw_cells = line.strip().strip("|").split("|")
            cells_rows.append([parse_md_cell(c) for c in raw_cells])
        grid = []
        for r, cells in enumerate(cells_rows):
            grid.append({c: {**info, "anchorRow": r, "type": "table_cell", "colspan": 1}
                         for c, info in enumerate(cells)})
        tables.append({"rows": [{"type": "table_row", "content": c} for c in cells_rows], "grid": grid})
    return tables


def parse_md_cell(raw):
    raw = (raw or "").strip()
    links = [{"href": m.group(2), "kind": ""} for m in MD_LINK.finditer(raw)]
    mentions = [{"name": m.group(1), "mis": ""} for m in MD_MENTION.finditer(raw)]
    text = MD_LINK.sub(lambda m: m.group(2), raw).strip()
    return {"text": text, "mentions": mentions, "links": links}


# ---------------- 业务解析 ----------------

def header_of(table):
    if not table["grid"]:
        return []
    row0 = table["grid"][0]
    width = max(row0.keys()) + 1 if row0 else 0
    return [(row0.get(c) or {}).get("text", "") for c in range(width)]


def pick_table(tables, table_index):
    candidates = []
    for i, t in enumerate(tables):
        header = header_of(t)
        mapping = map_header(header)
        missing = [f for f in REQUIRED if f not in mapping]
        candidates.append((i, t, header, mapping, missing))
    if table_index is not None:
        for c in candidates:
            if c[0] == table_index:
                if c[4]:
                    raise SystemExit(f"表格 #{table_index} 缺少必需列 {c[4]}；表头={c[2]}")
                return c
        raise SystemExit(f"没有表格 #{table_index}，共 {len(candidates)} 张表")
    usable = [c for c in candidates if not c[4]]
    if not usable:
        detail = "\n".join(f"  表格 #{c[0]} 表头={c[2]} 缺少={c[4]}" for c in candidates)
        raise SystemExit(f"没有找到含必需列 {REQUIRED} 的表格：\n{detail}")
    if len(usable) > 1:
        usable.sort(key=lambda c: len(c[1]["grid"]), reverse=True)
        print(f"[warn] 多张表符合条件，选用表格 #{usable[0][0]}（{len(usable[0][1]['grid'])} 行），"
              f"其余候选={[u[0] for u in usable[1:]]}", file=sys.stderr)
    return usable[0]


def cell_value(info):
    """把单元格统一成 {text, url, kind}。"""
    info = info or {}
    text = info.get("text", "")
    url, kind = "", ""
    for link in info.get("links") or []:
        href = link.get("href", "")
        if "ones.sankuai.com" in href:
            url, kind = href, "ones"
            break
        if "km.sankuai.com" in href:
            url, kind = href, "km"
    if not url and info.get("links"):
        url = info["links"][0].get("href", "")
        kind = info["links"][0].get("kind", "") or "link"
    if not text:
        text = url
    return {"text": text, "url": url, "kind": kind}


def ones_kind(url):
    if "/workItem/requirement/" in url:
        return "requirement"
    if "/workItem/devTask/" in url or "/workItem/task/" in url:
        return "devtask"
    return "other"


def ones_ids(url, text=""):
    item = re.search(r"/detail/(\d+)", url or "")
    if not item:
        item = re.search(r"(\d{6,})", url or "")
    if not item:
        item = re.search(r"(\d{6,})", text or "")
    space = re.search(r"/product/(\d+)/", url or "")
    return (item.group(1) if item else ""), (space.group(1) if space else "")


def build_records(table, mapping):
    grid = table["grid"]
    records = []
    last_person = {"name": "", "mis": ""}
    last_person_row = 0
    for r in range(1, len(grid)):
        row = grid[r]
        rec = {"row": r}

        def take(field):
            if field not in mapping:
                return None, 0
            info = row.get(mapping[field])
            if not info:
                return None, 0
            return info, info.get("anchorRow", r)

        person_info, person_anchor = take("person")
        person = {"name": "", "mis": ""}
        if person_info:
            if person_info.get("mentions"):
                person = {"name": person_info["mentions"][0]["name"],
                          "mis": person_info["mentions"][0]["mis"]}
            else:
                person = {"name": person_info.get("text", "").lstrip("@").strip(), "mis": ""}
        if person["name"]:
            last_person = person
            last_person_row = r
            rec["person"] = dict(person)
            rec["personSource"] = "own" if person_anchor == r else f"merged(第{person_anchor}行)"
        else:
            # 开发人员列空 = 与上一行同一人（表格里同一人的连续任务行）
            rec["person"] = dict(last_person)
            rec["personSource"] = f"carry(第{last_person_row}行)" if last_person["name"] else "empty"

        for field in ("title", "workload", "date", "status", "labels"):
            info, anchor = take(field)
            rec[field] = (info or {}).get("text", "")
            if anchor and anchor != r:
                rec[field + "Source"] = f"merged(第{anchor}行)"

        dt_info, dt_anchor = take("devtask")
        dt_val = cell_value(dt_info)
        rec["devtaskId"] = ones_ids(dt_val["url"])[0] or dt_val["text"]
        rec["devtaskUrl"] = dt_val["url"]

        for field in REQ_FIELDS:
            info, anchor = take(field)
            val = cell_value(info)
            rec[field] = val
            rec[field + "Source"] = "own" if anchor == r else (
                f"merged(第{anchor}行)" if anchor else "empty"
            )
            if anchor and anchor != r:
                rec[field + "anchorRow"] = anchor

        records.append(rec)
    return records


def group_records(records):
    groups, order, orphans = {}, [], []
    for rec in records:
        url = rec["req"]["url"]
        req_id, space_id = ones_ids(url, rec["req"]["text"])
        if not req_id or ones_kind(url) != "requirement":
            orphans.append({
                "row": rec["row"],
                "person": rec["person"],
                "title": rec.get("title", ""),
                "devtaskId": rec.get("devtaskId", ""),
                "reqText": rec["req"]["text"],
                "reqUrl": url,
                "reqKind": ones_kind(url) if url else "",
                "prd": rec["prd"],
                "pages": rec["pages"],
                "new": rec["new"],
            })
            continue

        if req_id not in groups:
            groups[req_id] = {
                "reqId": req_id,
                "spaceId": space_id,
                "reqUrl": url,
                "persons": [],
                "tasks": [],
                "prd": {"text": "", "url": "", "kind": ""},
                "pages": {"text": "", "url": "", "kind": ""},
                "isNew": "否",
                "notes": [],
            }
            order.append(req_id)
        g = groups[req_id]

        if rec["person"]["name"] and rec["person"] not in g["persons"]:
            g["persons"].append(rec["person"])
        g["tasks"].append({
            "row": rec["row"],
            "title": rec.get("title", ""),
            "workload": rec.get("workload", ""),
            "date": rec.get("date", ""),
            "status": rec.get("status", ""),
            "labels": rec.get("labels", ""),
            "devtaskId": rec.get("devtaskId", ""),
        })
        if rec["prd"]["text"] and not g["prd"]["text"]:
            g["prd"] = rec["prd"]
        if rec["pages"]["text"] and not g["pages"]["text"]:
            g["pages"] = rec["pages"]
        if rec["new"]["text"].strip() == "是":
            g["isNew"] = "是"
        for field in REQ_FIELDS:
            src = rec.get(field + "Source", "")
            if src.startswith("merged"):
                note = f"第{rec['row']}行「{field}」继承第{rec.get(field + 'anchorRow')}行（合并单元格）"
                if note not in g["notes"]:
                    g["notes"].append(note)

    return [groups[k] for k in order], orphans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-json")
    ap.add_argument("--md")
    ap.add_argument("--table-index", type=int)
    ap.add_argument("--json")
    args = ap.parse_args()

    if not args.doc_json and not args.md:
        raise SystemExit("必须提供 --doc-json 或 --md")

    tables = load_doc_json(args.doc_json) if args.doc_json else load_md(args.md)
    idx, table, header, mapping, _ = pick_table(tables, args.table_index)
    records = build_records(table, mapping)
    groups, orphans = group_records(records)

    result = {
        "source": {"kind": "doc-json" if args.doc_json else "md",
                   "path": args.doc_json or args.md},
        "table": {"index": idx, "header": header, "dataRows": len(records)},
        "columns": mapping,
        "groups": groups,
        "orphans": orphans,
        "records": records,
        "summary": {
            "dataRows": len(records),
            "reqGroups": len(groups),
            "newReqGroups": sum(1 for g in groups if g["isNew"] == "是"),
            "orphanRows": len(orphans),
            "orphansMarkedNew": sum(1 for o in orphans if o["new"]["text"].strip() == "是"),
        },
    }

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        open(args.json, "w", encoding="utf-8").write(out)
        print(json.dumps(result["summary"], ensure_ascii=False), file=sys.stderr)
        print(f"[ok] 表格#{idx} 已解析 → {args.json}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
