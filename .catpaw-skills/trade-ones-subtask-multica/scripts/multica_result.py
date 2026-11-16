#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Multica 创建结果并回 state.json 的 multica.results（供渲染结果表）。

用法：
  cat > /tmp/osm-multica-result.json <<'EOF'
  [{"reqId": 96115985, "issue": "hotel-trade-fullstack#123", "issueUrl": "https://...",
    "project": "酒店提单页", "status": "已创建", "note": ""}]
  EOF
  python3 multica_result.py --state /tmp/osm-state.json --input /tmp/osm-multica-result.json

未在 input 里出现的 reqId 会被忽略；input 里有但结果里缺失的条目会补成「未创建」。
"""

import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    state = json.load(open(args.state, encoding="utf-8"))
    incoming = json.load(open(args.input, encoding="utf-8"))
    items = (state.get("multica") or {}).get("input") or []
    by_req = {}
    for r in incoming:
        if r.get("reqId") is not None:
            by_req[r["reqId"]] = r

    results, missing = [], []
    for idx, it in enumerate(items, start=1):
        r = by_req.get(it.get("reqId")) or {}
        if not r:
            missing.append(it.get("reqName"))
        owner = (it.get("owners") or [{}])[0]
        results.append({
            "seq": idx,
            "person": owner.get("name", ""),
            "reqName": it.get("reqName", ""),
            "reqId": it.get("reqId"),
            "reqUrl": it.get("reqUrl", ""),
            "prdUrl": it.get("prdUrl", ""),
            "pages": it.get("pages", ""),
            "project": r.get("project", ""),
            "issue": r.get("issue", ""),
            "issueUrl": r.get("issueUrl", ""),
            "status": r.get("status", "未创建"),
            "note": r.get("note", ""),
        })

    state.setdefault("multica", {})["results"] = results
    json.dump(state, open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(json.dumps({
        "results": len(results),
        "missing": missing,
        "byStatus": {s: sum(1 for x in results if x["status"] == s)
                     for s in sorted({x["status"] for x in results})},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
