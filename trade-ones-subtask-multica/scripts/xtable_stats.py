#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从父排期文档的「1.1 国内酒店 / 1.2 境外酒店 / 1.3 民宿」小节里取三张多维表格，
按用户口径汇总「本周新增 / 已评待排期 / 跟进中 / 已排期(本周需求池) / 下周投入 pd」。

用法：
  python3 xtable_stats.py --xml /tmp/osm-parent.xml --week W43 --out /tmp/osm-stats.json [--mis zhangce07]
"""

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

PD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*pd", re.I)
ONES_REQ_RE = re.compile(r"/workItem/requirement/detail/(\d+)")
PRODUCT_RE = re.compile(r"/product/(\d+)/")

# 已上线/无需投入的历史行即使打了「Wxx 新增」也不计入本周新增
SKIP_NEW_STATUS = ("已完成", "不涉及")

# 统计「本周排期概览」时只算还在推进的需求：研发状态已结束的行不计，
# 研发状态为空的行视为还没进 ONES 排期（通常就是本周新增），也不计。
DROP_DEV_STATUS = ("已上线", "已归档")

# 下周投入 pd 只统计「本周需求池」（下周真正要投）的行，与需求排期枚举一致
PD_SCHED_STATUS = "本周需求池"

# 需求承接率 = 本周排期池需求数 / 排期表需求数，只算境内+境外，民宿一律不计。
# 分母只取「本周评审过、已进入排期流程」的两类状态：已接的「本周需求池」
# + 没接下的「已评待排期」；已完成/跟进中/暂停中是历史或在途需求，不进分母。
RATE_DOMAINS = ("境内", "境外")
RATE_NUM_STATUS = ("本周需求池",)
RATE_DEN_STATUS = ("本周需求池", "已评待排期")

SECTION_KEYS = [("境内", ("国内酒店", "境内")), ("境外", ("境外",)), ("民宿", ("民宿",))]

COL_ALIASES = {
    "req": ["需求ones", "需求", "需求ones地址"],
    "sched": ["需求排期", "排期"],
    "dev": ["研发状态"],
    "next": ["下周投入", "下周人力"],
    "borrow": ["本周借调", "借调"],
    "owner": ["需求主R", "需求负责人"],
    "prd": ["需求文档prd", "需求文档", "需求prd", "prd"],
}


def run(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("命令失败：%s\n%s" % (" ".join(cmd), out.stderr[-800:]))
    return out.stdout


def parse_json_stdout(stdout):
    """CLI 会在 JSON 前打印日志行，取最后一个 JSON 对象。"""
    start = stdout.find("{")
    while start >= 0:
        try:
            return json.loads(stdout[start:])
        except json.JSONDecodeError:
            start = stdout.find("{", start + 1)
    raise SystemExit("CLI 输出里没有 JSON：%s" % stdout[:300])


def find_xtables(xml):
    """返回 [(小节标题, xtableId)]，按文档顺序。"""
    marks = [(m.start(), m.end(), re.sub(r"<[^>]+>", "", m.group(2)))
             for m in re.finditer(r"<(h[1-6])\b[^>]*>(.*?)</\1>", xml, re.S)]
    tables = [(m.start(), m.group(1)) for m in
              re.finditer(r'<km-xtable\b[^>]*xtableId="(\d+)"', xml)]
    result = []
    for pos, xtable_id in tables:
        head = ""
        for _, end, text in marks:
            if end <= pos:
                head = text.strip()
            else:
                break
        result.append((head, xtable_id))
    return result


def pick_sections(xml):
    picked = {}
    for head, xtable_id in find_xtables(xml):
        for name, keys in SECTION_KEYS:
            if name in picked:
                continue
            if any(k in head for k in keys):
                picked[name] = xtable_id
                break
    return picked


def column_map(table_id, mis):
    raw = parse_json_stdout(run(["oa-skills", "citadel-database", "getTableMeta",
                                 "--tableId", table_id, "--mis", mis, "--raw"]))
    names = {c["columnName"].strip().lower(): c["colId"] for c in raw.get("columns", [])}
    mapping = {}
    for field, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in names:
                mapping[field] = names[alias]
                break
    missing = [f for f in ("req", "sched", "next") if f not in mapping]
    if missing:
        raise SystemExit("表格 %s 缺少必需列 %s（现有列：%s）"
                         % (table_id, missing, list(names)))
    return mapping


def cell_map(row):
    return {c["colId"]: c for c in row.get("cellData") or []}


def text_of(cell):
    return "".join(v.get("value", "") for v in (cell or {}).get("textCellValue") or []).strip()


def link_of(cell):
    for v in (cell or {}).get("textCellValue") or []:
        if v.get("link"):
            return v["link"]
    return ""


def people_of(cell):
    return [{"mis": p.get("mis", ""), "name": p.get("name", ""), "empId": p.get("empId", "")}
            for p in (cell or {}).get("peopleDTOList") or []]


def clean_req_name(text, week):
    name = re.sub(r"[（(]?\s*%s\s*新增\s*[）)]?" % week, "", text, flags=re.I)
    name = re.sub(r"^需求\s*", "", name.strip())
    return name.strip()


def query_rows(table_id, col_ids, mis):
    raw = parse_json_stdout(run(["oa-skills", "citadel-database", "queryTableData",
                                 "--tableId", table_id,
                                 "--columnIds", ",".join(str(c) for c in col_ids),
                                 "--mis", mis, "--raw"]))
    path = raw.get("tmpFile")
    if not path or not os.path.exists(path):
        raise SystemExit("没有拿到表格 %s 的数据缓存文件" % table_id)
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def collect_section(name, table_id, mis, week):
    mapping = column_map(table_id, mis)
    rows = query_rows(table_id, sorted(set(mapping.values())), mis)

    stat = collections.Counter()
    stat_raw = collections.Counter()
    dropped = collections.Counter()
    pd_next, pd_borrow = 0.0, 0.0
    new_reqs, skipped_new = [], []
    for row in rows:
        cells = cell_map(row)
        sched = (cells.get(mapping["sched"]) or {}).get("selectCellValue") or ""
        dev = (cells.get(mapping["dev"]) or {}).get("selectCellValue") if "dev" in mapping else ""
        stat_raw[sched or "(空)"] += 1
        if dev in DROP_DEV_STATUS or not dev:
            dropped["%s|%s" % (sched or "(空)", dev or "空")] += 1
        else:
            stat[sched or "(空)"] += 1

        # 下周投入：一个单元格里可能并列多个人（@A2pd @B1pd），要把所有 Npd 相加，
        # 只取第一个会少算。口径只统计「本周需求池」的行（下周真正要投的需求）。
        next_text = text_of(cells.get(mapping["next"])) if "next" in mapping else ""
        pd_all = sum(float(m.group(1)) for m in PD_RE.finditer(next_text))
        if sched == PD_SCHED_STATUS:
            pd_next += pd_all
        borrow_text = text_of(cells.get(mapping["borrow"])) if "borrow" in mapping else ""
        pd_borrow += sum(float(m.group(1)) for m in PD_RE.finditer(borrow_text))

        req_cell = cells.get(mapping["req"])
        req_text = text_of(req_cell)
        if not re.search(r"%s\s*新增" % week, req_text, re.I):
            continue
        if sched in SKIP_NEW_STATUS:
            skipped_new.append({"reqText": req_text, "section": name, "sched": sched})
            continue
        req_url = link_of(req_cell)
        req_m = ONES_REQ_RE.search(req_url)
        space_m = PRODUCT_RE.search(req_url)
        prd_cell = cells.get(mapping["prd"]) if "prd" in mapping else None
        new_reqs.append({
            "section": name,
            "reqText": req_text,
            "reqName": clean_req_name(req_text, week),
            "reqId": int(req_m.group(1)) if req_m else None,
            "spaceId": int(space_m.group(1)) if space_m else None,
            "reqUrl": req_url,
            "prdUrl": link_of(prd_cell),
            "prdText": text_of(prd_cell),
            "owners": people_of(cells.get(mapping["owner"])) if "owner" in mapping else [],
            "sched": sched,
            "nextPd": pd_all,
        })

    return {
        "section": name, "tableId": table_id, "columns": mapping,
        "rows": len(rows), "schedule": dict(stat), "scheduleRaw": dict(stat_raw),
        "droppedByDevStatus": dict(dropped),
        "nextPd": round(pd_next, 1), "borrowPd": round(pd_borrow, 1),
        "newReqs": new_reqs, "skippedNew": skipped_new,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", required=True)
    ap.add_argument("--week", required=True)
    ap.add_argument("--mis", default=os.environ.get("SSO_USER_ID") or os.environ.get("MIS") or "")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not args.mis:
        raise SystemExit("需要 --mis 或环境变量 SSO_USER_ID")

    xml = open(args.xml, encoding="utf-8").read()
    sections = pick_sections(xml)
    missing = [n for n, _ in SECTION_KEYS if n not in sections]
    if missing:
        raise SystemExit("父文档里没找到小节对应的多维表格：%s" % missing)

    detail = {name: collect_section(name, sections[name], args.mis, args.week)
              for name, _ in SECTION_KEYS}

    total_sched = collections.Counter()
    for d in detail.values():
        total_sched.update(d["schedule"])
    new_all = [r for d in detail.values() for r in d["newReqs"]]
    skipped_new = [r for d in detail.values() for r in d["skippedNew"]]
    pd_parts = [detail[n]["nextPd"] for n, _ in SECTION_KEYS]

    rate_num = sum(detail[n]["schedule"].get(s, 0)
                   for n, _ in SECTION_KEYS if n in RATE_DOMAINS for s in RATE_NUM_STATUS)
    rate_den = sum(detail[n]["schedule"].get(s, 0)
                   for n, _ in SECTION_KEYS if n in RATE_DOMAINS for s in RATE_DEN_STATUS)
    rate_auto = "%.1f%%" % (rate_num * 100.0 / rate_den) if rate_den else ""

    stats = {
        "week": args.week,
        "sections": detail,
        "newReqs": new_all,
        "skippedNew": skipped_new,
        "counts": {
            "new": len(new_all),
            "pendingSchedule": total_sched.get("已评待排期", 0),
            "following": total_sched.get("跟进中", 0),
            "scheduled": total_sched.get("本周需求池", 0),
        },
        "pd": {
            "境内": pd_parts[0], "境外": pd_parts[1], "民宿": pd_parts[2],
            "total": round(sum(pd_parts), 1),
            "borrow": round(sum(d["borrowPd"] for d in detail.values()), 1),
        },
        "rateAuto": rate_auto,
        "rateDetail": {
            "num": rate_num, "den": rate_den,
            "domains": list(RATE_DOMAINS),
            "numStatuses": list(RATE_NUM_STATUS),
            "denStatuses": list(RATE_DEN_STATUS),
            "excludedSection": "民宿",
        },
    }
    open(args.out, "w", encoding="utf-8").write(json.dumps(stats, ensure_ascii=False, indent=2))
    print(json.dumps({"counts": stats["counts"], "pd": stats["pd"],
                      "rateAuto": rate_auto, "rateDetail": stats["rateDetail"],
                      "newReqs": [r["reqName"] for r in new_all]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
