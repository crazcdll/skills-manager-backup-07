#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""落地步骤（role=landing）语义的唯一实现。

为什么单独成模块
────────────────
“打开落地页”从旧独立阶段（C3）并入步骤管线后，语义横跨四层：
装载（补形状）→ 执行（补必填 hook）→ 判定（override 写回）→ 收口（blocked 进报告）。
若每层各写一点判断，代码就会变成“补丁堆”。因此这里集中三条规则，其余文件只调用：

  ① 形状 —— `ensure_confirm`：首步 open-url 必然是落地步，补齐
     `role / page_ready / 内建视觉断言`，手写 CASES 与业务模型注入两条路径自动一致；
  ② 判定 —— `LANDING_HOOK_ID`：落地确认 hook 必填，结论只能来自
     `override-step-result --assert-verdict`（见 hook_templates.json::on_landing_visual_assertion）；
  ③ 收口 —— `should_block_case` + `guidance`：终态 fail 代表用例前置不成立，
     case 记 blocked 并推进报告，等价旧阶段的 skip_to_next_case。

`role` 字段本身的合法性校验仍留在 `shared/step_schema.py`（通用步骤模型职责），
本模块只承载“落地”这一种角色的语义。
"""

from __future__ import annotations

import copy

from aitest.shared.step_schema import LANDING_ROLE, normalize_role

# 内建落地确认断言：判据是「目标页是否真的打开」，不是业务内容。
LANDING_VISUAL_EXPECT = "落地页正常打开"

# 落地确认 hook id（模板与 required 标记见 hook_templates.json）
LANDING_HOOK_ID = "verify_landing_page"


def is_landing_step(step) -> bool:
    """判断步骤（CASES / steps_json / flow-context 的字典）是否落地步骤。"""
    if not isinstance(step, dict):
        return False
    return normalize_role(step.get("role")) == LANDING_ROLE


def is_landing_candidate(step, index: int) -> bool:
    """位置语义：首步的 open-url 就是落地步骤（与作者是否写 role 无关）。"""
    if not isinstance(step, dict) or index != 0:
        return False
    return str(step.get("action") or "").strip() == "open-url"


def ensure_confirm(step: dict, index: int) -> dict:
    """把落地步骤规范为引擎内建形态，返回新字典（不改入参）。

    · role       —— 执行期据此改变失败归因与收口语义；
    · page_ready —— 断言必须在页面稳定之后；
    · 视觉断言   —— 至少 1 条 visual（落地页截图自证）；作者已写 visual
      则保留（尊重更精确的判据），只写文本断言时两者并存。
    """
    if not is_landing_candidate(step, index):
        return step
    out = copy.deepcopy(step)
    out["role"] = LANDING_ROLE
    out["page_ready"] = True
    asserts = [a for a in (out.get("asserts") or []) if isinstance(a, dict)]
    if not any(str(a.get("kind") or "") == "visual" for a in asserts):
        asserts.append({"kind": "visual", "expect": LANDING_VISUAL_EXPECT})
    out["asserts"] = asserts
    return out


def should_block_case(step, ok, stage) -> bool:
    """落地步骤终态失败 → 结束本 case（blocked）。

    只在走查阶段收口一次：重复 override（幂等重放）不会把下一个 case 也跳掉。
    """
    if not is_landing_step(step) or ok != 0:
        return False
    return str(stage or "").startswith("C4_walkthrough_")


def guidance(reason: str, *, terminal: bool = False):
    """落地收口指引 —— 唯一文案来源（步骤执行层与 override 终态层共用）。

    terminal=False：动作层失败（push 失败），仍有重试 hook → 先修入口，再写终态；
    terminal=True ：落地确认已判 fail，引擎已把 case 标记 blocked 并推进到报告阶段。
    """
    lines = [
        "STEP [LANDING] 落地入口未打开：本 case 前置不成立（blocked），不是用例业务失败",
        f"  原因: {reason or '未知'}",
    ]
    if terminal:
        lines.append("  → case 已标记 blocked、后续走查步骤已跳过；执行 <入口> flow-next 进入报告阶段")
        lines.append("  → 若确属环境/设备不可恢复（设备失联、登录体系故障），再用 flow-fail --cleanup")
    else:
        lines.append("  → 先按 hooks 重试/修复入口（≤3 次）；确认不可达后收口（写入终态）:")
        lines.append("     <入口> override-step-result --fail --sid <SID> "
                     "--assert-verdict '{\"<断言ID>\":{\"result\":\"fail\",\"verdict\":\"visual\","
                     "\"actual\":\"...\",\"reason\":\"...\"}}' --desc '落地入口不可用'（断言 id 见 hook-info）")
        lines.append("  → 该 override 会自动把本 case 标记 blocked 并跳到报告阶段"
                     "（不要手工 skip-case，也不要用 flow-fail）")
    return lines
