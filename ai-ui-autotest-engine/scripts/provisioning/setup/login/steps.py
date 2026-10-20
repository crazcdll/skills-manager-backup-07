#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 环境前置步骤：把"登录前要做的副作用"步骤化，并**声明**每步的重启策略。

【本层唯一职责】把登录前的环境副作用（重置 / AppMock 启用 / 环境切换 / 泳道与域名映射）
收拢为**有序、可单独验收**的步骤，并把"这一步为什么要冷重启"写成声明。

⚠️ **重启点只增不减**：本文件是登录前置步骤重启时机的唯一清单，
   由 `dev/check_architecture.py::check_login_restart_declared`（规则 15）以基线锁定数量：
     · ResetMockEnv           不重启
     · EnableAppMock          已确认启用 → 清数据+预授权+冷启动
                              已下发未确认 → 冷启动（可确认平台）
                                              / 清数据+预授权+冷启动（不可确认平台）
                              启用失败     → 每轮冷启动后重试
     · SwitchServerEnv        环境切换后冷启动
     · PushLocation           下发模拟定位后冷重启回首页（定位需重启才在首页生效）
     · ConfigureSwimline      泳道/域名映射变更后冷启动
     · ConfigureUrlMappings   登录后激活域名映射 → 冷启动
     · EnablePtestMock        不重启
     · PushBundleLock         不重启
"""
import re
import time

from platform.appmock.device import appmock_enable, check_appmock_sdk_enabled
from platform.appmock.ops import push_testability_scheme, reset_appmock_environment
from platform.appmock.swimlane import (
    appmock_ensure_url_mappings, appmock_env_set, appmock_swimline_add,
    appmock_swimline_list, appmock_swimline_switch,
)
from provisioning.setup.app_lifecycle import (
    _cold_restart_app, restart_app_after_env_switch,
)
from provisioning.setup.login.policy import (
    ProvisionStep, Provisioned, RestartPolicy, StepOutcome,
)
from shared.case_utils import set_mock_domain


# ═══════════════════════════════════════════════════════════════════
# 步骤：服务端环境重置（无重启）
# ═══════════════════════════════════════════════════════════════════

class ResetMockEnv(Provisioned):
    """重置服务端 AppMock 环境（清理残留规则 / 域名映射 / 泳道 / 环境）。

    **best-effort**：AppMock 服务端清理属后台清理动作，失败不应阻断登录
    （例如未取到 SSO Cookie 时代理会返回 5xx）。失败只记录到 detail 并继续，
    由调用方按日志排查。
    """

    step = ProvisionStep(id="reset_mock_env", restart=RestartPolicy.NONE)

    def run(self, plan, ctx):
        set_mock_domain(ctx.mis)
        ok = reset_appmock_environment(mis=ctx.mis)
        if not ok:
            print("RESET-ENV: ⚠️ 部分清理步骤失败（不阻断登录，继续执行）")
        return StepOutcome(step_id=self.step.id, ok=True,
                           detail="reset-env 完成" if ok else "reset-env 部分步骤失败（已忽略）")


# ═══════════════════════════════════════════════════════════════════
# 步骤：认证动作前的环境澄清（消除遮挡弹窗）
# ═══════════════════════════════════════════════════════════════════

class SettlePopups(Provisioned):
    """认证动作下发前把屏幕上的弹窗消除干净（restart=NONE）。

    **时机契约（守卫规则 23 锁定）**：本步骤必须是 pre 管线的**最后一步**，即排在所有
    重启类步骤（EnableAppMock / SwitchServerEnv / ConfigureSwimline）**之后**。
    系统级弹窗（通知权限、定位权限/引导）是在 **App 启动之后**才出现的：若澄清排在
    最后一次冷重启之前，最后那次重启后新起的弹窗就无人处理、只能靠认证动作自清兜底
    （实测：登录页被「定位服务引导」覆盖 ⇒ 元素定位与登录态判定双失败）。

    实现委托**唯一澄清入口** `environment_reconciler.reconcile_environment`：
    词表在 `platform/popup/patterns.py`，采集/点击在 `devices/popup.py`，
    两端共用同一条路径（Android 与鸿蒙语义一致，无平台分支）。
    """

    step = ProvisionStep(
        id="settle_popups",
        restart=RestartPolicy.NONE,
        restart_reason="弹窗消除无副作用，且系统弹窗不改变 App 状态，无需重启",
    )

    def run(self, plan, ctx):
        from provisioning.setup.environment_reconciler import reconcile_environment

        vr = reconcile_environment(wait_for_popup_ms=3000, label="login:pre")
        detail = (f"已消除 {len(vr.dismissed)} 个弹窗"
                  if vr and vr.any_dismissed else "无遮挡弹窗")
        return StepOutcome(step_id=self.step.id, ok=True, detail=detail)


# ═══════════════════════════════════════════════════════════════════
# 步骤：AppMock SDK 启用（三个分支各自的重启语义）
# ═══════════════════════════════════════════════════════════════════

class EnableAppMock(Provisioned):
    """启用设备端 AppMock SDK，并按分支施加冷重启。

    三个分支：
      · enable 成功且**可确认**   → `COLD_CLEAR_DATA`（清数据→预授权→冷启），
                                   消除弹窗成功后再冷启一次
      · enable 成功但**无法确认** → 可确认平台 `COLD`；不可确认平台 `COLD_CLEAR_DATA`
                                   （无状态查询通道 ⇒ 权限准备必须在本分支完成）
      · enable 失败              → 冷重启后重试
    """

    step = ProvisionStep(
        id="enable_appmock",
        restart=RestartPolicy.COLD_CLEAR_DATA,
        restart_reason=(
            "清除残留登录态并让 AppMock 代理生效：必须清数据后再预授权再冷启动，"
            "顺序不可互换（清数据会重置已授权限）"
        ),
    )

    def __init__(self, max_attempts=3):
        self.max_attempts = max_attempts

    def run(self, plan, ctx):
        for attempt in range(1, self.max_attempts + 1):
            enable_ok = appmock_enable(ctx.mis)
            sdk_verified = check_appmock_sdk_enabled()

            if enable_ok and sdk_verified:
                print(f"SDK-ENABLE: ✅ AppMock SDK 已确认启用（第 {attempt} 轮）")
                print("SDK-ENABLE: 清除 App 数据 + 重启 App 使网络栈完全走代理通道...")
                if _cold_restart_app(clear_data=True):
                    print("SDK-ENABLE: ✅ App 已冷启动完成（数据已清除）")
                else:
                    print("SDK-ENABLE: ⚠️ App 前台等待超时，继续执行")
                # 冷重启后代理可能丢失，重新下发一次
                appmock_enable(ctx.mis)
                return StepOutcome(step_id=self.step.id, ok=True,
                                   detail=f"已确认启用（第 {attempt} 轮）",
                                   restart_applied=RestartPolicy.COLD_CLEAR_DATA)

            if enable_ok and not sdk_verified:
                print(f"SDK-ENABLE: ⚠️ 已下发启用（第 {attempt} 轮），但设备端状态无法查询确认")
                # ★ 能力位驱动（非平台分支）：`can_verify_appmock_state=False` 的平台
                #   走不到"已确认"分支，因此必须在本分支完成「清数据 → 预授权 → 冷启动」，
                #   否则权限准备不会被执行（鸿蒙即此情况）。
                #   Android 声明 True ⇒ 本分支不清数据（保持其既有判定语义）。
                #   注：_cold_restart_app(clear_data=True) 内部顺序为 clear → grant → stop → launch，
                #   恰好满足「清数据必须在预授权之前」（清数据会重置已授权限）。
                need_clear = not getattr(ctx.ops, "can_verify_appmock_state", True)
                if need_clear:
                    print("SDK-ENABLE: 本平台无 AppMock 状态查询通道 → "
                          "在此完成清数据 + 预授权 + 冷启动")
                print("SDK-ENABLE: 冷重启 App 使网络栈走代理通道...")
                if _cold_restart_app(clear_data=need_clear):
                    print("SDK-ENABLE: ✅ App 已冷启动完成")
                else:
                    print("SDK-ENABLE: ⚠️ App 前台等待超时，继续执行")
                return StepOutcome(
                    step_id=self.step.id, ok=True,
                    detail=("已下发但无法确认（无状态查询通道，已顺带清数据+预授权）"
                            if need_clear else "已下发但无法确认（无状态查询通道）"),
                    restart_applied=(RestartPolicy.COLD_CLEAR_DATA if need_clear
                                     else RestartPolicy.COLD))

            if attempt < self.max_attempts:
                hint = "（状态查询显示启用，疑似假阳性）" if sdk_verified else ""
                print(f"SDK-ENABLE: ⚠️ 第 {attempt} 轮启用失败{hint}，冷重启后重试...")
                _cold_restart_app()
                time.sleep(2)

        return StepOutcome(step_id=self.step.id, ok=False,
                           detail=f"{self.max_attempts} 轮后 AppMock 仍无法启用",
                           restart_applied=RestartPolicy.COLD)


# ═══════════════════════════════════════════════════════════════════
# 步骤：下发模拟定位（下发 + 冷重启）
# ═══════════════════════════════════════════════════════════════════


class PushLocation(Provisioned):
    """下发模拟定位并重启 App 使定位生效。

    为什么必须有这一步：App 在"没有任何定位"时会卡在「定位中，请稍候」，首页渲染不出
    「去登录」入口，登录导航直接失败（实测：清数据+预授权+冷启动后首页无入口；下发定位后
    入口即出现、可点进 `passport.LoginActivity`）。定位对所有认证方式**统一前置**，
    认证动作自身不再携带定位。

    **通道**：把 `testability_location` action 经**通用可测性 scheme** 下发（与
    signin / 锁包同一条通道，见 `shared/case_utils.encode_scheme_payload` +
    `AppDescriptor.testability_scheme_prefix`）。承载页是 **MRN 容器**
    （`mrn.container.mrnbaseactivity`），内容**直接进原生视图树**，因此：
      · 无需任何 H5 特化的"等页面就绪"逻辑（旧 `_wait_h5_*` 已整体删除）；
      · 下发结果可由 `push_testability_scheme(verify=True)` 按视图树直接复核。
    官方 `imeituan control location` 走的是 Pillow-**H5**（`/pillow/m/qrconfig`），
    内容原生树读不到、只能靠焦点/探针猜，故不再采用（通道对比见
    `provisioning/setup/location.build_location_action`）。

    时机：排在环境切换/泳道冷重启**之后**（此时已是最终环境）、`SettlePopups` 之前；
    下发后**重启一次 App** 让定位在首页生效并回到前台。
    """

    step = ProvisionStep(
        id="push_location",
        restart=RestartPolicy.COLD,
        restart_reason="定位下发后需冷重启 App 才回到首页并让定位在首页生效（登录入口依赖定位）",
    )

    def run(self, plan, ctx):
        """下发 `testability_location` action（通用可测性 scheme）并冷重启回首页。"""
        from provisioning.setup.location import LOCATION_PRESETS, build_location_action

        loc = LOCATION_PRESETS.get(plan.location) if plan.location else None
        if not loc:
            return StepOutcome(step_id=self.step.id, ok=True, skipped=True,
                               detail=f"未配置/未知定位预设 {plan.location!r}，跳过")
        # verify=True：下发后按**原生视图树**复核结果页（失败会有明确文案）——
        # 比旧 H5 的"焦点 / DOM 非空"判定确定性高得多，也免去 H5 就绪等待。
        ok, _scheme, detail = push_testability_scheme(build_location_action(loc), verify=True)
        if not ok:
            return StepOutcome(step_id=self.step.id, ok=False,
                               detail=f"定位下发失败: {detail or '未知错误'}")
        _cold_restart_app()
        return StepOutcome(
            step_id=self.step.id, ok=True,
            detail=f"定位({plan.location}) 已下发并冷重启回首页",
            restart_applied=RestartPolicy.COLD,
        )

# ═══════════════════════════════════════════════════════════════════
# 步骤：服务端环境切换
# ═══════════════════════════════════════════════════════════════════

class SwitchServerEnv(Provisioned):
    """切换 AppMock 代理环境并冷重启。

    `target_value` 为传给 AppMock 的环境名（默认 alpha）。
    """

    step = ProvisionStep(
        id="switch_server_env",
        restart=RestartPolicy.COLD,
        restart_reason="切换代理环境后必须冷重启，使网络栈按新环境重新初始化",
    )

    def __init__(self, target_value="alpha"):
        self.target_value = target_value

    def run(self, plan, ctx):
        appmock_env_set(self.target_value, mis=ctx.mis)
        print(f"[login] ✅ 代理环境已切换为 {self.target_value}")
        restart_app_after_env_switch(label=self.target_value)
        # 冷重启后重新下发一次启用（网络栈重建后代理可能丢失）
        appmock_enable(ctx.mis)
        return StepOutcome(step_id=self.step.id, ok=True,
                           detail=f"env={self.target_value}",
                           restart_applied=RestartPolicy.COLD)


# ═══════════════════════════════════════════════════════════════════
# 步骤：泳道配置
# ═══════════════════════════════════════════════════════════════════

class ConfigureSwimline(Provisioned):
    """配置并切换泳道（复用已有规则），随后冷重启。

    纯域名映射模式（无 lane_name 但有 url_mappings）走 `SwitchServerEnv(alpha)`。
    """

    step = ProvisionStep(
        id="configure_swimline",
        restart=RestartPolicy.COLD,
        restart_reason="泳道/域名映射变更后必须冷重启，使路由与映射生效",
    )

    def run(self, plan, ctx):
        if not plan.swimline:
            appmock_env_set("alpha", mis=ctx.mis)
            print("[login-swimline] 纯域名映射模式：已切换 alpha 测试环境")
            restart_app_after_env_switch(label="swimline")
            return StepOutcome(step_id=self.step.id, ok=True,
                               detail="纯域名映射模式（alpha）",
                               restart_applied=RestartPolicy.COLD)

        url_pat = plan.swimline.url_pattern or "/*"
        rule_id = self._find_or_create_rule(url_pat, plan.swimline.lane_name, ctx)
        if not rule_id:
            return StepOutcome(step_id=self.step.id, ok=False, detail="泳道创建失败")

        if not appmock_swimline_switch(rule_id, mis=ctx.mis):
            return StepOutcome(step_id=self.step.id, ok=False,
                               detail=f"泳道切换失败 ruleId={rule_id}")
        print(f"[login-swimline] 泳道已切换 ruleId={rule_id}")

        if plan.url_mappings:
            results = appmock_ensure_url_mappings(list(plan.url_mappings), mis=ctx.mis)
            print(f"[login-swimline] 域名映射已配置 ({len(results)} 条)")

        restart_app_after_env_switch(label="swimline")
        return StepOutcome(step_id=self.step.id, ok=True,
                           detail=f"lane={plan.swimline.lane_name} ruleId={rule_id}",
                           restart_applied=RestartPolicy.COLD)

    @staticmethod
    def _find_or_create_rule(url_pat, lane_name, ctx):
        raw = appmock_swimline_list(mis=ctx.mis)
        items = raw.get("items", []) if isinstance(raw, dict) else (raw or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            item_url = item.get("url", "") or item.get("urlPattern", "")
            if item_url == url_pat:
                rule_id = str(item.get("id") or item.get("ruleId"))
                print(f"[login-swimline] 复用已有泳道规则 ruleId={rule_id}")
                return rule_id

        result = appmock_swimline_add(url_pat, lane_name, mis=ctx.mis)
        rule_id = str(result.get("id") or result.get("ruleId") or "")
        if not rule_id and result.get("raw"):
            m = re.search(r'id[=:]\s*(\d+)', result["raw"])
            if m:
                rule_id = m.group(1)
        if rule_id:
            print(f"[login-swimline] 泳道已创建 ruleId={rule_id}")
        return rule_id


# ═══════════════════════════════════════════════════════════════════
# 步骤：登录后域名映射激活
# ═══════════════════════════════════════════════════════════════════

class ConfigureUrlMappings(Provisioned):
    """登录后激活域名映射并冷重启。

    只在"泳道模式下无 lane_name 且有域名映射"时执行（纯域名映射模式）；
    作为 recovery 段的一部分复用时同样保持冷重启语义。
    """

    step = ProvisionStep(
        id="configure_url_mappings",
        restart=RestartPolicy.COLD,
        restart_reason="域名映射需冷重启后才对网络栈生效",
    )

    def run(self, plan, ctx):
        if plan.url_mappings:
            results = appmock_ensure_url_mappings(list(plan.url_mappings), mis=ctx.mis)
            print(f"[login-swimline] 域名映射已配置 ({len(results)} 条)")
        restart_app_after_env_switch(label="url-mapping")
        return StepOutcome(step_id=self.step.id, ok=True,
                           detail=f"{len(plan.url_mappings)} 条映射",
                           restart_applied=RestartPolicy.COLD)


# ═══════════════════════════════════════════════════════════════════
# 步骤：ptest mock（无重启）
# ═══════════════════════════════════════════════════════════════════

class EnablePtestMock(Provisioned):
    step = ProvisionStep(id="enable_ptest_mock", restart=RestartPolicy.NONE)

    def run(self, plan, ctx):
        from platform.appmock.ptest import enable_ptest_mock
        # 排除场景 Mock 路径：否则 ptest 全量 partMock 规则会命中短路，遮蔽场景 Mock
        exclude_rules = tuple(ctx.extra.get("ptest_exclude_rules") or ())
        mock_id = enable_ptest_mock(ctx.mis, exclude_rules=exclude_rules)
        return StepOutcome(step_id=self.step.id, ok=True,
                           detail=f"ptest mock 已配置 (mockId={mock_id})")


# ═══════════════════════════════════════════════════════════════════
# 步骤：MRN 锁包（无重启）
# ═══════════════════════════════════════════════════════════════════

class PushBundleLock(Provisioned):
    step = ProvisionStep(id="push_bundle_lock", restart=RestartPolicy.NONE)

    def run(self, plan, ctx):
        configs = []
        for b in plan.bundles:
            if not isinstance(b, dict) or not b.get("name"):
                continue
            if not b.get("version"):
                print(f"  ⏭️ {b['name']} 仅声明包名无版本，跳过锁包")
                continue
            configs.append({"type": "mrnbundle", "info": {
                "isStage": 1 if ctx.extra.get("bundle_env") == "stage" else 0,
                "bundleName": b["name"], "bundleVersion": b["version"],
            }})
        if not configs:
            return StepOutcome(step_id=self.step.id, ok=True, skipped=True,
                               detail="无可锁包项")
        ok, _, detail = push_testability_scheme(configs, verify=True, verify_wait=3.0)
        return StepOutcome(step_id=self.step.id, ok=bool(ok), detail=detail or "锁包已下发")


ALL_STEPS = {
    "reset_mock_env": ResetMockEnv,
    "enable_appmock": EnableAppMock,
    "push_location": PushLocation,
    "switch_server_env": SwitchServerEnv,
    "configure_swimline": ConfigureSwimline,
    "configure_url_mappings": ConfigureUrlMappings,
    "enable_ptest_mock": EnablePtestMock,
    "push_bundle_lock": PushBundleLock,
}


__all__ = list(ALL_STEPS) + ["ALL_STEPS"]
