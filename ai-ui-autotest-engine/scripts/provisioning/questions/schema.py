#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Question Schema —— 问题定义与校验（全框架唯一事实来源）。

一条 Question 就是一份可序列化的 dict（可直接落 `intake.json`）；本模块负责：

  - 默认值填充（`normalize_question`）
  - 契约校验（`validate_questions`）：字段类型 / 白名单 / 条件引用完整性 / options 一致性
  - 对外视图（`public_view`）：剥离不可序列化字段（如 `resolve` 回调）

设计约束：schema 违反属**脚本缺陷**（provider 写错），一律 raise ContractError，
不做静默兜底。
"""
import re

from shared.errors import ContractError, UsageError

# ── 白名单（扩展先改这里，再改 provider）──────────────────────────────
GROUPS = ("identity", "device", "env", "scope", "config", "placeholder")
INPUT_TYPES = ("text", "mixed", "single", "multi")
SOURCES = ("ask", "derived")

# 对外可见的字段（剥离 resolve 等不可序列化项）
_PUBLIC_KEYS = (
    "id", "group", "order", "prompt", "input_type", "required",
    "options", "default", "depends_on", "source", "sensitive", "note",
)

# ═══════════════════════════════════════════════════════════════════
# AskQuestion 渲染契约（AI 只负责原样渲染，零判断）
# ═══════════════════════════════════════════════════════════════════
#
# AskQuestion 是纯选择题工具（每题至少 2 个选项）。为让「选择题 / 填空题」
# 都能落到同一个工具上，框架统一定义两个信号值：
#   · __manual_input__ —— 用户选择「手动输入」：题目**不落值**，AI 在对话中
#                          收取真实值后再 input-answer。
#   · __skip__         —— 用户选择「跳过」：仅 required=false 的题可跳过，
#                          引擎按该题 default 落值（无 default 则为 None）。
MANUAL_INPUT_VALUE = "__manual_input__"
SKIP_VALUE = "__skip__"

_MANUAL_INPUT_OPTION = {"value": MANUAL_INPUT_VALUE, "label": "✏️ 手动输入"}
_SKIP_OPTION = {"value": SKIP_VALUE, "label": "⏭️ 跳过（稍后再说）"}


def build_render(q: dict) -> dict:
    """计算题目在 AskQuestion 上的渲染规格。

    · 封闭选项题（single/multi 且 options ≥ 2）→ mode="choice"，原样透传 options；
    · 其余（text/mixed / options 不足）→ mode="free_text"，固定给「手动输入 / 跳过」两项。
    无论哪种，`render.options` 长度恒 ≥ 2，AI 直接原样交给 AskQuestion 即可。
    """
    options = [dict(o) for o in (q.get("options") or []) if not o.get("disabled")]
    if q.get("input_type") in ("single", "multi") and len(options) >= 2:
        mode = "choice"
    else:
        mode = "free_text"
        options = [dict(_MANUAL_INPUT_OPTION), dict(_SKIP_OPTION)]
    render = {"mode": mode, "options": options}
    if q.get("default") is not None:
        render["default"] = q.get("default")
    return render


def build_hint(q: dict) -> str:
    """按题目生成「下一步该怎么做」的操作指引（替代历史硬编码 ai_guide）。"""
    qid = q["id"]
    if q.get("source") == "derived":
        # 派生题引擎自动回填、永不提问，不能沿用「交给 AskQuestion」的问句（那会误导 AI）
        note = q.get("note")
        return "引擎自动派生（无需提问 / 无需作答）" + (f"：{note}" if note else "")
    required = bool(q.get("required"))
    if build_render(q)["mode"] == "choice":
        return (
            f"{'必填' if required else '选填'}。把 render.options 原样交给 AskQuestion，"
            f"用户选定后执行 input-answer --id {qid} --value <所选 value>"
        )
    if required:
        return (
            f"必填。把 render.options（手动输入/跳过）原样交给 AskQuestion；"
            f"用户选『✏️ 手动输入』后在对话中收取真实值，再执行 "
            f"input-answer --id {qid} --value <值>（该题必填，跳过会被拒绝）"
        )
    return (
        f"选填。把 render.options（手动输入/跳过）原样交给 AskQuestion；"
        f"用户选『✏️ 手动输入』后在对话中收取真实值并 input-answer --id {qid} --value <值>；"
        f"选『⏭️ 跳过』则执行 input-answer --id {qid} --value {SKIP_VALUE}"
    )


def coerce_value(value, options):
    """把单值向 options 声明的基本类型靠拢（bool/int/float）；无法判定时原样返回。

    解决 JSON 基本类型与 options 声明类型不一致（如 "true" vs True）——
    这是 `input-seed`（JSON 对象）与 `input-answer`（--value 字符串）共用的
    类型容错，避免调用方因类型写法差异被误判为非法选项。
    """
    candidates = [o.get("value") for o in (options or []) if not o.get("disabled")]
    if not candidates:
        return value
    target = type(candidates[0])
    if target is bool:
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "1", "yes", "y", "on"):
                return True
            if low in ("false", "0", "no", "n", "off"):
                return False
        elif isinstance(value, (int, float)):
            return bool(value)
    elif target is int:
        if isinstance(value, str):
            try:
                return int(value.strip())
            except (ValueError, TypeError):
                pass
        elif isinstance(value, float) and value == int(value):
            return int(value)
    elif target is float:
        if isinstance(value, str):
            try:
                return float(value.strip())
            except (ValueError, TypeError):
                pass
        elif isinstance(value, int):
            return float(value)
    return value


def validate_value(q: dict, value):
    """封闭选项题（single/multi）白名单校验 + 类型容错，返回规范化后的值。

    唯一事实来源：`input-answer` 与 `input-seed` 共用本函数，杜绝两处口径漂移。
    开放式题目（text/mixed，或未声明 options）原样返回。
    非法选项 raise UsageError（早失败，不静默兜底）。
    """
    if q.get("input_type") not in ("single", "multi"):
        return value
    allowed = [o.get("value") for o in (q.get("options") or []) if not o.get("disabled")]
    if not allowed:
        return value
    raw_values = value if isinstance(value, list) else [value]
    normalized = []
    for v in raw_values:
        if v in allowed:
            normalized.append(v)
            continue
        coerced = coerce_value(v, q.get("options"))
        if coerced in allowed:
            normalized.append(coerced)
            continue
        raise UsageError(
            f"{q['id']} 取值不在选项内: {v!r}；可选值 {allowed}")
    return normalized if isinstance(value, list) else normalized[0]


def question_view(q: dict) -> dict:
    """题目对外视图 = 基础字段 + render + hint（AI 唯一消费入口）。"""
    view = public_view(q)
    view["render"] = build_render(q)
    view["hint"] = build_hint(q)
    return view

_DEFAULTS = {
    "group": "config",
    "order": 0,
    "prompt": "",
    "input_type": "text",
    "required": False,
    "options": [],
    "default": None,
    "depends_on": [],
    "source": "ask",
    "resolve": None,
    "sensitive": False,
    "value": None,
    # 仅 source=derived 有意义：是否允许用户经 input-seed 覆盖（覆盖后引擎不再重算）。
    # 默认 False —— 派生值 = 当前输入的纯函数，不接受外部注入。
    "overridable": False,
}

# depends_on 支持三种写法：
#   "<id>"                           —— 纯依赖：必须先解决该问题（无门控）
#   "<id> (==|!=) '<literal>'"        —— 依赖 + 单值门控：条件不满足则本问题不适用
#   "<id> in ('a','b')"               —— 依赖 + 集合门控：id 取值不在集合内则本问题不适用
#     （集合门控用于「一个可选能力适用于多个环境」的场景，由能力矩阵派生，
#      见 `validators/env_validator.capability_depends_on`）
# 多条 depends_on 之间为 **AND**（任一不满足即不适用）。
_BARE_ID_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")
_PREDICATE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*(['\"])(.*?)\3\s*$"
)
_IN_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+in\s*\(\s*(.*?)\s*\)\s*$"
)


def _parse_in_items(raw: str) -> tuple:
    """解析 `in ('a','b')` 的集合字面量 → 字符串元组（去引号 / 忽略空项）。"""
    items = tuple(
        s.strip().strip("'\"") for s in str(raw).split(",") if s.strip()
    )
    if not items:
        raise ContractError("depends_on 不合法：`in ()` 集合不能为空")
    return items


def parse_dep(expr: str):
    """解析一条 depends_on → (question_id, op|None, literal|None)；不合法则 ContractError。

    op ∈ {None, '==', '!=', 'in'}；`in` 的 literal 为字符串元组，其余为字符串/None。
    """
    text = str(expr)
    m = _PREDICATE_RE.match(text)
    if m:
        return m.group(1), m.group(2), m.group(4)
    m = _IN_RE.match(text)
    if m:
        return m.group(1), "in", _parse_in_items(m.group(2))
    m = _BARE_ID_RE.match(text)
    if m:
        return m.group(1), None, None
    raise ContractError(
        f"depends_on 不合法：{expr!r}"
        "（支持 `<id>`，`<id> == '<literal>'` / `<id> != '<literal>'`，"
        "或 `<id> in ('a', 'b')`）"
    )


def referenced_ids(question: dict) -> set:
    """question.depends_on 引用的 question id 集合（供拓扑排序 + 悬空检查）。"""
    return {parse_dep(e)[0] for e in (question.get("depends_on") or [])}


def normalize_question(raw: dict) -> dict:
    """填充默认值（不校验；校验见 validate_questions）。"""
    if not isinstance(raw, dict):
        raise ContractError(f"question 必须是 dict，得到 {type(raw).__name__}")
    q = dict(_DEFAULTS)
    q.update(raw)
    q["options"] = list(q.get("options") or [])
    q["depends_on"] = list(q.get("depends_on") or [])
    return q


def public_view(q: dict) -> dict:
    """对外视图：只保留可序列化字段（不下发 resolve 回调 / 已解析值）。"""
    return {k: q.get(k) for k in _PUBLIC_KEYS}


def _check_one(q: dict):
    qid = q.get("id")
    if not qid or not isinstance(qid, str):
        raise ContractError(f"question 缺少合法 id：{q!r}")
    if q["group"] not in GROUPS:
        raise ContractError(f"question {qid}: group={q['group']!r} 不在 {GROUPS}")
    if q["input_type"] not in INPUT_TYPES:
        raise ContractError(
            f"question {qid}: input_type={q['input_type']!r} 不在 {INPUT_TYPES}")
    if q["source"] not in SOURCES:
        raise ContractError(f"question {qid}: source={q['source']!r} 不在 {SOURCES}")
    if q["source"] == "derived" and not callable(q.get("resolve")):
        raise ContractError(f"question {qid}: source=derived 必须提供可调用 resolve")
    if not isinstance(q["required"], bool):
        raise ContractError(f"question {qid}: required 必须是 bool")
    for expr in q["depends_on"]:
        parse_dep(expr)
    if q["input_type"] == "text" and q["options"]:
        raise ContractError(f"question {qid}: input_type=text 不应带 options")
    if q["input_type"] in ("single", "multi", "mixed"):
        for opt in q["options"]:
            if not isinstance(opt, dict) or "value" not in opt:
                raise ContractError(
                    f"question {qid}: options 项必须是 {{value,label}}: {opt!r}")


def validate_questions(questions: list, known_ids=None):
    """整体校验：逐条合法 + id 唯一 + depends_on 引用不悬空。

    Args:
        known_ids: 除声明问题外，**允许被 depends_on 引用**的额外 id
                   （典型：provider `derive()` 产出的派生键，如 `device_type`）。

    Raises:
        ContractError: 任一违反（早失败，不静默兜底）
    """
    normalized = []
    seen = set()
    for raw in questions:
        q = normalize_question(raw)
        _check_one(q)
        if q["id"] in seen:
            raise ContractError(f"question id 重复：{q['id']}")
        seen.add(q["id"])
        normalized.append(q)
    allowed = seen | set(known_ids or ())
    for q in normalized:
        missing = referenced_ids(q) - allowed
        if missing:
            raise ContractError(
                f"question {q['id']}: depends_on 引用不存在的问题 {sorted(missing)}")
    return normalized
