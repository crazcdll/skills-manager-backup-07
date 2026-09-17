#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境准备合并命令 —— 一条命令完成 set-mis + reset-env + 登录 + 环境配置 + 锁包。

登录流程由 login_strategy.py 调度，五种环境类型对应五种策略。
失败即终止，不降级不继续。
"""
import json
import os
import shutil
from core.util.json_utils import read_json
from core.errors import AppError, AutotestError, ConfigError, MockError
from core.util.case_utils import set_current_user_mis
from mock.appmock_ops import reset_appmock_environment, push_testability_scheme
from core.util.paths import get_active_case
from core.util.case_utils import current_case_workspace, resolve_case_path, resolve_mis
from core.flow.flow_context import read_meta_fields, update_meta_fields
from core.audit.runtime_audit import append_event, register_evidence
from core.util.records import frame_path
from core.sop.constants import FLOW_CONTEXT_FILENAME
from environment.validators.env_validator import (
    validate_env_config, EnvValidationError, DEFAULT_APP,
    ENV_TYPE_MAP, ENV_NAME_TO_TYPE,
)
from environment.setup.sdk_enable import sdk_enable_and_restart
from environment.setup.login_strategy import build_login_strategy
from mock.ptest_mock import enable_ptest_mock
from actions.assertion_utils import format_visual_check_hint


def _step(n, total, title):
    print(f"\n{'='*60}", flush=True)
    print(f"[env-prepare] Step {n}/{total}: {title}", flush=True)
    print(f"{'='*60}", flush=True)

def _build_bundle_configs(bundles_str, bundle_env):
    """解析锁包参数，返回 testability scheme 配置列表。"""
    is_stage = 1 if bundle_env == "stage" else 0
    configs = []
    for item in bundles_str.split(","):
        item = item.strip()
        if ":" not in item:
            # 仅声明包名无版本：不锁包（执行时用户提供版本后才会锁包）
            print(f"  ⏭️ {item} 仅声明包名无版本，跳过锁包（执行时用户提供版本后才会锁包）")
            continue
        name, version = item.split(":", 1)
        name, version = name.strip(), version.strip()
        if name and version:
            configs.append({"type": "mrnbundle", "info": {
                "isStage": is_stage, "bundleName": name, "bundleVersion": version,
            }})
            print(f"  📦 {name} -> {version} ({bundle_env})")
    if configs:
        print(f"BUNDLE-LOCK: ✅ {len(configs)} 个 MRN bundle 配置已构建")
    return configs

def cmd_env_prepare(args):
    """环境准备合并入口。策略模式派发。

    参数自动填充：--env / --account / --password / --location / --bundles /
    --lane-name / --url-pattern / --url-mapping / --mis 缺省时从 flow-context.json
    的 env 块和 meta 块自动读取。
    """

    # ── 从 flow-context.json 自动填充缺失参数 ──
    case_name = get_active_case()
    fc_env = {}
    _ctx = {}
    if case_name:
        fc_path = os.path.join(resolve_case_path(case_name), FLOW_CONTEXT_FILENAME)
        meta = read_meta_fields(fc_path)
        try:
            _ctx = read_json(fc_path, default={})
            fc_env = _ctx.get("env", {})
        except Exception:
            fc_env = {}

        # --mis 缺省时从 meta 或 resolve_mis 获取
        if not args.mis:
            args.mis = meta.get("user_mis", "") or resolve_mis()

        # --env 缺省时从 env.type 映射
        if not args.env and fc_env.get("type"):
            args.env = ENV_TYPE_MAP.get(fc_env["type"], fc_env["type"])

        # --account / --password / --location 缺省时从 env 块获取
        if not args.account:
            args.account = fc_env.get("account") or None
        if not args.password:
            args.password = fc_env.get("_password_raw") or None
        if not args.location:
            args.location = fc_env.get("location") or None

        # --bundles / --bundle-env 缺省时从 env.bundle_lock（对象数组）获取；
        # version 为空的项仅声明目标，不参与锁包。
        if not args.bundles and fc_env.get("bundle_lock"):
            args.bundles = ",".join(
                (f"{b['name']}:{b['version']}" if b.get("version") else b["name"])
                for b in fc_env["bundle_lock"]
                if isinstance(b, dict) and b.get("name")
            )

        # --ptest 缺省时从 env.ptest 获取
        if args.ptest is None:
            args.ptest = bool(fc_env.get("ptest"))

        # --lane-name / --url-pattern / --url-mapping 缺省时从 env 块获取。
        # B 环境统一使用 env.swimline.{lane_name,url_pattern}。
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
    mis = args.mis
    app = _ctx.get("meta", {}).get("app") or fc_env.get("app") or DEFAULT_APP
    device_type = _ctx.get("meta", {}).get("device_type")

    # 凭证已在 flow-init → validate_env_config 阶段解析到位，
    # _password_raw 一定是真实凭证，此处直接透传，不再二次解析。
    resolved_password = args.password
    if not resolved_password and env == "online":
        raise ConfigError(
            f"{env} 环境必须提供凭证；解决: 在 steps-input.json 的 env.password 中填写真实凭证"
        )

    # 从 flow-context 读取 auth_method
    env_type_code = ENV_NAME_TO_TYPE.get(env, env)
    auth_method = fc_env.get("auth_method")

    env_config = {
        "type": env_type_code,
        "auth_method": auth_method,
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
    }

    try:
        normalized_env = validate_env_config(env_config, app=app, device_type=device_type)
    except EnvValidationError as e:
        raise ConfigError(f"环境配置校验失败: {e}") from e

    # 构建登录策略
    try:
        strategy = build_login_strategy(normalized_env, app=app)
    except ValueError as e:
        raise ConfigError(f"登录策略构建失败: {e}") from e

    # 策略前置校验
    ok, err = strategy.validate()
    if not ok:
        raise ConfigError(f"登录策略校验失败: {err}")

    # ── 计算步数 ──
    steps = 3  # reset + AppMock enable + 登录
    if normalized_env.get("ptest"):
        steps += 1
    if args.bundles:
        steps += 1
    n = 0
    testability_configs = []

    # ══════════════════════════════════════════════════════════
    #  Step 1: set-mis + reset-env（所有环境通用）
    # ══════════════════════════════════════════════════════════
    n += 1
    _step(n, steps, "设置 MIS + 环境重置")
    set_current_user_mis(mis)
    reset_appmock_environment(mis=mis)

    # ══════════════════════════════════════════════════════════
    #  Step 2: 设备端 AppMock SDK 启用（所有环境通用）
    # ══════════════════════════════════════════════════════════
    n += 1
    _step(n, steps, "设备端 AppMock SDK 启用")
    if not sdk_enable_and_restart(mis):
        raise AppError("AppMock SDK 启用失败，中止环境准备")

    # ══════════════════════════════════════════════════════════
    #  Step 3: ptest mock 配置（独立于登录的测试开关，env.ptest=true 时执行）
    # ══════════════════════════════════════════════════════════
    if normalized_env.get("ptest"):
        n += 1
        _step(n, steps, "ptest mock 配置")
        try:
            enable_ptest_mock(mis)
        except AutotestError as e:
            raise MockError(f"ptest mock 配置失败，中止环境准备: {e}") from e

    # ══════════════════════════════════════════════════════════
    #  Step 4: 执行登录策略
    # ══════════════════════════════════════════════════════════
    n += 1
    _step(n, steps, f"{strategy.get_auth_method()} 登录 ({env} 环境)")

    ok, shot, extra = strategy.execute(mis)
    if not ok:
        append_event(
            resolve_case_path(case_name),
            "login.failed",
            {"env": env, "method": strategy.get_auth_method(), "account": mis},
        )
        raise AppError(f"LOGIN FAILED: {env} 环境登录失败，中止环境准备")

    # 凭证登录需将截图归档到可读取的 frames 目录（而非依赖会被清理的 .run 顶层文件），
    # 确保人工核验、失败收口和报告引用同一证据。
    if strategy.get_auth_method() == "password":
        if not case_name or not shot or not os.path.isfile(shot):
            raise AppError("凭证登录未生成可读取的结果截图，无法完成登录视觉核验")
        evidence_path = frame_path(current_case_workspace(resolve_case_path(case_name), _ctx), "login-result.png")
        try:
            shutil.copy2(shot, evidence_path)
        except OSError as e:
            raise AppError(f"无法归档登录结果截图: {e}") from e
        if not os.path.isfile(evidence_path):
            raise AppError("登录结果截图归档后不存在，无法完成登录视觉核验")
        shot = evidence_path
        update_meta_fields(fc_path, {"login_evidence": {"path": shot, "status": "pending_visual_check"}})
        register_evidence(resolve_case_path(case_name), "login", "password_visual", "pending", [shot], stage="B2_login")
        print(format_visual_check_hint("env-prepare", shot, "已归档为此次 Case 的登录证据，直接读图确认登录结果即可"))
    elif shot:
        register_evidence(resolve_case_path(case_name), "login", strategy.get_auth_method(), "pending", [shot], stage="B2_login")
        print(format_visual_check_hint("env-prepare", shot))
    if extra:
        testability_configs.extend(extra)

    # ══════════════════════════════════════════════════════════
    #  登录状态验证
    # ══════════════════════════════════════════════════════════
    ok, verify_detail = strategy.verify()
    if not ok:
        raise AppError(f"LOGIN VERIFY FAILED: {verify_detail}")

    if strategy.get_auth_method() == "qahome":
        register_evidence(
            resolve_case_path(case_name), "login", "qahome_inspect_tree", "verified",
            details={"verification": verify_detail}, stage="B2_login"
        )
    if verify_detail and verify_detail != "[NEEDS_VISUAL_CHECK]":
        print(f"[env-prepare] ✅ 登录状态验证通过: {verify_detail}")

    # ══════════════════════════════════════════════════════════
    #  Step 5: MRN 锁包（可选）
    # ══════════════════════════════════════════════════════════
    if args.bundles:
        n += 1
        _step(n, steps, "MRN 锁包")
        cfg = _build_bundle_configs(args.bundles, args.bundle_env)
        if cfg:
            testability_configs.extend(cfg)

    # ── 合并推送 testability scheme ──
    has_bundle_lock = any(c["type"] == "mrnbundle" for c in testability_configs) if testability_configs else False
    if testability_configs:
        print(f"[env-prepare] 推送 testability scheme（{len(testability_configs)} 条配置）...")
        ok, _, detail = push_testability_scheme(testability_configs, verify=True, verify_wait=3.0)
        types = [c["type"] for c in testability_configs]
        register_evidence(
            resolve_case_path(case_name), "testability_config", "scheme_dispatch",
            "verified" if ok else "failed", details={"types": types, "detail": detail}, stage="B2_login"
        )
        if ok:
            print(f"[env-prepare] ✅ testability scheme 推送并验证成功 ({', '.join(types)})")
        elif has_bundle_lock:
            raise ConfigError(f"MRN 锁包失败，中止环境准备（bundle 版本可能不存在或已过期）: {detail}")
        else:
            raise ConfigError(f"testability scheme 执行失败: {detail}")

    append_event(
        resolve_case_path(case_name),
        "environment.prepared",
        {"env": env, "auth_method": strategy.get_auth_method(), "account_type": normalized_env.get("type", "")},
    )
    print(f"\n[env-prepare] ✅ 环境准备完成（{env} 环境，{n}/{steps} 步）")
