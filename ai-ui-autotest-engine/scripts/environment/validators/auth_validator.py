#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证方式校验器 — 独立的登录方式选择 + 凭证收集。

与 env_validator 解耦：env_validator 只负责「在什么环境测」，
auth_validator 只负责「怎么登录」，两者独立选择、正交组合。

认证规则：
  password → 凭证登录，account + password 必填
  qahome   → QAHome 验证码登录，account 必填
  noop     → 免登录，不需要 account/password

设备类型约束（DEVICE_TYPE_ALLOWED_AUTH_METHODS）：
  local（本地真机）→ 只允许 noop（不自动登录，避免污染真机数据）
"""

from environment.helpers.question_utils import apply_known_value
from core.errors import ConfigError

# 认证方式 → 认证约束。唯一事实来源，新增认证方式时在此追加。
AUTH_METHOD_RULES = {
    "password": {
        "desc": "凭证登录",
        "password_required": True,
        "account_required": True,
    },
    "qahome": {
        "desc": "QAHome 验证码登录",
        "password_required": False,
        "account_required": True,
    },
    "noop": {
        "desc": "默认已登录（跳过登录）",
        "password_required": False,
        "account_required": False,
    },
}

# device_type → 允许的 auth_method 集合。
# 与 APP_ENV_TYPE_RULES 正交：这是"设备维度"对登录方式的约束，不区分环境。
# 不在白名单中的 device_type 视为不限制。
DEVICE_TYPE_ALLOWED_AUTH_METHODS = {
    "local": {"noop"},
}

# 认证方式 → 中文描述
AUTH_METHOD_DESC = {
    "password": "凭证登录",
    "qahome": "QAHome 验证码登录",
    "noop": "默认已登录（跳过登录）",
}

_MIN_PASSWORD_LENGTH = 6
_PLACEHOLDER_RE = __import__('re').compile(
    r'^([\*\.\_\-]+|placeholder|REPLACE_WITH_\w+|todo|fixme|changeme|password|test1*|dummy|none|null|undefined|N/?A)$',
    __import__('re').IGNORECASE,
)
_MASKED_RE = __import__('re').compile(r'^.{1,4}\*{2,}.{0,4}$')


def _is_real_password(password):
    """判断凭证是否为真实可用凭证（非占位符/脱敏/过短）。"""
    if not password or not isinstance(password, str):
        return False
    password = password.strip()
    if len(password) < _MIN_PASSWORD_LENGTH:
        return False
    if _PLACEHOLDER_RE.match(password):
        return False
    if _MASKED_RE.match(password):
        return False
    if len(set(password)) == 1:
        return False
    return True


class AuthValidationError(ConfigError):
    """认证方式/凭证校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "AUTH_CONFIG_INVALID"


def get_allowed_auth_methods(device_type: str):
    """返回指定 device_type 下允许的 auth_method 集合；None 表示不限制。"""
    return DEVICE_TYPE_ALLOWED_AUTH_METHODS.get(device_type)


def get_auth_method_rules() -> dict:
    """获取认证方式规则表（深拷贝，防止调用方意外修改）。"""
    return dict(AUTH_METHOD_RULES)


def _auth_method_options(allowed_auth_methods=None):
    """生成认证方式选择题选项。

    allowed_auth_methods: 可选，设备类型限制的认证方式白名单。
    传入时仅展示白名单内的选项，并标注"设备限制"。
    """
    options = []
    for auth_method in sorted(AUTH_METHOD_RULES.keys()):
        rule = AUTH_METHOD_RULES[auth_method]
        label = f"{auth_method} — {rule['desc']}"
        needs = []
        if rule["account_required"]:
            needs.append("需手机号")
        if rule["password_required"]:
            needs.append("需密码")
        if needs:
            label += f"（{'、'.join(needs)}）"
        if allowed_auth_methods is not None and auth_method not in allowed_auth_methods:
            options.append({"value": auth_method, "label": label, "disabled": True})
        else:
            options.append({"value": auth_method, "label": label})
    return options


def _build_auth_questions(auth_method, rule, known_values=None):
    """构造认证信息收集清单。

    auth_method 为 None 时只生成认证方式选择题（不生成凭证字段）；
    auth_method 已确定时根据认证规则生成对应凭证字段。
    """
    questions = []

    # ── ① credential：随认证方式变化 ──
    if auth_method is not None and (rule or {}).get("account_required", True):
        questions.append({
            "id": "account",
            "group": "credential",
            "order": 20,
            "prompt": "测试手机号",
            "input_type": "mixed",
            "required": True,
            "source": "ask",
            "default": None,
            "resolved": False,
            "options": [
                {"value": "__manual_input__", "label": "✏️ 手动输入手机号"},
                {"value": "__skip__", "label": "⏭️ 稍后再说"},
            ],
            "validate": r"^1[3-9]\d{9}$",
            "validate_hint": "需为 11 位数字格式",
        })

    if auth_method is not None and (rule or {}).get("password_required"):
        questions.append({
            "id": "password",
            "group": "credential",
            "order": 21,
            "prompt": "该账号的登录凭证",
            "input_type": "mixed",
            "required": True,
            "source": "ask",
            "default": None,
            "resolved": False,
            "sensitive": True,
            "options": [
                {"value": "__manual_input__", "label": "✏️ 手动输入凭证"},
                {"value": "__skip__", "label": "⏭️ 稍后再说"},
            ],
            "validate_hint": f"真实凭证，长度 ≥ {_MIN_PASSWORD_LENGTH}，不接受占位符/脱敏串",
        })

    questions.sort(key=lambda q: q["order"])
    return [apply_known_value(q, known_values, allow_manual_input=True) for q in questions]


def get_auth_required_fields(auth_method=None, known_values=None,
                              no_more_questions=False, device_type=None):
    """根据认证方式返回必填项清单。

    auth_method: 认证方式标识符，可选。
      - 不传 → 返回认证方式选择题（首问），用户选定后 AI 以 --type 二次调用
      - 已传 → 直接返回该认证方式的凭证字段
    known_values: 调用方从用户原始提示词中解析出的字段值。
    no_more_questions: 用户声明信息已备齐时传 True。
    device_type: 传入且命中设备白名单限制时（如 local 只允许 noop），
                 auth_method 会被自动收窄到白名单内取值。
    """
    if auth_method:
        auth_method = str(auth_method).lower()

    allowed_auth_methods = get_allowed_auth_methods(device_type) if device_type else None
    device_locked_from = None
    if allowed_auth_methods is not None:
        if auth_method is not None and auth_method not in allowed_auth_methods:
            device_locked_from = auth_method
        auth_method = sorted(allowed_auth_methods)[0]

    auth_method_unknown = auth_method is None
    if not auth_method_unknown and auth_method not in AUTH_METHOD_RULES:
        raise AuthValidationError(
            f"不支持的认证方式: {auth_method}，支持: {'/'.join(AUTH_METHOD_RULES.keys())}"
        )

    if auth_method_unknown:
        # 选择模式：auth_method 未定，返回认证方式选择题
        questions = _build_auth_questions(None, None, known_values)
        questions.insert(0, apply_known_value({
            "id": "auth_method",
            "group": "identity",
            "order": 5,
            "prompt": "选择登录方式",
            "input_type": "mixed",
            "required": True,
            "source": "ask",
            "default": None,
            "options": _auth_method_options(allowed_auth_methods),
            "resolved": False,
        }, known_values))
        rule = None
    else:
        rule = AUTH_METHOD_RULES[auth_method]
        questions = _build_auth_questions(auth_method, rule, known_values)
        if allowed_auth_methods is not None:
            # 登录方式已被设备类型唯一锁定，插入只读说明
            questions.insert(0, {
                "id": "auth_method_confirm",
                "group": "identity",
                "order": 5,
                "prompt": f"登录方式已由设备类型锁定为 {auth_method}（{rule['desc']}），无需询问用户",
                "input_type": "readonly",
                "required": False,
                "source": "device_locked",
                "default": auth_method,
                "options": None,
                "resolved": True,
                "skip_reason": (
                    f"设备类型限定登录方式为 {'/'.join(sorted(allowed_auth_methods))}"
                    + (f"；原 auth_method={device_locked_from} 已被自动收窄" if device_locked_from else "")
                ),
            })

    missing_required = [
        q["id"] for q in questions
        if q.get("required", True) and not q.get("resolved")
    ]
    if no_more_questions:
        ask_now = []
    else:
        ask_now = [
            q["id"] for q in questions
            if not q.get("resolved") and (
                q["source"] in ("ask", "flow_extract")
                or (q["source"] == "config_file" and q.get("ask_if_missing"))
            )
        ]

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

    if rule is None:
        notes_parts = ["登录方式待用户选择"]
        if allowed_auth_methods is not None:
            notes_parts.append(
                f"设备类型已将登录方式锁定为 {auth_method}，不要向用户展示/询问登录方式选项"
            )
    else:
        auth_desc = AUTH_METHOD_DESC.get(auth_method, auth_method)
        notes_parts = [f"{auth_desc}方式"]
        if allowed_auth_methods is not None:
            notes_parts.append(
                f"设备类型已将登录方式锁定为 {auth_method}，不要向用户展示/询问登录方式选项"
                + (f"（原指定的 {device_locked_from} 已被自动收窄）" if device_locked_from else "")
            )
            if auth_method == "noop":
                notes_parts.append("noop 方式不自动登录，需引导用户在设备上手动完成登录后再继续")
    if no_more_questions:
        notes_parts.append("用户已声明信息备齐，跳过咨询，直接使用各字段 default 值执行")
        if missing_required:
            notes_parts.append(f"⚠️ 以下必填项仍未获知，将使用 default（可能为空）: {', '.join(missing_required)}")
    elif ask_now:
        notes_parts.append(f"本次需一次性收集: {', '.join(ask_now)}")
    else:
        notes_parts.append("无待收集项（凭证已就绪）")
    if not no_more_questions:
        parts = []
        if ask_choice_now:
            parts.append(f"有选项的题目（{', '.join(ask_choice_now)}）→ 用 AskQuestion 收集")
        if ask_text_now:
            parts.append(f"文本输入的题目（{', '.join(ask_text_now)}）→ AI 直接在聊天中展示给用户一次性输入，然后调用 save-answers --answers 保存")
        if parts:
            notes_parts.append("；".join(parts))
        notes_parts.append("按 order 排序提问；required=false 的题目仍需展示但可留空/跳过")

    return {
        "auth_method": auth_method,
        "auth_method_unknown": auth_method_unknown,
        "desc": rule["desc"] if rule else "待用户选择",
        "questions": questions,
        "ask_now": ask_now,
        "ask_choice_now": ask_choice_now,
        "ask_text_now": ask_text_now,
        "missing_required": missing_required,
        "no_more_questions": no_more_questions,
        "notes": "。".join(notes_parts),
    }


def validate_auth_config(auth_dict):
    """校验认证配置块，通过时返回标准化后的 auth 配置。

    auth_dict 应包含: auth_method, account, password（可选）
    校验失败时抛出 AuthValidationError。
    """
    if not isinstance(auth_dict, dict):
        raise AuthValidationError("auth 配置必须是字典")

    auth_method = auth_dict.get("auth_method")
    if not auth_method:
        raise AuthValidationError("auth_method 不能为空（password/qahome/noop）")

    auth_method = str(auth_method).lower()
    if auth_method not in AUTH_METHOD_RULES:
        raise AuthValidationError(
            f"不支持的认证方式: {auth_method}，支持: {'/'.join(AUTH_METHOD_RULES.keys())}"
        )

    rule = AUTH_METHOD_RULES[auth_method]
    account = auth_dict.get("account")
    password = auth_dict.get("password")

    if rule.get("account_required", True) and not account:
        raise AuthValidationError(
            f"认证方式 {auth_method} ({rule['desc']}) 必须提供 account（测试手机号）"
        )

    if rule["password_required"]:
        if not _is_real_password(password):
            hint = "未填写 password" if not password else (
                f"password 值 \"{password}\" 不是有效凭证（占位符/脱敏/过短）"
            )
            raise AuthValidationError(
                f"认证方式 {auth_method} ({rule['desc']}) 凭证登录必须提供真实凭证。\n"
                f"  当前问题: {hint}\n"
                f"  解决方法: 用 AskQuestion 向用户询问真实凭证"
            )
        normalized_password = password

    # 构建标准化结果
    normalized = dict(auth_dict)
    normalized.update({
        "auth_method": auth_method,
        "account": account,
        "_password_raw": normalized_password if rule["password_required"] else password,
    })
    normalized.pop("password", None)

    return normalized