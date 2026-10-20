#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录流程注册表：目标环境 → 前置/后置步骤序列（唯一事实来源）。

把"某环境要做什么"从控制流变成数据，编排层按表执行。

两张表：
  ENV_STEPS  target_env → EnvPipeline(pre 步骤 + post 步骤)
  （AUTH_ACTIONS / LOGIN_STATE_PROBES 分别在 actions/ 与 probes/ 中注册）
"""
from dataclasses import dataclass, field
from typing import Callable, Tuple

from provisioning.setup.login.plan import (
    TARGET_ENV_ALPHA, TARGET_ENV_NONE, TARGET_ENV_ONLINE, TARGET_ENV_SWIMLINE,
)
from provisioning.setup.login.steps import (
    ConfigureSwimline, ConfigureUrlMappings, EnableAppMock, PushLocation, ResetMockEnv,
    SettlePopups, SwitchServerEnv,
)


@dataclass(frozen=True)
class EnvPipeline:
    """某目标环境的环境前置管线。

    pre:  认证动作**之前**必须完成的步骤（含各自的声明式重启）
    post: 认证动作**之后**需要完成的步骤（如登录后激活域名映射）
    """

    pre: Tuple[Callable, ...] = field(default_factory=tuple)
    post: Tuple[Callable, ...] = field(default_factory=tuple)


# 所有"要登录"的环境共有的起手式（两类职责分开声明，见下方 _SETTLE_LAST）：
#   ResetMockEnv   重置 AppMock 账号级环境（无重启）
#   EnableAppMock  启用设备端 SDK（按分支冷重启；不可确认平台在该分支内完成清数据+预授权）
_COMMON_PRE = (ResetMockEnv, EnableAppMock)

# 定位统一前置（所有"要登录"的环境共用）：下发模拟定位保证 App 有定位，并重启一次使其生效。
# 为什么必须前置：App 无定位会卡「定位中」⇒ 首页渲染不出「去登录」入口 ⇒ 登录导航失败
# （实测）。排在环境切换/泳道冷重启**之后**（此时已是最终环境），`SettlePopups` 之前。
_PUSH_LOCATION = (PushLocation,)

# **环境澄清必须排在所有重启类步骤之后**（守卫规则 23 锁定，SettlePopups 必须是 pre 末位）：
#   SettlePopups  消除"App 启动之后"才弹出的系统弹窗（通知/定位引导）——冷重启里的
#                 "启动前消除"覆盖不到这类弹窗。若澄清排在最后一次冷重启**之前**，
#                 最后那次重启后新起的弹窗无人处理，只能靠认证动作自清兜底
#                 （实测：登录页被「定位服务引导」覆盖 ⇒ 元素定位 + 登录态判定双失败）。
_SETTLE_LAST = (SettlePopups,)

# 「清数据冷重启后必须重建的登录前置不变量」（单一事实来源）─────────────────
# EnableAppMock 以 `RestartPolicy.COLD_CLEAR_DATA` 清数据冷重启：设备侧随之丢失
# 「定位」与「弹窗同意态」。因此 **任何**触发清数据冷重启的路径（主管线 pre /
# 认证失败恢复）其后都必须重建本段，否则重演两类实测回归：
#   · 无定位  → 首页渲染不出「去登录」入口 ⇒ 登录导航失败（首跳「我的」亦然）
#   · 未澄清  → 登录页被系统弹窗（定位引导等）遮挡 ⇒ 元素定位 / 登录态判定双失败
# 顺序不可换：定位的重启在前、澄清（SettlePopups）必须收尾（守卫规则 23）。
# 仅在"要登录"的环境需要；D/noop 无登录，不纳入本段。
_AFTER_CLEAR_LOGIN_PREREQ = _PUSH_LOCATION + _SETTLE_LAST

ENV_STEPS = {
    # A(online)：reset → enable → 定位 → 澄清 → [ptest] → 下发 signin（无重启）
    TARGET_ENV_ONLINE: EnvPipeline(pre=_COMMON_PRE + _AFTER_CLEAR_LOGIN_PREREQ),

    # C(alpha) 与"B 但泳道配置为空而降级"的形态：额外切 alpha 环境（R5，含冷重启）
    # 定位排在其**之后**（在最终环境里下发并重启生效）；澄清必须最后。
    TARGET_ENV_ALPHA: EnvPipeline(
        pre=_COMMON_PRE + (SwitchServerEnv,) + _AFTER_CLEAR_LOGIN_PREREQ),

    # B(swimline)：
    #   · 有 lane_name → 配置泳道（R6，含登录前域名映射 ensure）→ 定位 → 澄清
    #   · 无 lane_name → 走纯域名映射模式（R5 切 alpha）→ 登录后再激活映射（R7）
    # 两种形态共用同一 target_env，由 `build_pipeline` 分流。
    TARGET_ENV_SWIMLINE: EnvPipeline(
        pre=_COMMON_PRE + (ConfigureSwimline,) + _AFTER_CLEAR_LOGIN_PREREQ,
        post=(),
    ),

    # D(noop)：不推送登录 scheme、不因登录而重启；
    # 但 reset-env 与 AppMock enable 对所有环境通用
    # （Step1/Step2 无环境条件），故此处同样保留，仅"认证动作"退化为 noop。
    TARGET_ENV_NONE: EnvPipeline(pre=_COMMON_PRE + _SETTLE_LAST, post=()),
}


def build_pipeline(plan) -> EnvPipeline:
    """按 plan 解析出实际要执行的管线（含 swimline 两种形态的分流）。

    纯域名映射模式（swimline 但无 lane_name）：
      pre 用 `SwitchServerEnv(alpha)` 替代 `ConfigureSwimline`，
        post 追加 `ConfigureUrlMappings`。
    """
    pipeline = ENV_STEPS.get(plan.target_env, EnvPipeline())
    if plan.target_env == TARGET_ENV_SWIMLINE and plan.swimline is None:
        return EnvPipeline(
            pre=_COMMON_PRE + (SwitchServerEnv,) + _AFTER_CLEAR_LOGIN_PREREQ,
            post=(ConfigureUrlMappings,),
        )
    return pipeline


def build_repair_pipeline(plan) -> EnvPipeline:
    """认证失败「完整恢复」用的环境不变量重建管线（与 pre 同源）。

    恢复段会先做一次「清数据冷重启」（复用 `EnableAppMock`），设备侧状态随数据清除而
    丢失，因此 **必须**在之后重建 `_AFTER_CLEAR_LOGIN_PREREQ`（定位 + 澄清）。

    历史回归（本函数即为修复它而设）：恢复段只做 `EnableAppMock` 却漏 `PushLocation`
    ⇒ 清数据后首页无「去登录」入口 ⇒ 重试导航失败。

    步骤取自本模块的同一批常量（单一事实来源）：pre 的"清数据后置"若有变化，这里自动
    跟随 —— 从结构上杜绝恢复段再次与 pre 漂移、漏步。

    Args:
        plan: LoginPlan（读取 target_env / url_mappings）
    Returns:
        「清数据冷重启」之后应执行的恢复步骤序列（EnvPipeline.pre）。
    """
    if plan.target_env == TARGET_ENV_NONE:
        # D/noop 不自动登录：无定位诉求，仅保留澄清（与 pre 同源）
        return EnvPipeline(pre=_SETTLE_LAST)
    pre = ()
    if plan.target_env == TARGET_ENV_SWIMLINE and getattr(plan, "url_mappings", None):
        # 纯域名映射模式：映射需在设备侧重新激活（沿用既有恢复行为，不回归）
        pre = (ConfigureUrlMappings,)
    return EnvPipeline(pre=pre + _AFTER_CLEAR_LOGIN_PREREQ)


__all__ = ["EnvPipeline", "ENV_STEPS", "build_pipeline", "build_repair_pipeline"]
