#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置校验器 — 独立的可选配置项收集（ptest、bundle_lock 等）。

与 env_validator / auth_validator 正交：可选配置不依赖环境类型或认证方式，
ptest 是"线上环境 + partMock 注入"的独立测试开关，可与任意环境/认证方式组合；
bundle_lock 是 MRN 锁包配置，同样独立于环境与认证。

本模块不包含任何必填项，所有字段均为 required=False。
"""

import json
import re
import os
from environment.helpers.question_utils import apply_known_value
from core.util.case_utils import read_env_answers, save_env_answers
from core.errors import ConfigError


class ConfigValidationError(ConfigError):
    """可选配置（ptest/锁包）校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "OPTIONAL_CONFIG_INVALID"


def _extract_flow_bundle_names(flow_path):
    """从 Flow「可测性环境」表提取目标锁包包名列表（仅包名）。
    与 env_validator 中的 extract_flow_bundle_names 逻辑一致。
    """
    _FLOW_BUNDLE_ROW_RE = re.compile(r'\|\s*(?:目标锁包|MRN锁包|锁包)\s*\|\s*(.+?)\s*\|')
    try:
        with open(flow_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []
    names = []
    for m in _FLOW_BUNDLE_ROW_RE.findall(content):
        raw = m.strip().replace("`", "")
        raw = re.sub(r'（.*?）|\(.*?\)', '', raw).strip()
        for part in raw.split(","):
            part = part.strip()
            if ":" in part:
                part = part.split(":")[0].strip()
            if part and part not in names:
                names.append(part)
    return names


def _build_config_questions(known_values=None, bundle_names=None):
    """构造可选配置项清单。

    所有项均为 required=False，用户不提供时按 default 静默生效。
    """
    questions = []

    # ── ptest：独立测试开关 ──
    questions.append({
        "id": "ptest",
        "group": "optional",
        "order": 45,
        "prompt": "是否需要开启 ptest（注入 isPtest/isGreyTest/isDevBundle 参数）？",
        "input_type": "mixed",
        "required": False,
        "source": "ask",
        "default": False,
        "options": [
            {"value": True, "label": "开启 ptest（线上环境 + partMock 注入）"},
            {"value": False, "label": "不开（纯线上）"},
        ],
        "resolved": False,
    })

    # ── bundle_lock：MRN 锁包配置 ──
    bundle_lock_prompt = "是否需要锁定特定 MRN bundle？（仅声明包名不锁包；提供版本才会锁包；无需请跳过）"
    if bundle_names:
        bundle_lock_prompt = (
            "是否需要锁定 MRN bundle？Flow 声明的目标包: " + ", ".join(bundle_names)
            + "（仅声明包名不锁包；提供版本才会锁包；无需请跳过）"
        )
    questions.append({
        "id": "bundle_lock",
        "group": "optional",
        "order": 50,
        "prompt": bundle_lock_prompt,
        "input_type": "mixed",
        "required": False,
        "source": "ask",
        "default": [],
        "resolved": False,
        "options": [
            {"value": "__manual_input__", "label": "✏️ 手动输入锁包配置"},
            {"value": "__skip__", "label": "⏭️ 跳过（无需锁包）"},
        ],
        "note": f"Flow 声明的目标锁包: {', '.join(bundle_names)}" if bundle_names else None,
        "validate_hint": "数组，每项 {name: 包名, version: 版本号}；version 为空=仅声明目标不锁包，提供 version 才会锁包；无需锁包留空即可",
    })

    questions.sort(key=lambda q: q["order"])
    return [apply_known_value(q, known_values) for q in questions]


def get_config_required_fields(flow_source=None, known_values=None, no_more_questions=False):
    """返回可选配置项清单。

    flow_source: Flow markdown 文件路径（可选，用于提取锁包信息）。
    known_values: 调用方从用户原始提示词中解析出的字段值。
    no_more_questions: 用户声明信息已备齐时传 True。
    """
    # 从 flow_source 提取锁包信息
    bundle_names = None
    if flow_source:
        try:
            bundle_names = _extract_flow_bundle_names(flow_source)
        except Exception:
            bundle_names = None

    questions = _build_config_questions(known_values, bundle_names=bundle_names)

    ask_now = [
        q["id"] for q in questions
        if not q.get("resolved") and q["source"] in ("ask", "flow_extract")
    ]

    if no_more_questions:
        ask_now = []

    # 将 ask_now 拆分为选择题和文本输入题，AI 按类型分别处理
    if not no_more_questions:
        ask_choice_now = [
            q["id"] for q in questions
            if q.get("input_type") == "mixed" and q["id"] in ask_now
        ]
        ask_text_now = [
            q["id"] for q in questions
            if q.get("input_type") == "text" and q["id"] in ask_now
        ]
    else:
        ask_choice_now = []
        ask_text_now = []

    notes_parts = ["可选配置项"]
    if no_more_questions:
        notes_parts.append("用户已声明信息备齐，跳过咨询，直接使用各字段 default 值执行")
    elif ask_now:
        notes_parts.append(f"本次需一次性收集: {', '.join(ask_now)}")
        parts = []
        if ask_choice_now:
            parts.append(f"有选项的题目（{', '.join(ask_choice_now)}）→ 用 AskQuestion 收集")
        if ask_text_now:
            parts.append(f"文本输入的题目（{', '.join(ask_text_now)}）→ AI 直接在聊天中展示给用户一次性输入，然后调用 save-answers --answers 保存")
        if parts:
            notes_parts.append("；".join(parts))
        notes_parts.append("required=false 的题目可留空/跳过，不阻塞流程")
    else:
        notes_parts.append("无待收集项（可选配置均已就绪）")

    return {
        "questions": questions,
        "ask_now": ask_now,
        "ask_choice_now": ask_choice_now,
        "ask_text_now": ask_text_now,
        "no_more_questions": no_more_questions,
        "notes": "。".join(notes_parts),
    }


def validate_config(config_dict):
    """校验可选配置块，通过时返回标准化后的 config 配置。

    config_dict 应包含: ptest（可选）、bundle_lock（可选）
    校验失败时抛出 ConfigValidationError。
    """
    if not isinstance(config_dict, dict):
        raise ConfigValidationError("config 配置必须是字典")

    normalized = dict(config_dict)

    # ptest 校验
    ptest = normalized.get("ptest", False)
    if not isinstance(ptest, bool):
        raise ConfigValidationError("ptest 必须是布尔值 true/false")
    normalized["ptest"] = ptest

    # bundle_lock 校验
    bundle_lock = normalized.get("bundle_lock", [])
    if not isinstance(bundle_lock, list):
        raise ConfigValidationError("bundle_lock 必须是数组（每项 {name, version} 对象）；无锁包请传 []")
    normalized_bundle_lock = []
    for item in bundle_lock:
        if not isinstance(item, dict):
            raise ConfigValidationError(
                f"bundle_lock 每项必须是对象 {{name, version}}: {item!r}"
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigValidationError(
                f"bundle_lock 每项必须提供非空 name（包名）: {item!r}"
            )
        version = item.get("version")
        if version not in (None, ""):
            if not isinstance(version, str) or not version.strip():
                raise ConfigValidationError(
                    f"bundle_lock 每项 version 必须是非空字符串或省略（省略=仅声明目标不锁包）: {item!r}"
                )
        entry = {"name": name.strip()}
        if version:
            entry["version"] = version.strip()
        normalized_bundle_lock.append(entry)
    normalized["bundle_lock"] = normalized_bundle_lock

    return normalized


def cmd_config_required(args):
    """可选配置收集：ptest、锁包等（所有字段 required=False）。"""
    if args.answers:
        try:
            answers = json.loads(args.answers)
        except ValueError:
            raise ConfigError(f"--answers 不是合法 JSON: {args.answers}")
        if not isinstance(answers, dict):
            raise ConfigError(f"--answers 必须是 JSON 对象: {args.answers}")
        save_env_answers(answers)

    known_values = read_env_answers()
    result = get_config_required_fields(
        flow_source=args.flow_source,
        known_values=known_values,
        no_more_questions=args.no_more_questions,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    save_env_answers(known_values)

    # ── AI 引导提示 ──
    if result.get("ask_now"):
        ai_guide = """
========== 🤖 AI 引导 ==========
📌 触发策略判断：
   - 用户完全没提配置信息 → 直接通过 AskQuestion 展示上面的可选配置项
   - 用户已提供部分/全部配置 → 用 --answers 预填已知值，只问剩余项
   - 用户明确说信息已给全 → 加 --no-more-questions 强制跳过
⚠️ 模糊参数确认：用户可能给了裸值（如"需要ptest，不锁包"），
   不要强行猜映射值，主动向用户确认
📋 操作步骤：
1. 将上面输出的可选配置项（ptest/锁包等）通过 AskQuestion 展示给用户
2. 所有字段均为可选（required=false），用户可选择「⏭️ 跳过」
3. 有 default 值的用 `mixed` 展示默认值；已保存的值作为可选选项展示
4. 用户确认后，调用 `save-answers --answers '{"ptest":true/false,"bundle_lock":[...]}'` 保存
5. 然后继续执行 `flow-convert --tag {tag}` 进入流程转换阶段
================================"""
        print(ai_guide)