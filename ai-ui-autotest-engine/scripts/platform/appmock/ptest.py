#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ptest mock 生命周期管理。

ptest 是「线上环境(A) + 一个 partMock 规则」：在 AppMock 服务端创建/复用一个
partMock 规则，为请求注入 isPtest/isGreyTest/isDevBundle 参数与 ptest UA 头，
并推送 htptest debugconfig 到设备开启 HTTP 测试通道。

两条硬约束（均按最佳方案实现，非补丁）：

1. **适用环境受限**：仅线上环境(A)允许开启（唯一事实来源
   `provisioning/validators/env_validator.ENV_CAPABILITIES`），采集/校验/执行
   三层统一门控。
2. **不得遮蔽场景 Mock**：AppMock 对同一请求**命中即短路**，ptest 的全量 partMock
   规则（`/.*?$`）会抢在场景响应型 Mock（如 preview）之前命中，导致场景 Mock 不
   生效（历史事故：alpha 环境 preview 未 Mock → 提单页「售罄」）。因此本模块按
   「场景 Mock 的 URI 规则」生成**负向前瞻排除**规则，两类规则即可共存。

生命周期（启用/停用对称）：
  enable_ptest_mock(mis, exclude_rules)  — 落地/复用规则 + 开启 + 存 mockId + push htptest(1)
  disable_ptest_mock(mis)                — 关闭规则 + 清除 mockId + 回滚 htptest(0)
"""
import hashlib
import json

from platform.appmock.rules import appmock_create, appmock_on, appmock_off
from platform.appmock.ops import (
    save_ptest_mock_id, load_ptest_mock_id, clear_ptest_mock_id,
    push_testability_scheme,
)
from shared.errors import MockError


# ptest 无排除项时的规则 = 全量 partMock（给所有请求注入参数 + UA）
_PTEST_RULE_MATCH_ALL = "/.*?$"
_PTEST_MOCK_TYPE = 1
_PTEST_RESPONSE_BODY = ""
_PTEST_REQUEST_HEADER = json.dumps({"user-agent": "mtdp-infosec/scan1.0_dTSg9uAN"}, indent=4)
_PTEST_REQUEST_PARAM = json.dumps(
    {"isPtest": True, "isGreyTest": True, "isDevBundle": 1}, indent=4
)

# 规则 desc：既是说明，也是平台「命中复用」的 key（同 rule 不同 desc 会被当成新规则）。
# 前缀必须稳定；不同排除集用指纹后缀区分——既保证同集合复用同一条规则（不无限新建），
# 又让规则语义可追溯。
_PTEST_DESC_PREFIX = (
    "[ai-ui-autotest-engine-ptest] "
    "请求注入 isPtest/isGreyTest/isDevBundle 参数 + ptest UA 头"
)

# 示例 URL：addMockConfig 带 exampleUrl 时正则 rule 也受理（平台据此校验正则是否命中）。
# 必须落在「仍受 ptest 覆盖」的路径上（不得命中排除集）。
_PTEST_EXAMPLE_URL = "/mapi/autotest-ptest-example.bin"


def _normalize_patterns(exclude_rules) -> list:
    """规整场景 Mock 的 URI 规则（去空、去重、保序）。"""
    out = []
    for rule in (exclude_rules or ()):
        rule = str(rule or "").strip()
        if rule and rule not in out:
            out.append(rule)
    return out


def build_ptest_rule(exclude_rules=()) -> str:
    """构造 ptest 的 URI 规则。

    无排除项 → 全量匹配 `/.*?$`；有排除项 → 负向前瞻排除这些场景 Mock 路径，
    使被 Mock 的接口不再被 ptest 抢先命中（否则场景 Mock 静默失效）。
    """
    patterns = _normalize_patterns(exclude_rules)
    if not patterns:
        return _PTEST_RULE_MATCH_ALL
    alts = "|".join(patterns)
    return f"^(?!.*(?:{alts})).*$"


def build_ptest_desc(exclude_rules=()) -> str:
    """构造 ptest 规则 desc（平台命中复用的 key；排除集不同则指纹不同）。"""
    patterns = _normalize_patterns(exclude_rules)
    if not patterns:
        return _PTEST_DESC_PREFIX
    fingerprint = hashlib.md5("|".join(sorted(patterns)).encode("utf-8")).hexdigest()[:8]
    return f"{_PTEST_DESC_PREFIX}（排除场景 Mock 路径 {fingerprint}）"


def _ptest_rule_kwargs(exclude_rules=()) -> dict:
    """构造 ptest 规则的创建参数（desc 是平台命中复用的 key 之一）。"""
    return dict(
        rule=build_ptest_rule(exclude_rules),
        response_body=_PTEST_RESPONSE_BODY,
        desc=build_ptest_desc(exclude_rules),
        status=1,
        mock_type=_PTEST_MOCK_TYPE,
        request_header=_PTEST_REQUEST_HEADER,
        request_param=_PTEST_REQUEST_PARAM,
        example_url=_PTEST_EXAMPLE_URL,
    )


def _resolve_ptest_mock_id(mis: str, exclude_rules=()) -> str:
    """解析（必要时落地）ptest 规则，返回 mockId。

    携带 example_url 走 addMockConfig 一步建规则：平台对同 (rule, desc) 重复提交
    直接返回既有 mockId，不新建，故本函数天然幂等。

    Raises:
        MockError: 拿不到 mockId
    """
    result = appmock_create(mis=mis, **_ptest_rule_kwargs(exclude_rules))
    mock_id = result.get("mockId")
    if not mock_id:
        raise MockError(f"ptest partMock 规则落地失败: {result.get('error', '')}")
    return mock_id


def enable_ptest_mock(mis: str, exclude_rules=()) -> str:
    """确保 ptest 规则存在并开启，同时推送 htptest 设备配置。

    Args:
        mis: 用户 MIS 号
        exclude_rules: 需要避开的场景 Mock URI 规则（负数前瞻排除），避免 ptest
                       的全量规则遮蔽场景响应型 Mock。

    Returns:
        生效的 ptest 规则 mockId

    Raises:
        MockError: 规则落地/开启或 htptest 推送任一失败
    """
    patterns = _normalize_patterns(exclude_rules)
    if patterns:
        print(f"[ptest-mock] 排除场景 Mock 路径 {len(patterns)} 条（避免命中短路遮蔽）")
    print("[ptest-mock] 配置 ptest partMock 规则...")
    mock_id = _resolve_ptest_mock_id(mis, patterns)

    if not appmock_on(mock_id):
        raise MockError(f"ptest 规则开启失败: mockId={mock_id}")
    save_ptest_mock_id(mock_id)

    # 推送 htptest 设备配置（HTTP 测试通道开关，独立于登录的可测性配置）
    ok, _, detail = push_testability_scheme(
        [{"type": "htptest", "info": {"value": 1}}],
        verify=True, verify_wait=3.0,
    )
    if not ok:
        raise MockError(f"htptest 设备配置推送失败: {detail}")

    print(f"[ptest-mock] ✅ ptest partMock 规则已启用 "
          f"(mockId={mock_id}, rule={build_ptest_rule(patterns)})")
    return mock_id


def disable_ptest_mock(mis: str = None) -> bool:
    """关闭已记录的 ptest partMock 规则并**对称回滚**设备侧 htptest 开关。

    Returns:
        True 规则已关闭 / False 无记录或关闭失败（htptest 回滚为 best-effort，
        不影响返回值——其内部已自兜底，不抛异常）。
    """
    mock_id = load_ptest_mock_id()
    rule_off = False
    if mock_id:
        rule_off = appmock_off(mock_id, mis=mis)
        clear_ptest_mock_id()
        print(f"[ptest-mock] {'✅' if rule_off else '⚠️'} ptest 规则已关闭 (mockId={mock_id})")
    else:
        print("[ptest-mock] 无已记录的 ptest 规则，跳过规则关闭")

    # 启用时 push htptest=1，停用时对称 push 0（避免设备侧开关残留）
    ok, _, detail = push_testability_scheme(
        [{"type": "htptest", "info": {"value": 0}}], verify=False,
    )
    if ok:
        print("[ptest-mock] ✅ htptest 设备开关已回滚")
    else:
        print(f"[ptest-mock] ⚠️ htptest 回滚未生效: {detail or '推送失败'}")
    return rule_off
