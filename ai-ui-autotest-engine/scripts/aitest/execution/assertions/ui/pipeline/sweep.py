#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""当前位置的滚动补看（scroll sweep）—— 断言用。

【扫描顺序（固定）】
  1. 不移动页面：直接采集当前视图树（MRN 的 dump 自带视口外节点，
     经常一次就能覆盖目标，命中即结束，不产生任何滚动截图）
  2. 仍未命中 → 向下补看 1 屏：滑动 1 次 + 截图 1 张（不再重复采集）
  3. 结束：停在当前位置，不回滚（后续步骤入口通常自带滚动/定位）

【为什么不滑到顶部】
断言关心的是「页面有没有这个文案」，不依赖从哪里开始看。从当前位置直接
取证，省掉盲滑到顶的 6~10s；向下补 1 屏已经覆盖绝大多数「首屏没有」的场景。

【为什么滚动时不再 dump】
一次 uiautomator dump 在这台设备上要 8~25s，是扫描的主要成本（滑动 + 截图
只要 ~3s）。截图已经足以作为「文案是否出现」的证据：程序化命中在第一次
dump 里就能拿到，拿不到的直接把截图交给 AI 判定。

【截图数量】
一次扫描 = 当前屏 1 张 + 向下 1 张；同一步内的后续断言复用同一组截图
（见 _SWEEP_CACHE），不会每条断言各截一遍。

【截图命名】
`<sid>_<断言id>_cur0.png` / `<sid>_<断言id>_down1.png`：**必须带 sid**——
同一 case 内多个步骤都会做补看取证，只按断言 id 命名会让后一步覆盖掉前一步的证据。
"""

from __future__ import annotations

import hashlib
import os
import sys
import time

from aitest.shared.context import get_platform_ops
from aitest.execution.screen.screen_layout import ScreenLayout
from aitest.execution.screen.inspect_tree import (
    find_substring_candidates,
    get_current_nodes,
    invalidate_cache,
    _find_best_nodes,
)
from aitest.execution.steps.handlers.base import _do_swipe


# ─── 扫描参数（成本：一次 dump + 向下 1 屏 ~3s） ────────────────────────
MAX_DOWN_SCREENS = 1      # 默认只向下补看 1 屏（绝大多数“首屏没有”的文案就在下一屏）
SWIPE_RATIO = 0.7         # 每屏滑动幅度（相对手势区域全幅）
SWIPE_DURATION_MS = 250   # 单次滑动时长（取证滑动，不需要长按拖拽的跟手感）
SETTLE_SEC = 0.25         # 滑动后等待渲染稳定
DUMP_WAIT_SEC = 2         # 当前屏采集超时
CACHE_TTL_SEC = 120       # 同页面整页截图的复用窗口（同一步多条断言共用一次扫描）

# 同页面（同一步骤）的整页快照缓存：同一步内多条断言只扫一次
_SWEEP_CACHE = {"case_ws": None, "step_key": None, "cur_md5": "", "ts": 0.0,
                "data": None}


def _fingerprint(nodes):
    """节点集合指纹（文案 + 视口偏移）。"""
    if not nodes:
        return "0:empty"
    parts = []
    for n in nodes:
        text = n.get("text") or n.get("content_desc") or ""
        parts.append(f"{text}|{n.get('viewport_offset')}|{n.get('viewport_offset_x')}")
    digest = hashlib.md5("\u0001".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{len(nodes)}:{digest}"


def _swipe_view(direction, layout, ratio=SWIPE_RATIO):
    """按比例滚动一屏。

    direction 为**用户语义**（想看的方向）：
      "down" → 想看下方 → 物理上滑；"up" → 想看上方 → 物理下滑。
    """
    full = layout.swipe_area_bottom - layout.swipe_area_top
    step = max(int(full * ratio), 200)
    if direction == "down":
        _do_swipe(direction="up",
                  y_from=layout.swipe_area_bottom,
                  y_to=layout.swipe_area_bottom - step,
                  dur=SWIPE_DURATION_MS)
    else:
        _do_swipe(direction="down",
                  y_from=layout.swipe_area_top,
                  y_to=layout.swipe_area_top + step,
                  dur=SWIPE_DURATION_MS)


def _shot(path):
    """截一张图；失败返回 None（不阻断扫描）。"""
    try:
        ok = get_platform_ops().screenshot(path)
        return path if ok and os.path.exists(path) else None
    except Exception:  # noqa: BLE001
        return None


def _file_md5(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return ""


def _same_shot(prev_path, cur_path):
    """两屏截图是否同一画面（到底判定）。

    字节完全一致 → 同一画面；字节数差异极小（<0.2%）→ 也只是状态栏时钟变了，
    内容没有滚动。无 Pillow 时这是最便宜且稳定的“到底”信号。
    """
    if not prev_path or not cur_path:
        return False
    if os.path.getsize(prev_path) == os.path.getsize(cur_path):
        return _file_md5(prev_path) == _file_md5(cur_path)
    try:
        a, b = os.path.getsize(prev_path), os.path.getsize(cur_path)
    except OSError:
        return False
    return abs(a - b) / max(a, b) < 0.002


def _match_expects(nodes, expects):
    """在节点集合中匹配所有待查文案（同一步多条断言合并一次扫描）。

    Args:
        expects: {assert_id: expect_text}

    Returns:
        {assert_id: {"match_level", "matched_text", "node", "verdict", "in_viewport"}}
        口径与 T1/T1.5 一致：L0/L1 精确 → exact；唯一子串 → semantic；
        多形态子串（语义不确定）→ 不命中，交策略层原有 T2 流程。
    """
    hits = {}
    for aid, text in expects.items():
        ranked = _find_best_nodes(nodes, text)
        if ranked:
            level, _idx, node = ranked[0]
            hits[aid] = {
                "match_level": level,
                "matched_text": (node.get("text") or node.get("content_desc") or text),
                "node": node,
                "verdict": "exact",
                "in_viewport": node.get("in_viewport", True),
            }
            continue
        candidates = find_substring_candidates(nodes, text)
        if not candidates:
            continue
        forms = {(c[2].get("text") or c[2].get("content_desc") or "").strip()
                 for c in candidates}
        if len(forms) == 1:
            node = candidates[0][2]
            hits[aid] = {
                "match_level": candidates[0][0],
                "matched_text": next(iter(forms)),
                "node": node,
                "verdict": "semantic",
                "in_viewport": node.get("in_viewport", True),
            }
    return hits


def sweep_for_texts(expects, *, case_ws=None, tag="", max_down=MAX_DOWN_SCREENS,
                    ratio=SWIPE_RATIO, step_key=None):
    """当前位置取证：采集一次 → 未命中向下补看 1 屏截图（不回滚）。

    Args:
        expects: {assert_id: expect_text}，同一步多条断言一次扫描完成
        case_ws: case 工作目录；提供时每屏截图落 `<case_ws>/diagnostics/sweep/`
        tag: 截图文件名前缀（通常传断言 id）
        max_down: 向下最多扫几屏（默认 1）
        ratio: 每屏滑动幅度
        step_key: 步骤标识（如 sid）；同一步内多次调用直接复用第一次的扫描结果

    Returns:
        dict:
          applicable     bool   是否完成扫描
          hits           dict   命中信息 {assert_id: {...}}
          scans          list   各屏记录 [{index, screenshot, hit_ids}]
          screens        int    产生的截图数
          screenshots    list   截图路径（当前屏 + 向下补看屏）
          stopped_reason str    hit / boundary / max_swipes / no_tree  等
          restored       bool   是否已回到取证起点（不回滚，恒为 False）
          start_fingerprint str
    """
    result = {
        "applicable": False, "hits": {}, "scans": [], "screens": 0, "screenshots": [],
        "stopped_reason": "no_tree", "restored": False, "start_fingerprint": "",
        "nodes": [],
    }
    if not expects:
        return result

    prefix = tag or next(iter(expects))
    # 文件名带 sid：同 case 内多个步骤都会补看取证，只按断言 id 命名会互相覆盖证据
    stem = f"{step_key}_{prefix}" if step_key else prefix
    shot_dir = None
    if case_ws:
        shot_dir = os.path.join(case_ws, "diagnostics", "sweep")
        try:
            os.makedirs(shot_dir, exist_ok=True)
        except Exception:  # noqa: BLE001
            shot_dir = None

    def _sweep_shot(name):
        if not shot_dir:
            return None
        return _shot(os.path.join(shot_dir, f"{stem}_{name}.png"))

    def _record(shot_path, hit_ids):
        result["scans"].append({
            "index": len(result["scans"]),
            "screenshot": shot_path or "",
            "hit_ids": sorted(hit_ids),
        })
        if shot_path:
            result["screenshots"].append(shot_path)
        result["screens"] += 1

    # 0) 同一步骤已经扫过整页 → 直接复用那组截图与视图树，不再滚动/采集
    cached = _SWEEP_CACHE["data"]
    same_step = step_key is not None and _SWEEP_CACHE["step_key"] == step_key
    if (cached and _SWEEP_CACHE["case_ws"] == case_ws and same_step
            and time.time() - _SWEEP_CACHE["ts"] <= CACHE_TTL_SEC):
        hits = _match_expects(cached["nodes"], expects)
        result.update(applicable=True, hits=hits, restored=False,
                      start_fingerprint=cached.get("fingerprint", ""),
                      nodes=cached["nodes"])
        result["screenshots"] = list(cached["screenshots"])
        result["screens"] = len(result["screenshots"])
        result["scans"] = [{"index": 0, "screenshot": (cached["screenshots"] or [""])[0],
                            "hit_ids": sorted(hits.keys())}]
        result["stopped_reason"] = "hit" if hits else cached["stopped_reason"]
        return result

    layout = ScreenLayout.from_ops(get_platform_ops())

    # 1) 当前位置直接采集一次（不移动页面）
    invalidate_cache()
    nodes = get_current_nodes(wait_sec=DUMP_WAIT_SEC)
    if nodes is None:
        return result

    start_fp = _fingerprint(nodes)
    result["start_fingerprint"] = start_fp
    result["nodes"] = nodes
    cur_shot = _sweep_shot("cur0")

    # 2) 当前这一棵视图树直接匹配（MRN dump 含视口外节点）
    hits = _match_expects(nodes, expects)
    _record(cur_shot, list(hits.keys()))
    if hits:
        result.update(applicable=True, hits=hits, stopped_reason="hit")
        _save_cache(case_ws, step_key, cur_shot, nodes, start_fp, result)
        return result

    # 3) 向下补看：默认只滑 1 屏、只截 1 张（dump 是主要耗时来源，不再逐屏采集）
    prev_shot = cur_shot
    boundary = False
    for i in range(1, max_down + 1):
        _swipe_view("down", layout, ratio)
        time.sleep(SETTLE_SEC)
        shot = _sweep_shot(f"down{i}")
        if not shot or (prev_shot and _same_shot(prev_shot, shot)):
            boundary = True          # 画面没变 = 到底（或页面不可滚动），这一屏不重复留证据
            break
        _record(shot, [])
        prev_shot = shot

    # 4) 结束：不回滚，停在当前位置
    result.update(applicable=True, restored=False)
    result["stopped_reason"] = "boundary" if boundary else "max_swipes"
    _save_cache(case_ws, step_key, cur_shot, nodes, start_fp, result)
    return result


def _save_cache(case_ws, step_key, cur_shot, nodes, fingerprint, result):
    """记录本次取证，供同一步后续断言复用（同一页面不再滚动+采集）。"""
    _SWEEP_CACHE.update({
        "case_ws": case_ws,
        "step_key": step_key,
        "cur_md5": _file_md5(cur_shot) if cur_shot else "",
        "ts": time.time(),
        "data": {
            "nodes": nodes,
            "fingerprint": fingerprint,
            "screenshots": list(result.get("screenshots") or []),
            "stopped_reason": result.get("stopped_reason", ""),
        },
    })


def safe_sweep(expects, *, case_ws=None, tag="", step_key=None):
    """扫描的容错包装：取证失败（dump/滑动异常）不得影响断言主流程。"""
    try:
        return sweep_for_texts(expects, case_ws=case_ws, tag=tag, step_key=step_key)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ 整页滚动扫描异常（忽略，按原流程继续判定）: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return {}


def sweep_evidence(outcome, hit_id=None):
    """把扫描结果压缩成可写入断言 evidence 的摘要（供报告与人工复核）。"""
    if not outcome or not outcome.get("applicable"):
        return {}
    summary = {
        "screens": outcome.get("screens", 0),
        "stopped_reason": outcome.get("stopped_reason", ""),
        "restored": bool(outcome.get("restored", False)),
        "screenshots": outcome.get("screenshots", []),
    }
    if hit_id and hit_id in (outcome.get("hits") or {}):
        hit = outcome["hits"][hit_id]
        for scan in outcome.get("scans", []):
            if hit_id in (scan.get("hit_ids") or []):
                summary["hit_screen"] = scan["index"]
                summary["hit_screenshot"] = scan.get("screenshot", "")
                break
        summary["hit_level"] = hit.get("match_level")
        summary["hit_in_viewport"] = hit.get("in_viewport", True)
    return summary


__all__ = [
    "MAX_DOWN_SCREENS", "SWIPE_RATIO",
    "sweep_for_texts", "safe_sweep", "sweep_evidence",
    "_match_expects", "_fingerprint",
]
