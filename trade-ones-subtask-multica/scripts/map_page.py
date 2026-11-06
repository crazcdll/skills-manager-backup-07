#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「涉及页面」→ Multica 项目 的映射（与 trade-ones-multica/scripts/map_page.py 内容一致，改一处必须同步另一处）。

一个项目对应多个页面叫法，所以不能只做完全匹配：
先按别名/项目名做归一化精确匹配，再做包含匹配（取最长别名），都命中不了就留空。

用法：
  multica --workspace-id "$WS" project list --output json > /tmp/projects.json
  python3 map_page.py --projects /tmp/projects.json --pages "主提单"
  python3 map_page.py --projects /tmp/projects.json --json '["超团提单","主提单","单详页"]'

输出（单条）：
  {"page":"主提单","project":"酒店提单页","projectId":"4d4e...","match":"alias","reason":""}
  {"page":"未知页","project":"","projectId":"","match":"none","reason":"未命中映射表"}
"""

import argparse
import json
import re
import sys

# ── 映射表：Multica 项目标题 → 该项目的页面叫法（项目标题本身也算一个叫法）──
# 只放语义确定的叫法，不放「提单」这种会把「超团提单」抢走的通用短词。
PAGE_ALIASES = {
    "酒店提单页": ["主提单", "新提单", "DUO提单", "主流程提单页", "主流程提单", "提单页"],
    "超团提单": ["超团提单", "超团"],
    "住宿活包提单页": ["住宿活包提单页", "活包提单页", "活包提单"],
    "酒店订单详情页": ["单详页", "订单详情页", "订单详情", "单详"],
    "退款详情页（前端+后端API）": ["退款详情页", "退款详情"],
    "退款页面": ["退款页面", "退款页"],
    "非房二期": ["非房二期", "非房"],
    "取消流程一致性": ["取消流程一致性", "取消流程"],
    "消费券": ["消费券"],
}

# 页面名里常见的噪声词，宽松归一化时去掉
NOISE_RE = re.compile(r"(页面|项目|相关|模块|改造|需求|\s)")


def norm(text):
    s = (text or "").strip().lower()
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", s)


def norm_loose(text):
    """更宽松的归一化：额外去掉「页面/项目/相关/模块」等噪声词。"""
    return NOISE_RE.sub("", norm(text))


def build_index(projects):
    """项目标题 → id；同时把映射表里已不存在的项目剔掉并给出提示。"""
    by_title = {norm(p.get("title", "")): p for p in projects or []}
    aliases = []
    dangling = []
    for title, names in PAGE_ALIASES.items():
        proj = by_title.get(norm(title))
        if not proj:
            dangling.append(title)
            continue
        for name in names + [title]:
            aliases.append((norm(name), norm_loose(name), title, proj.get("id", "")))
    # 项目标题本身也进索引（映射表没登记的新项目走同名匹配）
    for p in projects or []:
        t = p.get("title", "")
        aliases.append((norm(t), norm_loose(t), t, p.get("id", "")))
    return aliases, dangling


def resolve(page, aliases):
    p, pl = norm(page), norm_loose(page)
    if not p:
        return {"page": page, "project": "", "projectId": "", "match": "none",
                "reason": "涉及页面为空"}

    # 1) 精确：页面 == 某个叫法（或项目标题）
    hits = [a for a in aliases if a[0] == p or (pl and a[1] == pl)]
    titles = sorted({h[2] for h in hits})
    if len(titles) == 1:
        return {"page": page, "project": titles[0],
                "projectId": next(h[3] for h in hits if h[2] == titles[0]),
                "match": "exact", "reason": ""}
    if len(titles) > 1:
        return {"page": page, "project": "", "projectId": "", "match": "conflict",
                "reason": "精确匹配到多个项目：%s" % "、".join(titles)}

    # 2) 包含：页面里含某个叫法，取最长（最具体的）那条
    cands = [a for a in aliases if a[0] and a[0] in p]
    if cands:
        longest = max(len(a[0]) for a in cands)
        top = [a for a in cands if len(a[0]) == longest]
        titles = sorted({a[2] for a in top})
        if len(titles) == 1:
            return {"page": page, "project": titles[0], "projectId": top[0][3],
                    "match": "contains", "reason": "命中别名「%s」" % top[0][0]}
        return {"page": page, "project": "", "projectId": "", "match": "conflict",
                "reason": "「%s」同时命中多个项目：%s" % (top[0][0], "、".join(titles))}

    # 3) 兜底：页面名被项目标题包含（项目名比页面叫法更长时）
    cands = [a for a in aliases if p in a[0]]
    if cands and len({a[2] for a in cands}) == 1:
        return {"page": page, "project": cands[0][2], "projectId": cands[0][3],
                "match": "contains", "reason": "页面名被项目标题包含"}

    return {"page": page, "project": "", "projectId": "", "match": "none",
            "reason": "未命中映射表，请补一条别名或直接指定项目"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", help="multica project list --output json 的输出文件")
    ap.add_argument("--pages", action="append", default=[], help="单个页面名，可多次传")
    ap.add_argument("--json", help="页面名 JSON 数组字符串")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    projects = json.load(open(args.projects, encoding="utf-8")) if args.projects else []
    pages = list(args.pages)
    if args.json:
        pages += json.loads(args.json)
    if not pages:
        raise SystemExit("需要 --pages 或 --json")

    aliases, dangling = build_index(projects)
    out = [resolve(p, aliases) for p in pages]
    if dangling:
        print("提示：映射表里这些项目在当前工作区不存在，已跳过：%s" % "、".join(dangling),
              file=sys.stderr)
    print(json.dumps(out[0] if len(out) == 1 else out,
                     ensure_ascii=False, indent=1 if args.pretty else None))


if __name__ == "__main__":
    main()
