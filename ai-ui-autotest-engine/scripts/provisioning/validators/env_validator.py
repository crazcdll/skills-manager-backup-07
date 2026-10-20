#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境配置校验器 —— 只负责「在什么环境测」的规则与校验。

美团（meituan）环境类型定义：
  A (online)   → 线上环境
  B (swimline) → 泳道/域名映射环境
  C (alpha)    → alpha 测试环境
  D (noop)     → 默认已登录环境

未在 APP_ENV_TYPE_RULES 中注册的 App 直接报错。

本模块是**环境规则与校验的唯一事实来源**；问题的声明与收集由
`provisioning/questions/providers/env.py` 负责。
"""
import json
import re

from shared.errors import ConfigError, ContractError

DEFAULT_APP = "meituan"

# ── 环境类型唯一声明（code → (env_name, desc)）──────────────────────
# 环境类型 ↔ env_name 的事实来源**只此一处**：ENV_TYPE_MAP / ENV_NAME_TO_TYPE /
# APP_ENV_TYPE_RULES 全部由本表派生。新增环境类型时只改这里。
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
# 只包含环境范围的描述，不包含认证方式（认证方式见 auth_validator.py）。
APP_ENV_TYPE_RULES = {
    "meituan": {
        code: {"env_name": name, "desc": desc}
        for code, (name, desc) in _ENV_TYPE_DEFS.items()
    },
    # "dianping": {...}  # 点评环境类型待调研，未注册前禁止使用
}


# ── 环境能力矩阵：env_type → 该环境支持的可选能力（唯一事实来源）────────
#
# 「可选能力」指与环境强相关的可选配置项，其 id 与问题 id 对齐：
#   ptest                          —— 线上环境的 partMock 注入（仅 A）
#   swim_lane_name / swim_url_mappings —— 泳道 / 域名映射（仅 B）
#
# 为什么需要这张表：采集层（questions/providers）决定「问不问」，校验层
# （validators）决定「能不能生效」，两处若各自硬编码条件，必然漂移——历史上
# ptest 就在采集层无条件可问、校验层 docstring 声称「与环境正交」，最终在
# alpha(C) 环境与场景 Mock 互相遮蔽。此处收敛为唯一事实来源，两层统一派生。
#
# 语义依据：ptest = 「线上环境 + partMock 注入」，仅线上环境(A)可选；未知环境
# 一律视为「不适用」（新增环境类型默认不继承任何可选能力，需显式登记）。
ENV_CAPABILITIES = {
    "A": frozenset({"ptest"}),                                 # online  线上环境
    "B": frozenset({"swim_lane_name", "swim_url_mappings"}),   # swimline 泳道/域名映射
    "C": frozenset(),                                          # alpha   alpha 测试环境
    "D": frozenset(),                                          # noop    默认已登录环境
}


def field_applicable(field: str, env_type) -> bool:
    """可选字段在给定环境类型下是否适用（未知环境 / 未登记字段一律不适用）。"""
    caps = ENV_CAPABILITIES.get(str(env_type or "").upper())
    return caps is not None and str(field) in caps


def capability_depends_on(field: str) -> list:
    """可选字段的 `depends_on` 表达式列表（唯一事实来源：ENV_CAPABILITIES）。

    单一环境 → `["env_type == 'A'"]`；多环境 → `["env_type in ('A', 'D')"]`。
    字段未登记（任何环境都不适用）时 raise —— 声明侧与门控侧必须一致，静默
    返回空列表会让问题退化为「无条件适用」，是危险的兜底。
    """
    envs = sorted(code for code, caps in ENV_CAPABILITIES.items() if field in caps)
    if not envs:
        raise ContractError(
            f"可选字段 {field!r} 未在 ENV_CAPABILITIES 登记（任何环境都不适用）；"
            "如需对外开放，请先在环境能力矩阵中声明其适用环境"
        )
    if len(envs) == 1:
        return [f"env_type == '{envs[0]}'"]
    return [f"env_type in ({', '.join(repr(e) for e in envs)})"]


class EnvValidationError(ConfigError):
    """环境配置校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "ENV_CONFIG_INVALID"


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


def validate_env_config(env_dict, app=DEFAULT_APP, device_type=None):
    """校验 env 配置块，通过时返回填充默认值后的标准化 env。

    复合校验入口，内部调用三个子校验器：
      - 本模块：环境类型（type/env_name）
      - auth_validator：认证方式（auth_method/account/_password_raw）
      - config_validator：可选配置（ptest/bundle_lock）
    """
    from provisioning.validators.auth_validator import validate_auth_config, AuthValidationError
    from provisioning.validators.config_validator import validate_config, ConfigValidationError

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

    # 校验可选配置（带 env_type：可选能力必须与环境匹配，见 ENV_CAPABILITIES）
    try:
        config = validate_config(env_dict, env_type=env_type)
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
# 本表是该映射的**唯一事实来源**：登录侧只按 `plan.auth_method` 从
# `provisioning/setup/login/actions/` 取动作实现（AUTH_ACTIONS），不再自带一份映射。
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

    此映射是 env_type → auth_method 的唯一事实来源（登录侧按 `plan.auth_method` 取
    AUTH_ACTIONS 实现，不再自带一份映射），确保用户选择的 env_type 自动导出正确的
    auth_method，无需用户额外选择。
    """
    # 设备类型约束优先于环境类型推断
    from provisioning.validators.auth_validator import get_allowed_auth_methods
    allowed_auth_methods = get_allowed_auth_methods(device_type) if device_type else None
    if allowed_auth_methods is not None and len(allowed_auth_methods) == 1:
        # 设备类型已将登录方式唯一锁定（如 local→noop），直接返回
        return next(iter(allowed_auth_methods))

    return _ENV_TYPE_AUTH_MAP.get(env_type.upper() if env_type else "", "qahome")


def get_env_summary(env_dict):
    """生成环境配置多行文本摘要。"""
    from provisioning.validators.auth_validator import AUTH_METHOD_DESC

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


# ═══════════════════════════════════════════════════════════════════
# intake → env 合成（环境配置的唯一输入源）
# ═══════════════════════════════════════════════════════════════════

def _as_json_list(value):
    """把答案规整为列表：JSON 字符串 → list；空 → []。"""
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
    return value if isinstance(value, list) else []


def build_env_from_intake(intake):
    """由信息收集结果（intake.json）合成 steps-input 的 env 块。

    **env 的唯一输入源**：AI 不再手写 env，`validate_steps_json` 在校验前
    用本函数把 intake 合成进 env（intake 覆盖 AI 残留值）。
    字段映射见 `provisioning/questions/providers/env.py` 的问题声明。
    """
    if not isinstance(intake, dict):
        return {}
    env = {}
    if intake.get("env_type"):
        env["type"] = intake["env_type"]
    if intake.get("auth_method"):
        env["auth_method"] = intake["auth_method"]
    # 账号由两个**互斥**来源合成（门控见 providers/auth.py）：
    #   手填 account（凭证登录） / 引擎生成 test_account（验证码登录）；
    # 互斥门控保证此刻至多一个有值，取先出现者。
    account = intake.get("account") or intake.get("test_account")
    if account is not None:
        env["account"] = account
    if intake.get("password"):
        env["password"] = intake["password"]
    # ptest 仅线上(A)适用：按能力矩阵归一化，env 块只 materialize 适用能力。
    if "ptest" in intake and field_applicable("ptest", intake.get("env_type")):
        env["ptest"] = bool(intake["ptest"])
    if "bundle_lock" in intake:
        env["bundle_lock"] = _as_json_list(intake["bundle_lock"])

    # B 环境：泳道名 + 域名映射（结构化收集，避免二次解析）
    lane_name = str(intake.get("swim_lane_name") or "").strip()
    if lane_name:
        env["swimline"] = {"lane_name": lane_name, "url_pattern": "/*"}
    url_mappings = _as_json_list(intake.get("swim_url_mappings"))
    if url_mappings:
        env["url_mappings"] = url_mappings
    return env
