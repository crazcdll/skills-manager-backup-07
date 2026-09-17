#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针链聚合层：聚合 native / webview 等多渲染探针的结果。

供 locators.find-text/find-icon/find-input 与 probe-status 使用，
与断言/交互通道（inspect_tree_has_text / inspect_tree_find_center）
同源，保证"断言能过、定位能找到"的一致性。

核心思想：渲染层由谁绘制，就由哪个探针回答——native 查视图树，
webview 查 CDP DOM，二者都是只读查询，聚合时不重复采集。
"""
import sys

from core.errors import soft_fail
from screen_state.inspect_tree import native_find_center, list_text_nodes


def probe_chain():
    """返回当前探针链（惰性初始化，见 context.get_probes）。"""
    from context import get_probes
    return get_probes()


def probe_find_text(text) -> dict:
    """探针链级文本定位：依次询问 native → webview，返回首个命中的探针结果。

    与断言通道（inspect_tree_has_text）同源，但额外返回坐标与来源标识。

    Returns:
        dict: {"found": bool, "probe_name": str|None,
               "center": (cx,cy)|None, "matched_text": str|None}
    """
    native = native_find_center(text, detail=True)
    if native is not None:
        if isinstance(native, dict):
            return {
                "found": True,
                "probe_name": "native",
                "center": native.get("center"),
                "matched_text": native.get("matched_text") or text,
            }
        return {"found": True, "probe_name": "native",
                "center": native, "matched_text": text}
    for probe in probe_chain():
        if probe.probe_name == "native":
            continue
        try:
            if probe.find_text(text):
                center = probe.find_center(text)
                return {
                    "found": True,
                    "probe_name": probe.probe_name,
                    "center": center,
                    "matched_text": text,
                }
        except Exception as e:
            sys.stderr.write(f"  ⚠️  {probe.probe_name} 探针定位失败: {e}\n")
    return {"found": False, "probe_name": None, "center": None, "matched_text": None}


def probe_list_texts(limit=None) -> list:
    """探针链级文本聚合：native 视图树 + webview DOM 的全部可见文本。

    native 优先（按 y 坐标排序），webview 追加（避免重复行）。
    """
    seen = set()
    merged = []

    def _append(text):
        t = (text or "").strip()
        if t and t not in seen:
            seen.add(t)
            merged.append(t)

    try:
        for it in list_text_nodes(wait_sec=3, max_attempts=1):
            _append(it["text"])
    except Exception as e:
        soft_fail("device", "PROBE_LIST_TEXTS_FAILED", e)
    for probe in probe_chain():
        if probe.probe_name == "native":
            continue
        try:
            for line in probe.list_texts():
                _append(line)
        except Exception as e:
            sys.stderr.write(f"  ⚠️  {probe.probe_name} 文本列表失败: {e}\n")
    if limit is not None:
        return merged[:limit]
    return merged


def probe_describe_chain() -> list:
    """探针链健康状态摘要，供 [DIAG] 与 probe-status 命令输出。"""
    out = []
    for probe in probe_chain():
        info = {"probe_name": probe.probe_name, "available": probe.available()}
        describe = getattr(probe, "describe", None)
        if callable(describe):
            try:
                info.update(describe())
            except Exception as e:
                info["describe_error"] = str(e)
        out.append(info)
    return out