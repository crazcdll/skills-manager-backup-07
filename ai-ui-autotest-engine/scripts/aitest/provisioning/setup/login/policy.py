#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录编排的契约层：重启策略、前置步骤、以及各层的结果对象。

【设计要点】重启是**声明式**的：
  每个前置步骤用 `RestartPolicy` + `restart_reason` 显式声明"执行后施加什么重启、
  为什么必须重启"，由步骤自身就地执行 —— 在步骤定义处即可看清重启时机与理由。

⚠️ **重启点只增不减**：`dev/check_architecture.py::check_login_restart_declared`
   （规则 15）以基线锁定登录前置步骤的重启点数量，重构/新增平台不得减少。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class RestartPolicy(Enum):
    """前置步骤执行后需要施加的重启形态。

    四种形态：
      NONE              — 不重启（password 下发后 / noop / reset-env / ptest / 锁包）
      COLD              — force_stop + launch（环境切换后、enable 后无状态查询、重试恢复）
      COLD_CLEAR_DATA   — 清数据 → 预授权 → force_stop + launch（AppMock 已确认启用分支）
      COLD_AFTER_POPUP  — 弹窗（同意）点击后，再冷启一次让状态生效。
                          实际落点：`provisioning/setup/app_lifecycle._cold_restart_app()` 内
                          —— 清数据分支下弹窗消除成功时会再 force_stop + launch 一次；
                          因此它是"词汇表成员"，不由某个 ProvisionStep 单独声明。
    """

    NONE = "none"
    COLD = "cold"
    COLD_CLEAR_DATA = "cold_clear_data"
    COLD_AFTER_POPUP = "cold_after_popup"


@dataclass(frozen=True)
class ProvisionStep:
    """一个环境前置步骤。

    Attributes:
        id: 稳定标识（日志 / 验收锚点用，禁止随意改名）
        restart: 本步骤执行后需要施加的重启形态
        restart_reason: restart != NONE 时**必填** —— 说明"为什么这里必须重启"
    """

    id: str
    restart: RestartPolicy = RestartPolicy.NONE
    restart_reason: str = ""


@dataclass
class StepOutcome:
    """单个前置步骤的执行结果。"""

    step_id: str
    ok: bool
    detail: str = ""
    skipped: bool = False
    restart_applied: RestartPolicy = RestartPolicy.NONE
    evidence: Tuple[str, ...] = ()


@dataclass
class AuthOutcome:
    """认证动作的结果。

    needs_visual_check 为 True 时，编排层保留「读图确认」语义
    （凭证登录的既有机制，**不改**）。
    """

    ok: bool
    detail: str = ""
    needs_visual_check: bool = False
    evidence: Tuple[str, ...] = ()
    # 结构化失败原因，供 hooks 路由（见 login/hooks.py::LOGIN_REASON_HOOKS）
    reason: Optional[str] = None
    raw_result: Optional[dict] = None


@dataclass
class ProbeResult:
    """登录态判定结果。"""

    logged_in: bool
    detail: str = ""
    user_id: str = ""
    reliable: bool = True  # False = 结论不确定（需人工/读图二次确认）
    evidence: Tuple[str, ...] = ()


class Provisioned(ABC):
    """可执行的前置步骤实现契约。"""

    step: ProvisionStep

    @abstractmethod
    def run(self, plan, ctx) -> StepOutcome:
        ...


@dataclass
class LoginContext:
    """编排上下文：把"平台/App/工作域/证据目录"等依赖**显式注入**各层。

    各层通过 ctx 取依赖，而不是各自去 `shared.context.get_platform_ops()` 拉全局单例，
    以便按层约束依赖面（“动作层不直接绑定平台全局”目前靠约定，未加静态守卫）。
    """

    ops: object                    # PlatformOps 实例
    app: object                    # AppDescriptor 实例
    mis: str = ""
    device_type: str = ""
    case_dir: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def platform(self) -> str:
        return getattr(self.app, "platform", "")


__all__ = [
    "RestartPolicy", "ProvisionStep", "StepOutcome",
    "AuthOutcome", "ProbeResult", "Provisioned", "LoginContext",
]
