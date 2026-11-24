#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可测性 action 校验器 —— Pillow testability config 的唯一校验事实来源。

规则来源
────────
· `testability-actions` Skill 的 `references/actions.json`（action 注册表：type /
  info 字段 / 取值含义）与 `references/block2-scheme.md`（组合与顺序约束）。
· 本模块只**校验**、不改写：配置原样下发给设备。校验层一旦"顺手补默认值"，
  就会产生第二套事实，设备端行为与 steps.json 声明不一致。

两类问题
────────
· error   —— 下发后一定不可用（缺必填字段、取值越界、互斥字段同时出现、
             host 无 env、出现 scheme 等），直接 fail-fast，绝不静默过滤。
· warning —— 可能可用但不符合推荐用法（未注册 type、单例重复、
             signin 晚于环境切换等），只打印不阻断。

职责边界：`scheme`（落地跳转）不属于可测性配置，必须由 `env.scheme` +
`steps[0]` 的 `open-url` 表达；放进 testability 会让 B2 先跳一次、step 再跳一次。

为什么必须前置校验：`push_testability_scheme` 是**整表**下发，任何一条 action
结构错误都会让 SDK 在该条上失败，登录态 / 锁包 / 上报可能全部落空——等到 B2 下发
甚至设备执行时才暴露，代价是一整台模拟器 + 一轮前置流程。
"""

import json

from aitest.shared.errors import ConfigError


class TestabilityValidationError(ConfigError):
    """可测性 action 列表校验失败。category=env（配置问题，非脚本缺陷）。"""

    code = "TESTABILITY_CONFIG_INVALID"


# ═══════════════════════════════════════════════════════════════════
# 注册表（与 actions.json 对齐）
# ═══════════════════════════════════════════════════════════════════

# 已注册的 action type：未登记的类型只告警不阻断（平台会持续新增 action）。
_KNOWN_TYPES = frozenset({
    "mock", "mockpicasso", "mockbabel", "mockh5", "mockshark", "mockScanResult",
    "remote_ws", "scheme", "closecomet", "env", "host", "reportresult",
    "testability_report", "getstoragereport", "setstoragereport", "mrnenv",
    "mrnbundle", "machbundle", "reccebundle", "picassobundle", "horn", "hornreset",
    "abtest", "knbstorage", "maxstorage", "msistorage", "testability_location",
    "signin", "signout", "kdbsignin", "klsignin", "privacymode", "clearCache",
    "lockmmp", "hideH5FootBar", "setPikeEnv", "getPublish", "sendPublish",
    "trafficReport", "set4GNetwork", "duoconfig", "immessage", "language",
    "translation", "set_cookie", "set_local_storage", "web_start_configs",
    "test_cases", "cipstorage", "kdbgeneraljump", "knbBridge", "merchantPoi",
    "modifyRequestHeader", "openVQAReport", "graytest", "htptest", "request",
    "domino", "envsakhorn", "hotelstorage", "im_api_env", "im_sdk_env", "lockmsc",
    "mmp_package", "urllock", "set_local_city", "switch_local_scene", "delay",
    "fedoai", "opendebug", "removedebugicon", "reportClickArea",
})

# 同一份配置里只允许出现一次（出现两次时 SDK 执行顺序未定义，结果不可预期）。
_SINGLETON_TYPES = frozenset({
    "signin", "signout", "kdbsignin", "klsignin", "env",
    "mock", "mockpicasso", "mockbabel", "mockh5", "mockshark", "mockScanResult",
    "remote_ws", "closecomet", "reportresult", "testability_report",
    "getstoragereport", "setstoragereport", "mrnenv", "hornreset", "language",
    "translation", "privacymode", "clearCache", "lockmmp", "hideH5FootBar",
    "set4GNetwork", "setPikeEnv", "trafficReport", "duoconfig", "delay", "fedoai",
    "testability_location", "hotelstorage", "im_api_env", "im_sdk_env",
    "switch_local_scene", "set_local_city", "domino", "openVQAReport",
})

# info.value 必须是 0/1（含布尔）的开关类 action。
_BOOL01_VALUE_TYPES = frozenset({
    "closecomet", "reportresult", "getstoragereport", "setstoragereport",
    "privacymode", "clearCache", "lockmmp", "hideH5FootBar", "trafficReport",
    "set4GNetwork", "hornreset", "translation", "graytest", "htptest",
    "envsakhorn", "opendebug", "removedebugicon", "getPublish",
})

# info.value 的整数区间（闭区间）。
_INT_RANGE_VALUE = {
    "mrnenv": (0, 3),        # 0 Production / 1 Test / 2 Staging / 3 LocalServer
    "language": (0, 3),      # 简中 / 英 / 日 / 韩
    "setPikeEnv": (1, 4),    # 1 开 beta / 2 关 beta / 3 开 stage / 4 关 stage
}

# 必填字符串字段（空串等同于缺失）。
_REQUIRED_FIELDS = {
    "mock": ("value",),
    "mockpicasso": ("value",),
    "mockbabel": ("value",),
    "mockh5": ("value",),
    "mockshark": ("value",),
    "mockScanResult": ("value",),
    "remote_ws": ("value",),
    "kdbgeneraljump": ("value",),
    "set_local_city": ("value",),
    "hotelstorage": ("value",),
    "env": ("envId",),
    "host": ("produrl", "url"),
    "picassobundle": ("bundleName", "bundleVersion"),
    "knbstorage": ("key",),
    "maxstorage": ("key",),
    "msistorage": ("key",),
    "duoconfig": ("pageId", "protocolId", "version"),
    "sendPublish": ("key", "value"),
    "request": ("url",),
    "urllock": ("url", "newUrl"),
    "knbBridge": ("knbBridgeName", "key", "callbacks"),
    "modifyRequestHeader": ("key", "value", "url"),
    "set_cookie": ("name", "value"),
    "set_local_storage": ("name", "value"),
    "im_api_env": ("env",),
    "im_sdk_env": ("env",),
    "klsignin": ("klaccount", "klpassword"),
    "mmp_package": ("mmpEnv",),
}


# ═══════════════════════════════════════════════════════════════════
# 基础工具
# ═══════════════════════════════════════════════════════════════════

def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_number(value):
    """宽松取数：接受 int / 布尔 / 数字字符串；非法返回 None。"""
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _to_int(value):
    number = _to_number(value)
    if number is None or not float(number).is_integer():
        return None
    return int(number)


def _to_bool01(value):
    """0/1 语义归一：True→1，False→0，其他非法返回 None。"""
    number = _to_int(value)
    return number if number in (0, 1) else None


def _env_code(value) -> str:
    """环境类型归一（唯一事实来源：`env_validator.normalize_env_type`）。"""
    from aitest.provisioning.validators.env_validator import normalize_env_type
    return normalize_env_type(value)


def _require(info: dict, key: str, where: str, errors: list) -> None:
    if _is_blank(info.get(key)):
        errors.append(f"{where}: 缺少必填字段 info.{key}")


def _require_bool01(info: dict, key: str, where: str, errors: list) -> None:
    if _is_blank(info.get(key)):
        errors.append(f"{where}: 缺少必填字段 info.{key}（0/1）")
    elif _to_bool01(info.get(key)) is None:
        errors.append(f"{where}: info.{key} 只能是 0/1，实际 {info.get(key)!r}")


def _optional_bool01(info: dict, key: str, where: str, errors: list) -> None:
    if info.get(key) is not None and _to_bool01(info.get(key)) is None:
        errors.append(f"{where}: info.{key} 只能是 0/1，实际 {info.get(key)!r}")


# ═══════════════════════════════════════════════════════════════════
# 单条 action 校验
# ═══════════════════════════════════════════════════════════════════

def _check_meta(action: dict, where: str, errors: list) -> None:
    for key in ("index", "priority"):
        if action.get(key) is not None and _to_int(action[key]) is None:
            errors.append(f"{where}: {key} 必须是整数，实际 {action[key]!r}")
    for key in ("serial", "disabled"):
        if action.get(key) is not None and not isinstance(action[key], bool):
            errors.append(f"{where}: {key} 必须是布尔值，实际 {action[key]!r}")
    if action.get("desc") is not None and not isinstance(action["desc"], str):
        errors.append(f"{where}: desc 必须是字符串")


def _check_value_fields(action_type: str, info: dict, where: str, errors: list) -> None:
    if action_type in _BOOL01_VALUE_TYPES:
        _require_bool01(info, "value", where, errors)
        return
    if action_type in _INT_RANGE_VALUE:
        low, high = _INT_RANGE_VALUE[action_type]
        number = _to_int(info.get("value"))
        if number is None:
            errors.append(f"{where}: 缺少 info.value（{low}~{high}）")
        elif not low <= number <= high:
            errors.append(f"{where}: info.value={number} 越界，只允许 {low}~{high}")
        return
    for key in _REQUIRED_FIELDS.get(action_type, ()):
        _require(info, key, where, errors)


def _check_signin(info: dict, where: str, errors: list) -> None:
    _require(info, "account", where, errors)
    if _to_int(info.get("loginType", 0)) == 1:
        pass  # SSO 登录不需要密码
    else:
        _require(info, "password", where, errors)
    if info.get("signin") is not None and not info.get("signin"):
        errors.append(f"{where}: signin.signin 为假值，登录不会执行")
    if info.get("countryCode") is not None and _to_int(info.get("countryCode")) is None:
        errors.append(f"{where}: signin.countryCode 必须是数字串，实际 {info.get('countryCode')!r}")


def _check_bundles(action_type: str, info: dict, where: str, errors: list) -> None:
    _optional_bool01(info, "isStage", where, errors)
    _require(info, "bundleName", where, errors)
    if action_type == "reccebundle":
        # recce 允许锁「最新包」：bundleVersion 必须显式给出（可为空串）
        if "bundleVersion" not in info:
            errors.append(f"{where}: reccebundle 需要 bundleVersion（锁最新包时显式填空串）")
    else:
        _require(info, "bundleVersion", where, errors)


def _check_horn(info: dict, where: str, errors: list) -> None:
    for key in ("config", "key", "strategy"):
        _require(info, key, where, errors)
    value_type = info.get("valueActualType")
    if isinstance(value_type, dict):
        errors.append(f"{where}: horn.valueActualType 必须是字符串（int/boolean/string/array/json）")
    elif not _is_blank(value_type) and str(value_type) not in {"int", "boolean", "string", "array", "json"}:
        errors.append(
            f"{where}: horn.valueActualType={value_type!r} 不在 int/boolean/string/array/json"
        )
    _optional_bool01(info, "isForceMock", where, errors)
    _optional_bool01(info, "reset", where, errors)


def _check_abtest(info: dict, where: str, errors: list) -> None:
    _require(info, "abTestKey", where, errors)
    strategy = str(info.get("strategy") or "").strip()
    if not strategy:
        errors.append(f"{where}: 缺少必填字段 info.strategy")
        return
    is_meituan = len(strategy) == 1 and strategy.isalpha() and strategy.islower()
    is_dianping = (
        len(strategy) == 3
        and strategy.startswith("s_")
        and strategy[2].isalpha()
        and strategy[2].islower()
    )
    if not (is_meituan or is_dianping):
        errors.append(f"{where}: abtest.strategy 只能是 a-z（美团）或 s_a-s_z（点评），实际 {strategy!r}")


def _check_location(info: dict, where: str, errors: list) -> None:
    _require_bool01(info, "open", where, errors)
    if _to_bool01(info.get("open")) != 1:
        return
    has_city = not _is_blank(info.get("cityName"))
    has_geo = not _is_blank(info.get("latitude")) and not _is_blank(info.get("longitude"))
    if not (has_city or has_geo):
        errors.append(f"{where}: 开启定位需要 cityName 或 latitude+longitude")
    if has_geo:
        lat = _to_number(info.get("latitude"))
        lng = _to_number(info.get("longitude"))
        if lat is None or not -90 <= lat <= 90:
            errors.append(f"{where}: latitude={info.get('latitude')!r} 非法（-90~90）")
        if lng is None or not -180 <= lng <= 180:
            errors.append(f"{where}: longitude={info.get('longitude')!r} 非法（-180~180）")


def _check_immessage(info: dict, where: str, errors: list) -> None:
    value = _to_int(info.get("value"))
    if value is None or not 0 <= value <= 3:
        errors.append(f"{where}: immessage.value 只能是 0~3，实际 {info.get('value')!r}")
    elif value != 0 and not isinstance(info.get("data"), dict):
        errors.append(f"{where}: immessage.data 必须是对象（value={value} 需要消息内容）")


def _check_send_publish(info: dict, where: str, errors: list) -> None:
    value = info.get("value")
    if isinstance(value, (dict, list)):
        return
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}: sendPublish.value 必须是 JSON 字符串")
        return
    try:
        json.loads(value)
    except json.JSONDecodeError:
        errors.append(f"{where}: sendPublish.value 不是合法 JSON")


def _check_lockmsc(info: dict, where: str, errors: list) -> None:
    version = str(info.get("version") or "").strip()
    app_id = str(info.get("appId") or "").strip()
    build_id = str(info.get("buildId") or "").strip()
    if version and (app_id or build_id):
        errors.append(f"{where}: lockmsc.version 与 appId/buildId 互斥")
    elif not version and not (app_id and build_id):
        errors.append(f"{where}: lockmsc 需要 version（基础包）或 appId+buildId（业务包）")


def _check_mmp(info: dict, where: str, errors: list) -> None:
    env = str(info.get("mmpEnv") or "").strip().lower()
    if env not in ("prod", "test", "stage"):
        errors.append(f"{where}: mmp_package.mmpEnv 只能是 prod/test/stage，实际 {info.get('mmpEnv')!r}")
    if _is_blank(info.get("mmpVersionId")) and _is_blank(info.get("mmp_urlScheme")):
        errors.append(f"{where}: mmp_package 需要 mmpVersionId 或 mmp_urlScheme")


def _check_cipstorage(info: dict, where: str, errors: list) -> None:
    for key in ("channel", "key", "value", "type", "level", "user"):
        _require(info, key, where, errors)
    if _to_int(info.get("type")) not in (0, 1, 2):
        errors.append(f"{where}: cipstorage.type 只能是 0/1/2，实际 {info.get('type')!r}")
    if _to_int(info.get("level")) not in (0, 1, 2, 3):
        errors.append(f"{where}: cipstorage.level 只能是 0~3，实际 {info.get('level')!r}")
    if _to_bool01(info.get("user")) is None:
        errors.append(f"{where}: cipstorage.user 只能是 0/1，实际 {info.get('user')!r}")


def _check_test_cases(info: dict, where: str, errors: list) -> None:
    cases = info.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append(f"{where}: test_cases.cases 必须是非空数组")
        return
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"{where}: cases[{index}] 必须是对象")
            continue
        for key in ("case_name", "case_info"):
            if _is_blank(case.get(key)):
                errors.append(f"{where}: cases[{index}] 缺少 {key}")


_SPECIAL_CHECKS = {
    "signin": _check_signin,
    "horn": _check_horn,
    "abtest": _check_abtest,
    "testability_location": _check_location,
    "immessage": _check_immessage,
    "sendPublish": _check_send_publish,
    "lockmsc": _check_lockmsc,
    "mmp_package": _check_mmp,
    "cipstorage": _check_cipstorage,
    "test_cases": _check_test_cases,
}


def _check_fields(action_type: str, info: dict, where: str, errors: list) -> None:
    if action_type == "scheme":
        errors.append(
            f"{where}: 可测性配置里不能包含 scheme（落地跳转必须由 steps[0] 的 open-url 表达，"
            "否则 B2 会提前跳转、step 再跳一次）"
        )
        return
    if action_type in ("mrnbundle", "machbundle", "reccebundle"):
        _check_bundles(action_type, info, where, errors)
    elif action_type == "host":
        url = str(info.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            errors.append(f"{where}: host.url 必须是 http(s):// 地址，实际 {url!r}")
    elif action_type in ("mock", "mockpicasso", "mockbabel", "mockh5", "mockshark"):
        value = str(info.get("value") or "").strip()
        if value and "{{" not in value and not value.startswith(("http://", "https://")):
            errors.append(f"{where}: {action_type}.value 必须是 http(s):// 地址或模板，实际 {value!r}")
    elif action_type == "knbstorage":
        if info.get("level") is not None and _to_int(info.get("level")) not in (0, 1):
            errors.append(f"{where}: knbstorage.level 只能是 0/1，实际 {info.get('level')!r}")
    elif action_type == "testability_report":
        _require_bool01(info, "open", where, errors)
    elif action_type == "openVQAReport":
        _require_bool01(info, "open", where, errors)
        if info.get("vqaUploadScore") is not None:
            score = _to_int(info.get("vqaUploadScore"))
            if score is None or not 0 <= score <= 100:
                errors.append(f"{where}: vqaUploadScore 必须是 0~100 的整数，实际 {info.get('vqaUploadScore')!r}")
    elif action_type == "delay":
        time_value = _to_int(info.get("time"))
        if time_value is None or time_value < 0:
            errors.append(f"{where}: delay.time 必须是非负整数（毫秒），实际 {info.get('time')!r}")
    elif action_type == "domino":
        if _is_blank(info.get("value")):
            errors.append(f"{where}: domino.value 不能为空")
        if str(info.get("type") or "") != "bindId":
            errors.append(f"{where}: domino.type 必须是 bindId，实际 {info.get('type')!r}")
    elif action_type == "merchantPoi":
        if _is_blank(info.get("poiId")) and _is_blank(info.get("poiIdStr")):
            errors.append(f"{where}: merchantPoi 需要 poiId 或 poiIdStr")
    elif action_type == "fedoai":
        _optional_bool01(info, "floatingView", where, errors)
        if info.get("whitelist") is not None and not isinstance(info["whitelist"], str):
            errors.append(f"{where}: fedoai.whitelist 必须是字符串")
    else:
        checker = _SPECIAL_CHECKS.get(action_type)
        if checker:
            checker(info, where, errors)


def _check_env_capability(action_type: str, info: dict, env_type: str, where: str, errors: list) -> None:
    """与环境能力矩阵联动：ptest 类能力只在线上环境（A 基准 / P 泳道）可生效。"""
    if action_type != "htptest" or _to_bool01(info.get("value")) != 1:
        return
    env_code = _env_code(env_type)
    if env_code and env_code not in ("A", "P"):
        errors.append(
            f"{where}: htptest（住宿 ptest）仅线上环境（A 基准 / P 线上泳道）可用，当前环境 {env_code}；"
            "请改用场景 Mock 或切换到线上环境"
        )


# ═══════════════════════════════════════════════════════════════════
# 列表级校验
# ═══════════════════════════════════════════════════════════════════

def _check_duplicates(actions: list, errors: list, warnings: list) -> None:
    seen = {}
    for index, action in enumerate(actions):
        action_type = str(action.get("type") or "").strip()
        if action_type not in _SINGLETON_TYPES:
            continue
        if action_type in seen:
            first_index, first_info = seen[action_type]
            if first_info == (action.get("info") or {}):
                warnings.append(
                    f"可测性配置重复：{action_type} 出现两次且内容相同（第 {first_index + 1}、{index + 1} 条）"
                )
            else:
                errors.append(
                    f"可测性配置冲突：{action_type} 是单例，但第 {first_index + 1} 条与第 {index + 1} 条内容不同，"
                    "执行顺序未定义"
                )
        else:
            seen[action_type] = (index, action.get("info") or {})


def _check_pairs(actions: list, errors: list) -> None:
    types = {str(a.get("type") or "").strip() for a in actions}
    if "host" in types and "env" not in types:
        errors.append("可测性配置组合：host（域名映射）必须与 env（网络环境）同时使用")


def _check_order(actions: list, warnings: list) -> None:
    types = [str(a.get("type") or "").strip() for a in actions]
    if "signin" in types:
        signin_at = types.index("signin")
        earlier = [t for t in types[:signin_at] if t in ("env", "host", "im_api_env", "im_sdk_env")]
        if earlier:
            warnings.append(
                f"可测性配置顺序：signin 在 {', '.join(earlier)} 之后，登录可能命中错误环境；建议先登录再切环境"
            )


def _check_indexes(actions: list, errors: list) -> None:
    seen = {}
    for index, action in enumerate(actions):
        value = _to_int(action.get("index"))
        if value is None:
            continue
        if value in seen:
            errors.append(f"可测性配置 index 重复：第 {seen[value] + 1} 条与第 {index + 1} 条都是 {value}")
        else:
            seen[value] = index


def validate_testability(configs, env_type=None) -> list:
    """校验 Pillow 可测性 action 列表，返回 warning 列表；error 直接抛异常。

    Args:
        configs: `env.testability` 原始列表（steps.json / CASES case env）。
        env_type: 场景环境类型（A/P/B/C/E/D 或 online/online_ptest/swimline/alpha/urlmapping/noop），用于
            能力适用性判断（如 htptest 仅 A/P）。缺省时跳过该类校验。

    Raises:
        TestabilityValidationError: 存在任一 error；message 汇总前 20 条，
            detail 保留完整清单。
    """
    if configs is None or configs == []:
        return []
    if not isinstance(configs, list):
        raise TestabilityValidationError(
            f"env.testability 必须是数组（Pillow action 列表），实际 {type(configs).__name__}"
        )

    errors, warnings = [], []
    actions = []
    for index, action in enumerate(configs):
        where = f"testability[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{where}: 必须是对象 {{type, info, ...}}，实际 {type(action).__name__}")
            continue
        action_type = str(action.get("type") or "").strip()
        if not action_type:
            errors.append(f"{where}: 缺少 type")
            continue

        info = action.get("info")
        if info is None:
            info = {}
        elif not isinstance(info, dict):
            errors.append(f"{where}: info 必须是对象，实际 {type(info).__name__}")
            continue

        actions.append(action)
        if action_type not in _KNOWN_TYPES:
            warnings.append(f"{where}: type={action_type!r} 未在可测性 action 注册表中，按原样下发")

        _check_meta(action, where, errors)
        _check_value_fields(action_type, info, where, errors)
        _check_fields(action_type, info, where, errors)
        _check_env_capability(action_type, info, env_type, where, errors)

    if actions:
        _check_duplicates(actions, errors, warnings)
        _check_pairs(actions, errors)
        _check_indexes(actions, errors)
        _check_order(actions, warnings)

    if errors:
        raise TestabilityValidationError(
            "可测性配置校验失败（下发后不可用，已阻断）",
            detail="\n".join(errors[:20]) + ("\n…" if len(errors) > 20 else ""),
        )
    return warnings
