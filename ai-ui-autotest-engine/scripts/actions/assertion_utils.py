#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 自动化测试共享底层工具——被 commands/* / step/* 共享，无模块级状态，避免循环依赖。"""
import os
import re
import time

from core.errors import UsageError, soft_fail
from core.util.paths import RUN_DIR, ensure_dirs, active_case_context_path, get_active_case
from core.util.case_utils import current_case_workspace, resolve_case_path
from core.util.records import frame_path
from core.flow.flow_context import load_context
from context import get_platform_ops, get_app_descriptor
from screen_state.screen_layout import ScreenLayout
from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree, invalidate_cache

def auto_dismiss_recce(raw=None) -> bool:
    """检测 Recce 调试浮层并在必要时拖到右上角，返回是否执行了拖拽操作。"""
    ops = get_platform_ops()
    prefixes = get_app_descriptor().debug_overlay_prefixes
    recce_prefix = next((p for p in prefixes if "recce" in p), None)
    if not recce_prefix:
        return False

    try:
        layout = ScreenLayout.from_ops(ops)
    except Exception:
        layout = ScreenLayout(1080, 2340)

    if raw is None:
        raw = dump_inspect_tree()
    if raw is None:
        return False

    overlay_nodes = [
        node for node in parse_inspect_tree(raw)
        if node["class_name"].startswith(recce_prefix)
        and node["clickable"]
        and None not in (node["x"], node["y"], node["w"], node["h"])
    ]
    if not overlay_nodes:
        return False

    node = overlay_nodes[0]
    cx = min(max(node["x"] + node["w"] // 2, 1), layout.width - 2)
    cy = min(max(node["y"] + node["h"] // 2, 1), layout.height - 2)

    if layout.is_in_recce_corner(cx, cy):
        return False

    if not ops.swipe(cx, cy, layout.recce_corner_x, layout.recce_corner_y, duration_ms=1500):
        return False
    time.sleep(0.8)
    return True


def _try_shoot_for_diagnosis(gone_text: str):
    """截取诊断现场图，统一归档到当前 case 的 frames/ 目录；无活跃 Flow 时退回 .run 顶层。"""
    try:
        ensure_dirs()
        safe_tag = re.sub(r"[^\w\u4e00-\u9fff]+", "_", gone_text)[:20] or "diag"
        case_name = get_active_case()
        root_dir = resolve_case_path(case_name)
        ctx = load_context(root_dir) if case_name and active_case_context_path() else None
        if ctx:
            out_path = frame_path(current_case_workspace(root_dir, ctx), f"diag_{safe_tag}.png")
        else:
            out_path = os.path.join(RUN_DIR, f"_diag_{safe_tag}.png")
        ops = get_platform_ops()
        if not ops.screenshot(out_path):
            return None
        if os.path.isfile(out_path):
            return out_path
    except Exception as e:
        soft_fail("device", "DIAGNOSTIC_SHOT_FAILED", e)
    return None

def format_visual_check_hint(label: str, shot_path: str, judge_desc: str = "") -> str:
    """统一生成 [NEEDS_VISUAL_CHECK] 提示文案，避免各处手写措辞不一致。"""
    base = (f"{label}: [NEEDS_VISUAL_CHECK] 该截图已自动拍摄（内部已等待渲染/操作完成），"
            f"直接读取此文件判定即可，无需 sleep 等待或重新执行 screenshot 命令")
    if judge_desc:
        base += f"（{judge_desc}）"
    return f"{base}: {shot_path}"

def _resolve_step_ok(args=None, *, passed=False, failed=False, ok=None, allow_none=False):
    """解析步骤判定：1=通过 / 0=失败 / 2=警告；allow_none 时可返回 None=无判定。

    常规记录必须用 --pass/--fail/--ok 显式声明判定，避免忘写导致结论丢失。
    allow_none 专用于「只记备注、不做判定」的场景（如 action 文案口径差异）：
    返回 None → 记录携带 ok=None → 报告层归入 annotations/notes，不参与统计。

    支持两种调用方式：
    1. 从 argparse Namespace：_resolve_step_ok(args) — 自动读取 passed/failed/ok
    2. 从 keyword args：_resolve_step_ok(passed=..., failed=..., ok=...)
    """
    if args is not None:
        passed = getattr(args, "passed", False)
        failed = getattr(args, "failed", False)
        ok = getattr(args, "ok", None)

    if passed and failed:
        raise UsageError("--pass 与 --fail 不能同时传")
    if passed:
        return 1
    if failed:
        return 0

    if ok is not None:
        return ok

    if allow_none:
        return None

    raise UsageError(
        "必须显式指定结果：--pass（通过）/ --fail（失败）/ --ok 2（警告）；"
        "只记备注不做判定时请传 --note <说明>。"
    )
