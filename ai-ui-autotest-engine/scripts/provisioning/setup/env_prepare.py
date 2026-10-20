#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境准备入口（CLI 边界 + 证据收口）。

【本文件的职责已收窄为两件事】
  1. CLI 边界：把命令行参数 / flow-context 自动填充成 env 配置块（**不再掺业务编排**）
  2. 证据收口：登录结果截图归档、审计事件、ack 门禁提示

真正的登录编排在 `provisioning/setup/login/`（L1 Plan → L2 Steps → L3 Action → L4 Probe），
本文件不再持有任何登录策略分支。

失败即终止，不降级不继续。
"""
import json
import os
import shutil

from shared.errors import AppError, ConfigError
from shared.json_utils import read_json
from shared.paths import get_active_run
from shared.case_utils import current_case_workspace, resolve_case_path, resolve_mock_domain
from execution.engine.flow.flow_context import (
    load_context, read_meta_fields, save_context, update_meta_fields,
)
from shared.observability.runtime_audit import append_event, register_evidence
from shared.records import frame_path
from execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from provisioning.validators.env_validator import (
    DEFAULT_APP, ENV_NAME_TO_TYPE, ENV_TYPE_MAP, EnvValidationError,
    validate_env_config,
)
from provisioning.setup.login import LoginContext, LoginPlan, execute_login
from execution.steps.assertion_utils import format_visual_check_hint
from shared.context import get_app_descriptor, get_platform_ops


def _step(n, total, title):
    print(f"\n{'='*60}", flush=True)
    print(f"[env-prepare] Step {n}/{total}: {title}", flush=True)
    print(f"{'='*60}", flush=True)


def _parse_bundle_lock(bundles_str):
    """把 `--bundles name:version,...` 解析为 bundle_lock 结构。

    仅声明包名无版本的项保留（表示"目标版本待执行时提供"），由锁包步骤跳过。
    """
    result = []
    for item in (bundles_str or "").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, version = item.split(":", 1)
            result.append({"name": name.strip(), "version": version.strip()})
        else:
            result.append({"name": item, "version": ""})
    return result


def _resolve_mock_exclude_rules(mock_ids, mis=None):
    """取出场景 Mock 的 URI 规则，供 ptest 规则做负向前瞻排除。

    为什么在服务端查而非本地推导：只有平台侧的 `rule` 字段才是「真正参与匹配」的
    口径。查不到的 id 跳过（不阻断环境准备）。mis 为 AppMock 工作域（mock_domain）。
    """
    from platform.appmock.rules import appmock_get
    rules = []
    for mid in (mock_ids or []):
        detail = appmock_get(str(mid), mis=mis)
        rule = (detail or {}).get("rule")
        if rule and rule not in rules:
            rules.append(str(rule))
    return rules


def _persist_login_hooks(fc_path, hooks):
    """把登录阶段登记的 hook 落到 flow-context 的 runtime.login_hooks。

    为何在 flow 边界落盘：登录层（provisioning/setup/login/hooks.py）只做纯路由，
    不依赖 execution.* 的 hook 引擎；落盘由已持有 flow-context 写入职责的本文件负责
    （保证 provisioning 层的分层依赖方向不被破坏）。
    `hook-info` 在步骤里找不到 hook 时会回退查该处。
    """
    if not hooks or not fc_path:
        return
    try:
        ctx = load_context(fc_path)
        if ctx is None:
            return
        runtime = ctx.setdefault("runtime", {})
        existing = [h for h in (runtime.get("login_hooks") or [])
                    if h.get("id") not in {h2.get("id") for h2 in hooks}]
        runtime["login_hooks"] = existing + list(hooks)
        save_context(fc_path, ctx)
    except Exception as e:  # noqa: BLE001 — hook 落盘失败不得掩盖原始登录失败
        print(f"[login-hook] ⚠️ hook 落盘失败（不影响失败判定）: {e}")


def cmd_env_prepare(args):
    """环境准备合并入口。

    参数自动填充：--env / --account / --password / --location / --bundles /
    --lane-name / --url-pattern / --url-mapping / --mis 缺省时从 flow-context.json
    的 env 块和 meta 块自动读取。
    """
    case_name = get_active_run()
    fc_env = {}
    _ctx = {}
    if case_name:
        fc_path = os.path.join(resolve_case_path(case_name), FLOW_CONTEXT_FILENAME)
        read_meta_fields(fc_path)  # 触发一次读取以便尽早暴露文件问题
        try:
            _ctx = read_json(fc_path, default={})
            fc_env = _ctx.get("env", {})
        except Exception:
            fc_env = {}

        if not args.mis:
            args.mis = resolve_mock_domain()
        if not args.env and fc_env.get("type"):
            args.env = ENV_TYPE_MAP.get(fc_env["type"], fc_env["type"])
        if not args.account:
            args.account = fc_env.get("account") or None
        if not args.password:
            args.password = fc_env.get("_password_raw") or None
        if not args.location:
            args.location = fc_env.get("location") or None
        if not args.bundles and fc_env.get("bundle_lock"):
            args.bundles = ",".join(
                (f"{b['name']}:{b['version']}" if b.get("version") else b["name"])
                for b in fc_env["bundle_lock"]
                if isinstance(b, dict) and b.get("name")
            )
        if args.ptest is None:
            args.ptest = bool(fc_env.get("ptest"))

        swimline = fc_env.get("swimline") or {}
        if not args.lane_name:
            args.lane_name = swimline.get("lane_name") if isinstance(swimline, dict) else None
        if not args.url_pattern:
            args.url_pattern = swimline.get("url_pattern") if isinstance(swimline, dict) else None
        if not args.url_mapping:
            um = fc_env.get("url_mappings")
            if um:
                args.url_mapping = json.dumps(um, ensure_ascii=False)

    env = args.env
    mock_domain = args.mis
    app = _ctx.get("meta", {}).get("app") or fc_env.get("app") or DEFAULT_APP
    device_type = _ctx.get("meta", {}).get("device_type")

    resolved_password = args.password
    if not resolved_password and env == "online":
        raise ConfigError(
            f"{env} 环境必须提供凭证；解决: 在 steps-input.json 的 env.password 中填写真实凭证"
        )

    env_config = {
        "type": ENV_NAME_TO_TYPE.get(env, env),
        "auth_method": fc_env.get("auth_method"),
        "account": args.account,
        "password": resolved_password,
        "location": args.location,
        "ptest": bool(args.ptest),
        "swimline": (
            {"lane_name": args.lane_name, "url_pattern": args.url_pattern or "/*"}
            if args.lane_name else None
        ),
        "url_mappings": (
            json.loads(args.url_mapping) if isinstance(args.url_mapping, str) and args.url_mapping else []
        ),
        "bundle_lock": _parse_bundle_lock(args.bundles),
    }

    # ── L1：派生并校验登录计划（校验规则复用三张校验表）──
    try:
        validate_env_config(dict(env_config), app=app, device_type=device_type)
        plan = LoginPlan.derive(env_config, app=app, device_type=device_type)
    except EnvValidationError as e:
        raise ConfigError(f"环境配置校验失败: {e}") from e
    except Exception as e:
        raise ConfigError(f"登录计划派生失败: {e}") from e

    print(f"[env-prepare] 登录计划: auth={plan.auth} env_type={plan.env_type} "
          f"target_env={plan.target_env} bundles={len(plan.bundles)} ptest={plan.ptest}")

    # ptest 与场景 Mock 共存时：把场景 Mock 的 URI 规则作为 ptest 的排除项，
    # 避免 ptest 全量规则命中短路、遮蔽场景 Mock（历史事故根因）。
    # 场景 Mock 为 case 级，这里取所有 case 的并集（meta.mock_union），与 ptest（环境级）正交。
    ptest_exclude_rules = []
    if args.ptest:
        scenario_mock_ids = _ctx.get("meta", {}).get("mock_union") or []
        ptest_exclude_rules = _resolve_mock_exclude_rules(scenario_mock_ids, mis=mock_domain)
        print(f"[env-prepare] ptest 排除场景 Mock 路径: {ptest_exclude_rules or '无'}")
    login_ctx = LoginContext(
        ops=get_platform_ops(),
        app=get_app_descriptor(),
        mis=mock_domain or "",
        device_type=device_type or "",
        case_dir=resolve_case_path(case_name) if case_name else "",
        extra={"bundle_env": getattr(args, "bundle_env", None),
               "ptest_exclude_rules": ptest_exclude_rules},
    )

    steps = 1 + (1 if plan.ptest else 0) + (1 if plan.bundles else 0)
    n = 0
    n += 1
    _step(n, steps, f"登录编排（{plan.auth} / {plan.target_env}）")

    result = execute_login(
        plan, login_ctx,
        run_dir=resolve_case_path(case_name) if case_name else "",
    )

    # 登录异常 → 登记 AI 介入 hook（失败也要落盘，供 hook-info 查询）
    _persist_login_hooks(
        os.path.join(resolve_case_path(case_name), FLOW_CONTEXT_FILENAME) if case_name else "",
        result.get("hooks") or [],
    )

    if not result["ok"]:
        append_event(
            resolve_case_path(case_name) if case_name else "",
            "login.failed",
            {"env": env, "method": plan.auth, "account": mock_domain,
             "detail": result["detail"], "hook_ids": result.get("hook_ids", [])},
        )
        raise AppError(f"LOGIN FAILED: {env} 环境登录失败: {result['detail']}")

    # ── 证据收口（凭证登录必须产出可读截图）──
    evidence = tuple(result.get("evidence") or ())
    shot = evidence[0] if evidence else None
    if plan.auth == "password":
        if not case_name or not shot or not os.path.isfile(shot):
            raise AppError("凭证登录未生成可读取的结果截图，无法完成登录视觉核验")
        fc_path = os.path.join(resolve_case_path(case_name), FLOW_CONTEXT_FILENAME)
        evidence_path = frame_path(
            current_case_workspace(resolve_case_path(case_name), _ctx), "login-result.png")
        try:
            shutil.copy2(shot, evidence_path)
        except OSError as e:
            raise AppError(f"无法归档登录结果截图: {e}") from e
        if not os.path.isfile(evidence_path):
            raise AppError("登录结果截图归档后不存在，无法完成登录视觉核验")
        update_meta_fields(fc_path, {"login_evidence": {"path": evidence_path,
                                                       "status": "pending_visual_check"}})
        register_evidence(resolve_case_path(case_name), "login", "password_visual",
                          "pending", [evidence_path], stage="B2_login")
        print(format_visual_check_hint("env-prepare", evidence_path,
                                       "已归档为此次 Case 的登录证据，直接读图确认登录结果即可"))
    elif shot:
        register_evidence(resolve_case_path(case_name), "login", plan.auth,
                          "pending", [shot], stage="B2_login")
        print(format_visual_check_hint("env-prepare", shot))

    probe = result.get("probe")
    if probe is not None and not probe.reliable:
        print("[env-prepare] ⚠️ 登录态判定为「前台判定」语义（Android 既定行为），"
              "最终结论以读图为准")
    elif probe is not None:
        print(f"[env-prepare] ✅ 登录态验证通过: logged_in={probe.logged_in} "
              f"userId={probe.user_id or '-'}")

    # qahome 的登录态由「前台判定」确认 → 登记为 **verified** 证据。
    # ⚠️ 必须登记：`ack login_completed` 的门禁在无 meta.login_evidence 时会回退查
    # `verified_evidence(run_dir, "login")`（只认 evidence_status=verified），
    # 缺这条会导致 ack 失败、SOP 卡在 B2_login。
    if plan.auth == "qahome" and case_name:
        register_evidence(
            resolve_case_path(case_name), "login", "qahome_inspect_tree", "verified",
            details={"verification": probe.detail if probe else ""}, stage="B2_login",
        )

    append_event(
        resolve_case_path(case_name) if case_name else "",
        "environment.prepared",
        {"env": env, "auth_method": plan.auth, "account_type": plan.env_type,
         "target_env": plan.target_env, "restart_policies":
             [f"{s.step_id}:{s.restart_applied.value}" for s in result.get("steps", [])]},
    )
    print(f"\n[env-prepare] ✅ 环境准备完成（{env} 环境，{n}/{steps} 步）")
