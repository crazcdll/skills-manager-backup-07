#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate / _format_json_error CLI 命令。

职责：解析 CLI 参数 → 校验 steps-input.json → 格式化输出。
"""
import json

from core.errors import PayloadError, UsageError
from core.flow.flow_init import validate_steps_json


def _format_json_error(e, raw_text=""):
    """将 json.JSONDecodeError 格式化为带上下文片段的友好错误消息。"""
    msg = f"JSON 语法错误: {e.msg} (行 {e.lineno} 列 {e.colno})"
    if not raw_text:
        return msg
    lines = raw_text.splitlines()
    if e.lineno < 1 or e.lineno > len(lines):
        return msg
    err_line = lines[e.lineno - 1]
    start = max(0, e.colno - 1 - 60)
    end = min(len(err_line), e.colno - 1 + 60)
    snippet = err_line[start:end]
    pointer = " " * (e.colno - 1 - start) + "^"
    msg += f"\n  出错位置: ...{snippet}..."
    msg += f"\n            {' ' * max(0, 4 - len('...'))} {pointer}"
    return msg


def _cmd_validate(args):
    """validate --input <steps-input.json>"""
    if not getattr(args, "json", None):
        raise UsageError("VALIDATE FAIL: 需要 --input 参数")

    raw = args.json
    try:
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise PayloadError(f"VALIDATE FAIL: 读取文件失败: {e}") from e

    try:
        ai_input = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PayloadError(f"VALIDATE FAIL: {_format_json_error(e, raw)}") from e

    try:
        merged_env, batch_name, cases = validate_steps_json(ai_input)
    except ValueError as e:
        raise PayloadError(f"VALIDATE FAIL: {e}") from e

    print(f"VALIDATE OK: {len(cases)} cases, batch={batch_name or '(unnamed)'}")
    print(f"  env type: {merged_env.get('type', '?')}")
    for i, case in enumerate(cases):
        case_id = case.get("case_id", f"case-{i+1:02d}")
        case_name = case.get("case_name", f"Case {i+1}")
        steps = case.get("steps", [])
        ls = case.get("landing_scheme", "")
        ls_short = ls[:80] + ("..." if len(ls) > 80 else "")
        ui_n = sum(1 for s in steps if s.get("kind", "ui") == "ui")
        api_n = sum(1 for s in steps if s.get("kind") == "api")
        track_n = sum(1 for s in steps if s.get("kind") == "track")
        print(f"  Case {i}: {case_id} ({case_name}) — {len(steps)} steps ({ui_n} ui, {api_n} api, {track_n} track)")
        print(f"    landing: {ls_short}")