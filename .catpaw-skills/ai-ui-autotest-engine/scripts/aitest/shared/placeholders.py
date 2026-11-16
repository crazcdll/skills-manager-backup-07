#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""占位符文法 + 统一替换（全仓库唯一事实来源）。

文法（只有一种）：
  · 占位符 `{xxx}` —— `\w+`（含中文/数字/下划线），值由 `vars` 声明决定；
  · `{{...}}` 双花括号段为**平台所有**（Pillow 注入如 `{{ip}}`、
    `{{config.get('extra.mock.port')}}`），提取与替换都原样保留。

变量来源统一在 `vars` 声明，引擎不再内置第二种语法：
  · `{"value": ...}` 转化期固定值
  · `{"ask": true, "desc": ...}` 执行前由提问流程收集
  · `{"date": 4, "format": "%Y-%m-%d"}` 相对批次日期基线的偏移

职责收敛（禁止再各自实现）：
  · 提取：`extract_placeholders` / `collect_case_placeholder_text`
  · 替换：`substitute`（唯一替换实现）
  · 日期：`date_base` / `resolve_date_offset`（`vars.date` 与替换共用同一基线）

execution 层的 `placeholder_resolver` 与 provisioning 层的 Question Provider
共用本模块，避免多份正则/多份替换实现互相漂移。
"""
import json
import os
import re
from datetime import datetime, timedelta

# 统一正则：占位符格式 {xxx}
PLACEHOLDER_RE = re.compile(r'\{(\w+)\}', re.UNICODE)

# 平台所有段：{{ip}} / {{config.get(...)}} 等，替换与提取时必须整段跳过。
PLATFORM_BRACE_RE = re.compile(r'\{\{[^{}]*\}\}')

# `vars.date` 未指定 format 时的默认日期格式
DEFAULT_DATE_FORMAT = '%Y-%m-%d'

# 单次替换的最大轮次：答案可能包含其他占位符，逐轮展开直到稳定。
# 上限同时防御自引用（如 a -> {a}）导致的死循环。
MAX_SUBSTITUTION_PASSES = 5

# 断言中承载文案的字段（与 AssertionSpec schema 一致）
ASSERT_TEXT_FIELDS = ("expect", "criteria", "on_fail")

# `vars` 声明允许的子字段（value / date / ask 三选一）
VAR_SPEC_KEYS = ("value", "ask", "date", "format", "desc", "example")

_VAR_NAME_RE = re.compile(r'^\w+$', re.UNICODE)


def validate_var_spec(name, spec, where: str = None) -> list:
    """校验单条 `vars` 声明（value / date / ask 三选一）。

    `steps-generate`、`flow-json`、`flow-init` 共用本实现，避免三处校验漂移。
    返回错误列表（为空即合法）。
    """
    where = where or f"vars.{name}"
    errors = []
    var_name = str(name).strip()
    if not var_name or not _VAR_NAME_RE.match(var_name):
        return [f"{where}: 变量名非法（须与占位符文法一致：\\w+）"]
    if not isinstance(spec, dict):
        return [f"{where} 必须是对象（value / ask / date）"]

    unknown = [key for key in spec if key not in VAR_SPEC_KEYS]
    if unknown:
        errors.append(f"{where} 不支持字段 {unknown}（仅支持 {list(VAR_SPEC_KEYS)}）")
    if "ask" in spec and not isinstance(spec["ask"], bool):
        errors.append(f"{where}.ask 必须是布尔值")

    has_value = "value" in spec
    has_date = "date" in spec
    ask = spec.get("ask") is True
    if sum((has_value, has_date, ask)) != 1:
        errors.append(f"{where}: value / date / ask 必须三选一")

    if has_date:
        offset = spec["date"]
        if isinstance(offset, bool) or not isinstance(offset, int):
            errors.append(f"{where}.date 必须是整数天数（可为负）")
        fmt = spec.get("format")
        if fmt is not None and (
            not isinstance(fmt, str) or not fmt.strip() or "{" in fmt or "}" in fmt
        ):
            errors.append(f"{where}.format 必须是非空日期格式字符串，如 %Y-%m-%d")
    elif "format" in spec:
        errors.append(f"{where}.format 只能与 date 一起使用")

    if ask and not str(spec.get("desc") or "").strip():
        errors.append(f"{where}.ask=true 必须提供 desc（提问文案）")

    if has_value:
        value = spec["value"]
        if isinstance(value, str):
            if "{" in value or "}" in value:
                errors.append(f"{where}.value 不能含花括号：日期用 date，其他用 value/ask")
        elif not isinstance(value, (int, float, bool)):
            errors.append(f"{where}.value 必须是字符串/数字/布尔")
    return errors


def extract_placeholders(text: str) -> list:
    """从文本中提取 {xxx} 占位符，返回去重后的名称列表（已排序）。

    `{{...}}` 平台段整段跳过，不参与提取。
    """
    if not text:
        return []
    if '{{' in text:
        text = PLATFORM_BRACE_RE.sub('', text)
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def collect_case_placeholder_text(case: dict) -> str:
    """收集 case 中所有可能含 {xxx} 占位符的字段，拼接为完整文本。

    覆盖字段：landing_scheme、steps[].action_arg / action_anchor / wait_text、
    steps[].asserts（expect / criteria / on_fail / targets）、
    steps[].track_assert / api_assert（JSON 序列化后扫描）。
    提取逻辑只此一份，steps_generator 与 placeholder_resolver 共用。
    """
    if not isinstance(case, dict):
        return ""
    texts = [case.get("landing_scheme", "")]
    for s in case.get("steps", []) or []:
        if not isinstance(s, dict):
            continue
        texts.append(s.get("action_arg", ""))
        texts.append(s.get("action_anchor", ""))
        texts.append(s.get("wait_text", ""))
        for a in s.get("asserts", []) or []:
            if isinstance(a, dict):
                for field in ASSERT_TEXT_FIELDS:
                    texts.append(a.get(field, ""))
                for target in a.get("targets") or []:
                    if isinstance(target, str):
                        texts.append(target)
        for field in ("track_assert", "api_assert"):
            value = s.get(field)
            if value:
                texts.append(json.dumps(value, ensure_ascii=False))
    return "\n".join(t for t in texts if isinstance(t, str) and t)


def _date_base() -> datetime:
    """日期解析基线：同一批用例必须共用同一天，避免跨零点分片日期漂移。

    默认取本机当前时间；批量编排可设置 `AI_UITEST_DATE_BASE`（YYYY-MM-DD
    或 ISO 时间）把整批 shard 锚定到同一个"今天"。
    """
    raw = os.environ.get("AI_UITEST_DATE_BASE", "").strip()
    if raw:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return datetime.now()


def date_base() -> datetime:
    """本批次日期基线（同一次 run 的所有 `vars.date` 共用）。"""
    return _date_base()


def resolve_date_offset(offset: int, fmt: str = None, now: datetime = None) -> str:
    """把 `vars.date` 的 `offset`（相对今天的偏移天数，可为负）解析为字面日期。"""
    base = now or _date_base()
    return (base + timedelta(days=int(offset))).strftime(fmt or DEFAULT_DATE_FORMAT)


def find_unresolved_placeholders(text: str) -> list:
    """返回文本中仍未解析的占位符（`{xxx}`），用于执行前硬门禁。"""
    if not text:
        return []
    if '{{' in text:
        text = PLATFORM_BRACE_RE.sub('', text)
    return sorted({f"{{{name}}}" for name in PLACEHOLDER_RE.findall(text)})


def _mask_platform_braces(text: str):
    """把 `{{...}}` 段落换成不含花括号的哨兵，替换完再还原。"""
    if '{{' not in text:
        return text, []
    saved = []

    def _keep(match):
        saved.append(match.group(0))
        return f"\x00{len(saved) - 1}\x00"

    return PLATFORM_BRACE_RE.sub(_keep, text), saved


def _restore_platform_braces(text: str, saved: list) -> str:
    for i, raw in enumerate(saved):
        text = text.replace(f"\x00{i}\x00", raw)
    return text


def _substitute_text(text: str, answers: dict) -> str:
    """替换占位符；**支持答案里再含占位符**（最多 5 轮直到稳定）。"""
    if not text:
        return text
    text, platform = _mask_platform_braces(text)
    for _ in range(MAX_SUBSTITUTION_PASSES):
        before = text
        if '{' in text:
            text = PLACEHOLDER_RE.sub(
                lambda m: str(answers.get(m.group(1), m.group(0))),
                text,
            )
        if text == before:
            break
    return _restore_platform_braces(text, platform)


def substitute(obj, answers: dict):
    """递归替换 dict/list/str 中的 `{xxx}`（唯一替换实现）。

    未在 answers 中的占位符原样保留（由调用方的完整性门禁负责报错）。
    """
    answers = answers or {}
    if isinstance(obj, dict):
        return {k: substitute(v, answers) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(item, answers) for item in obj]
    if isinstance(obj, str):
        return _substitute_text(obj, answers)
    return obj
