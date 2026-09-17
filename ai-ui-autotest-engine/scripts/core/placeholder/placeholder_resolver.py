#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符解析、校验与替换模块 — 统一管理 steps-input.json 中的 {xxx} 占位符。

职责：
1. 从 steps-input.json 的全部字段（flow_content / landing_scheme / steps[].action_arg 等）
   提取所有 {xxx} 占位符，并锚定到每个占位符所在的 Case + Step 上下文
2. 与 env_answers.json 交叉校验，确认为用户已确认的值
3. 提供 CLI 入口（placeholder-required），供 AI 在阶段 0 收集和验证占位符
4. 提供 CLI 入口（placeholder-substitute），自动将 env_answers.json 中的值替换回
   steps-input.json，输出替换后的 JSON 文件

与 env-required 的边界：
  - env-required 负责环境配置（MIS/账号/密码/泳道/锁包）
  - placeholder-required/substitute 负责业务测试数据（{param_name} 等）

统一正则：r'{(\w+)}' 是所有校验和替换的唯一事实来源。
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

from core.errors import PayloadError, UsageError
from core.util.json_utils import write_json_atomic, read_json

# 统一正则：占位符格式 {xxx}（兼容 {{xxx}}，\w+ 不包含 + 故 {T+N} 不会被匹配）
_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

# 日期占位符：{T+N} 或 {T+N:format}
#   - {T+4}              → 4天后，默认格式 %Y-%m-%d
#   - {T+4:%Y%m%d}       → 4天后，yyyyMMdd 格式（民宿用）
#   - {T+10:%Y-%m-%d}    → 10天后，YYYY-MM-DD 格式（酒店用）
# format 是 Python strftime 格式串（不含右花括号），不传时默认 %Y-%m-%d
# 兼容 {{T+N}} 旧写法（花括号转义）
_DATE_PLACEHOLDER_RE = re.compile(r'\{?\{T\+(\d+)(?::([^}]+))?\}\}?')

# 断言中承载文案的字段（新断言 schema：expect / criteria / on_fail / targets）。
# 历史实现只扫 a["text"]，新 schema 下会漏掉断言里的占位符，使占位符门禁形同虚设。
_ASSERT_TEXT_FIELDS = ("expect", "criteria", "on_fail")


def _assert_texts(assert_item):
    """取出单条断言里所有可能含占位符的文本（expect / criteria / on_fail / targets）。"""
    if not isinstance(assert_item, dict):
        return []
    texts = [assert_item.get(field, "") for field in _ASSERT_TEXT_FIELDS]
    for target in assert_item.get("targets") or []:
        if isinstance(target, str):
            texts.append(target)
    return texts


def extract_placeholders(text: str) -> list:
    """从文本中提取 {xxx} 占位符，返回去重后的名称列表。"""
    if not text:
        return []
    found = _PLACEHOLDER_RE.findall(text)
    return sorted(set(found))


def _is_date_placeholder(name: str) -> bool:
    """判断占位符名称是否为 {T+N} 或 {T+N:format} 日期类型。"""
    return bool(re.match(r'^T\+\d+(?::.+)?$', name))


def extract_all_placeholders(text: str) -> dict:
    """从文本中提取所有占位符并分类，返回 {name: type_or_value}。

    type_or_value 取值：
      - None: {xxx} 通用占位符，需要 AI 审校时填充或用户提供
      - "__date__": {T+N} 或 {T+N:format} 日期占位符，由引擎自动解析
    """
    result = {}
    for ph in _PLACEHOLDER_RE.findall(text):
        result[ph] = None  # 需要 AI 审校填充或用户提供
    for day_offset, fmt in _DATE_PLACEHOLDER_RE.findall(text):
        name = f"T+{day_offset}:{fmt}" if fmt else f"T+{day_offset}"
        result[name] = "__date__"  # 自动解析
    return result


def resolve_placeholders(obj, env_answers: dict):
    """统一替换占位符：{T+N} / {T+N:format} → 自动计算日期，{xxx} → env_answers 值。
    
    这是 flow-init 中唯一的替换入口，替换旧的 _replace_date_placeholders 和 _substitute_in_dict 两步调用。
    """
    # 默认日期格式（{T+N} 不带 format 时使用）
    _DEFAULT_DATE_FORMAT = '%Y-%m-%d'

    def _resolve_text(text: str) -> str:
        if not text or ('{T+' not in text and '{' not in text):
            return text
        # 第一步：替换 {T+N} 或 {T+N:format} → 自动计算日期（基于当前时间）
        #   group(1)=天数偏移, group(2)=格式串（可为 None，None 时用默认格式）
        text = _DATE_PLACEHOLDER_RE.sub(
            lambda m: (datetime.now() + timedelta(days=int(m.group(1)))).strftime(
                m.group(2) or _DEFAULT_DATE_FORMAT
            ),
            text,
        )
        # 第二步：替换 {xxx} → env_answers 中的值
        text = _PLACEHOLDER_RE.sub(
            lambda m: str(env_answers.get(m.group(1), m.group(0))),
            text,
        )
        return text

    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, env_answers) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_placeholders(item, env_answers) for item in obj]
    elif isinstance(obj, str):
        return _resolve_text(obj)
    return obj


def _collect_placeholder_text(case: dict) -> str:
    """收集 case 中所有可能含 {xxx} 占位符的字段，拼接为完整文本。

    覆盖字段：
      - landing_scheme（URL 跳链）
      - steps[].action_arg（动作参数，如 open-url 的 scheme）
      - steps[].asserts（断言数组，提取 text 字段）
      - steps[].action_anchor / wait_text
      - steps[].track_assert / api_assert（JSON 序列化后扫描）
    """
    texts = []
    texts.append(case.get("landing_scheme", ""))
    for s in case.get("steps", []):
        texts.append(s.get("action_arg", ""))
        texts.append(s.get("action_anchor", ""))
        texts.append(s.get("wait_text", ""))
        for field in ("asserts",):
            for a in s.get(field, []):
                texts.extend(_assert_texts(a))
        for field in ("track_assert", "api_assert"):
            val = s.get(field)
            if val:
                texts.append(json.dumps(val, ensure_ascii=False))
    return "\n".join(texts)


def extract_placeholders_from_steps(steps_input: dict) -> dict:
    """从 steps-input.json 中所有可能含占位符的字段提取 {xxx}。

    返回: {case_id: [placeholder_name, ...]}
    """
    result = {}
    cases = steps_input.get("cases", [])
    for i, case in enumerate(cases):
        case_id = case.get("case_id", f"case-{i+1:02d}")
        combined = _collect_placeholder_text(case)
        placeholders = extract_placeholders(combined)
        if placeholders:
            result[case_id] = placeholders
    return result


# ═══════════════════════════════════════════════════════════════════
# 上下文感知：将每个占位符锚定到其来源（Case + Step + 字段）
# ═══════════════════════════════════════════════════════════════════

def _extract_placeholders_with_context(steps_input: dict) -> dict:
    """提取占位符并追踪每个占位符的来源上下文。

    返回: {placeholder_name: {"sources": [{"case_id", "case_name", "scene_tag",
           "sid", "desc", "field"}, ...]}}
    """
    context = {}
    for case in steps_input.get("cases", []):
        case_id = case.get("case_id", "")
        case_name = case.get("case_name", "")
        scene_tag = case.get("scene_tag", "")

        def _add_source(ph, sid="", desc="", field=""):
            if ph not in context:
                context[ph] = {"sources": []}
            context[ph]["sources"].append({
                "case_id": case_id,
                "case_name": case_name,
                "scene_tag": scene_tag,
                "sid": sid,
                "desc": desc,
                "field": field,
            })

        # landing_scheme
        for ph in extract_placeholders(case.get("landing_scheme", "")):
            _add_source(ph, field="landing_scheme")
        # steps
        for s in case.get("steps", []):
            sid = s.get("sid", "")
            desc = s.get("desc", "")
            for ph in extract_placeholders(s.get("action_arg", "")):
                _add_source(ph, sid=sid, desc=desc, field="action_arg")
            for ph in extract_placeholders(s.get("action_anchor", "")):
                _add_source(ph, sid=sid, desc=desc, field="action_anchor")
            for ph in extract_placeholders(s.get("wait_text", "")):
                _add_source(ph, sid=sid, desc=desc, field="wait_text")
            for field in ("asserts",):
                for a in s.get(field, []):
                    for text in _assert_texts(a):
                        for ph in extract_placeholders(text):
                            _add_source(ph, sid=sid, desc=desc, field=field)
            for field in ("track_assert", "api_assert"):
                val = s.get(field)
                if val:
                    for ph in extract_placeholders(json.dumps(val, ensure_ascii=False)):
                        _add_source(ph, sid=sid, desc=desc, field=field)
    return context


def _build_context_prompt(placeholder_name: str, sources: list) -> str:
    """根据占位符的来源上下文生成语义化的 prompt。"""
    # 收集所有步骤描述（去重）
    step_descs = []
    for src in sources:
        if src.get("desc"):
            desc = src["desc"]
            if desc not in [d[0] for d in step_descs]:
                sid = src.get("sid", "")
                step_descs.append((desc, sid))

    # 生成带上下文的 prompt
    if step_descs:
        # 取第一个步骤描述作为核心上下文
        main_desc = step_descs[0][0]
        # 从步骤描述中提取关键业务信息（取前 20 个字）
        context_hint = main_desc[:20]
        # 如果描述中包含了占位符名的含义，直接使用
        return f"{context_hint} 的 {placeholder_name}"
    else:
        # 如果没有步骤描述，用 case 名称
        case_names = sorted(set(s.get("case_name", "") for s in sources if s.get("case_name")))
        if case_names:
            return f"{'、'.join(case_names)} 的 {placeholder_name}"
        return f"Flow 数据依赖 {placeholder_name}"


# ═══════════════════════════════════════════════════════════════════
# 校验
# ═══════════════════════════════════════════════════════════════════

def check_resolved(steps_input_path: str) -> list:
    """检查 steps-input.json 中的占位符是否已在 env_answers.json 中解析。

    返回: 未解析的占位符列表 [(case_id, placeholder), ...]
    """
    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()

    if not os.path.isfile(steps_input_path):
        return []

    steps_input = read_json(steps_input_path, default={})

    unresolved = []
    case_placeholders = extract_placeholders_from_steps(steps_input)
    for case_id, placeholders in case_placeholders.items():
        for ph in placeholders:
            if _is_date_placeholder(ph):
                continue  # 日期占位符自动解析，不校验
            data_key = ph
            if data_key not in env_answers:
                unresolved.append((case_id, ph))

    return unresolved


# ═══════════════════════════════════════════════════════════════════
# 问题构建（带语义上下文）
# ═══════════════════════════════════════════════════════════════════

def build_questions(steps_input_path: str) -> list:
    """为 steps-input.json 中所有占位符构建问题列表。

    每个问题的 prompt 会包含占位符所在的步骤上下文（desc），
    让用户知道这个参数是用于哪个场景。
    """
    if not os.path.isfile(steps_input_path):
        return []

    steps_input = read_json(steps_input_path, default={})

    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()

    # 获取带上下文的占位符信息
    context_map = _extract_placeholders_with_context(steps_input)

    questions = []
    seen = set()
    # 按 case 顺序排列，保持可读性
    case_placeholders = extract_placeholders_from_steps(steps_input)
    for case_id, placeholders in case_placeholders.items():
        for ph in placeholders:
            if _is_date_placeholder(ph):
                continue  # 日期占位符自动解析，不提问
            if ph in seen:
                continue
            seen.add(ph)
            data_key = ph
            already_resolved = data_key in env_answers

            # 获取上下文并生成语义化 prompt
            sources = context_map.get(ph, {}).get("sources", [])
            prompt = _build_context_prompt(ph, sources)

            # 附加来源信息（用于调试/追溯）
            source_summary = []
            for src in sources:
                case_name = src.get("case_name", "")
                sid = src.get("sid", "")
                field = src.get("field", "")
                parts = []
                if case_name:
                    parts.append(case_name)
                if sid:
                    parts.append(sid)
                if field:
                    parts.append(f"[{field}]")
                source_summary.append(" · ".join(parts))
            note = "；".join(sorted(set(source_summary))) if source_summary else ""

            questions.append({
                "id": data_key,
                "group": "data",
                "order": 30 + len(seen),
                "prompt": prompt,
                "input_type": "text",
                "required": True,
                "source": "ask",
                "default": env_answers.get(data_key, ""),
                "resolved": already_resolved,
                "skip_reason": f"已从 env_answers.json 读取到 {env_answers.get(data_key, '')}" if already_resolved else None,
                "note": note,
            })

    return questions


# ═══════════════════════════════════════════════════════════════════
# 自动替换：将 env_answers.json 的值回填到 steps-input.json
# ═══════════════════════════════════════════════════════════════════

def _substitute_in_text(text: str, env_answers: dict) -> str:
    """将文本中的 {xxx} 替换为 env_answers 中的值。"""
    if not text:
        return text

    def _replace(m):
        ph = m.group(1)
        data_key = ph
        if data_key in env_answers:
            return str(env_answers[data_key])
        return m.group(0)  # 未找到时保留原占位符

    return _PLACEHOLDER_RE.sub(_replace, text)


def _substitute_in_dict(obj, env_answers: dict):
    """递归遍历 dict/list，将所有字符串中的 {xxx} 替换为实际值。"""
    if isinstance(obj, dict):
        return {k: _substitute_in_dict(v, env_answers) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_in_dict(item, env_answers) for item in obj]
    elif isinstance(obj, str):
        return _substitute_in_text(obj, env_answers)
    return obj


def substitute_steps_input(steps_input_path: str, output_path: str = None) -> dict:
    """读取 steps-input.json，将 {xxx} 替换为 env_answers.json 中的值。

    参数:
      steps_input_path: 输入的 steps-input.json 路径
      output_path: 输出路径（可选），不传时只返回 dict 不写文件

    返回: 替换后的 dict
    """
    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()

    steps_input = read_json(steps_input_path, default={})

    resolved = _substitute_in_dict(steps_input, env_answers)

    if output_path:
        write_json_atomic(output_path, resolved)

    return resolved


# ═══════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════

def _cmd_placeholder_required(args):
    """placeholder-required 命令入口。

    模式：
      - 默认模式：纯文本输出未解析的占位符清单，AI 直接展示给用户
      - --batch-answers：一次性接收所有答案并持久化，验证全部已解析后输出确认
      - --check：校验占位符是否全部解析，未解析则报错退出
    """
    steps_input = getattr(args, "steps_input", None)
    if not steps_input:
        raise UsageError("需要 --steps-input 参数")

    if not os.path.isfile(steps_input):
        raise PayloadError(f"steps-input 文件不存在: {steps_input}")

    batch_mode = getattr(args, "batch_answers", False)
    check_mode = getattr(args, "check", False)

    # 自动持久化 --answers
    answers_raw = getattr(args, "answers", None)
    if answers_raw:
        try:
            answers = json.loads(answers_raw)
        except ValueError:
            raise UsageError(f"--answers 不是合法 JSON: {answers_raw}")
        if not isinstance(answers, dict):
            raise UsageError(f"--answers 必须是 JSON 对象: {answers_raw}")
        from core.util.case_utils import save_env_answers
        save_env_answers(answers)

    # --batch-answers 模式：一次性批量提交答案
    if batch_mode and answers_raw:
        from core.util.case_utils import read_env_answers
        env_answers = read_env_answers()
        case_placeholders = extract_placeholders_from_steps(steps_input)
        all_phs = set()
        for ph_list in case_placeholders.values():
            all_phs.update(ph_list)
        unresolved = [ph for ph in sorted(all_phs) if ph not in env_answers]
        if unresolved:
            print(f"PLACEHOLDER-BATCH FAIL: 以下 {len(unresolved)} 个占位符未解析:")
            for ph in unresolved:
                print(f"  - {ph}")
            raise PayloadError(f"存在 {len(unresolved)} 个未解析占位符")
        print(json.dumps({
            "ok": True,
            "resolved": len(all_phs),
            "placeholders": sorted(all_phs),
        }, ensure_ascii=False, indent=2))
        return

    # --check 模式：校验模式
    if check_mode:
        unresolved = check_resolved(steps_input)
        if unresolved:
            print(f"PLACEHOLDER-CHECK FAIL: 以下占位符未在 env_answers.json 中解析:", file=sys.stderr)
            for case_id, ph in unresolved:
                print(f"  Case {case_id}: {ph}", file=sys.stderr)
            raise PayloadError("请先通过 placeholder-required --steps-input <path> 收集用户输入")
        print(json.dumps({"ok": True, "resolved": True}, ensure_ascii=False, indent=2))
        return

    # 默认模式：纯文本输出未解析的占位符清单
    questions = build_questions(steps_input)
    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()
    unresolved = [q for q in questions if not q.get("resolved")]
    if not unresolved:
        print("所有占位符已解析，无需收集。")
        return
    print("需要收集以下参数，请一次性提供：")
    print()
    for q in unresolved:
        prompt = q.get("prompt", q.get("id", "?"))
        note = q.get("note", "")
        print(f"  {q['id']}: {prompt}")
        if note:
            for line in note.split("；"):
                line = line.strip()
                if line:
                    print(f"    使用位置: {line}")
    print()
    print("请提供以上所有参数的值。")


def _cmd_placeholder_substitute(args):
    """placeholder-substitute 命令入口。

    读取 env_answers.json，将 steps-input.json 中的 {xxx} 替换为实际值，
    输出替换后的 JSON 文件。
    """
    steps_input = getattr(args, "steps_input", None)
    if not steps_input:
        raise UsageError("需要 --steps-input 参数")

    if not os.path.isfile(steps_input):
        raise PayloadError(f"steps-input 文件不存在: {steps_input}")

    output = getattr(args, "output", None)
    if not output:
        # 默认输出：在原文件名基础上加 .resolved 后缀
        base, ext = os.path.splitext(steps_input)
        output = f"{base}.resolved{ext}"

    resolved = substitute_steps_input(steps_input, output_path=output)

    # 统计替换情况（复用已读入内存的 steps_input 数据）
    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()
    original = read_json(steps_input, default={})
    case_placeholders = extract_placeholders_from_steps(original)
    total_placeholders = sum(len(v) for v in case_placeholders.values())
    resolved_count = 0
    for placeholders in case_placeholders.values():
        for ph in placeholders:
            if ph in env_answers:
                resolved_count += 1

    result = {
        "ok": True,
        "input": os.path.abspath(steps_input),
        "output": os.path.abspath(output),
        "total_placeholders": total_placeholders,
        "resolved": resolved_count,
        "unresolved": total_placeholders - resolved_count,
        "all_resolved": resolved_count == total_placeholders,
    }
    if not result["all_resolved"]:
        result["warning"] = f"有 {result['unresolved']} 个占位符未在 env_answers.json 中找到对应值，已在输出中保留原样"

    print(json.dumps(result, ensure_ascii=False, indent=2))