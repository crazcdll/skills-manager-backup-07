#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「本周新增需求」整理成《Multica 新任务创建输入》表的数据，写入 state.json。

开发人员取 ONES 子任务创建结果（该需求对应的排期人员）；没有排期人员时退回多维表格
的「需求主R」。涉及页面一律留空，等用户手填。

用法：
  python3 multica_input.py --state /tmp/osm-state.json --stats /tmp/osm-stats.json
输出：写入 state["multica"]["input"]，并在 stdout 打印汇总与缺 PRD 的需求。
"""

import argparse
import json
import re

ONES_REQ_RE = re.compile(r"/workItem/requirement/detail/(\d+)")


def canonical_req_url(req_id, space_id):
    if not req_id:
        return ""
    if space_id:
        return "https://ones.sankuai.com/ones/product/%s/workItem/requirement/detail/%s" % (
            space_id, req_id)
    return "https://ones.sankuai.com/ones/workItem/requirement/detail/%s" % req_id


def devs_from_ones(ones_results, req_id):
    devs, seen = [], set()
    for r in ones_results:
        if r.get("issueId") != req_id:
            continue
        uid = r.get("uid") or r.get("person")
        if uid in seen:
            continue
        seen.add(uid)
        devs.append({"name": r.get("person", ""), "uid": r.get("uid", ""),
                     "empId": r.get("empId", "")})
    return devs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--stats", required=True)
    args = ap.parse_args()

    state = json.load(open(args.state, encoding="utf-8"))
    stats = json.load(open(args.stats, encoding="utf-8"))
    ones_results = (state.get("ones") or {}).get("results") or []

    items, no_prd, no_dev = [], [], []
    for idx, req in enumerate(stats.get("newReqs") or [], start=1):
        req_id = req.get("reqId")
        devs = devs_from_ones(ones_results, req_id) if req_id else []
        if not devs:
            devs = [{"name": p.get("name", ""), "uid": p.get("mis", ""),
                     "empId": p.get("empId", "")} for p in req.get("owners") or []]
        if not devs:
            no_dev.append(req.get("reqName"))

        prd_url = req.get("prdUrl") or ""
        if not prd_url:
            no_prd.append({"reqName": req.get("reqName"), "reqId": req_id,
                           "reqUrl": req.get("reqUrl", "")})

        items.append({
            "seq": idx,
            "section": req.get("section", ""),
            "reqId": req_id,
            "reqName": req.get("reqName", ""),
            "taskTitle": req.get("reqName", ""),
            "reqUrl": req.get("reqUrl") or canonical_req_url(req_id, req.get("spaceId")),
            "prdUrl": prd_url,
            "owners": devs,
            "pages": "",
            "nextPd": req.get("nextPd", 0),
        })

    state.setdefault("multica", {})["input"] = items
    json.dump(state, open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(json.dumps({
        "items": len(items),
        "noPrd": no_prd,
        "noDev": no_dev,
        "titles": [i["taskTitle"] for i in items],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
