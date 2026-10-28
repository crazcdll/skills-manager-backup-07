#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符文法 + 统一替换（全仓库唯一事实来源）。

文法：
  · 通用占位符 `{xxx}` —— `\\w+`（含中文/数字/下划线），兼容 `{{xxx}}` 旧写法；
  · 日期占位符 `{T+N}` / `{T+N:format}` —— 由引擎自动解析，**不提问**。

职责收敛（禁止再各自实现）：
  · 提取：`extract_placeholders` / `collect_case_placeholder_text`
  · 替换：`substitute`（唯一替换实现；`{T+N}` 解析 + `{xxx}` 取值）
  · 判断：`is_date_placeholder`

execution 层的 `placeholder_resolver` 与 provisioning 层的 Question Provider
共用本模块，避免多份正则/多份替换实现互相漂移。
"""
import json
import os
import re
from datetime import datetime, timedelta

# 统一正则：占位符格式 {xxx}（兼容 {{xxx}}，\w+ 不包含 + 故 {T+N} 不会被匹配）
PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

# 日期占位符：{T+N} / {T-N} / {T+N:format}（兼容 {{T+N}} 旧写法）
# `T-1` 用于回溯日期（如昨日），与 `T+1` 共用同一套解析。
DATE_PLACEHOLDER_RE = re.compile(r'\{?\{T([+-]\d+)(?::([^}]+))?\}\}?')

# {T+N}(:format) —— 判断单个名称是否为日期占位符
_DATE_NAME_RE = re.compile(r'^T[+-]\d+(?::.+)?$')

# {T+N} 不带 format 时的默认日期格式
DEFAULT_DATE_FORMAT = '%Y-%m-%d'

# 单次替换的最大轮次：答案可能包含日期/其他命名占位符，逐轮展开直到稳定。
# 上限同时防御自引用（如 a -> {a}）导致的死循环。
MAX_SUBSTITUTION_PASSES = 5

# 断言中承载文案的字段（与 AssertionSpec schema 一致）
ASSERT_TEXT_FIELDS = ("expect", "criteria", "on_fail")


def extract_placeholders(text: str) -> list:
    """从文本中提取 {xxx} 占位符，返回去重后的名称列表（已排序）。"""
    if not text:
        return []
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def is_date_placeholder(name: str) -> bool:
    """是否为 {T+N} / {T+N:format} 日期占位符（引擎自动解析，无需提问）。"""
    return bool(_DATE_NAME_RE.match(str(name)))


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


def find_unresolved_placeholders(text: str) -> list:
    """返回文本中仍未解析的占位符（日期 + 命名），用于执行前硬门禁。"""
    if not text:
        return []
    found = [m.group(0) for m in DATE_PLACEHOLDER_RE.finditer(text)]
    found.extend(f"{{{name}}}" for name in PLACEHOLDER_RE.findall(text))
    return sorted(set(found))


def _substitute_text(text: str, answers: dict, with_dates: bool,
                     now: datetime = None) -> str:
    """替换占位符；**支持答案里再含占位符**（最多 5 轮直到稳定）。

    关键场景：Flow 的 `{checkinDate}` 被回答成 `{T+10:%Y-%m-%d}`。
    单轮实现会先做日期替换（此时文本里还只有 `{checkinDate}`）再把答案插进去，
    结果把 `{T+10...}` 原样留给 App（历史批量任务实际踩到）。
    因此必须循环：日期解析 → 命名替换 → 再检查新插入的日期/命名占位符。
    """
    if not text:
        return text
    now = now or _date_base()
    for _ in range(MAX_SUBSTITUTION_PASSES):
        before = text
        if with_dates and '{T' in text:
            text = DATE_PLACEHOLDER_RE.sub(
                lambda m: (now + timedelta(days=int(m.group(1)))).strftime(
                    m.group(2) or DEFAULT_DATE_FORMAT
                ),
                text,
            )
        if '{' in text:
            text = PLACEHOLDER_RE.sub(
                lambda m: str(answers.get(m.group(1), m.group(0))),
                text,
            )
        if text == before:
            break
    return text


def substitute(obj, answers: dict, with_dates: bool = True, _now: datetime = None):
    """递归替换 dict/list/str 中的占位符（唯一替换实现）。

    · `with_dates=True`（默认）：先解析 `{T±N(:format)}` → 日期，再替换 `{xxx}` → answers 值；
    · `with_dates=False`：只替换 `{xxx}`（用于尚未到执行期的场景）。
    · `_now`：同一批/同一次解析共用日期基线；外部一般不需要传。
    未在 answers 中的占位符原样保留。
    """
    answers = answers or {}
    if _now is None:
        _now = _date_base()
    if isinstance(obj, dict):
        return {k: substitute(v, answers, with_dates, _now) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(item, answers, with_dates, _now) for item in obj]
    if isinstance(obj, str):
        return _substitute_text(obj, answers, with_dates, _now)
    return obj
