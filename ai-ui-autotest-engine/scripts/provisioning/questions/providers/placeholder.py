#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符 provider —— 从本 workspace 的用例提取 `{xxx}` 并逐条提问。

来源（长期口径，二者同文法、取并集）：
  1. `flows_dir()/*.md`（AI 写完 Flow 即可提问）；
  2. task 的 `steps-input*.json`（`steps-generate` 之后的兜底/超集）。
日期占位符 `{T+N}` 由引擎自动解析，不上问。

问答 id 即占位符名 → `flow-init` 的占位符替换直接消费 intake 答案。
prompt 附带「出现位置」上下文（Flow 文件 / Case），便于判断应填什么值。
"""
import json
import os

from provisioning.questions.registry import QuestionProvider, register_provider
from shared.paths import flows_dir, steps_input_dir
from shared.placeholders import extract_placeholders, is_date_placeholder


def _placeholders() -> dict:
    """扫描本 workspace 的 Flow .md 与 steps-input → {占位符名: [来源, ...]}。"""
    found = {}

    def _add(names, source):
        for name in names:
            if is_date_placeholder(name):
                continue
            sources = found.setdefault(name, [])
            if source not in sources:
                sources.append(source)

    directory = flows_dir()
    if os.path.isdir(directory):
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".md"):
                continue
            try:
                with open(os.path.join(directory, fname), encoding="utf-8") as fh:
                    _add(extract_placeholders(fh.read()), fname)
            except OSError:
                continue

    tmp = steps_input_dir()
    if os.path.isdir(tmp):
        for fname in sorted(os.listdir(tmp)):
            if not (fname.startswith("steps-input") and fname.endswith(".json")):
                continue
            try:
                with open(os.path.join(tmp, fname), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for case_id, names in (_extract_placeholders_from_steps(data) or {}).items():
                _add(names, f"{fname}:{case_id}")

    return found


def _extract_placeholders_from_steps(steps_input: dict) -> dict:
    """从 steps-input 提取占位符 → {case_id: [names]}（占位符文法统一于 shared）。"""
    result = {}
    for i, case in enumerate(steps_input.get("cases", []) or []):
        case_id = case.get("case_id", f"case-{i + 1:02d}")
        found = extract_placeholders(json.dumps(case, ensure_ascii=False))
        if found:
            result[case_id] = found
    return result


@register_provider
class PlaceholderQuestionProvider(QuestionProvider):
    name = "placeholder"

    def questions(self, ctx) -> list:
        questions = []
        for i, (name, sources) in enumerate(sorted(_placeholders().items())):
            prompt = f"请提供占位符 {{{name}}} 的值"
            if sources:
                prompt += f"（出现在：{', '.join(sources[:5])}）"
            questions.append({
                "id": name, "group": "placeholder", "order": 60 + i,
                "prompt": prompt, "input_type": "text", "required": True,
            })
        return questions
