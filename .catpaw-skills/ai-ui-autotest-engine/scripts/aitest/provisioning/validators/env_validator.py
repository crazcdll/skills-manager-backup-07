#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境配置校验器 —— 只负责「在什么环境测」的规则与校验。

**统一环境分类（两维，唯一说法）：部署面 × 接入方式**

| 场景 | 部署面 | 接入方式 | env.type | 关键配置 |
|---|---|---|---|---|
| 线上基准环境 | 线上 | 直连 | A (online) | — |
| 线上泳道环境 | 线上 | 泳道（ptest） | P (online_ptest) | partMock 注入 isPtest/isGreyTest/isDevBundle |
| 测试基准环境 | 测试 | 直连 | C (alpha) | alpha 代理环境，无路由改造 |
| 测试泳道环境 | 测试 | 泳道 | B (swimline) | `swimline.lane_name` |
| 测试域名映射环境 | 测试 | 域名映射 | E (urlmapping) | `url_mappings` |

**一个环境类型就是一个场景**：不存在独立的 `ptest` 开关，`env.ptest` 只是 `type=P`
的派生事实（由引擎写入，不接受外部单独设置）。

**泳道与域名映射是两种独立环境，分开使用**：B 只接受泳道名，E 只接受域名映射，
同一份 env 里两者不能共存（`swim_url_mappings` 仅 E 适用、`swim_lane_name` 仅 B 适用）。
`D`（noop）**不属于环境分类**：它是「免登录」认证方式，只用于跳过登录编排。

未在 APP_ENV_TYPE_RULES 中注册的 App 直接报错。

本模块是**环境规则与校验的唯一事实来源**；问题的声明与收集由
`provisioning/questions/providers/env.py` 负责。
"""
import json
import re

from aitest.shared.errors import ConfigError, ContractError
from aitest.provisioning.credentials import Credential, describe, resolve

DEFAULT_APP = "meituan"

# ── 统一环境分类：场景名 / 两维坐标 ──────────────────────────
# 场景名是**唯一说法**：问卷选项、环境摘要、报告、pipeline 文档只用这里的文字，
# 不要再写「线上环境 / 泳道环境 / alpha 环境」等旧叫法。
ENV_SCENARIO_LABEL = {
    "A": "线上基准环境",
    "P": "线上泳道环境（ptest）",
    "C": "测试基准环境（alpha 域名）",
    "B": "测试泳道环境（泳道名）",
    "E": "测试域名映射环境（域名映射）",
    "D": "免登录（认证方式，不属于环境分类）",
}

# env.type → (部署面, 接入方式)；D 返回 (None, None)：认证维度不参与环境分类
ENV_TYPE_AXES = {
    "A": ("online", "base"),
    "P": ("online", "lane"),
    "B": ("test", "lane"),
    "C": ("test", "base"),
    "D": (None, None),
    "E": ("test", "mapping"),
}
ENV_NETWORK_LABEL = {"online": "线上", "test": "测试"}
ENV_CHANNEL_LABEL = {"base": "基准（直连）", "lane": "泳道", "mapping": "域名映射"}

# ── 环境类型唯一声明（code → (env_name, desc)）──────────────────
# 环境类型 ↔ env_name 的事实来源**只此一处**：ENV_TYPE_MAP / ENV_NAME_TO_TYPE /
# APP_ENV_TYPE_RULES 全部由本表派生。新增环境类型时只改这里。
_ENV_TYPE_DEFS = {
    "A": ("online", ENV_SCENARIO_LABEL["A"]),
    "P": ("online_ptest", ENV_SCENARIO_LABEL["P"]),
    "B": ("swimline", ENV_SCENARIO_LABEL["B"]),
    "C": ("alpha", ENV_SCENARIO_LABEL["C"]),
    "D": ("noop", ENV_SCENARIO_LABEL["D"]),
    "E": ("urlmapping", ENV_SCENARIO_LABEL["E"]),
}

# env.type → env_name（env-prepare / AppMock 使用的环境名）
ENV_TYPE_MAP = {code: name for code, (name, _desc) in _ENV_TYPE_DEFS.items()}
# env_name → env.type（反查表，由正向表推导，供 env-prepare --env 反向映射）
ENV_NAME_TO_TYPE = {name: code for code, (name, _desc) in _ENV_TYPE_DEFS.items()}

# 问卷选项顺序：线上基准 → 线上泳道 → 测试基准 → 测试泳道 → 测试域名映射 → 免登录
ENV_SCENARIO_OPTIONS = [
    {"value": code, "label": ENV_SCENARIO_LABEL[code]}
    for code in ("A", "P", "C", "B", "E", "D")
]


def normalize_env_type(value) -> str:
    """env.type 归一：大小写不敏感；兼容 env_name（online / online_ptest / ...）。

    未识别的值原样返回（由校验层报错，不静默降级）。
    """
    raw = str(value or "").strip()
    code = raw.upper()
    if code in ENV_TYPE_MAP:
        return code
    return ENV_NAME_TO_TYPE.get(raw.lower(), code)

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
#   swim_lane_name                 —— 测试泳道（B）：泳道名
#   swim_url_mappings              —— 测试域名映射（E）：域名映射
#
# 泳道与域名映射是**两种独立环境**，互斥：B 不同时带域名映射，E 不同时带泳道名。
# ptest 不是可选能力而是环境类型 P（线上泳道），因此不在本表中。
# 采集层（questions/providers）据此决定「问不问」，校验层据此决定「能不能生效」。
ENV_CAPABILITIES = {
    "A": frozenset(),                        # 线上基准（直连）
    "P": frozenset(),                        # 线上泳道（ptest 由类型决定）
    "B": frozenset({"swim_lane_name"}),     # 测试泳道
    "C": frozenset(),                        # 测试基准（直连）
    "D": frozenset(),                        # 免登录（认证维度）
    "E": frozenset({"swim_url_mappings"}),  # 测试域名映射
}


def field_applicable(field: str, env_type) -> bool:
    """可选字段在给定环境类型下是否适用（未知环境 / 未登记字段一律不适用）。"""
    caps = ENV_CAPABILITIES.get(normalize_env_type(env_type))
    return caps is not None and str(field) in caps


def describe_env_type(env_type) -> str:
    """环境场景名（唯一说法）：线上基准 / 线上泳道 / 测试基准 / 测试泳道 / 测试域名映射。"""
    code = normalize_env_type(env_type)
    return ENV_SCENARIO_LABEL.get(code, f"未登记环境（{code or '?'}）")


def env_axes(env_type):
    """环境类型 → (部署面, 接入方式)；未登记 / D 返回 (None, None)。"""
    return ENV_TYPE_AXES.get(normalize_env_type(env_type), (None, None))


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


# ── env 配置块的合法键：当前方案的唯一形态 ─────────────────────────────
#
# 与 steps.json / steps-input / intake 合成、以及 AppMock 下发字段**同名**
# （snake_case）。这里做硬门禁：未知键直接报错，不再透传 —— 透传会让写错的
# 配置（中文键、camelCase 别名、已废弃字段）静默不生效，比报错更难排查。
ENV_CONFIG_KEYS = frozenset({
    # 环境类型 + 认证（intake 合成的必/可选字段）
    "type", "env_name", "app", "auth_method", "credential",
    # 可选能力（适用性见 ENV_CAPABILITIES）：泳道与域名映射互斥
    "bundle_lock", "swimline", "url_mappings",
    # 场景声明（steps.json / steps-input / 平台直传）
    "scheme", "landing_scheme", "mock_ids", "testability", "vars", "preconditions",
    # 运行期派生（登录/定位/运行域；ptest 为 type=P 的派生事实）
    "ptest", "location", "login_env", "mock_domain",
})


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
      - auth_validator：认证方式要求（要不要密码 / 账号）
      - config_validator：可选配置（bundle_lock）

    凭证的**来源**不在这里判定：交给 `credentials.resolve`（显式优先，否则 provider
    默认值），本层只负责把结果物化进 env 并校验它够不够用。
    """
    from aitest.provisioning.validators.auth_validator import validate_credential, AuthValidationError
    from aitest.provisioning.validators.config_validator import validate_config, ConfigValidationError

    if not isinstance(env_dict, dict):
        raise EnvValidationError("env 必须是字典")

    unknown = sorted(set(env_dict) - ENV_CONFIG_KEYS)
    if unknown:
        raise EnvValidationError(
            f"env 存在不认识的字段 {unknown}（支持 {sorted(ENV_CONFIG_KEYS)}）；"
            "env 字段与引擎 / AppMock 同名，统一 snake_case"
        )

    env_type = normalize_env_type(env_dict.get("type"))
    if not env_type:
        raise EnvValidationError("env.type 不能为空（A / P / B / C / D / E）")

    # ptest 是派生字段：只允许作为 P 的等价物出现，禁止叠在其它环境上（旧 A+ptest 写法）
    if env_dict.get("ptest") and env_type != "P":
        raise EnvValidationError(
            "ptest 已并入环境类型：线上泳道请用 env.type=P，不要把 ptest 叠在其它环境上"
        )

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
    # ptest 是环境类型 P（线上泳道）的**派生事实**，不对外接受输入
    env_config["ptest"] = env_type == "P"

    # 认证方式 + 凭证：单点解析（显式优先，否则该方式的 provider 默认）→ 校验
    auth_method = str(
        env_dict.get("auth_method") or infer_auth_method(env_type, device_type)
    ).lower()
    credential = resolve(auth_method, env_dict)
    try:
        validate_credential(auth_method, credential)
    except AuthValidationError as e:
        raise EnvValidationError(f"认证配置校验失败: {e}") from e
    env_config["auth_method"] = auth_method
    env_config["credential"] = credential.to_dict() if credential else None

    # 校验可选配置（带 env_type：可选能力必须与环境匹配，见 ENV_CAPABILITIES）
    try:
        config = validate_config({**env_dict, "type": env_type}, env_type=env_type)
        env_config.update(config)
    except ConfigValidationError as e:
        raise EnvValidationError(f"可选配置校验失败: {e}")

    # ── 测试泳道（B）：只接受泳道名；域名映射是独立环境 E，不混用 ──
    if env_type == "B":
        if env_config.get("url_mappings"):
            raise EnvValidationError(
                "环境 B（测试泳道）不接受 url_mappings：域名映射是独立环境 E（测试域名映射），二者分开使用"
            )
        swimline = env_config.get("swimline")
        lane_name = swimline.get("lane_name") if isinstance(swimline, dict) else None
        if not isinstance(lane_name, str) or not lane_name.strip():
            raise EnvValidationError(
                "环境 B（测试泳道）必须提供 swimline.lane_name；只做域名映射请改用环境 E（测试域名映射）"
            )
        url_pattern = swimline.get("url_pattern") or "/*"
        if not isinstance(url_pattern, str) or not url_pattern.strip():
            raise EnvValidationError("环境 B 的 swimline.url_pattern 必须是非空字符串")
        env_config["swimline"] = {
            "lane_name": lane_name.strip(),
            "url_pattern": url_pattern.strip(),
        }

    # ── 测试域名映射（E）：只接受 url_mappings；泳道是独立环境 B，不混用 ──
    if env_type == "E":
        if env_config.get("swimline"):
            raise EnvValidationError(
                "环境 E（测试域名映射）不接受 swimline（泳道名）：泳道是独立环境 B（测试泳道），二者分开使用"
            )
        mappings = env_config.get("url_mappings")
        if not isinstance(mappings, list) or not mappings:
            raise EnvValidationError(
                "环境 E（测试域名映射）必须提供 url_mappings（[{url, betaUrl|ppeUrl}]）"
            )
        for idx, item in enumerate(mappings):
            if not isinstance(item, dict) or not str(item.get("url") or "").strip():
                raise EnvValidationError(f"环境 E 的 url_mappings[{idx}] 必须是对象且包含 url")
        env_config["url_mappings"] = [
            {k: str(item[k]).strip() for k in ("url", "betaUrl", "ppeUrl") if str(item.get(k) or "").strip()}
            for item in mappings
        ]

    return env_config


# ── env_type → auth_method 映射表 ──
# 本表是该映射的**唯一事实来源**：登录侧只按 `plan.auth_method` 从
# `provisioning/setup/login/actions/` 取动作实现（AUTH_ACTIONS），不再自带一份映射。
# 新增 env_type 时需同步更新此表。
_ENV_TYPE_AUTH_MAP = {
    "A": "password",  # online        → 凭证登录（线上基准）
    "P": "password",  # online_ptest  → 凭证登录（线上泳道）
    "B": "qahome",    # swimline      → QAHome 验证码登录（测试泳道）
    "C": "qahome",    # alpha         → QAHome 验证码登录（测试基准）
    "D": "noop",      # 免登录
    "E": "qahome",    # urlmapping    → QAHome 验证码登录（测试域名映射）
}


def infer_auth_method(env_type: str, device_type: str = None) -> str:
    """根据环境类型推断默认的认证方式。

    规则：
      A (online)        → password（凭证登录，线上基准）
      P (online_ptest)  → password（凭证登录，线上泳道）
      B (swimline)      → qahome（QAHome 验证码登录，测试泳道）
      C (alpha)         → qahome（QAHome 验证码登录，测试基准）
      D (noop)          → noop（不自动登录）
      E (urlmapping)    → qahome（QAHome 验证码登录，测试域名映射）

    设备类型约束覆盖环境类型推断：
      device_type=local → 强制返回 noop（本地真机不自动登录，避免污染真机数据）

    此映射是 env_type → auth_method 的唯一事实来源（登录侧按 `plan.auth_method` 取
    AUTH_ACTIONS 实现，不再自带一份映射），确保用户选择的 env_type 自动导出正确的
    auth_method，无需用户额外选择。
    """
    # 设备类型约束优先于环境类型推断
    from aitest.provisioning.validators.auth_validator import get_allowed_auth_methods
    allowed_auth_methods = get_allowed_auth_methods(device_type) if device_type else None
    if allowed_auth_methods is not None and len(allowed_auth_methods) == 1:
        # 设备类型已将登录方式唯一锁定（如 local→noop），直接返回
        return next(iter(allowed_auth_methods))

    return _ENV_TYPE_AUTH_MAP.get(normalize_env_type(env_type), "qahome")


def get_env_summary(env_dict):
    """生成环境配置多行文本摘要。"""
    from aitest.provisioning.validators.auth_validator import AUTH_METHOD_DESC

    env_type = env_dict.get("type", "?")
    app = env_dict.get("app", DEFAULT_APP)
    auth_method = env_dict.get("auth_method", "?")
    cred = Credential.from_dict(env_dict.get("credential"))

    network, channel = env_axes(env_type)
    lines = [
        f"环境场景: {describe_env_type(env_type)}",
        f"环境类型: {env_type}",
    ]
    if network:
        lines.append(f"部署面 / 线路: {ENV_NETWORK_LABEL[network]} / {ENV_CHANNEL_LABEL[channel]}")
    lines += [
        f"认证方式: {AUTH_METHOD_DESC.get(auth_method, auth_method)}",
        f"登录凭证: {describe(cred)}",
    ]

    # 可选配置
    bundle_lock = env_dict.get("bundle_lock", [])
    if bundle_lock:
        locked = [b["name"] for b in bundle_lock if b.get("version")]
        lines.append(f"锁包: {', '.join(locked) if locked else '仅声明目标（无版本，不锁包）'}")

    if env_dict.get("ptest"):
        lines.append("ptest: 开启（线上泳道：partMock 注入 isPtest/isGreyTest/isDevBundle）")

    swimline = env_dict.get("swimline")
    if swimline:
        lines.append(f"泳道: {swimline.get('lane_name', '')} ({swimline.get('url_pattern', '/*')})")

    url_mappings = env_dict.get("url_mappings", [])
    if url_mappings:
        lines.append(f"域名映射: {len(url_mappings)} 条（测试域名映射环境）")

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
    env_type = normalize_env_type(intake.get("env_type"))
    if intake.get("env_type"):
        env["type"] = env_type
    if intake.get("auth_method"):
        env["auth_method"] = intake["auth_method"]
    # 凭证：结构化单字段（account / password / country_code / source）。
    # 来源解析（内置 / 用户提供 / 号池）已在问题层完成，此处只做物化。
    credential = Credential.from_dict(intake.get("credential"))
    if credential is not None:
        env["credential"] = credential.to_dict()
    # ptest：不是独立输入，而是环境类型 P（线上泳道）的派生事实
    if env_type == "P":
        env["ptest"] = True
    if "bundle_lock" in intake:
        env["bundle_lock"] = _as_json_list(intake["bundle_lock"])

    # 测试泳道（B）：泳道名；测试域名映射（E）：域名映射。两者互斥，按能力矩阵分派，
    # 避免 env_type 切换后旧值残留（driver._reconcile 也会清掉不适用项）。
    if field_applicable("swim_lane_name", env_type):
        lane_name = str(intake.get("swim_lane_name") or "").strip()
        if lane_name:
            env["swimline"] = {"lane_name": lane_name, "url_pattern": "/*"}
    if field_applicable("swim_url_mappings", env_type):
        url_mappings = _as_json_list(intake.get("swim_url_mappings"))
        if url_mappings:
            env["url_mappings"] = url_mappings
    return env
