#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook-info CLI 命令。

职责：按需查询单个 hook 的完整 cli_hint（模板 + 运行时参数现场渲染）。

背景：hook 实例持久化到 flow-context 时只携带 id/desc/required/hint_params，
不再存 cli_hint 全文（见 core/sop/hook_render.py::_finalize_hooks）。AI 需要 hook 的
完整操作指引时，用本命令查询一次即可，替代早期"每步全量打印"的模式。
"""

from core.errors import PayloadError
from core.util.case_utils import resolve_case_path
from core.flow.flow_context import load_context
from core.sop.hook_templates import get_hook_template
from core.sop.hook_render import render_hook_cli_hint


def _find_hook_instance(ctx, hook_id, sid=None):
    """在 flow-context 中查找 hook 实例（携带 hint_params）。

    优先级：指定 sid 的步骤 > 第一个包含该 hook 的步骤。
    返回 (hook_dict | None, sid | None)。
    """
    for s in ctx.get("steps", []):
        if sid and s.get("sid") != sid:
            continue
        for h in s.get("hooks", []):
            if h.get("id") == hook_id:
                return h, s.get("sid")
    return None, None


def _cmd_hook_info(args):
    """hook-info --hook-id ID [--sid SID]: 输出单个 hook 的完整 cli_hint。"""
    hook_id = args.hook_id
    sid = getattr(args, "sid", None) or None

    tmpl = get_hook_template(hook_id)
    if tmpl is None:
        raise PayloadError(f"HOOK-INFO ERROR: 未找到 hook 模板: {hook_id}")

    run_dir = resolve_case_path(getattr(args, "dir", None))
    hook_instance, inst_sid = None, sid
    ctx = load_context(run_dir) if run_dir else None
    if ctx is not None:
        hook_instance, inst_sid = _find_hook_instance(ctx, hook_id, sid)
        if sid and hook_instance is None:
            print(f"HOOK-INFO WARN: 步骤 {sid} 中未找到 hook {hook_id}，回退到模板默认渲染")
        hook_instance = hook_instance or {}

    target_sid = sid or inst_sid or "{sid}"
    # 回退场景（flow-context 中无该 hook 实例）：注入 id 使模板查找生效
    hook_instance = dict(hook_instance or {})
    hook_instance.setdefault("id", hook_id)
    lines = render_hook_cli_hint(hook_instance, target_sid)
    if not lines:
        print(f"HOOK-INFO: hook {hook_id} 无 cli_hint")
        return

    print(f"HOOK-INFO: {hook_id} (sid={target_sid})")
    for line in lines:
        print(f"  {line}")
