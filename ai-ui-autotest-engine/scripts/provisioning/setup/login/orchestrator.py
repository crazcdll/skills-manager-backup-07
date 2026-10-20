#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录编排层：把 L1~L4 组装成一次可执行、可验收的登录流程。

执行顺序：
  1. env pipeline.pre      环境前置（重置 / AppMock 启用 / 环境切换 / 泳道）
                            —— 澄清步骤（SettlePopups）固定排在 pre **末位**（所有重启之后）
  2. ptest（可选）
  3. auth action           认证动作；qahome 附带两层重试链
  4. env pipeline.post     登录后环境配置（域名映射激活）
  5. post 重启后澄清        post 阶段实际发生冷重启时，按唯一入口复核屏幕干净度
  6. login state probe     登录态判定（按平台探针）
  7. bundle lock（可选）

重启由**步骤内部**就地执行（`ProvisionStep.restart` + `restart_reason`），本层只按声明打点，
不集中触发 —— 因此每个重启点的时机与顺序稳定可预期；
`dev/check_architecture.py::check_login_restart_declared`（规则 15）以基线锁定数量，
只允许增加、不允许减少。
"""
from provisioning.setup.environment_reconciler import reconcile_environment
from provisioning.setup.login.actions import create_auth_action
from provisioning.setup.login.hooks import emit_login_hook
from provisioning.setup.login.plan import LoginPlan
from provisioning.setup.login.policy import LoginContext, ProbeResult, RestartPolicy
from provisioning.setup.login.probes import get_login_state_probe
from provisioning.setup.login.registry import build_pipeline, build_repair_pipeline
from provisioning.setup.login.steps import EnableAppMock

# qahome 失败后的「完整恢复」= 重新启用（含清数据冷重启）+ 重建清数据后丢失的登录前置不变量。
# ⚠️ 恢复步骤**不在此手挑**：统一由 `registry.build_repair_pipeline` 派生（单一事实来源），
#    避免再次出现「漏 PushLocation ⇒ 清数据后首页无「去登录」入口 ⇒ 导航失败」的回归。
_RECOVERY_REENABLE = EnableAppMock


def _recovery_steps(plan):
    """完整恢复的步骤序列：重新启用（清数据冷重启）→ 重建登录前置不变量（定位 + 澄清）。"""
    return (_RECOVERY_REENABLE,) + tuple(build_repair_pipeline(plan).pre)


def _log_restart(step, policy: RestartPolicy, reason: str):
    """声明式重启打点：让"哪一步、以什么形态、为什么重启"在日志里可读。"""
    if policy is RestartPolicy.NONE:
        return
    print(f"[restart] {step.id}: {policy.value} — {reason}")


def _run_steps(step_cls_list, plan: LoginPlan, ctx: LoginContext, *, phase: str):
    """顺序执行步骤；返回 (all_ok, 首个失败结果, 各步结果)。"""
    results = []
    for step_cls in step_cls_list:
        step = step_cls()
        policy = getattr(step, "step").restart
        _log_restart(step.step, policy, step.step.restart_reason)
        outcome = step.run(plan, ctx)
        outcome.restart_applied = policy
        results.append(outcome)
        print(f"[login:{phase}] step={outcome.step_id} ok={outcome.ok} "
              f"restart={policy.value} detail={outcome.detail}")
        if not outcome.ok:
            return False, outcome, results
    return True, None, results


# 恢复**无效**的失败原因：完整恢复能改变的只有**设备侧环境**（包状态、页面渲染、
# 被顶掉的前台、崩溃进程）。若根因在**外部状态**，冷重启无法改变它，只会再发一次码、
# 把频控压得更重 —— 此时宁可按引擎执行原则 5「快速失败并收尾」，直接登记 hook 交 AI。
_RECOVERY_INEFFECTIVE_REASONS = frozenset({
    "no_new_sms",          # 短信未下发 / 未入库（外部短信池）
    "sms_rate_limited",    # 短信网关频控（再发码只会更糟）
    "missing_credential",  # 计划里就没有账号，与设备无关
})


def _perform_with_qahome_recovery(action, plan: LoginPlan, ctx: LoginContext):
    """认证动作 + 恢复链：首次尝试 → （按需）完整恢复 → 再试一次。

    分层：动作层做环境内廉价重试（`qahome_login` 自身），本函数做环境级昂贵恢复
    （清数据冷重启 + 重建登录前置不变量）。`_RECOVERY_INEFFECTIVE_REASONS` 里的原因
    根因在外部状态，冷重启改变不了 → 直接上抛交 AI。
    ⚠️ 恢复步骤统一经 `registry.build_repair_pipeline` 派生；恢复含清数据，**必须**随之
    重建登录前置不变量（定位 + 澄清），否则清数据后首页无「去登录」入口。
    """
    # 首次尝试：成功即返回（失败才进入恢复链，避免把首次尝试误记为"重试"）
    outcome = action.perform(plan, ctx)
    if outcome.ok:
        return outcome

    reason = outcome.reason or "qahome_login_failed"
    if reason in _RECOVERY_INEFFECTIVE_REASONS:
        print(f"[login:qahome] ⏭️ 失败原因 {reason} 非设备侧问题，完整恢复无法改变结果，"
              "直接上抛交 AI 介入")
        return outcome

    # 完整恢复：清数据冷重启 + 重建登录前置不变量（步骤由 registry 派生）
    print(f"[login:qahome] 🔄 首次失败（{reason}），执行完整恢复"
          "（清数据冷重启 + 重建登录前置不变量）...")
    ok, failed, _ = _run_steps(_recovery_steps(plan), plan, ctx, phase="recovery")
    if not ok:
        print(f"[login:qahome] ❌ 完整恢复失败（step={failed.step_id}）：{failed.detail}")
        return outcome

    print("[login:qahome] 🔄 恢复步骤：重新登录...")
    return action.perform(plan, ctx)


def execute_login(plan: LoginPlan, ctx: LoginContext, run_dir: str = "") -> dict:
    """执行一次登录流程。

    Returns:
        dict: {
          ok: bool,
          needs_visual_check: bool,   # True → 保留"读图确认"语义（F-1）
          detail: str,
          evidence: tuple,            # 截图等证据路径
          probe: ProbeResult | None,
          steps: list[StepOutcome],
          hook_ids: list[str],        # 已登记的 AI 介入 hook
        }
    """
    pipeline = build_pipeline(plan)
    steps = []

    # ── 1. 环境前置（pre）──────────────────────────────────────────
    ok, failed, pre_results = _run_steps(pipeline.pre, plan, ctx, phase="pre")
    steps.extend(pre_results)
    if not ok:
        hooks = emit_login_hook("appmock_unconfirmed", step_id=failed.step_id,
                                detail=failed.detail, run_dir=run_dir)
        return {"ok": False, "needs_visual_check": False,
                "detail": f"环境前置失败: {failed.step_id} — {failed.detail}",
                "evidence": (), "probe": None, "steps": steps,
                "hook_ids": [h["id"] for h in hooks], "hooks": hooks}

    # ── 2. ptest（可选）────────────────────────────────────────────
    if plan.ptest:
        from provisioning.setup.login.steps import EnablePtestMock
        ptest = EnablePtestMock()
        _log_restart(ptest.step, ptest.step.restart, ptest.step.restart_reason)
        steps.append(ptest.run(plan, ctx))

    # ── 3. 认证动作 ────────────────────────────────────────────────
    action = create_auth_action(plan.auth)
    print(f"[login] 执行认证动作: {plan.auth}（target_env={plan.target_env}）")
    if plan.auth == "qahome":
        outcome = _perform_with_qahome_recovery(action, plan, ctx)
    else:
        outcome = action.perform(plan, ctx)

    steps.append(_outcome_as_step(action, outcome))

    if not outcome.ok:
        hooks = emit_login_hook(outcome.reason or "login_action_failed",
                                action=plan.auth, detail=outcome.detail,
                                evidence=outcome.evidence, run_dir=run_dir)
        return {"ok": False, "needs_visual_check": outcome.needs_visual_check,
                "detail": outcome.detail, "evidence": outcome.evidence,
                "probe": None, "steps": steps,
                "hook_ids": [h["id"] for h in hooks], "hooks": hooks}

    # ── 4. 环境后置（post）────────────────────────────────────────
    if pipeline.post:
        ok, failed, post_results = _run_steps(pipeline.post, plan, ctx, phase="post")
        steps.extend(post_results)
        if not ok:
            hooks = emit_login_hook("env_switch_ineffective", step_id=failed.step_id,
                                    detail=failed.detail, run_dir=run_dir)
            return {"ok": False, "needs_visual_check": False,
                    "detail": f"登录后环境配置失败: {failed.step_id} — {failed.detail}",
                    "evidence": outcome.evidence, "probe": None, "steps": steps,
                    "hook_ids": [h["id"] for h in hooks], "hooks": hooks}

        # ── 4b. 重启后澄清（唯一入口复核）────────────────────────
        # 不变量：**任何设备态变更（冷重启）之后，屏上都必须是干净的**。
        # pre 阶段由 `SettlePopups` 排在所有重启步骤之后保证（规则 23 锁定）；
        # post 阶段（域名映射激活等）同样会冷重启，它新起的系统弹窗会盖住登录后的页面，
        # 而 Android 的登录态判定/取证都依赖屏幕内容 —— 故此处按**实际生效的重启**复核。
        if any(s.restart_applied is not RestartPolicy.NONE for s in post_results):
            reconcile_environment(label="login:post", wait_for_popup_ms=3000)

    # ── 5. 登录态判定（平台探针）───────────────────────────────
    # 判定契约：
    #   · Android：凭证登录不做程序化判定（判据=读图），也不引入额外副作用；
    #              qahome / noop 用 `check_login_state`，不就判失败
    #   · Harmony：任何认证方式都用真登录态（`auth status`）
    probe = get_login_state_probe(ctx.platform)
    if plan.auth == "password" and not probe.authoritative_for_password:
        probe_result = ProbeResult(
            logged_in=True, reliable=False,
            detail="凭证登录以读图确认为准（不做程序化探测）",
        )
        print(f"[login] 登录态判定：跳过程序化探测（{probe.name} 对凭证登录非权威，"
              "判据 = 读图 [NEEDS_VISUAL_CHECK]）")
    else:
        probe_result = probe.probe()
        print(f"[login] 登录态探针 {probe.name}: logged_in={probe_result.logged_in} "
              f"reliable={probe_result.reliable} detail={probe_result.detail}")

    # 判定未通过 → 登记 hook 交给 AI 判断（不在此处擅自重试/放行）
    # qahome/noop 的判定同样"不就判失败"（与 Android 契约一致）
    if not probe_result.logged_in:
        hooks = emit_login_hook("login_state_unconfirmed", probe=probe.name,
                                detail=probe_result.detail,
                                evidence=outcome.evidence, run_dir=run_dir)
        return {"ok": False, "needs_visual_check": True,
                "detail": f"登录态判定未通过: {probe_result.detail}",
                "evidence": outcome.evidence, "probe": probe_result, "steps": steps,
                "hook_ids": [h["id"] for h in hooks], "hooks": hooks}

    if not probe_result.reliable:
        # Android 契约：程序化只能判前台，最终由读图确认
        print("[login] ⚠️ 探针结论为「不可完全确认」（Android 前台判定语义），"
              "最终以读图为准确认（[NEEDS_VISUAL_CHECK]）")

    # ── 6. 锁包（可选）────────────────────────────────────────────
    if plan.bundles:
        from provisioning.setup.login.steps import PushBundleLock
        lock = PushBundleLock()
        _log_restart(lock.step, lock.step.restart, lock.step.restart_reason)
        lock_outcome = lock.run(plan, ctx)
        steps.append(lock_outcome)
        if not lock_outcome.ok:
            return {"ok": False, "needs_visual_check": outcome.needs_visual_check,
                    "detail": f"MRN 锁包失败: {lock_outcome.detail}",
                    "evidence": outcome.evidence, "probe": probe_result,
                    "steps": steps, "hook_ids": []}

    return {
        "ok": True,
        "needs_visual_check": bool(outcome.needs_visual_check or not probe_result.reliable),
        "detail": outcome.detail or probe_result.detail,
        "evidence": outcome.evidence,
        "probe": probe_result,
        "steps": steps,
        "hook_ids": [],
    }


def _outcome_as_step(action, outcome):
    """把认证动作结果包装成 StepOutcome，便于统一日志/验收。"""
    from provisioning.setup.login.policy import StepOutcome
    return StepOutcome(
        step_id=f"auth:{getattr(action, 'method', '?')}",
        ok=outcome.ok,
        detail=outcome.detail,
        restart_applied=RestartPolicy.NONE,  # 认证动作本身不重启
        evidence=outcome.evidence,
    )


__all__ = ["execute_login"]
