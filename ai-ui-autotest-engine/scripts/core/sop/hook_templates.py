#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook 模板数据（纯 prompt 文本）的加载与索引。

【为什么单独成模块】
原 `sop_definitions.py` 内嵌了 370+ 行中文 prompt 文本（desc / cli_hint），
导致「改一句文案 = 改代码 = 触发逻辑回归」。现数据本体外置于
同目录 `hook_templates.json`，本模块只负责加载与索引 —— 改文案只动数据。

数据结构（json）：
    { "<group_key>": [ {"id": str, "desc": str, "required": bool,
                        "cli_hint": str(可选), "auto": bool(可选), ...}, ... ] }

group_key 语义（消费者见 core/sop/hook_router.py::get_hooks_for_result）：
    pre_step / on_pass / on_text_assertion / on_visual_assertion /
    on_text_visual_recheck / on_api_fields_assertion / on_track_fields_assertion /
    on_text_not_found / on_target_unresolved / on_target_ambiguous / on_target_blocked /
    on_viewport_resolve / on_scroll_target_not_found / on_scroll_exhausted /
    on_warn / on_fail / on_back_unexpected

注：原模板中若干组共享的长 prompt 文本（如 text 断言共用的 desc/cli_hint）在导出时
已内联为字面量，不再是「数据引用代码常量」，从而彻底解除数据对代码的依赖。
"""
import json
from functools import lru_cache
from pathlib import Path

from core.errors import ContractError

_DATA_FILE = Path(__file__).with_name("hook_templates.json")


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ContractError(
            f"Hook 模板数据文件缺失或损坏: {_DATA_FILE}（{e}）"
            f"——模板数据在 hook_templates.json，请确认它随 Skill 一同打包"
        ) from e


# 模块级常量：保持既有引用形态（HOOK_TEMPLATES["on_fail"] 等）不变
HOOK_TEMPLATES = _load()

# hook id → 模板 索引（懒加载，供 hook-info / render_hook_cli_hint 按需查询）
_HOOK_TEMPLATE_INDEX = None


def get_hook_template(hook_id):
    """按 id 在全部模板组中查找 hook 模板，未找到返回 None。"""
    global _HOOK_TEMPLATE_INDEX
    if _HOOK_TEMPLATE_INDEX is None:
        index = {}
        for group in HOOK_TEMPLATES.values():
            for t in group:
                if t.get("id"):
                    index[t["id"]] = t
        _HOOK_TEMPLATE_INDEX = index
    return _HOOK_TEMPLATE_INDEX.get(hook_id)
