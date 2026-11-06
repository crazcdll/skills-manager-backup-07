#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把外部产出的 JSON / 字符串合并进 state.json，避免手改大 JSON 出错。

用法：
  python3 state_set.py --state /tmp/osm-state.json --set ones.results=@/tmp/osm-ones.json
  python3 state_set.py --state /tmp/osm-state.json --set newDocId=2793439441 \
      --set parentUrl=https://km.sankuai.com/collabpage/2793615111
  python3 state_set.py --state /tmp/osm-state.json --get ones.results
"""

import argparse
import json


def load_value(raw):
    if raw.startswith("@"):
        return json.load(open(raw[1:], encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def dig(state, path):
    node = state
    for part in path.split(".")[:-1]:
        node = node.setdefault(part, {})
    return node, path.split(".")[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="PATH=VALUE")
    ap.add_argument("--get")
    args = ap.parse_args()

    state = json.load(open(args.state, encoding="utf-8"))

    if args.get:
        node = state
        for part in args.get.split("."):
            node = node[part]
        print(json.dumps(node, ensure_ascii=False, indent=2))
        return

    for item in args.set:
        if "=" not in item:
            raise SystemExit("--set 需要 PATH=VALUE 形式：%s" % item)
        path, raw = item.split("=", 1)
        parent, key = dig(state, path)
        parent[key] = load_value(raw)

    json.dump(state, open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("updated:", args.state)


if __name__ == "__main__":
    main()
