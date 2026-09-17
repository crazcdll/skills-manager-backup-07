#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元素定位命令 — 视图树采集、文案/图标/输入框定位。

涵盖 inspect-tree 采集、find-text/find-icon/find-input 定位、probe-status 探针诊断等 CLI 命令。
设备管理命令（install-app / force-stop / launch / set-location / disconnect / shell）请见 device_cmds.py。
"""
import json
import os

from core.errors import DeviceError
from core.util.paths import INSPECT_TREE_CACHE, INSPECT_TREE_PARSED, ensure_dirs
from context import get_platform_ops
from screen_state.inspect_tree import (
    dump_inspect_tree, parse_inspect_tree, _find_best_nodes, _center_of,
    find_anchor_neighborhood,
    MATCH_EXACT, MATCH_EXACT_DESC,
)


def _dump_parsed_text(nodes, local_parsed):
    """把节点的文本类属性落盘，供人工核对。"""
    with open(local_parsed, "w", encoding="utf-8") as f:
        for n in nodes:
            parts = []
            if n.get("text"):
                parts.append(f"mText={n['text']}")
            if n.get("content_desc"):
                parts.append(f"desc={n['content_desc']}")
            if n.get("m_id"):
                parts.append(f"mID={n['m_id']}")
            if parts:
                f.write(f"  [{n['class_name']}] " + " | ".join(parts) + "\n")


def _cmd_inspect_tree(args):
    """采集 Native 视图树并落盘，输出结构概览（只采集不查询，定位用 find-text/find-icon/find-input）。"""
    local_json = INSPECT_TREE_CACHE
    local_parsed = INSPECT_TREE_PARSED
    ensure_dirs()

    tree = dump_inspect_tree(wait_sec=getattr(args, "wait", 6))
    if tree is None:
        raise DeviceError("INSPECT-TREE FAIL: 采集失败")

    nodes = parse_inspect_tree(tree)
    text_count = sum(1 for n in nodes if n.get("all_text"))
    clickable_count = sum(1 for n in nodes if n["clickable"])
    icon_count = sum(1 for n in nodes
                     if n["clickable"] and not (n.get("all_text") or "").strip())

    print("INSPECT-TREE OK:")
    print(f"  本地缓存: {local_json} ({os.path.getsize(local_json)/1024:.0f} KB)")
    print(f"  节点总数: {len(nodes)} · 有文案 {text_count} · 可点击 {clickable_count} · 无文案图标 {icon_count}")
    _dump_parsed_text(nodes, local_parsed)
    print(f"  解析文本: {local_parsed}")
    print("  定位元素: find-text --text <文案> / find-icon --anchor <邻近文案> / find-input --anchor <锚点>")


def _cmd_find_text(args):
    """按文案定位元素，输出匹配节点及其点击坐标。"""
    keyword = args.text
    from screen_state.probes import probe_find_text, probe_list_texts
    tree = dump_inspect_tree(wait_sec=getattr(args, "wait", 6))
    if tree is not None:
        nodes = parse_inspect_tree(tree)
        ranked = _find_best_nodes(nodes, keyword)
        if ranked:
            labels = {
                MATCH_EXACT: "精确(mText)",
                MATCH_EXACT_DESC: "精确(contentDescription)",
            }
            print(f"FIND-TEXT OK: '{keyword}' 匹配 {len(ranked)} 处 [native]")
            print(f"  {'cx':>5s} {'cy':>5s}  {'匹配级别':<24s} {'可点击':<6s} 文案")
            for lv, _idx, n in ranked[:15]:
                c = _center_of(n)
                cx, cy = c if c else ("?", "?")
                shown = (n.get("text") or n.get("content_desc") or "")[:36]
                print(f"  {cx:>5} {cy:>5}  {labels.get(lv, 'L%s' % lv):<24s} "
                      f"{str(n['clickable']):<6s} {shown}")
            mtext_hits = [n for n in nodes if n.get("text") and keyword in n["text"]]
            desc_hits = [n for n in nodes
                         if not n.get("text") and n.get("content_desc") and keyword in n["content_desc"]]
            if desc_hits and not mtext_hits:
                print("  提示: 关键词仅出现在 contentDescription 中")
            return 0

    result = probe_find_text(keyword)
    if result["found"]:
        center = result.get("center")
        if center:
            print(f"FIND-TEXT OK: '{keyword}' 命中于 [{result['probe_name']}] 渲染层")
            print(f"  可点击坐标: ({center[0]}, {center[1]})")
            print(f"  💡 该文案位于 {result['probe_name']} 渲染层，坐标为设备物理像素，"
                  f"可直接用 `tap --x {center[0]} --y {center[1]}` 或 "
                  f"`step tap --action-x {center[0]} --action-y {center[1]}` 点击")
        else:
            print(f"FIND-TEXT OK: '{keyword}' 命中于 [{result['probe_name']}] 渲染层（无坐标）")
        return 0

    print(f"FIND-TEXT NOT_FOUND: '{keyword}'")
    near = [t for t in probe_list_texts(limit=30)
            if len(t) <= 20][:12]
    if near:
        print("  页面现有文案（探针链聚合，前 12 条）:")
        for t in near:
            print(f"    {t}")
    print("  若目标是无文案图标，改用 find-icon --anchor <邻近文案>")
    return 1


def _print_anchor_neighborhood(cmd_name, anchor, result):
    """打印 find_anchor_neighborhood 结果，find-icon/find-input 共用。"""
    matches = result["matches"]
    print(f"{cmd_name} OK: 锚点 '{anchor}' 命中 {len(matches)} 处，各自邻域结构如下"
          "（class 带\"(骨架)\"的节点仅用于连接结构，本身不是候选目标）：")
    for i, m in enumerate(matches):
        print(f"  --- 命中 #{i+1}：anchor_text={m['anchor_text']!r} hit_count={m['hit_count']} ---")
        print("  " + json.dumps(m["tree"], ensure_ascii=False))


def _cmd_find_icon(args):
    """以锚点文案定位其周边结构，用于挑出无文案的图标按钮。"""
    result = find_anchor_neighborhood(args.anchor, wait_sec=getattr(args, "wait", 6))
    if result["found"]:
        _print_anchor_neighborhood("FIND-ICON", args.anchor, result)
        return
    from screen_state.probes import probe_find_text
    wv = probe_find_text(args.anchor)
    if wv["found"]:
        print(f"FIND-ICON NOT_FOUND(native): 锚点 '{args.anchor}' 未在 native 视图树找到，"
              f"但存在于 [{wv['probe_name']}] 渲染层")
        if wv.get("center"):
            cx, cy = wv["center"]
            print(f"  该文案可点击坐标: ({cx}, {cy})")
            print(f"  💡 WebView 页面无结构邻域树，图标定位请改用 "
                  f"`find-text --text \"{args.anchor}\"` 获取坐标，或用截图目测后 "
                  f"`tap --x <x> --y <y>` 指定精确坐标")
        else:
            print(f"  💡 该文案在 WebView 中无坐标，请截图目测后 `tap --x <x> --y <y>` 执行")
        return 1
    print(f"FIND-ICON NOT_FOUND: 锚点 '{args.anchor}' 未在当前页面找到")
    print("  请先 find-text --text 确认页面现有文案，再选取图标邻近的文案作为锚点")
    return 1


def _cmd_find_input(args):
    """以锚点文案定位其周边结构，用于挑出目标输入框。"""
    result = find_anchor_neighborhood(args.anchor, wait_sec=getattr(args, "wait", 6))
    if result["found"]:
        _print_anchor_neighborhood("FIND-INPUT", args.anchor, result)
        return
    from screen_state.probes import probe_find_text
    wv = probe_find_text(args.anchor)
    if wv["found"]:
        print(f"FIND-INPUT NOT_FOUND(native): 锚点 '{args.anchor}' 未在 native 视图树找到，"
              f"但存在于 [{wv['probe_name']}] 渲染层")
        if wv.get("center"):
            cx, cy = wv["center"]
            print(f"  该文案可点击坐标: ({cx}, {cy})")
            print(f"  💡 WebView 页面无结构邻域树，输入框定位请改用 "
                  f"`find-text --text \"{args.anchor}\"` 获取坐标，或截图目测后 "
                  f"`tap --x <x> --y <y>` + `input-text --x <x> --y <y>` 执行")
        else:
            print(f"  💡 该文案在 WebView 中无坐标，请截图目测后执行")
        return 1
    print(f"FIND-INPUT NOT_FOUND: 锚点 '{args.anchor}' 未在当前页面找到")
    return 1


def _cmd_probe_status(args):
    """输出探针链健康状态（排查 webview DOM 定位问题的首选命令）。"""
    from screen_state.probes import probe_describe_chain, probe_list_texts
    print("=== 探针链健康状态 ===")
    chain = probe_describe_chain()
    if not chain:
        raise DeviceError("探针链为空（可能未初始化 flow-context）")
    for c in chain:
        pn = c.get("probe_name")
        avail = "✅ 可用" if c.get("available") else "❌ 不可用"
        print(f"\n[{pn}] {avail}")
        if pn == "native":
            continue
        if pn == "webview":
            print(f"  socket        : {c.get('socket')}")
            print(f"  端口转发      : {c.get('port')}")
            print(f"  CDP 不可达原因: {c.get('cdp_dead_reason')}")
            print(f"  CDP 页面数    : {c.get('page_count')}")
            print(f"  目标页面      : {c.get('target_url') or '(无)'}")
            print(f"  目标状态      : attached={'Y' if c.get('target_attached') else 'N'} "
                  f"visible={'Y' if c.get('target_visible') else 'N'} "
                  f"empty={'Y' if c.get('target_empty') else 'N'}")
            print(f"  DOM 文本行数  : {c.get('dom_text_lines')}")
            if c.get("dom_text_lines") == 0:
                print(f"  💡 DOM 文本为 0：可能选中了僵尸/未渲染页面，或 CDP 未读到内容")
        else:
            for k, v in c.items():
                if k not in ("probe_name", "available"):
                    print(f"  {k}: {v}")
    if getattr(args, "texts", False):
        print("\n=== 探针链聚合文本预览（前 30 条）===")
        for i, t in enumerate(probe_list_texts(limit=30), 1):
            print(f"  {i:>2}. {t}")