#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符 provider —— 从 task 的 steps-input 提取 `{xxx}` 并逐条提问。

来源：task 的 `steps-input*.json`（`steps-generate` 之后的产物）。
只有 `vars` 里声明为 `ask: true` 的变量才提问；`value` / `date` 已在
`flow-init` 落成确定值，不上问。

问答 id 即占位符名 → `flow-init` 的变量替换直接消费 intake 答案。
prompt 使用 `vars.<name>.desc` / `.example`，并附「出现位置」上下文。
"""
import json
import os

from aitest.provisioning.questions.registry import QuestionProvider, register_provider
from aitest.shared.paths import steps_input_dir
from aitest.shared.placeholders import collect_case_placeholder_text, extract_placeholders


def _placeholders() -> dict:
    """扫描 steps-input → {name: {sources, desc, example}}（仅 ask 变量）。"""
    found = {}

    tmp = steps_input_dir()
    if not os.path.isdir(tmp):
        return found

    for fname in sorted(os.listdir(tmp)):
        if not (fname.startswith("steps-input") and fname.endswith(".json")):
            continue
        if fname.endswith(".raw.json"):
            continue  # flow-init 留存的原文快照，含未替换占位符，不得再上问
        try:
            with open(os.path.join(tmp, fname), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        for i, case in enumerate(data.get("cases", []) or []):
            if not isinstance(case, dict):
                continue
            case_id = case.get("case_id", f"case-{i + 1:02d}")
            case_vars = case.get("vars") or {}
            for name in extract_placeholders(collect_case_placeholder_text(case)):
                spec = case_vars.get(name) or {}
                if spec.get("ask") is not True:
                    continue
                entry = found.setdefault(name, {"sources": [], "desc": "", "example": ""})
                source = f"{fname}:{case_id}"
                if source not in entry["sources"]:
                    entry["sources"].append(source)
                entry["desc"] = entry["desc"] or str(spec.get("desc") or "").strip()
                entry["example"] = entry["example"] or str(spec.get("example") or "").strip()

    return found


@register_provider
class PlaceholderQuestionProvider(QuestionProvider):
    name = "placeholder"

    def questions(self, ctx) -> list:
        questions = []
        for i, (name, meta) in enumerate(sorted(_placeholders().items())):
            desc = meta["desc"]
            if desc:
                prompt = f"请提供「{desc}」的值（占位符 {{{name}}}）"
            else:
                prompt = f"请提供占位符 {{{name}}} 的值"
            sources = meta["sources"]
            if sources:
                prompt += f"，出现在：{', '.join(sources[:5])}"
            if meta["example"]:
                prompt += f"，示例：{meta['example']}"
            questions.append({
                "id": name, "group": "placeholder", "order": 60 + i,
                "prompt": prompt, "input_type": "text", "required": True,
            })
        return questions
