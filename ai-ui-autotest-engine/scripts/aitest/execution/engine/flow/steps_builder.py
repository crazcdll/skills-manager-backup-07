#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""steps-input.json 结构与语义校验 —— 从 flow_init.py 提取的共享模块。

被 flow_init.py（执行期）、steps_generator.py（生成期）
两方共同使用，避免上游模块逆向依赖下游模块。

包含：
  build_steps_json      — 将 case steps 数组编译为 steps_json 结构
  validate_steps_json   — 校验 steps-input.json 的结构和语义

不包含：
  init_from_steps_json        — flow-context 初始化（执行期专属，留在 flow_init.py）
"""

from aitest.execution.engine.sop.actions import STEP_ACTIONS
from aitest.provisioning.validators.env_validator import validate_env_config, EnvValidationError
from aitest.provisioning.validators.device_validator import validate_device_combination, DeviceValidationError
from aitest.provisioning.validators.testability_validator import (
    TestabilityValidationError,
    validate_testability,
)
from aitest.shared.landing import ensure_confirm
from aitest.shared.step_schema import normalize_role, role_error


def build_steps_json(case_steps, case_id=""):
    """将 case steps 数组编译为 steps_json 结构。

    验证步骤结构合法性（kind/action/sid/asserts 等），
    返回结构化 steps_json 列表。校验失败时 raise ValueError。
    """
    if not isinstance(case_steps, list) or not case_steps:
        raise ValueError(f"Case {case_id} 的 steps 必须是非空数组")
    allowed_actions = STEP_ACTIONS
    seen_sids = set()
    errors = []
    _R = lambda sid, desc: f"（case: {case_id}, sid: {sid}, desc: {desc}）"

    for i, s in enumerate(case_steps):
        sid, desc, action = s.get("sid"), s.get("desc"), s.get("action")
        kind = s.get("kind", "ui")
        if not isinstance(sid, str) or not sid.strip() or not isinstance(desc, str) or not desc.strip():
            errors.append(f"Case {case_id} 第 {i + 1} 步必须提供非空 sid 和 desc")
            continue
        if sid in seen_sids:
            errors.append(f"Case {case_id} 步骤 sid 重复: {sid}（desc: {desc}）")
        seen_sids.add(sid)
        if kind not in {"ui", "api", "track"}:
            errors.append(f"{kind.upper()} 步骤 {_R(sid, desc)} kind 非法: {kind!r}（仅支持 ui/api/track）")
            continue
        _kind_rules = {
            "ui": {
                "forbidden": ("api_assert", "track_assert"),
                "required": ("action",),
                "action_check": lambda a: a in allowed_actions,
                "arg_check": lambda a, s: a in ("tap-text", "scroll-until", "open-url", "blur-input") and not s.get("action_arg"),
            },
            "api": {
                "forbidden": ("action", "action_arg", "asserts", "step-type", "screenshot", "wait_text"),
                "required": ("api_assert",),
                "action_check": None,
                "arg_check": None,
            },
            "track": {
                "forbidden": ("action", "action_arg", "asserts", "step-type", "screenshot", "wait_text"),
                "required": ("track_assert",),
                "action_check": None,
                "arg_check": None,
            },
        }
        _kr = _kind_rules[kind]
        _conflicts = [f for f in _kr["forbidden"] if s.get(f) is not None]
        if _conflicts:
            errors.append(
                f"{kind.upper()} 步骤 {_R(sid, desc)} 包含不允许的字段: "
                f"{', '.join(_conflicts)}。请将 UI 断言/操作拆分为独立的 ui 步骤。"
            )
        for _req in _kr["required"]:
            if not s.get(_req):
                errors.append(f"{kind.upper()} 步骤 {_R(sid, desc)} 缺少必填字段: {_req}")
        if _kr["action_check"] and action and not _kr["action_check"](action):
            errors.append(f"{kind.upper()} 步骤 {_R(sid, desc)} action 非法: {action!r}")
        if _kr["arg_check"] and _kr["arg_check"](action, s):
            errors.append(f"{kind.upper()} 步骤 {_R(sid, desc)} 的 {action} 必须提供 action_arg")
        # api_assert 结构硬校验：path 为空会匹配任意录制请求 → 静默假通过
        if kind == "api":
            _api = s.get("api_assert")
            if isinstance(_api, dict):
                if not str(_api.get("path") or "").strip():
                    errors.append(
                        f"API 步骤 {_R(sid, desc)} 的 api_assert.path 必填且不能为空"
                        f"（path 为空会匹配任意录制请求，导致静默假通过）"
                    )
                _efs = _api.get("expected_fields")
                if _efs is not None:
                    if not isinstance(_efs, list):
                        errors.append(
                            f"API 步骤 {_R(sid, desc)} 的 api_assert.expected_fields 必须是数组"
                        )
                    else:
                        for _ei, _ef in enumerate(_efs):
                            if not isinstance(_ef, dict) or not str(_ef.get("field") or "").strip():
                                errors.append(
                                    f"API 步骤 {_R(sid, desc)} 的 expected_fields[{_ei}] 必须提供非空 field"
                                    f"（如 {{\"source\":\"request\",\"field\":\"goodsId\",\"expected\":\"123\"}}）"
                                )
        # track_assert 结构硬校验：match 为空时 match_events 直接返回空 → 步骤必失败。
        # 运行时已安全（不会假通过），但应在生成/装载期尽早拦截，避免白等 10s 轮询。
        if kind == "track":
            _track = s.get("track_assert")
            if isinstance(_track, dict) and not str(_track.get("match") or "").strip():
                errors.append(
                    f"TRACK 步骤 {_R(sid, desc)} 的 track_assert.match 必填且不能为空"
                    f"（正确示例: {{\"track_assert\":{{\"match\":\"事件名\"}}}}）"
                )
            # 埋点期望字段：{字段名: 期望值} 对象。语义名允许，由 AI 判定时落到实测字段。
            _tef = _track.get("expected_fields") if isinstance(_track, dict) else None
            if _tef is not None and not isinstance(_tef, dict):
                errors.append(
                    f"TRACK 步骤 {_R(sid, desc)} 的 track_assert.expected_fields 必须是对象"
                    f"（如 {{\"page_type\":\"全日房\",\"button_name\":\"房型详情\"}}）"
                )

        # 校验 role（目前仅落地步骤使用）：合法性规则与编译层共用 shared.step_schema，
        # 避免「编译期认为是落地步骤、执行期不认」的双份判定。
        role = normalize_role(s.get("role"))
        _role_err = role_error(role, index=i, kind=kind, action=action)
        if _role_err:
            errors.append(f"步骤 {_R(sid, desc)} {_role_err}")
        # 校验 asserts 字段（新协议）
        asserts = s.get("asserts", [])
        if asserts and not isinstance(asserts, list):
            errors.append(f"步骤 {_R(sid, desc)} 的 asserts 必须是数组")
        if s.get("step-type") == "assert" and not asserts and kind == "ui":
            errors.append(
                f"步骤 {_R(sid, desc)} 声明 step-type=assert 但未提供任何断言"
                f"（asserts 至少填一项）。"
                f"空断言会恒定判为 PASS，掩盖真实缺陷"
            )
        # 校验 asserts 中各断言（文本/视觉同构：kind / match / expect / targets）
        if asserts:
            valid_kinds = {"text", "visual"}
            valid_matches = {"present", "gone"}
            for i, a in enumerate(asserts):
                if not isinstance(a, dict):
                    errors.append(f"步骤 {_R(sid, desc)} asserts[{i}] 必须是对象（如 "
                                  f"{{\"kind\":\"text\",\"match\":\"present\",\"expect\":\"目标文案\"}}）")
                    continue
                a_kind = a.get("kind")
                if a_kind not in valid_kinds:
                    errors.append(f"步骤 {_R(sid, desc)} asserts[{i}] 的 kind 非法: {a_kind!r}（仅支持 {valid_kinds}）")
                if not str(a.get("expect") or "").strip():
                    errors.append(f"步骤 {_R(sid, desc)} asserts[{i}] 必须提供 expect（目标短句）")
                a_match = a.get("match") or "present"
                if a_kind == "text" and a_match not in valid_matches:
                    errors.append(f"步骤 {_R(sid, desc)} asserts[{i}] kind=text 的 match 非法: {a_match!r}（仅支持 {valid_matches}）")
                if a.get("targets") is not None and not isinstance(a.get("targets"), list):
                    errors.append(f"步骤 {_R(sid, desc)} asserts[{i}] 的 targets 必须是数组")

    if errors:
        raise ValueError(
            " | ".join(e for e in errors)
        )

    steps_json = []
    for index, s in enumerate(case_steps):
        built = {
            "sid": s["sid"],
            "kind": s.get("kind", "ui"),
            "desc": s["desc"],
            "action": s.get("action"),
            "action_arg": s.get("action_arg"),
            "direction": s.get("direction"),
            "action_anchor": s.get("action_anchor"),
            "action_x": s.get("action_x"),
            "action_y": s.get("action_y"),
            "asserts": s.get("asserts", []),
            "step-type": s.get("step-type"),
            "screenshot": s.get("screenshot"),
            "page_ready": s.get("page_ready", False),
            "status": "pending",
            "ok": None,
            "started_at": None,
            "completed_at": None,
            "hooks": [],
            "action_type": None,
            "fail_reason": None,
            "track_assert": s.get("track_assert"),
            "api_assert": s.get("api_assert"),
            "role": normalize_role(s.get("role")),
        }
# 落地步骤归一化：role / page_ready / 内建视觉确认断言（运行期截图自证）。
# 放在装载层（CASES → flow-context 的唯一汇聚点）而不是某个入口，
# 手写 CASES 与 business-steps 注入两条路径自动一致。
        steps_json.append(ensure_confirm(built, index))
    return steps_json


_CASE_ENV_KEYS = ("type", "swimline", "url_mappings", "bundle_lock",
                  "testability")


def _normalize_case_env(env, errors, case_id, fallback_env_type=""):
    """cases[].env（场景声明）→ 引擎 env 片段。

    这里收到的是引擎层 env（snake_case）。
    """
    out = {}
    if env.get("type"):
        out["type"] = str(env["type"]).strip()
    swim = env.get("swimline")
    if swim is not None:
        if not isinstance(swim, dict):
            errors.append(
                f"Case {case_id} env.swimline 必须是对象 {{lane_name, url_pattern}}"
            )
        else:
            lane = str(swim.get("lane_name") or "").strip()
            pattern = str(swim.get("url_pattern") or "").strip()
            if lane:
                out["swimline"] = {"lane_name": lane, "url_pattern": pattern or "/*"}
    for key in ("url_mappings", "bundle_lock"):
        value = env.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(f"Case {case_id} env.{key} 必须是数组")
            continue
        out[key] = value

    # 可测性配置：结构 + 语义前置校验。这里失败时整台模拟器还没创建，
    # 比等到 B2 下发才发现不可用便宜得多；错误直接进 errors，不做静默过滤。
    testability = env.get("testability")
    if testability is not None:
        if not isinstance(testability, list):
            errors.append(f"Case {case_id} env.testability 必须是数组（Pillow action 列表）")
        else:
            try:
                for warning in validate_testability(
                    testability, env_type=out.get("type") or fallback_env_type
                ):
                    print(f"⚠️ Case {case_id} {warning}")
                out["testability"] = testability
            except TestabilityValidationError as exc:
                errors.append(f"Case {case_id} env.testability 校验失败：{exc.detail or exc}")
    return out


def _merge_case_env(cases, errors, fallback_env_type=""):
    """提取 case 级场景环境并收敛为批级 env。

    环境切换需要重启 App（并可能使 AppMock SDK 状态失效），因此一次 run 只允许
    一个可测环境：全批声明一致 → 采用该声明；不一致 → 报错并要求按环境拆分 run。
    """
    declared = []
    for i, case in enumerate(cases):
        env = case.get("env")
        if env is None:
            continue
        case_id = case.get("case_id") or f"case-{i + 1:02d}"
        if not isinstance(env, dict):
            errors.append(f"Case {case_id} env 必须是对象")
            continue
        unknown = [key for key in env if key not in _CASE_ENV_KEYS]
        if unknown:
            errors.append(
                f"Case {case_id} env 不支持字段 {unknown}（仅支持 {list(_CASE_ENV_KEYS)}）"
            )
            continue
        declared.append((case_id, env))

    if not declared:
        return {}
    first_id, first_env = declared[0]
    for case_id, env in declared[1:]:
        if env != first_env:
            errors.append(
                f"同一批次声明的可测环境不一致（{first_id} vs {case_id}）；"
                "一次 run 只切换一次环境，请按可测环境拆分为多个 run"
            )
            return {}
    return _normalize_case_env(first_env, errors, first_id, fallback_env_type)


def validate_steps_json(ai_input, env_info=None):
    """校验 steps-input.json 的结构和语义。

    env 块以 **intake 合成** 为基线，再用 `cases[].env`（场景声明，来自
    steps.json / Lyrebird mock 场景）覆盖可测环境字段；场景声明必须全批一致。
    返回 (merged_env, batch_name, cases)，或 raise ValueError。
    """
    if not isinstance(ai_input, dict):
        raise ValueError("steps-input.json 根节点必须是对象")

    from aitest.shared.intake import read_intake
    from aitest.provisioning.validators.env_validator import build_env_from_intake
    ai_env = dict(ai_input.get("env", {}) or {})
    ai_env.update(build_env_from_intake(read_intake()))
    # 批级 env 也可能直接带 testability（手写 steps-input / 平台直传），与 case 级同口径前置校验。
    if ai_env.get("testability") is not None:
        try:
            validate_testability(ai_env["testability"], env_type=ai_env.get("type"))
        except TestabilityValidationError as exc:
            raise ValueError(f"env.testability 校验失败：{exc.detail or exc}") from exc
    batch_name = ai_input.get("batch_name", "")
    cases = ai_input.get("cases", [])

    if not cases:
        raise ValueError("steps-input.json 必须包含 cases 数组")

    all_errors = []
    scenario_env = _merge_case_env(cases, all_errors, ai_env.get("type"))
    if scenario_env:
        ai_env.update(scenario_env)

    # 规则库直取：mockId 全局唯一，服务端解析归属域，调用方不声明域。
    ai_input["env"] = ai_env

    device_cfg = ai_input.get("device", {}) or {}
    device_app = device_cfg.get("app", "meituan")
    device_type_val = device_cfg.get("type", "sandbox")
    try:
        validate_device_combination(
            device_type_val,
            device_cfg.get("platform", "android"),
            device_app,
        )
    except DeviceValidationError as e:
        raise ValueError(str(e))

    merged_env = dict(ai_env)
    if env_info:
        merged_env.update(env_info)

    try:
        merged_env = validate_env_config(merged_env, app=device_app, device_type=device_type_val)
    except EnvValidationError as e:
        raise ValueError(f"环境配置校验失败: {e}")

    # 场景 Mock 为 case 级（flow-init 透传），此处不再做批级 mock 一致性校验

    for i, case in enumerate(cases):
        case_id = case.get("case_id", f"case-{i+1:02d}")
        landing_scheme = case.get("landing_scheme", merged_env.get("landing_scheme", ""))
        if not isinstance(landing_scheme, str) or not landing_scheme.strip():
            all_errors.append(f"Case {case_id} 缺少 landing_scheme（落地页 Scheme 必须提供）")
            continue
        # 占位符校验统一由③流程处理，此处不再重复检查 landing_scheme
        try:
            build_steps_json(case.get("steps", []), case_id=case_id)
        except ValueError as e:
            all_errors.append(str(e))

    if all_errors:
        raise ValueError("steps-input.json 校验失败（共 %d 个错误）:\n%s" % (
            len(all_errors),
            "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(all_errors))
        ))

    return merged_env, batch_name, cases