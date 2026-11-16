#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""触发人身份语义校验（数字员工账号不冒充人类触发者）。

问题（PR #9540 实证）：
  webhook/平台触发链路把执行账号 1024_aicragent 当 --trigger-mis 传入，
  学城报告「触发人」行、大象推送 people 行、cr_task 落库 trigger_mis
  三处都显示数字员工账号——它不是人类触发者，统计口径被污染。

修复原则（与 agent_name 白名单同思路，但语义相反——不猜替身）：
  - trigger_mis 命中数字员工账号特征（1024_ 前缀）→ 视为「未确认人类触发者」
  - 展示层降级为「AI 自动触发」标注，保留原始值进 _trigger_mis_raw 供追溯
  - 不自动替换成 PR 提交人（提交人≠触发人，替换=编造）
  - 落库 trigger_mis 置空串（服务端宽松解析，空串不覆盖既有值）
  - 团队群 @ 名单剔除该条（@ 数字账号无意义且可能转 uid 失败）
"""
import re

# 数字员工账号特征：1024_ 前缀（平台数字员工命名约定，如 1024_aicragent）
_DIGITAL_EMPLOYEE_RE = re.compile(r"^1024_[a-z0-9_]+$", re.IGNORECASE)


def clean_trigger_identity(mis, name):
    """校验触发人身份；返回 (display_mis, display_name, is_auto)。

    - 正常人类 mis：原样返回，is_auto=False
    - 数字员工账号（1024_ 前缀）：返回降级标注，is_auto=True
    - 空/None：空串，is_auto=False（调用方按原有 unknown 兜底）
    """
    v = (mis or "").strip()
    if not v:
        return ("", "", False)
    if _DIGITAL_EMPLOYEE_RE.match(v):
        return ("", "AI 自动触发", True)
    return (v, (name or "").strip() or v, False)
