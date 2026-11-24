#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow JSON 入口：业务步骤模型 → 引擎 CASES。

为什么需要这一层
────────────────
业务模型（P0 的 steps.json）只描述「用户看到什么、做什么」：
  action / wait / checks
它不应该知道引擎的内部约定（sid 规则、asserts 结构、blur 注入、step-type）。
本模块是**唯一的映射点**：引擎内部字段变化只改这里，两侧解耦。

不做的事
────────
· 不做语义理解（不推断文案、不补步骤、不猜 action）—— 那是 P0 Skill 的职责；
· 不做占位符替换与 blur-input 注入 —— 仍由 StepsGenerator 负责（执行期不变量）；
· 不猜变量值 —— `env.vars` 声明了 `value`/`ask`，未声明的占位符直接报错。

用法
────
    from aitest.execution.engine.flow.flow_json import to_cases
    cases = to_cases(flow_json_dict)

或命令行（供 P0 / CI 调用）：
    python3 scripts/aitest/execution/engine/flow/flow_json.py --in steps.json --out cases-<tag>.json

CLI 产出的是 `steps-generate` 直接可吃的 CASES 文件（`{batch_name, cases[]}`），
不是裸数组 —— 两者之间不允许再有一次手写搬运。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 支持直接 `python3 scripts/aitest/execution/engine/flow/flow_json.py` 运行：把 scripts/ 放进 sys.path。
# 注意：这是**独立转换脚本入口**（不经 cli.py），因此自己负责一次 sys.path；
# 包内其它模块不得仿照（入口统一收口在 scripts/cli.py）。
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from aitest.shared.placeholders import (  # noqa: E402
    collect_case_placeholder_text,
    extract_placeholders,
    validate_var_spec,
)
from aitest.shared.step_schema import (  # noqa: E402
    normalize_role,
    role_error,
)

# 业务 action → 引擎 action。
# `none` 是「本步只做断言、无操作」，引擎用 assert-text 表达（无副作用、可重放）。
ACTION_MAP = {
    "tap-text": "tap-text",
    "input-text": "input-text",
    "scroll-until": "scroll-until",
    "scroll-bottom": "scroll-edge",
    "back": "back",
    "open-url": "open-url",
    "none": "assert-text",
}

# 业务 check 类型 → 引擎断言。
# 说明：
#   render_ready —— 同时置位步骤 page_ready（截图前等页面稳定）；
#                   可以不带 text：Base case 只验证「页面能打开」，0 条 text 断言合法
#   vision       —— 视觉断言：截图后生成 verify_visual_assertion hook，由 AI 读本次运行截图判定
#                   （text 断言已经内建 verify_text_visual_recheck，无需额外的「文案+视觉」类型）
CHECK_TEXT_PRESENT = ("text", "present")
CHECK_TEXT_GONE = ("text", "gone")
CHECK_VISUAL = ("visual", "")

ACTION_ARG_REQUIRED = ("tap-text", "scroll-until", "open-url", "input-text")


class FlowJsonError(ValueError):
    """业务步骤 JSON 不合法（缺字段 / 枚举非法 / 结构不符）。"""


def _check_kind(check: dict) -> tuple:
    ctype = str(check.get("type") or "").strip()
    if ctype in ("text", "render_ready"):
        return CHECK_TEXT_PRESENT
    if ctype == "text_gone":
        return CHECK_TEXT_GONE
    if ctype == "vision":
        return CHECK_VISUAL
    raise FlowJsonError(
        f"未知 check.type: {ctype!r}（支持 text/render_ready/text_gone/vision）"
    )


def _build_assert(check: dict, step: dict) -> dict | None:
    """单条 check → 引擎断言；render_ready 不带 text 时返回 None（只留 page_ready）。"""
    ctype = str(check.get("type") or "").strip()
    text = str(check.get("text") or "").strip()
    if not text:
        if ctype == "render_ready":
            return None
        raise FlowJsonError(f"步骤 {step.get('id')} 存在空 check.text")

    kind, match = _check_kind(check)
    assert_spec = {"kind": kind, "expect": text}
    if kind == "text":
        assert_spec["match"] = match
    # 视觉断言只带预期文案，截图与 AI 判定由断言层完成
    return assert_spec


def _build_step(step: dict, sid: str, index: int) -> dict:
    kind = str(step.get("kind") or "ui").strip()
    name = str(step.get("name") or "").strip() or sid
    role = normalize_role(step.get("role"))
    err = role_error(
        role, index=index, kind=kind,
        action=str((step.get("action") or {}).get("kind") or "").strip(),
    )
    if err:
        raise FlowJsonError(f"步骤 {step.get('id') or index} {err}")

    if kind == "api":
        api = step.get("api") or {}
        fields = []
        for field in api.get("expectedFields") or []:
            item = {
                "source": str(field.get("source") or "response"),
                "field": str(field.get("field") or ""),
            }
            if str(field.get("expected") or "").strip():
                item["expected"] = str(field["expected"])
            fields.append(item)
        api_assert = {
            "method": str(api.get("method") or "GET").upper(),
            "path": str(api.get("path") or ""),
        }
        if fields:
            api_assert["expected_fields"] = fields
        return {"sid": sid, "kind": "api", "desc": name, "api_assert": api_assert}

    if kind == "track":
        track = step.get("track") or {}
        track_assert = {"match": str(track.get("match") or "")}
        expected = track.get("expectedFields")
        if isinstance(expected, dict) and expected:
            track_assert["expected_fields"] = dict(expected)
        return {"sid": sid, "kind": "track", "desc": name, "track_assert": track_assert}

    action_kind = str((step.get("action") or {}).get("kind") or "").strip()
    engine_action = ACTION_MAP.get(action_kind)
    if not engine_action:
        raise FlowJsonError(
            f"步骤 {step.get('id') or index} 的 action.kind 非法: {action_kind!r}"
            f"（支持 {sorted(ACTION_MAP)}）"
        )

    action = step.get("action") or {}
    action_arg = str(action.get("text") or "").strip()
    if engine_action == "input-text":
        # 锚点与输入值是两件事：引擎的 input-text 契约是
        # `{"anchor": "<输入框附近的锚点>", "text": "<要输入的值>"}`。
        action_arg = json.dumps(
            {"anchor": action_arg, "text": str(action.get("value") or "").strip()},
            ensure_ascii=False,
        )
    checks = step.get("checks") or []
    # 只有首步落地 open-url 允许无 check：它只负责把页面打开（就绪由后续断言步骤验证），
    # 生成期注入的 landing 步骤即走这条豁免；用例中途的 open-url 仍必须有断言，避免空跑通过。
    is_landing = engine_action == "open-url" and index == 0
    if not isinstance(checks, list) or (not checks and not is_landing):
        raise FlowJsonError(f"步骤 {step.get('id') or index} 至少需要 1 条 check")

    asserts = [item for item in (_build_assert(c, step) for c in checks) if item]
    wait = step.get("wait") or {}
    page_ready = (
        str(wait.get("type") or "") == "page_ready"
        or any(str(c.get("type")) == "render_ready" for c in checks)
    )

    return {
        "sid": sid,
        "kind": "ui",
        "desc": name,
        "action": engine_action,
        "action_arg": action_arg if engine_action in ACTION_ARG_REQUIRED else None,
        "asserts": asserts,
        "step-type": "assert" if engine_action == "assert-text" else "interaction",
        "page_ready": page_ready,
        "screenshot": None,
        "role": role,
    }


def _build_steps(steps: list) -> list:
    """按类型分前缀编号：UI=S / API=A / track=T（S/A/T 供报告与平台稳定引用）。"""
    counters = {"ui": 0, "api": 0, "track": 0}
    prefixes = {"ui": "S", "api": "A", "track": "T"}
    built = []
    for index, step in enumerate(steps):
        kind = str(step.get("kind") or "ui").strip()
        counters[kind] = counters.get(kind, 0) + 1
        sid = f"{prefixes.get(kind, 'S')}{counters[kind]}"
        built.append(_build_step(step, sid, index))
    return built


def _extract_mock_ids(flow: dict) -> list:
    """从 steps.json 提取场景 mockId：case 级 `mock_ids` 或 `env.mock_ids`。

    mockId 全局唯一，不声明归属域；列表元素可为字符串或含 id/mockId 的对象。
    """
    env = flow.get("env") or {}
    raw = flow.get("mock_ids") or env.get("mock_ids") or []
    if isinstance(raw, dict):
        raw = list(raw.keys())
    if not isinstance(raw, list):
        return []
    ids = []
    for item in raw:
        if isinstance(item, dict):
            item = item.get("id") or item.get("mockId") or item.get("ruleId") or ""
        value = str(item).strip()
        if value and value not in ids:
            ids.append(value)
    return ids


def _extract_vars(flow: dict) -> dict:
    """steps.json 的 `env.vars` → case 级 vars（结构不变，引擎逐项解释）。

    `{name: {value} | {ask: true, desc} | {date: N, format?}}`：
      · value —— 转化期确定值，flow-init 直接注入答案；
      · ask   —— 执行前由提问流程收集，desc 即提问文案；
      · date  —— 相对批次日期基线偏移 N 天（可为负），format 默认 `%Y-%m-%d`；
      · desc/example 仅作说明与提问体验，不参与替换。
    """
    env = flow.get("env") or {}
    raw = env.get("vars")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise FlowJsonError("env.vars 必须是对象（{变量名: {value|ask|date, ...}}）")

    errors = []
    out = {}
    for raw_name, spec in raw.items():
        name = str(raw_name).strip()
        errors.extend(validate_var_spec(name, spec, where=f"env.vars.{name}"))
        out[name] = dict(spec) if isinstance(spec, dict) else spec
    if errors:
        raise FlowJsonError("env.vars 声明非法：\n" + "\n".join(f"  - {e}" for e in errors))
    return out


def _assert_placeholders_declared(case: dict):
    """硬门禁：case 里每个 `{xxx}` 都必须在 vars 声明，杜绝 AI 漏填/自造变量。"""
    declared = set((case.get("vars") or {}).keys())
    missing = [
        name for name in extract_placeholders(collect_case_placeholder_text(case))
        if name not in declared
    ]
    if missing:
        raise FlowJsonError(
            f"Case {case.get('case_id')}: 占位符 {missing} 未在 env.vars 声明"
            "（固定值用 value，执行前填写用 ask，日期用 date）"
        )


# env 字段与引擎、AppMock 同名（snake_case）；这里只做白名单校验与字段挑选，不改名。
ENV_KEYS = frozenset({
    "scheme", "type", "swimline", "url_mappings", "bundle_lock",
    "testability", "mock_ids", "vars",
    "preconditions",  # 说明性字段：允许出现，引擎不消费
})
SWIMLINE_KEYS = frozenset({"lane_name", "url_pattern"})


def _extract_env(flow: dict) -> dict:
    """steps.json 的 `env` → 引擎 case 级 env（同形状直传，只做白名单校验）。

    steps.json 的 `env` 是**场景声明**（deep-link 所在 mock 场景自带），
    执行期与 intake 合成结果合并（场景声明优先，intake 补凭证/ptest）。

    `scheme` / `vars` / `mock_ids` / `preconditions` 各有独立通道，
    不进入 case env；其余字段原样带入。
    """
    env = flow.get("env") or {}
    if not isinstance(env, dict):
        raise FlowJsonError("env 必须是对象（至少包含 scheme）")

    unknown = sorted(set(env) - ENV_KEYS)
    if unknown:
        raise FlowJsonError(
            f"env 存在不认识的字段 {unknown}（支持 {sorted(ENV_KEYS)}）"
            "（env 字段与引擎 / AppMock 同名，统一 snake_case）"
        )

    out = {}
    env_type = str(env.get("type") or "").strip()
    if env_type:
        out["type"] = env_type

    swim = env.get("swimline")
    if isinstance(swim, str):  # 简写：字符串即泳道名
        swim = {"lane_name": swim}
    if isinstance(swim, dict):
        unknown_swim = sorted(set(swim) - SWIMLINE_KEYS)
        if unknown_swim:
            raise FlowJsonError(
                f"env.swimline 存在不认识的字段 {unknown_swim}"
                f"（只接受 {sorted(SWIMLINE_KEYS)}）"
            )
        lane = str(swim.get("lane_name") or "").strip()
        pattern = str(swim.get("url_pattern") or "").strip()
        if lane:
            out["swimline"] = {"lane_name": lane, "url_pattern": pattern or "/*"}
        elif pattern:
            raise FlowJsonError("env.swimline 只有 url_pattern 没有 lane_name（泳道必须先有名字）")

    url_mappings = env.get("url_mappings")
    if isinstance(url_mappings, list) and url_mappings:
        out["url_mappings"] = url_mappings
    bundle_lock = env.get("bundle_lock")
    if isinstance(bundle_lock, list) and bundle_lock:
        out["bundle_lock"] = bundle_lock
    # 可测性配置就是 Pillow action 列表：原样透传，执行期整表下发（不拆不改）。
    # 结构错误在这里就拦住——语义校验由 flow-init（steps_builder）统一执行。
    testability = env.get("testability")
    if testability is not None:
        if not isinstance(testability, list):
            raise FlowJsonError("env.testability 必须是数组（Pillow action 列表）")
        if testability:
            out["testability"] = testability
    return out

LANDING_STEP_ID = "open-landing"


def _ensure_landing_step(steps: list, scheme: str) -> list:
    """落地页跳转统一由首步 `open-url` 表达（`env.scheme` 是唯一 URL 事实源）。

    · 首步已是 `open-url` —— URL 必须与 `env.scheme` 完全一致（双事实源/双跳直接拒绝）；
    · 首步不是 —— 在头部注入一条 open-url 步骤，避免「漏写落地动作 → 页面没打开就开始断言」
      这类静默失败（引擎侧只认步骤，没有独立的落地阶段兜底）；
    · 全为 api/track 步骤 —— 不注入：没有 UI 走查时打开页面无意义，也不该让入口不可用
      把纯接口用例判成 blocked。

    `role` 与视觉确认断言**不在这里写**：那是执行期不变量，由装载层
    `steps_builder.build_steps_json → shared.landing.ensure_confirm` 统一补齐，
    避免「业务模型入口」与「手写 CASES 入口」各维护一份。
    """
    if not any(str((s or {}).get("kind") or "ui").strip() == "ui" for s in steps):
        return steps

    first = steps[0] if steps else None
    if isinstance(first, dict):
        action = first.get("action") or {}
        if str(action.get("kind") or "").strip() == "open-url":
            url = str(action.get("text") or "").strip()
            if url != scheme:
                raise FlowJsonError(
                    f"首步 open-url 与 env.scheme 不一致：{url!r} != {scheme!r}"
                    "（落地入口只允许一个事实源，禁止两处各写一份）"
                )
            return steps
    return [
        {
            "kind": "ui",
            "id": LANDING_STEP_ID,
            "name": "打开落地页",
            "action": {"kind": "open-url", "text": scheme},
            "wait": {"type": "page_ready"},
        }
    ] + steps


def to_cases(flow: dict) -> list:
    """业务 Flow JSON → 引擎 CASES 数组（一个 Flow 对应一个 case）。"""
    if not isinstance(flow, dict):
        raise FlowJsonError("Flow JSON 根节点必须是对象")

    env = flow.get("env") or {}
    scheme = str(env.get("scheme") or "").strip()
    if not scheme:
        raise FlowJsonError("Flow 缺少 env.scheme（落地入口）")

    steps = flow.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise FlowJsonError("Flow 至少需要 1 个步骤")
    steps = _ensure_landing_step(steps, scheme)

    case = {
        "case_id": str(flow.get("caseId") or flow.get("id") or "").strip() or "case-01",
        "case_name": str(flow.get("title") or "untitled").strip(),
        "landing_scheme": scheme,
        "steps": _build_steps(steps),
    }
    mock_ids = _extract_mock_ids(flow)
    if mock_ids:
        case["mock_ids"] = mock_ids
    vars_spec = _extract_vars(flow)
    if vars_spec:
        case["vars"] = vars_spec
    case_env = _extract_env(flow)
    if case_env:
        case["env"] = case_env
    _assert_placeholders_declared(case)
    return [case]


def to_batch(flow: dict) -> dict:
    """业务 Flow JSON → 引擎 CASES 文件（steps-generate 的入参形状）。

    与 `steps-generate` 的契约一致：`{batch_name, device, env, cases[]}`。
    `env` 留空（由 intake 合成 + case 级场景声明覆盖），`device` 缺省由
    StepsGenerator 兜底，避免在映射层硬编码设备形态。
    """
    cases = to_cases(flow)
    batch = {
        "batch_name": str(flow.get("batchName") or flow.get("title") or "").strip(),
        "cases": cases,
    }
    device = flow.get("device")
    if isinstance(device, dict) and device:
        batch["device"] = device
    return batch


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="业务步骤 JSON → 引擎 CASES")
    parser.add_argument("--in", dest="input", required=True, help="steps.json 路径")
    parser.add_argument("--out", dest="output", required=True, help="输出 CASES JSON 路径")
    args = parser.parse_args(argv)

    try:
        flow = load(args.input)
        batch = to_batch(flow)
        cases = batch["cases"]
    except (FlowJsonError, OSError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(batch, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    total_steps = sum(len(c["steps"]) for c in cases)
    total_asserts = sum(len(s.get("asserts") or []) for c in cases for s in c["steps"])
    total_api = sum(1 for c in cases for s in c["steps"] if s.get("kind") == "api")
    total_track = sum(1 for c in cases for s in c["steps"] if s.get("kind") == "track")
    print(
        f"✅ {args.output}（{len(cases)} case / {total_steps} 步 / {total_asserts} UI 断言 / "
        f"{total_api} 接口 + {total_track} 埋点）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
