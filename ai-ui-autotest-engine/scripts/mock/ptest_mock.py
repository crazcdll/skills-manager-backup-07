#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ptest mock 生命周期管理 —— 独立的测试开关，不隶属于任何环境类型。

ptest 不是一种环境类型，而是「线上环境 + 一个 partMock 规则」：在 AppMock
服务端创建/复用一个全量 partMock 规则（/.*?$），为所有请求注入
isPtest/isGreyTest/isDevBundle 参数与 ptest UA 头，并推送 htptest
debugconfig 到设备开启 HTTP 测试通道。

生命周期：
  enable_ptest_mock(mis)  — 创建/复用规则 + 开启 + 保存 mockId + 推送 htptest
  disable_ptest_mock(mis) — 关闭规则 + 清除 mockId（供 reset-env / T2 收尾调用）

与登录完全解耦：只依赖 AppMock SDK 启用（env-prepare Step 2），可与任意
登录方式（A 凭证 / B 验证码 / C 验证码 / D 免登录）自由组合。
"""
import json

from mock.appmock_rules import (
    NON_LITERAL_RULE_ERROR,
    appmock_create, appmock_on, appmock_off, appmock_provision_rule, appmock_update,
)
from mock.appmock_ops import (
    save_ptest_mock_id, load_ptest_mock_id, clear_ptest_mock_id,
    push_testability_scheme,
)
from core.errors import MockError


# ptest 规则 = 全量 partMock 规则：给所有请求注入 isPtest/isGreyTest/isDevBundle + ptest UA
_PTEST_RULE = "/.*?$"
_PTEST_MOCK_TYPE = 1
_PTEST_RESPONSE_BODY = ""
_PTEST_REQUEST_HEADER = json.dumps({"user-agent": "mtdp-infosec/scan1.0_dTSg9uAN"}, indent=4)
_PTEST_REQUEST_PARAM = json.dumps(
    {"isPtest": True, "isGreyTest": True, "isDevBundle": 1}, indent=4
)

# 当前 desc：既是规则说明，也是平台「命中复用」的 key 之一
# （同 rule 不同 desc 会被平台当成新规则，从而走新建通道）
_PTEST_DESC_PREFIX = "[ai-ui-autotest-engine-ptest]"
_PTEST_DESC = f"{_PTEST_DESC_PREFIX} 所有请求注入 isPtest/isGreyTest/isDevBundle 参数 + ptest UA 头"

# 历史 skill 名（hotel-ui-autotest）时期建下的规则用的是这个 desc：作为复用兜底，
# 命中后会把 desc 迁移到当前前缀，之后直接命中当前 desc。
_PTEST_DESC_LEGACY = (
    "[hotel-ui-autotest-ptest] 所有请求注入 isPtest/isGreyTest/isDevBundle 参数 + ptest UA 头"
)

# 占位字面规则：平台 addMockConfig 的新建通道只受理字面路径，正则规则必须先建后改
# （见 appmock_rules.appmock_provision_rule）。名字必须稳定，否则每次运行都会新建规则。
_PTEST_BOOTSTRAP_RULE = "/autotest-ptest-bootstrap$"


def _ptest_rule_kwargs(desc: str, rule: str = _PTEST_RULE) -> dict:
    """构造 ptest 规则的创建/更新参数（desc 不同即被平台视为不同规则）。"""
    return dict(
        rule=rule, response_body=_PTEST_RESPONSE_BODY, desc=desc, status=1,
        mock_type=_PTEST_MOCK_TYPE,
        request_header=_PTEST_REQUEST_HEADER,
        request_param=_PTEST_REQUEST_PARAM,
    )


def _bootstrap_failure_message(detail: str) -> str:
    """把平台原始报错翻译成可执行的结论。"""
    base = "ptest partMock 规则落地失败"
    if NON_LITERAL_RULE_ERROR in (detail or ""):
        return (
            f"{base}：平台拒绝该匹配规则（{detail}）。已依次尝试"
            "「复用当前 desc / 复用历史 desc / 字面占位规则 + updateMockConfig」三条路径仍失败，"
            "请拿账号信息找 AppMock 平台确认规则通道是否收紧。"
        )
    return f"{base}: {detail}"


def _resolve_ptest_mock_id(mis: str) -> tuple:
    """解析（必要时落地）ptest 规则，返回 (mockId, 来源说明)。

    顺序固定、全程幂等，用户首次执行也能落地：

      1. 用当前 desc 提交 `rule=/.*?$` —— 平台对同 (rule, desc) 重复提交是幂等的，
         命中既有规则时直接返回旧 mockId，不新建、不做格式校验；
      2. 用历史 desc 再试一次（老 skill 时期建的规则），命中后把 desc 迁移到当前前缀；
      3. 两条都没命中（账号下还没有 ptest 规则）→ 两步落地：
         先建稳定占位字面规则，再 `updateMockConfig` 把 rule 改成 `/.*?$`。

    Raises:
        RuntimeError: 三条路径都拿不到 mockId
    """
    for desc, source in (
        (_PTEST_DESC, "复用当前规则"),
        (_PTEST_DESC_LEGACY, "复用历史规则"),
    ):
        result = appmock_create(mis=mis, **_ptest_rule_kwargs(desc))
        mock_id = result.get("mockId")
        if not mock_id:
            continue
        if desc != _PTEST_DESC:
            # desc 迁移：否则后续每轮都只能靠「历史 desc」这一支命中，
            # 且人工在平台上无法从 desc 辨认规则归属。
            if appmock_update(
                mock_id=mock_id, rule=_PTEST_RULE, desc=_PTEST_DESC,
                request_header=_PTEST_REQUEST_HEADER,
                request_param=_PTEST_REQUEST_PARAM,
                mock_type=_PTEST_MOCK_TYPE,
            ):
                source = "复用历史规则并迁移 desc"
            else:
                print(f"[ptest-mock] ⚠️ 历史规则 desc 迁移失败（不影响本次执行）mockId={mock_id}")
        return mock_id, source

    result = appmock_provision_rule(
        rule=_PTEST_RULE, desc=_PTEST_DESC, placeholder_rule=_PTEST_BOOTSTRAP_RULE,
        response_body=_PTEST_RESPONSE_BODY, mis=mis, status=1,
        request_header=_PTEST_REQUEST_HEADER, request_param=_PTEST_REQUEST_PARAM,
        mock_type=_PTEST_MOCK_TYPE,
    )
    mock_id = result.get("mockId")
    if not mock_id:
        raise MockError(_bootstrap_failure_message(result.get("error", "")))
    return mock_id, "首次落地"


def enable_ptest_mock(mis: str) -> str:
    """确保 ptest 规则存在并开启，同时推送 htptest 设备配置。

    首次执行（账号下还没有 ptest 规则）同样能落地，见 _resolve_ptest_mock_id。

    Args:
        mis: 用户 MIS 号

    Returns:
        生效的 ptest 规则 mockId

    Raises:
        MockError: 规则落地/开启或 htptest 推送任一失败
    """
    print("[ptest-mock] 配置 ptest partMock 规则...")
    mock_id, source = _resolve_ptest_mock_id(mis)

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

    print(f"[ptest-mock] ✅ ptest partMock 规则已启用 (mockId={mock_id}, {source})")
    return mock_id


def disable_ptest_mock(mis: str = None) -> bool:
    """关闭已记录的 ptest partMock 规则并清除记录。

    Args:
        mis: 用户 MIS 号（fallback 时使用，默认自动获取）

    Returns:
        True 已关闭 / False 无记录或关闭失败
    """
    mock_id = load_ptest_mock_id()
    if not mock_id:
        print("[ptest-mock] 无已记录的 ptest 规则，跳过")
        return False
    ok = appmock_off(mock_id, mis=mis)
    clear_ptest_mock_id()
    if ok:
        print(f"[ptest-mock] ✅ ptest 规则已关闭 (mockId={mock_id})")
    else:
        print(f"[ptest-mock] ⚠️ ptest 规则关闭失败 (mockId={mock_id})")
    return ok
