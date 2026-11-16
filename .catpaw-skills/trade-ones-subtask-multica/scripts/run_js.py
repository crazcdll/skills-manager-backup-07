#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 scripts/js/*.js 模板填成可直接执行的 browser-action 命令，并回收 evaluate 结果。

两种模式：

1) 生成命令（默认）
   python3 run_js.py --template js/03-create.js \\
     --set TASKS=@/tmp/osm-alltasks.json --from 1 --to 4 \\
     --set WEEK_NUM='"43"' --set WEEK_ITERATION_ID=126576 \\
     --cmd-out /tmp/osm-cmd.json
   然后执行：
     catdesk browser-action "$(cat /tmp/osm-cmd.json)" > /tmp/osm-out.json

2) 回收结果（--extract）
   python3 run_js.py --extract /tmp/osm-out.json --save /tmp/osm-batch1.json
   python3 run_js.py --extract /tmp/osm-out.json --save /tmp/osm-results.json --append

取值规则（--set KEY=VALUE）：
  @/path/file.json  读文件并解析为 JSON（列表/对象/字符串都行）
  [..] {..} ".."    作为 JSON 字面量解析
  43 / 4.5 / true   作为 JSON 字面量解析（数字/布尔）
  其他              原样作为字符串（会自动加引号）

占位符在模板里长这样：const TASKS = __TASKS__;  （必须独立成 token）
"""

import argparse
import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"__([A-Z0-9_]+)__")


def parse_value(raw):
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as f:
            return json.load(f)
    stripped = raw.strip()
    if stripped and stripped[0] in '[{"' or stripped in ("true", "false", "null"):
        return json.loads(stripped)
    try:
        return json.loads(stripped)
    except (ValueError, TypeError):
        return raw


def build(args):
    template = open(args.template, encoding="utf-8").read()
    values = {}
    for item in args.set or []:
        if "=" not in item:
            raise SystemExit("--set 需要 KEY=VALUE 形式：%s" % item)
        key, raw = item.split("=", 1)
        values[key.strip()] = parse_value(raw)

    if args.slice_key:
        seq = values.get(args.slice_key)
        if not isinstance(seq, list):
            raise SystemExit("--slice-key %s 对应的值不是数组，无法切片" % args.slice_key)
        start = (args.slice_from or 1) - 1
        end = args.slice_to if args.slice_to else len(seq)
        values[args.slice_key] = seq[start:end]

    missing = sorted({m.group(1) for m in PLACEHOLDER.finditer(template)} - set(values))
    if missing:
        raise SystemExit("模板占位符没赋值：%s" % ", ".join("__%s__" % m for m in missing))

    def repl(match):
        return json.dumps(values[match.group(1)], ensure_ascii=False)

    script = PLACEHOLDER.sub(repl, template)
    command = {"action": "evaluate", "script": script}
    with open(args.cmd_out, "w", encoding="utf-8") as f:
        f.write(json.dumps(command, ensure_ascii=False))

    detail = ""
    if args.slice_key:
        detail = "第 %s-%s 条，共 %d 条" % (args.slice_from or 1,
                                       args.slice_to or "末", len(values[args.slice_key]))
    print(json.dumps({"cmd": args.cmd_out, "bytes": len(command["script"]),
                      "slice": detail or None}, ensure_ascii=False))
    print('执行：catdesk browser-action "$(cat %s)" > %s' % (args.cmd_out, args.stdout_out),
          file=sys.stderr)


def extract(args):
    text = open(args.extract, encoding="utf-8").read()
    payload = json.loads(text)
    if not payload.get("success", True):
        raise SystemExit("browser-action 返回失败：%s" % json.dumps(payload, ensure_ascii=False)[:400])
    result = (payload.get("data") or {}).get("result")
    if result is None:
        raise SystemExit("返回里没有 data.result：%s" % json.dumps(payload, ensure_ascii=False)[:400])
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            pass

    if args.append and os.path.exists(args.save):
        old = json.load(open(args.save, encoding="utf-8"))
        if isinstance(old, list) and isinstance(result, list):
            result = old + result
        elif isinstance(old, dict) and isinstance(result, dict):
            result = {**old, **result}
        else:
            raise SystemExit("--append 时旧结果与新结果类型不一致，无法合并")

    with open(args.save, "w", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2))
    summary = {
        "saved": args.save,
        "type": type(result).__name__,
        "size": len(result) if hasattr(result, "__len__") else None,
    }
    if isinstance(result, dict):
        for key in ("error", "weekNum", "weekIterationId", "counts", "errors", "invalid"):
            if key in result:
                summary[key] = result[key]
    print(json.dumps(summary, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", help="scripts/js/*.js 模板路径")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE", help="占位符赋值，可多次")
    ap.add_argument("--slice-key", help="需要按批次切片的占位符名，如 TASKS")
    ap.add_argument("--from", dest="slice_from", type=int, help="切片起始（1-based，含）")
    ap.add_argument("--to", dest="slice_to", type=int, help="切片结束（1-based，含）")
    ap.add_argument("--cmd-out", default="/tmp/osm-cmd.json", help="生成的 browser-action 命令文件")
    ap.add_argument("--stdout-out", default="/tmp/osm-out.json", help="browser-action stdout 落盘路径（仅提示）")
    ap.add_argument("--extract", help="回收模式：browser-action 的 stdout 文件")
    ap.add_argument("--save", help="回收模式：解析后的 JSON 落盘路径")
    ap.add_argument("--append", action="store_true", help="回收模式：与已有 --save 文件合并")
    args = ap.parse_args()

    if args.extract:
        if not args.save:
            raise SystemExit("--extract 必须同时给 --save")
        extract(args)
        return
    if not args.template:
        raise SystemExit("需要 --template（或用 --extract 走回收模式）")
    build(args)


if __name__ == "__main__":
    main()
