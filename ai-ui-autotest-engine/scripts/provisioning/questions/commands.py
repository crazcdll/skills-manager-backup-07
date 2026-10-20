#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息收集命令 —— `input-schema` / `input-seed` / `input-next` / `input-answer` / `input-status`。

统一驱动协议：AI 先发现（`input-schema`）→ 预置用户已给值（`input-seed`）→
再用一个固定循环逐题收集剩余项：
    input-next → AskQuestion → input-answer → … → done
"""
import json

from provisioning.questions.driver import answer, next_question, schema_view, seed, status
from shared.errors import UsageError
from shared.intake import IntakeContext
from shared.workspace import render_text

# 需要按 JSON 解析的 `--value` 前缀（其余原样作为字符串，避免手机号被转成数字）
_JSON_PREFIXES = ("true", "false", "null", "[", "{")


def _parse_value(raw: str):
    """把 `--value` 解析为合适类型：true/false/null/数组/对象按 JSON，其余保持字符串。"""
    text = (raw or "").strip()
    if text.startswith(_JSON_PREFIXES):
        try:
            return json.loads(text)
        except ValueError:
            return raw
    return raw


def _load_json_object(raw: str, cmd: str) -> dict:
    """解析 `--answers` 为 JSON 对象；非法直接 UsageError（早失败）。"""
    try:
        data = json.loads(raw)
    except ValueError:
        raise UsageError(f"{cmd}: --answers 不是合法 JSON: {raw}")
    if not isinstance(data, dict):
        raise UsageError(f"{cmd}: --answers 必须是 JSON 对象")
    return data


def cmd_input_next(args):
    result = next_question(IntakeContext())
    # 输出里的 next.cmd 是 AI 直接执行的命令 → 统一渲染为 workspace 入口
    print(render_text(json.dumps(result, ensure_ascii=False, indent=2)))


def cmd_input_answer(args):
    result = answer(IntakeContext(),
                    args.id, _parse_value(args.value))
    print(render_text(json.dumps(result, ensure_ascii=False, indent=2)))


def cmd_input_status(args):
    result = status(IntakeContext())
    print(render_text(json.dumps(result, ensure_ascii=False, indent=2)))


def cmd_input_schema(args):
    result = schema_view(IntakeContext())
    print(render_text(json.dumps(result, ensure_ascii=False, indent=2)))


def cmd_input_seed(args):
    result = seed(IntakeContext(), _load_json_object(args.answers, "input-seed"))
    print(render_text(json.dumps(result, ensure_ascii=False, indent=2)))
