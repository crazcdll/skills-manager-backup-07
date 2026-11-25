#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Case 收尾补扫（post-scan）：先快速回到页面顶部，再自上而下补看 N 屏，只截图、不 dump。

【为什么先回顶】
  走查结束时页面停在**最后一步的位置**（可能在页面中部/底部，甚至被弹层覆盖）。
  以该位置为起点向下补看，只能覆盖「最后一步以下」的残余片段，AI 复核时读到的也是
  残缺、无序的画面。先快速回顶（纯手势、不截图）再自上而下连拍，补扫证据就是一份
  「从页面顶部开始、按页面自上而下」的完整画面序列，与人工走查的阅读顺序一致。

【与断言内 sweep 的分工】
  sweep     —— 断言未命中时的「就地取证」：1 屏，命中即停（assertions/ui/pipeline/sweep.py）；
  post-scan —— 整个 case 走查结束后的「收尾取证」：回顶后自上而下连拍最多
               POST_SCAN_SCROLLS 帧（首帧即顶部画面），一次性交给 AI 与「此前失败/待判定的
               步骤」比对，用于改判那些「仅仅因为不在当时视口内」而被判失败的断言。

【为什么不 dump】
  一次 uiautomator dump 8~25s，是取证的主要成本；N 屏 dump 会到分钟级。
  「文案有没有出现」交给 AI 读图判定即可，引擎只负责产出证据。

【到底判定（提前终止条件）】
  相邻两帧字节等价（size 相等且 md5 相同，或 size 差异 < SAME_SHOT_TOLERANCE）
  → 内容没有滚动 = 已到底（含「页面本来就不够一屏、不可滚动」的短页面，此时只剩顶部
  一帧）：删掉这张重复帧并立即结束。
  注意这是「提前终止」而不是「保证滚满」：**无限滚动**页面永远不相等，
  由 POST_SCAN_SCROLLS 这个硬上限兜住，不会死循环。

【成本】
  回顶 = 8 次纯手势 ≈ 1.2s（不截图、不 dump）；
  单帧 = 滑动 250ms + 稳定 250ms + 截图 0.3~0.9s ≈ 0.8~1.4s；
  5 帧上限 ≈ 4~7s，加上回顶总 ≈ 5~8s（仍低于一次 dump）。
"""

from __future__ import annotations

import hashlib
import os
import time

from aitest.shared.context import get_platform_ops
from aitest.shared.records import alloc_shot_seq, frame_path
from aitest.execution.screen.screen_layout import ScreenLayout


# ─── 补扫参数（调整入口：这里改默认值 / 命令 --scrolls 单次覆盖） ──────────
POST_SCAN_SCROLLS = 5          # 补看帧数**上限**（含顶部首帧；到底即提前结束，不是固定值）
SWIPE_RATIO = 0.7              # 每屏滑动幅度（相对手势区域全幅，自上而下取证用）
SWIPE_DURATION_MS = 250        # 单次滑动时长（取证滑动，不需要拖拽跟手感）
SETTLE_SEC = 0.25              # 滑动后等待渲染稳定
SAME_SHOT_TOLERANCE = 0.002    # 相邻两帧字节差异 <0.2% 视为同一画面（已到底）

# 回顶阶段（纯手势、不截图）：只需覆盖「本 case 会向下补看的屏数」即可，
# 页面不足这么长时反复滑到底不会产生额外副作用（内容到顶后不再移动）。
SCROLL_TO_TOP = True           # 默认先把页面滚回顶部（命令 --no-reset-top 可临时关闭）
TOP_RESET_SWIPES = 8           # 回顶滑动次数（0.8 屏/次 ≈ 覆盖 6 屏高度，留足余量）
TOP_RESET_RATIO = 0.8          # 回顶滑动幅度（比取证滑动略大：只求快，不留证据）
TOP_RESET_DURATION_MS = 180    # 回顶滑动时长


def _swipe_down(layout, ratio=SWIPE_RATIO):
    """向页面下方滚动一屏（物理手指上滑：内容上移，露出下方内容）。

    `_do_swipe` 采用**函数内延迟导入**：handlers.base 与 assertions 包存在
    既有循环导入，模块级引入会让「先导入本模块」的入口（工具/单测）直接嗝。
    """
    from aitest.execution.steps.handlers.base import _do_swipe

    full = layout.swipe_area_bottom - layout.swipe_area_top
    step = max(int(full * ratio), 200)
    _do_swipe(direction="up",
              y_from=layout.swipe_area_bottom,
              y_to=layout.swipe_area_bottom - step,
              dur=SWIPE_DURATION_MS)


def _swipe_to_top(layout, swipes=TOP_RESET_SWIPES):
    """快速回到页面顶部：小步长连滑（物理手指下滑 = 内容下移，露出上方内容）。

    不截图、不 dump —— 这一段只为把取证起点挪到顶部，任何画面都不进证据，
    所以用「更大幅度 + 更短时长 + 固定次数」，成本 ≈ 1s 且与页面高度无关。
    页面不足这么长时，后续滑动不会改变内容，不会引入额外状态。
    """
    from aitest.execution.steps.handlers.base import _do_swipe

    full = layout.swipe_area_bottom - layout.swipe_area_top
    step = max(int(full * TOP_RESET_RATIO), 200)
    for _ in range(max(int(swipes), 1)):
        _do_swipe(direction="down",
                  y_from=layout.swipe_area_top,
                  y_to=layout.swipe_area_top + step,
                  dur=TOP_RESET_DURATION_MS)


def _capture(ops, path):
    """截一张图；失败返回 False（不阻断补扫）。"""
    try:
        return bool(ops.screenshot(path)) and os.path.exists(path)
    except Exception:  # noqa: BLE001 —— 取证失败降级为帧数变少
        return False


def _same_frame(prev_path, cur_path):
    """相邻两帧是否同一画面（到底信号）。

    字节完全一致 → 同一画面；字节数差异极小（<SAME_SHOT_TOLERANCE）→ 只是状态栏
    时钟变了，内容没有滚动。无 Pillow 时这是最便宜且稳定的「到底」信号。
    """
    if not prev_path or not cur_path:
        return False
    try:
        size_a, size_b = os.path.getsize(prev_path), os.path.getsize(cur_path)
    except OSError:
        return False
    if size_a == size_b:
        try:
            with open(prev_path, "rb") as fa, open(cur_path, "rb") as fb:
                return hashlib.md5(fa.read()).digest() == hashlib.md5(fb.read()).digest()
        except OSError:
            return False
    return abs(size_a - size_b) / max(size_a, size_b) < SAME_SHOT_TOLERANCE


def capture_frames(case_ws, scrolls=POST_SCAN_SCROLLS, reset_to_top=SCROLL_TO_TOP):
    """回到页面顶部后，自上而下连拍最多 scrolls 帧（不 dump 视图树）。

    帧序 = 页面自上而下顺序：第 1 帧是顶部画面（回顶后先截），其后每帧先向下滑一屏。

    截图落在 `<case_ws>/frames/`（override-step-result --img 只认该目录下的文件，
    放这里命中帧才能直接作为改判证据被报告引用），文件名 `postscan_down<i>_<seq>.png`。

    Args:
        scrolls: 帧数上限（含顶部首帧）。
        reset_to_top: 是否先快速回顶；关闭时退回「从当前位置向下补看」的旧行为。

    Returns:
        dict:
          applicable      bool  是否产出至少一帧
          frames          list  [{index, name, path}]，按页面自上而下顺序
          scrolls_done    int   实际完成的向下滚动次数（= 帧数 - 1）
          reset_to_top    bool  本次是否执行了回顶
          stopped_reason  str   max_scrolls / boundary / shot_failed / no_device
    """
    result = {"applicable": False, "frames": [], "scrolls_done": 0,
              "reset_to_top": bool(reset_to_top), "stopped_reason": "no_device"}
    try:
        ops = get_platform_ops()
        layout = ScreenLayout.from_ops(ops)
    except Exception:  # noqa: BLE001 —— 无设备/无法取布局时降级
        return result

    if reset_to_top:
        # 起点对齐到页面顶部：证据固定是「顶部 → 向下」的完整序列，先回顶再取证
        _swipe_to_top(layout)
        time.sleep(SETTLE_SEC)

    prev_path = None
    result["stopped_reason"] = "max_scrolls"
    for i in range(1, max(int(scrolls), 1) + 1):
        if i > 1:
            # 首帧即顶部画面（回顶后直接取证），其后每帧先滑一屏再截
            _swipe_down(layout)
            time.sleep(SETTLE_SEC)
        name = f"postscan_down{i}_{alloc_shot_seq(case_ws)}.png"
        path = frame_path(case_ws, name)
        if not _capture(ops, path):
            result["stopped_reason"] = "shot_failed"
            break
        if prev_path and _same_frame(prev_path, path):
            # 画面没滚动 = 已到底（或页面不可滚动）：这张是重复证据，删掉不留噪声
            try:
                os.remove(path)
            except OSError:
                pass
            result["stopped_reason"] = "boundary"
            break
        result["frames"].append({"index": i, "name": name, "path": path})
        result["scrolls_done"] = i - 1
        prev_path = path

    result["applicable"] = bool(result["frames"])
    return result


__all__ = [
    "POST_SCAN_SCROLLS", "SWIPE_RATIO", "SWIPE_DURATION_MS", "SETTLE_SEC",
    "SAME_SHOT_TOLERANCE", "SCROLL_TO_TOP", "TOP_RESET_SWIPES", "TOP_RESET_RATIO",
    "TOP_RESET_DURATION_MS", "capture_frames",
]
