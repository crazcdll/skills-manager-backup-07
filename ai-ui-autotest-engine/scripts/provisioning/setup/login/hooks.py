#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录阶段的异常 → Hook 路由（**纯映射，不依赖 hook 引擎内部**）。

【分层约束】本模块只做"失败原因 → hook id + 参数"的纯数据路由，**不 import**
`execution.*`。落盘（写 flow-context 的 `runtime.login_hooks`）与渲染由 flow 边界负责：
  · 落盘：`provisioning/setup/env_prepare.py`（它已持有 flow-context 写入职责）
  · 渲染：`python3 scripts/cli.py hook-info --hook-id <id> --dir <case>`
          （`hook_info_cmd` 在 steps 里找不到时会回退查 `runtime.login_hooks`）

【AI 介入闭环】
  env-prepare 失败
  → 本模块给出 hook id + 完整参数 + 证据路径，并打印查询命令（不刷屏）
  → AI 执行 `hook-info` 拿到渲染后的完整处置指引
  → AI 读证据（截图 / 页面文案 / pillow 结果 / hilog）判断根因
  → AI 采取动作（重推 scheme / 清数据重来 / 换包 / 换认证方式 / 申请加白 / 上抛）
  → AI 标记完成：python3 scripts/cli.py flow-next --done-hooks <id>
"""
from typing import Dict, List, Optional

# 失败原因（AuthOutcome.reason / StepOutcome 失败）→ hook id
# 新增异常场景：在此登记映射 + 在 hook_templates.json 的 on_login 分组增加同名模板。
#
# qahome 的 reason 由状态机细分（见 `login/actions/qahome.py`），但**不新增模板 id**：
# 细分原因复用既有两条"验证码登录"模板 —— 模板正文已按分段（触发 / 取码 / 提交）给出
# 处置指引，reason 只决定"归到哪条处置路径"，避免模板数量随内部状态膨胀。
LOGIN_REASON_HOOKS: Dict[str, str] = {
    "scheme_dispatch_failed": "resolve_login_scheme_not_dispatched",
    "login_action_failed": "resolve_login_action_failed",
    "login_stuck_loading": "resolve_login_stuck_loading",
    "login_state_unconfirmed": "resolve_login_state_unconfirmed",
    "popup_blocked": "resolve_login_popup_blocked",
    "qahome_login_failed": "resolve_qahome_login_failed",
    "qahome_sms_timeout": "resolve_qahome_sms_timeout",
    "env_switch_ineffective": "resolve_login_env_ineffective",
    "appmock_unconfirmed": "resolve_appmock_unconfirmed",
    "missing_credential": "resolve_login_missing_credential",
    # ── qahome 状态机细分原因 ────────────────────────────────────────
    # 起点/页面侧问题（动作层无法归一，需人工确认页面形态或导航入口）
    "page_state_invalid": "resolve_qahome_login_failed",
    "not_login_page": "resolve_qahome_login_failed",
    "code_not_sent": "resolve_qahome_login_failed",
    "send_code_missing": "resolve_qahome_login_failed",
    # 取码侧问题（短信池为空 / 频控 / 新码迟迟不到）
    "no_new_sms": "resolve_qahome_sms_timeout",
    "sms_rate_limited": "resolve_qahome_sms_timeout",
    # 回填/提交侧问题（码被拒 / 未进框 / 提交超时 / 前台未回归）
    "code_rejected": "resolve_qahome_login_failed",
    "code_not_entered": "resolve_qahome_login_failed",
    "code_input_missing": "resolve_qahome_login_failed",
    "submit_timeout": "resolve_qahome_login_failed",
    "foreground_not_restored": "resolve_qahome_login_failed",
    "app_crashed": "resolve_login_action_failed",
}

# 模板只允许使用这四个占位符（始终提供，避免渲染出「缺少参数」噪音）
_HINT_PLACEHOLDERS = ("detail", "action", "step_id", "probe")

STAGE_ID = "B2_login"


def build_login_hook(reason: str, *, detail: str = "", action: str = "",
                     step_id: str = "", probe: str = "",
                     evidence: Optional[tuple] = None) -> Optional[dict]:
    """把失败原因转成 hook 实例（纯数据，与步骤级 hook 落盘结构同构）。

    Returns:
        dict | None: {"id", "stage", "required", "hint_params", "evidence"}；无映射返回 None。
    """
    hook_id = LOGIN_REASON_HOOKS.get(reason or "")
    if not hook_id:
        return None
    params = {k: (v or "—") for k, v in zip(
        _HINT_PLACEHOLDERS, (detail, action, step_id, probe))}
    return {
        "id": hook_id,
        "stage": STAGE_ID,
        "required": True,
        "hint_params": params,
        "evidence": [str(e) for e in (evidence or ())],
    }


def emit_login_hook(reason: str, *, detail: str = "", action: str = "",
                    step_id: str = "", probe: str = "",
                    evidence: Optional[tuple] = None,
                    run_dir: str = "") -> List[dict]:
    """构造登录 hook 并打印**紧凑**提示（不打印模板全文，与引擎"按需查询"约定一致）。

    注意：落盘不在此处完成 —— 由调用方（flow 边界）在拿到返回值后写入
    `flow-context.json` 的 `runtime.login_hooks`。这样登录层无需依赖 `execution.*`。

    Returns:
        list[dict]: 命中时返回单元素列表，否则空列表。
    """
    instance = build_login_hook(reason, detail=detail, action=action,
                                step_id=step_id, probe=probe, evidence=evidence)
    if not instance:
        return []

    print(f"\n[login-hook] 登录异常已登记 AI 介入指引: {instance['id']}")
    if instance["evidence"]:
        print(f"[login-hook] 证据: {', '.join(instance['evidence'])}")
    dir_arg = f" --dir {run_dir}" if run_dir else ""
    print("[login-hook] 获取完整处置指引: "
          f"python3 scripts/cli.py hook-info --hook-id {instance['id']}{dir_arg}")
    return [instance]


__all__ = ["LOGIN_REASON_HOOKS", "STAGE_ID", "build_login_hook", "emit_login_hook"]
