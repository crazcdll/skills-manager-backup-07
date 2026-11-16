#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从父排期文档的 CitadelXML 解析「三、人员分布一览表」，产出：

  1) 原样复制用的表格 XML 片段（原有 nodeId / mention 的 uid、empId / ONES 卡片全部保留）
  2) ONES 子任务创建所需的 tasks（人员 / issueId / 人天 / 日序）
  3) colspan 与显式 Npd 不一致清单、无 ONES 链接但有 pd 的排期项、task 类型链接（不可挂子任务）

用法：
  oa-skills citadel getDocumentXml --contentId 2793615111 --mis "$MIS" --output /tmp/osm-parent.xml
  python3 schedule.py --xml /tmp/osm-parent.xml --out /tmp/osm-schedule.json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET

HEADING_HINTS = ["人员分布一览表", "人员分布"]
DAY_RE = re.compile(r"周[一二三四五]")
DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})")
PD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*pd", re.I)
WEEK_RE = re.compile(r"[Ww](\d{1,2})")
ONES_REQ_RE = re.compile(r"/workItem/requirement/detail/(\d+)")
ONES_TASK_RE = re.compile(r"/workItem/(?:task|devTask)/detail/(\d+)")
PRODUCT_RE = re.compile(r"/product/(\d+)/")


def find_block(xml, tag, start=0):
    """返回从 start 起第一个 <tag> 块（含自闭合）的 [begin, end)。"""
    m = re.compile(r"<%s\b" % tag).search(xml, start)
    if not m:
        return None
    begin, depth = m.start(), 0
    for t in re.compile(r"<(/?)%s\b[^>]*?(/?)>" % tag).finditer(xml, m.start()):
        if t.group(2):                      # 自闭合
            if depth == 0:
                return (begin, t.end())
            continue
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return (begin, t.end())
    return None


def extract_table(xml):
    """定位「人员分布一览表」标题之后的第一张表格。"""
    heading_end = -1
    for m in re.finditer(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", xml, re.S):
        plain = re.sub(r"<[^>]+>", "", m.group(1))
        if any(hint in plain for hint in HEADING_HINTS):
            heading_end = m.end()
            break
    if heading_end < 0:
        raise SystemExit("父文档里没有找到「人员分布一览表」标题")
    block = find_block(xml, "table", heading_end)
    if not block:
        raise SystemExit("「人员分布一览表」标题之后没有表格")
    return xml[block[0]:block[1]]


def cell_text(el):
    """单元格纯文本（保留卡片周边的 pd 文案）。"""
    if el is None:
        return ""
    parts = []
    for node in el.iter():
        if node.tag == "br":
            parts.append(" ")
        if node.text:
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def parse_table(table_xml):
    root = ET.fromstring("<root>%s</root>" % table_xml)
    table = root.find("table")
    rows = table.findall("tr")

    header_cells = rows[0].findall("th") + rows[0].findall("td")
    dates = [cell_text(c) for c in header_cells]
    has_header_dates = any(DAY_RE.search(d) and DATE_RE.search(d) for d in dates)

    tasks, non_ones, task_links = [], [], []
    for r, row in enumerate(rows[1:], start=1):
        cells = row.findall("th") + row.findall("td")
        if len(cells) < 3:
            continue
        mention = cells[1].find(".//km-mention")
        if mention is None:
            continue
        person = {
            "name": (mention.get("name") or "").strip(),
            "uid": (mention.get("uid") or "").strip(),
            "empId": (mention.get("empId") or mention.get("emp-id") or "").strip(),
        }

        day = 0  # 0 = 周一
        for cell in cells[2:]:
            colspan = int(cell.get("colspan") or 1)
            ones = [el for el in cell.iter()
                    if el.tag == "km-open-link" and "/workItem/" in (el.get("href") or "")]
            text = cell_text(cell)

            if not ones:
                m = PD_RE.search(text)
                if m:                        # 值班 / 团建 / 学城链接等非 ONES 排期项
                    non_ones.append({
                        "rowIndex": r, "person": person["name"], "colStart": day,
                        "colspan": colspan, "duration": float(m.group(1)),
                        "cellText": text[:80],
                    })
                day += colspan
                continue

            if len(ones) == 1:
                href = ones[0].get("href") or ""
                if ONES_TASK_RE.search(href):          # task 类型无法挂子任务
                    task_links.append({"rowIndex": r, "person": person["name"], "href": href})
                    day += colspan
                    continue
                m = PD_RE.search(text)
                tasks.append({
                    **person, "href": href,
                    "duration": float(m.group(1)) if m else float(colspan),
                    "colspan": colspan, "colStart": day, "colEnd": day + colspan - 1,
                    "rowIndex": r, "pdSource": "explicit" if m else "colspan",
                })
                day += colspan
                continue

            # 多需求单元格：每个需求取自己所在的 <p> 的 pd，按 pd 依次占位
            base = day
            for el in ones:
                href = el.get("href") or ""
                if ONES_TASK_RE.search(href):
                    task_links.append({"rowIndex": r, "person": person["name"], "href": href})
                    continue
                para = next((p for p in cell.iter("p") if el in list(p.iter())), None)
                m = PD_RE.search(cell_text(para) if para is not None else text)
                dur = float(m.group(1)) if m else 1.0
                span = max(int(round(dur)), 1)
                tasks.append({
                    **person, "href": href, "duration": dur, "colspan": dur,
                    "colStart": base, "colEnd": base + span - 1,
                    "rowIndex": r, "pdSource": "multi",
                })
                base += span
            day += colspan

    mismatches = []
    for t in tasks:
        if t["pdSource"] != "explicit" or abs(t["duration"] - t["colspan"]) <= 1e-6:
            continue
        m = ONES_REQ_RE.search(t["href"])
        mismatches.append({
            "person": t["name"], "rowIndex": t["rowIndex"], "colspan": t["colspan"],
            "duration": t["duration"], "issueId": int(m.group(1)) if m else None,
            "href": t["href"],
        })

    merged = {}
    for t in tasks:
        m = ONES_REQ_RE.search(t["href"])
        if not m:
            continue
        key = (t["uid"], m.group(1))
        if key not in merged:
            pm = PRODUCT_RE.search(t["href"])
            merged[key] = {**t, "issueId": int(m.group(1)),
                           "projectId": int(pm.group(1)) if pm else None}
        else:
            merged[key]["duration"] += t["duration"]
            merged[key]["colStart"] = min(merged[key]["colStart"], t["colStart"])
            merged[key]["colEnd"] = max(merged[key]["colEnd"], t["colEnd"])
    return dates, has_header_dates, list(merged.values()), mismatches, non_ones, task_links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--table-out", default="/tmp/osm-schedule-table.xml")
    args = ap.parse_args()

    xml = open(args.xml, encoding="utf-8").read()
    title_m = re.search(r"<km-title[^>]*>(.*?)</km-title>", xml, re.S)
    title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
    week_m = WEEK_RE.search(title)
    if not week_m:
        raise SystemExit("父文档标题里没有 Wxx 周次：%s" % title)
    week = "W%s" % week_m.group(1)

    table_xml = extract_table(xml)
    dates, has_dates, tasks, mismatches, non_ones, task_links = parse_table(table_xml)
    open(args.table_out, "w", encoding="utf-8").write(table_xml)

    payload = {
        "week": week, "parentTitle": title, "tableXmlPath": args.table_out,
        "dates": dates, "hasHeaderDates": has_dates, "tasks": tasks,
        "colspanDurationMismatches": mismatches,
        "nonOnesItems": non_ones, "skippedTaskLinks": task_links,
    }
    open(args.out, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))

    print(json.dumps({
        "week": week, "tasks": len(tasks), "persons": len({t["uid"] for t in tasks}),
        "mismatches": len(mismatches), "nonOnes": len(non_ones),
        "taskLinks": len(task_links), "hasHeaderDates": has_dates,
    }, ensure_ascii=False), file=sys.stderr)
    for t in tasks:
        print("  %-10s %s %spd d%d-d%d" % (t["name"], t["issueId"], t["duration"],
                                           t["colStart"], t["colEnd"]), file=sys.stderr)


if __name__ == "__main__":
    main()
