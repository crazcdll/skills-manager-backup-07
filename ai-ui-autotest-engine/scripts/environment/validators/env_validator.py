#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境配置校验器 — 只负责「在什么环境测」的范围选择。

登录方式（怎么登录）已拆分到 auth_validator.py，
可选配置（ptest/锁包）已拆分到 config_validator.py。

美团（meituan）环境类型定义：
  A (online)   → 线上环境
  B (swimline) → 泳道/域名映射环境
  C (alpha)    → alpha 测试环境
  D (noop)     → 默认已登录环境

未在 APP_ENV_TYPE_RULES 中注册的 App 直接报错。

validate_env_config 保留为复合校验入口，内部同时调用
auth_validator.validate_auth_config 和 config_validator.validate_config。
"""

from core.util.case_utils import resolve_mis, read_env_answers, save_env_answers
from environment.helpers.question_utils import apply_known_value
from environment.validators.auth_validator import get_auth_required_fields, AuthValidationError
from core.errors import ConfigError
import json
DEFAULT_APP = "meituan"

# ── 环境类型唯一声明（code → (env_name, desc)）──────────────────────
# 环境类型 ↔ env_name 的事实来源**只此一处**：ENV_TYPE_MAP / ENV_NAME_TO_TYPE /
# APP_ENV_TYPE_RULES 全部由本表派生。新增环境类型时只改这里。
# ⚠️ 禁止在其它模块（历史上散落在 core.sop.constants.ENV_TYPE_MAP、
#    env_prepare._reverse_env_type）再手写一份类型名映射，否则必然漂移。
_ENV_TYPE_DEFS = {
    "A": ("online", "线上环境"),
    "B": ("swimline", "泳道/域名映射环境"),
    "C": ("alpha", "alpha 测试环境"),
    "D": ("noop", "默认已登录环境"),
}

# env.type (A/B/C/D) → env_name（env-prepare / AppMock 使用的环境名）
ENV_TYPE_MAP = {code: name for code, (name, _desc) in _ENV_TYPE_DEFS.items()}
# env_name → env.type（反查表，由正向表推导，供 env-prepare --env 反向映射）
ENV_NAME_TO_TYPE = {name: code for code, (name, _desc) in _ENV_TYPE_DEFS.items()}

# App → 环境类型定义。对外的唯一事实来源（由 _ENV_TYPE_DEFS 派生），新增 App 支持时在此追加。
# 只包含环境范围的描述，不包含认证方式（认证方式已拆分到 auth_validator.py）。
APP_ENV_TYPE_RULES = {
    "meituan": {
        code: {"env_name": name, "desc": desc}
        for code, (name, desc) in _ENV_TYPE_DEFS.items()
    },
    # "dianping": {...}  # 点评环境类型待调研，未注册前禁止使用
}


class EnvValidationError(ConfigError):
    """环境配置校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "ENV_CONFIG_INVALID"


def _resolve_mis_silently():
    """读取已保存的 MIS（不抛异常）。用于判定 mis 是否还需要向用户提问。

    过滤掉 __manual_input__ / __skip__ 等信号值，避免被当作已保存的真实 MIS。
    """
    try:
        mis = resolve_mis() or ""
        if mis in ("__manual_input__", "__skip__"):
            return ""
        return mis
    except Exception:
        return ""


def _build_questions(env_type, env_type_rules, flow_placeholders=None, known_values=None):
    """构建环境范围相关的问题列表。

    env_type 为 None → 用户还没选环境类型，包含 env_type 选择题 + MIS 填写。
    env_type 已确定 → 包含 MIS 填写 + B 环境泳道配置（如果是 B 环境）。

    不包含认证方式和可选配置的问题。
    authentication 问题由 auth_validator.py 构建，
    可选配置问题由 config_validator.py 构建。
    """
    questions = []

    # ── ① env_type 选择题（仅当用户还没选环境类型时）──
    if env_type is None:
        questions.append(apply_known_value({
            "id": "env_type",
            "group": "identity",
            "order": 5,
            "prompt": "选择测试环境类型",
            "input_type": "mixed",
            "required": True,
            "source": "ask",
            "default": None,
            "options": _env_type_options(env_type_rules),
            "resolved": False,
        }, known_values))

    # ── ② MIS 始终必填，但优先从已保存的答案中读取 ──
    saved_mis = _resolve_mis_silently()
    mis_options = [
        {"value": "__manual_input__", "label": "✏️ 手动输入 MIS ID"},
        {"value": "__skip__", "label": "⏭️ 稍后再说"},
    ]
    if saved_mis:
        mis_options.insert(0, {"value": saved_mis, "label": f"使用已保存的: {saved_mis}"})
    questions.append({
        "id": "mis",
        "group": "identity",
        "order": 10,
        "prompt": "MIS ID（用于 AppMock / 云真机资源归属）",
        "input_type": "mixed",
        "required": True,
        "source": "config_file",
        "config_path": ".config/env_answers.json",
        "default": saved_mis or None,
        "resolved": bool(saved_mis),
        "options": mis_options,
        "ask_if_missing": True,
        "skip_reason": f"已从 .config/env_answers.json 读取到 {saved_mis}" if saved_mis else None,
    })

    # ── ③ B 环境泳道配置（仅当选择了 B 环境）──
    if env_type == "B":
        questions.append({
            "id": "swimline_or_url_mappings",
            "group": "scope",
            "order": 31,
            "prompt": "泳道名称 或 域名映射（选填，不填则跳过泳道配置）",
            "input_type": "text",
            "required": False,
            "source": "flow_extract",
            "default": None,
            "resolved": False,
        })

    questions.sort(key=lambda q: q["order"])
    return [apply_known_value(q, known_values, allow_manual_input=True) for q in questions]


def _env_type_options(env_type_rules):
    """按 App 环境类型规则生成选择题选项。

    只包含环境范围描述，不包含认证方式信息（认证方式已拆分到 auth_validator.py）。
    """
    options = []
    for env_type in sorted(env_type_rules.keys()):
        rule = env_type_rules[env_type]
        label = f"{env_type} — {rule['desc']}"
        options.append({"value": env_type, "label": label})
    return options


def get_env_type_rules(app: str) -> dict:
    """获取指定 App 的环境类型规则表，未注册的 App 直接报错。"""
    rules = APP_ENV_TYPE_RULES.get(app)
    if rules is None:
        supported = "、".join(APP_ENV_TYPE_RULES.keys())
        raise EnvValidationError(
            f"App「{app}」尚未注册环境类型规则（APP_ENV_TYPE_RULES 中无对应条目）。"
            f"当前仅支持: {supported}。"
        )
    return rules


def _resolve_env_type(env_type_arg, known_values):
    """确定最终的环境类型，优先级：--type 参数 > 已保存的答案。"""
    if env_type_arg:
        return str(env_type_arg).upper()
    if known_values and known_values.get("env_type"):
        return str(known_values["env_type"]).upper()
    return None


def _categorize_questions(questions, no_more_questions):
    """将问题列表按状态分类，返回各类字段的 ID 列表。

    Args:
        questions: 问题字典列表
        no_more_questions: 用户是否已声明信息备齐

    Returns:
        (missing_required, unresolved_questions, choice_questions, text_questions)
    """
    missing_required = [
        q["id"] for q in questions
        if q.get("required", True) and not q.get("resolved")
    ]

    if no_more_questions:
        return missing_required, [], [], []

    unresolved_questions = [
        q["id"] for q in questions
        if not q.get("resolved") and (
            q["source"] in ("ask", "flow_extract")
            or (q["source"] == "config_file" and q.get("ask_if_missing"))
        )
    ]

    choice_questions = [
        q["id"] for q in questions
        if q.get("input_type") == "mixed" and q["id"] in unresolved_questions
    ]

    text_questions = [
        q["id"] for q in questions
        if q.get("input_type") == "text" and q["id"] in unresolved_questions
    ]

    return missing_required, unresolved_questions, choice_questions, text_questions


def _build_notes(selected_env_type, no_more_questions, missing_required,
                 unresolved_questions, choice_questions, text_questions):
    """生成备注信息，指导 AI 如何处理这些问题。"""
    notes_parts = []

    # 环境类型状态
    if selected_env_type is None:
        notes_parts.append("环境类型待用户选择")
    else:
        notes_parts.append(f"环境类型: {selected_env_type['desc']}")

    # 收集状态
    if no_more_questions:
        notes_parts.append("用户已声明信息备齐，跳过咨询，直接使用各字段 default 值执行")
        if missing_required:
            notes_parts.append(
                f"⚠️ 以下必填项仍未获知，将使用 default（可能为空）: {', '.join(missing_required)}，"
                f"若为空会在 flow-init 阶段报错"
            )
    elif unresolved_questions:
        notes_parts.append(f"本次需一次性收集: {', '.join(unresolved_questions)}")
    else:
        notes_parts.append("无待收集项")

    # 问题类型提示
    if not no_more_questions:
        question_type_hints = []
        if choice_questions:
            question_type_hints.append(
                f"有选项的题目（{', '.join(choice_questions)}）→ 用 AskQuestion 收集"
            )
        if text_questions:
            question_type_hints.append(
                f"文本输入的题目（{', '.join(text_questions)}）→ "
                f"AI 直接在聊天中展示给用户一次性输入，然后调用 save-answers --answers 保存"
            )
        if question_type_hints:
            notes_parts.append("；".join(question_type_hints))
        notes_parts.append("按 order 排序提问；required=false 的题目仍需展示但可留空/跳过")

    return "".join(notes_parts)


def get_required_fields(flow_source, flow_placeholders=None, env_type=None, app=DEFAULT_APP,
                         known_values=None, no_more_questions=False, device_type=None):
    """根据 App + 环境类型返回必填项清单。

    第 1 步：确定环境类型（env_type）
    第 2 步：构建问题列表
    第 3 步：分类问题并生成备注

    env_type 确定优先级：
      1. --type 显式传入
      2. known_values 预填 env_type
      3. 均未提供 → 返回环境类型选择题，用户选定后 AI 以 --type 二次调用
    """
    # ── 第 1 步：确定环境类型 ──
    env_type = _resolve_env_type(env_type, known_values)

    # ── 第 2 步：校验并获取环境类型规则 ──
    env_type_rules = get_env_type_rules(app)
    if env_type and env_type not in env_type_rules:
        raise EnvValidationError(
            f"App「{app}」不支持环境类型: {env_type}，支持: {'/'.join(env_type_rules.keys())}"
        )

    selected_env_type = env_type_rules[env_type] if env_type else None

    # ── 第 3 步：构建问题列表 ──
    questions = _build_questions(env_type, env_type_rules, flow_placeholders, known_values)

    # ── 第 4 步：分类问题并生成备注 ──
    missing_required, unresolved_questions, choice_questions, text_questions = \
        _categorize_questions(questions, no_more_questions)

    notes = _build_notes(
        selected_env_type, no_more_questions, missing_required,
        unresolved_questions, choice_questions, text_questions,
    )

    return {
        "app": app,
        "env_type": env_type,
        "desc": selected_env_type["desc"] if selected_env_type else "待用户选择",
        "questions": questions,
        "ask_now": unresolved_questions,
        "ask_choice_now": choice_questions,
        "ask_text_now": text_questions,
        "missing_required": missing_required,
        "no_more_questions": no_more_questions,
        "notes": notes,
    }


def _merge_into_env_response(env_response, auth_response):
    """将认证问题合并到环境问题响应中。

    合并 questions、ask_now、missing_required、ask_choice_now、ask_text_now 等字段，
    同时追加 auth_method 信息和 notes 说明。
    """
    env_response["questions"].extend(auth_response["questions"])
    env_response["ask_now"].extend(
        qid for qid in auth_response["ask_now"]
        if qid not in env_response["ask_now"]
    )
    env_response["missing_required"].extend(
        qid for qid in auth_response["missing_required"]
        if qid not in env_response["missing_required"]
    )
    env_response.setdefault("ask_choice_now", []).extend(
        qid for qid in auth_response.get("ask_choice_now", [])
        if qid not in env_response.get("ask_choice_now", [])
    )
    env_response.setdefault("ask_text_now", []).extend(
        qid for qid in auth_response.get("ask_text_now", [])
        if qid not in env_response.get("ask_text_now", [])
    )
    env_response["auth_method"] = auth_response["auth_method"]
    env_response["auth_method_inferred"] = True

    # 追加认证方式说明到 notes
    auth_desc = auth_response.get("desc", auth_response["auth_method"])
    if auth_response.get("no_more_questions"):
        pass  # 无待收集项，不额外提示
    elif auth_response.get("ask_now"):
        env_response["notes"] += (
            f"；认证方式已根据环境类型自动推断为 {auth_response['auth_method']}（{auth_desc}），"
            f"与环境信息一并收集"
        )
    else:
        env_response["notes"] += (
            f"；认证方式已自动推断为 {auth_response['auth_method']}（{auth_desc}），凭证已就绪"
        )

    return env_response


def validate_env_config(env_dict, app=DEFAULT_APP, device_type=None):
    """校验 env 配置块，通过时返回填充默认值后的标准化 env。

    复合校验入口，内部调用三个子校验器：
      - 本模块：环境类型（type/env_name）
      - auth_validator：认证方式（auth_method/account/_password_raw）
      - config_validator：可选配置（ptest/bundle_lock）
    """
    from environment.validators.auth_validator import validate_auth_config, AuthValidationError
    from environment.validators.config_validator import validate_config, ConfigValidationError

    if not isinstance(env_dict, dict):
        raise EnvValidationError("env 必须是字典")

    env_type = env_dict.get("type")
    if not env_type:
        raise EnvValidationError("env.type 不能为空（A/B/C/D）")

    env_type = str(env_type).upper()
    env_type_rules = get_env_type_rules(app)
    if env_type not in env_type_rules:
        raise EnvValidationError(
            f"App「{app}」不支持环境类型: {env_type}，支持: {'/'.join(env_type_rules.keys())}"
        )

    rule = env_type_rules[env_type]

    # 构建标准化 env（保留原有字段，新增标准化字段）
    env_config = dict(env_dict)
    env_config.update({
        "app": app,
        "type": env_type,
        "env_name": rule["env_name"],
    })

    # 校验认证配置（如果提供了 auth_method 字段）
    if env_dict.get("auth_method"):
        try:
            auth_config = validate_auth_config(env_dict)
            env_config.update(auth_config)
        except AuthValidationError as e:
            raise EnvValidationError(f"认证配置校验失败: {e}")

    # 校验可选配置
    try:
        config = validate_config(env_dict)
        env_config.update(config)
    except ConfigValidationError as e:
        raise EnvValidationError(f"可选配置校验失败: {e}")

    # B 环境的泳道/域名映射配置是可选的。
    # 遵循「模板预置全部字段，默认空值，有值就执行，无值就跳过」原则。
    # 泳道配置和域名映射都为空时，type=B 仅表示使用 qahome 登录方式，
    # 不执行泳道切换/域名映射，不会报错。
    if env_type == "B":
        swimline = env_config.get("swimlane")
        if swimline is not None:
            if not isinstance(swimline, dict):
                raise EnvValidationError("环境 B 的 swimlane 必须是对象或 None")
            lane_name = swimline.get("lane_name")
            # 空字典或 lane_name 为空 → 视为未配置，跳过泳道配置
            if isinstance(lane_name, str) and lane_name.strip():
                url_pattern = swimline.get("url_pattern", "/*")
                if not isinstance(url_pattern, str) or not url_pattern.strip():
                    raise EnvValidationError("环境 B 的 swimlane.url_pattern 必须是非空字符串")
                env_config["swimline"] = {
                    "lane_name": lane_name.strip(),
                    "url_pattern": url_pattern.strip(),
                }
        # url_mappings/域名映射：有值保留，无值跳过，不报错

    return env_config


# ── env_type → auth_method 映射表 ──
# 与 login_strategy._build_meituan_strategy 的映射逻辑一致，作为唯一事实来源。
# 新增 env_type 时需同步更新此表。
_ENV_TYPE_AUTH_MAP = {
    "A": "password",  # online → 凭证登录
    "B": "qahome",    # swimline → QAHome 验证码登录
    "C": "qahome",    # alpha → QAHome 验证码登录
    "D": "noop",      # 已登录 → 不自动登录
}


def infer_auth_method(env_type: str, device_type: str = None) -> str:
    """根据环境类型推断默认的认证方式。

    规则：
      A (online)     → password（凭证登录）
      B (swimline)   → qahome（QAHome 验证码登录）
      C (alpha)      → qahome（QAHome 验证码登录）
      D (noop)       → noop（不自动登录）

    设备类型约束覆盖环境类型推断：
      device_type=local → 强制返回 noop（本地真机不自动登录，避免污染真机数据）

    此映射与 login_strategy._build_meituan_strategy 的登录策略派发逻辑一致，
    确保用户选择的 env_type 自动导出正确的 auth_method，无需用户额外选择。
    """
    # 设备类型约束优先于环境类型推断
    from environment.validators.auth_validator import get_allowed_auth_methods
    allowed_auth_methods = get_allowed_auth_methods(device_type) if device_type else None
    if allowed_auth_methods is not None and len(allowed_auth_methods) == 1:
        # 设备类型已将登录方式唯一锁定（如 local→noop），直接返回
        return next(iter(allowed_auth_methods))

    return _ENV_TYPE_AUTH_MAP.get(env_type.upper() if env_type else "", "qahome")


def get_env_summary(env_dict):
    """生成环境配置多行文本摘要。"""
    from environment.validators.auth_validator import AUTH_METHOD_DESC

    env_type = env_dict.get("type", "?")
    app = env_dict.get("app", DEFAULT_APP)
    env_type_rule = APP_ENV_TYPE_RULES.get(app, {}).get(env_type, {})
    auth_method = env_dict.get("auth_method", "?")
    account = env_dict.get("account", "?")
    has_password = bool(env_dict.get("_password_raw"))

    lines = [
        f"环境类型: {env_type} ({env_type_rule.get('desc', '未知')})",
        f"认证方式: {AUTH_METHOD_DESC.get(auth_method, auth_method)}",
    ]
    if account and account != "?":
        lines.append(f"登录账号: {account}")

    if auth_method == "password":
        lines.append(f"登录凭证: {'已提供' if has_password else '❌ 未提供'}")

    # 可选配置
    mock_ids = env_dict.get("mock_ids", [])
    if mock_ids:
        lines.append(f"Mock 规则: {len(mock_ids)} 条")

    bundle_lock = env_dict.get("bundle_lock", [])
    if bundle_lock:
        locked = [b["name"] for b in bundle_lock if b.get("version")]
        lines.append(f"锁包: {', '.join(locked) if locked else '仅声明目标（无版本，不锁包）'}")

    if env_dict.get("ptest"):
        lines.append("ptest: 开启（partMock 注入 isPtest/isGreyTest/isDevBundle）")

    swimline = env_dict.get("swimlane")
    if swimline:
        lines.append(f"泳道: {swimline.get('lane_name', '')} ({swimline.get('url_pattern', '/*')})")

    url_mappings = env_dict.get("url_mappings", [])
    if url_mappings:
        lines.append(f"域名映射: {len(url_mappings)} 条")

    return "\n".join(lines)


def mask_password(password):
    """凭证脱敏：保留前2后2，中间用*替代。"""
    if not password or len(password) <= 4:
        return "****"
    return password[:2] + "*" * (len(password) - 4) + password[-2:]


def cmd_env_required(args):
    """环境范围选择 + 认证方式自动推断。--type 已传则直接返回，否则返回选择题。"""
    if args.answers:
        try:
            answers = json.loads(args.answers)
        except ValueError:
            raise ConfigError(f"--answers 不是合法 JSON: {args.answers}")
        if not isinstance(answers, dict):
            raise ConfigError(f"--answers 必须是 JSON 对象: {args.answers}")
        save_env_answers(answers)

    saved_answers = read_env_answers()
    try:
        env_response = get_required_fields(
            args.flow_source,
            flow_placeholders=[],
            env_type=args.env_type,
            app=args.app,
            known_values=saved_answers,
            no_more_questions=args.no_more_questions,
        )
    except EnvValidationError as e:
        raise ConfigError(str(e)) from e

    # ── 当 env_type 确定后，自动推断 auth_method 并合并认证凭证字段 ──
    env_type = env_response.get("env_type")
    if env_type:
        auth_method = infer_auth_method(env_type, device_type=args.device_type)
        try:
            auth_response = get_auth_required_fields(
                auth_method=auth_method,
                known_values=saved_answers,
                no_more_questions=args.no_more_questions,
                device_type=args.device_type,
            )
        except AuthValidationError as e:
            raise ConfigError(f"认证配置推断失败: {e}") from e

        env_response = _merge_into_env_response(env_response, auth_response)

    print(json.dumps(env_response, ensure_ascii=False, indent=2))
    save_env_answers(saved_answers)

    # ── AI 引导提示 ──
    env_type = env_response.get("env_type")
    has_questions = env_response.get("ask_now") or env_response.get("questions")
    if not env_type and has_questions:
        ai_guide = """
========== 🤖 AI 引导（第1轮） ==========
📌 触发策略判断：
   - 用户完全没提环境信息 → 直接通过 AskQuestion 展示上面的选择题
   - 用户已提供 env_type/mis → 用 --answers 预填已知值，只问剩余项
   - 用户明确说信息已给全 → 加 --no-more-questions 强制跳过
⚠️ 模糊参数确认：用户可能给了一串裸值（如"线上，mis01，139xxx"），
   不要强行猜映射关系，主动向用户逐项确认
📋 操作步骤：
1. 将上面输出的 env_type 选择题 + mis 问题通过 AskQuestion 展示给用户（禁止自行构造/简化选项）
2. env_type 有 4 种选项：
   - A = 线上环境          → 自动推断 auth_method=password（凭证登录）
   - B = 泳道/域名映射环境  → 自动推断 auth_method=qahome（QAHome验证码登录）
   - C = alpha 测试环境    → 自动推断 auth_method=qahome（QAHome验证码登录）
   - D = 默认已登录环境    → 自动推断 auth_method=noop（跳过登录）
   ⚠️ 注意：设备类型可覆盖推断规则——local（本地真机）只能 noop
3. 有 default 值的字段用 `mixed` 展示默认值；已保存的值作为可选选项展示
4. 用户选择后，调用 `save-answers --answers '{"env_type":"用户所选value","mis":"mis值"}'` 保存
5. 然后重新执行 `env-required --app <app>`（此时 auth_method 会自动推断，进入第2轮）
=========================================="""
        print(ai_guide)
    elif env_type:
        ai_guide = """
========== 🤖 AI 引导（第2轮） ==========
📋 操作步骤：
1. env_type 已确定（{}），auth_method 已自动推断
2. 将上面输出的 credential 字段（account/password）通过 AskQuestion 展示给用户
   - 有 default 值的用 `mixed` 展示默认值
   - 文本输入题使用 `input_type=mixed`，自带「✏️ 手动输入」选项
   - 用户选择「手动输入」后，在聊天中询问具体值
3. 注意：密码是敏感信息，不回显在聊天中，提示用户直接输入
4. 用户填写后，调用 `save-answers --answers '{{"account":"用户输入账号","password":"用户输入密码"}}'` 保存
5. 然后继续执行 `config-required --flow-source <flow-文件路径>`
==========================================""".format(env_type)
        print(ai_guide)