#!/usr/bin/env python3
"""
路由基础数据类与共享逻辑

InfraContext  携带基础实体四元组
PublicPhase   P1（新建路径：固定等60s+轮询查合同）→ P2（其他路径查合同）→ P3（建合同）→ P4（建房型）
"""

import sys
import time
from dataclasses import dataclass
from typing import Optional

from hotel_testdata_cli.scripts.runner import StepError
from hotel_testdata_cli.infra import (
    query_contract,
    create_contract,
    create_room,
    _query_contract_no_via_tool465,
    _query_contracts_by_partner,
    _extract_contract_basic_info,
)

# 供应商创建后固定等待时长（秒）
_PARTNER_FIXED_WAIT_SEC = 60
# 固定等待后，轮询查合同的最大时长（秒）
_CONTRACT_POLL_TIMEOUT_SEC = 60
# 轮询间隔（秒）
_CONTRACT_POLL_INTERVAL_SEC = 10


@dataclass
class InfraContext:
    """四路汇聚后的基础实体上下文"""
    partner_id: str = ""
    poi_id: str = ""
    contract_no: str = ""           # 字符串，如 ZSFW-A9-24044462
    platform_contract_id: str = ""  # 数字型，套餐上单需要
    room_info_id: str = ""          # 逻辑房型ID
    real_room_id: str = ""
    room_name: str = ""
    from_path_a_new: bool = False   # 路径A/C 新建供应商时需要等待
    need_save_pool: bool = False    # 新建路径完成后需要存入数据池（由 fullday 在 goods 创建后执行）


def _poll_query_contract(
    partner_id: str,
    platform_contract_id: str,
    swimlane: str,
    dry_run: bool,
    timeout_sec: int = _CONTRACT_POLL_TIMEOUT_SEC,
    interval_sec: int = _CONTRACT_POLL_INTERVAL_SEC,
) -> dict:
    """
    轮询查询合同，直到查到或超时。
    两种方式都尝试（方式二优先：工具465；方式一：Thrift）。
    返回 {"contractNo": str, "contractId": str}，超时未查到返回 {}。
    """
    import math
    max_attempts = max(1, math.ceil(timeout_sec / interval_sec))
    for attempt in range(1, max_attempts + 1):
        # ── 方式二（工具465）───────────────────────────────────────────────
        if platform_contract_id and platform_contract_id not in ("", "0", "None", "null"):
            print(f"  📋 查合同（方式二：工具465 platformContractId={platform_contract_id}）... "
                  f"[{attempt}/{max_attempts}]")
            contract_no = _query_contract_no_via_tool465(
                platform_contract_id=platform_contract_id,
                dry_run=dry_run,
            )
            if contract_no:
                print(f"  ✅ 合同查询成功（方式二）contractNo={contract_no}")
                return {"contractNo": contract_no, "contractId": platform_contract_id}

        # ── 方式一（Thrift）───────────────────────────────────────────────
        print(f"  📋 查合同（方式一：Thrift partnerId={partner_id}）... [{attempt}/{max_attempts}]")
        try:
            resp = _query_contracts_by_partner(
                partner_id=partner_id,
                swimlane=swimlane,
                dry_run=dry_run,
            )
            if dry_run:
                return {}
            if resp.get("success") is True:
                basic = _extract_contract_basic_info(resp)
                if basic:
                    contract_no = basic.get("contractNum")
                    contract_id = basic.get("id") or basic.get("contractId")
                    if contract_no:
                        print(f"  ✅ 合同查询成功（方式一）contractNo={contract_no}")
                        return {"contractNo": contract_no, "contractId": str(contract_id or platform_contract_id)}
        except Exception as e:
            print(f"  ⚠️  方式一查询异常: {e}")

        if attempt < max_attempts:
            print(f"  ⏳ 暂无合同，{interval_sec}s 后重试...")
            time.sleep(interval_sec)

    print(f"  ⚠️  查合同超时（{timeout_sec}s），将尝试新建合同")
    return {}


def public_phase(
    ctx: InfraContext,
    need_contract: bool = True,     # 非房/超团 = False
    need_room: bool = True,         # 非房/超团按需 = False
    is_overseas: bool = False,
    room_type: int = 0,
    swimlane: str = "",
    dry_run: bool = False,
) -> InfraContext:
    """
    公共段 P1～P4。

    P1: 新建供应商后固定等待 60s，随后轮询查合同（最多再等 60s）
    P2: 查合同（两种方式轮询，已在 P1 等待时完成）/ 非新建路径直接查一次
    P3: 无合同时新建合同（带重试）
    P4: 创建房型
    """

    # ── P1：新建供应商后等待就绪并查合同 ────────────────────────────────────────
    if ctx.from_path_a_new and need_contract and not ctx.contract_no:
        print(f"\n⏳ [P1] 供应商创建中，等待 {_PARTNER_FIXED_WAIT_SEC}s 后查合同...")
        if not dry_run:
            # 固定等待 60s（供应商异步初始化）
            for remaining in range(_PARTNER_FIXED_WAIT_SEC, 0, -10):
                print(f"  ⏳ 还需等待 {remaining}s ...")
                time.sleep(min(10, remaining))
            print(f"  ✅ 等待完成，开始查询合同...")
            # 轮询查合同（最多再等 60s）
            contract_info = _poll_query_contract(
                partner_id=ctx.partner_id,
                platform_contract_id=ctx.platform_contract_id,
                swimlane=swimlane,
                dry_run=dry_run,
            )
            if contract_info.get("contractNo"):
                ctx.contract_no = contract_info["contractNo"]
                ctx.platform_contract_id = str(contract_info.get("contractId") or ctx.platform_contract_id)
            # 未查到合同，走 P3 新建

    # ── P2：非新建路径，直接查一次合同 ──────────────────────────────────────────
    elif need_contract and not ctx.contract_no:
        print("\n📋 [P2] 查询供应商已有合同...")
        try:
            contract_info = query_contract(
                partner_id=ctx.partner_id,
                platform_contract_id=ctx.platform_contract_id,
                swimlane=swimlane,
                dry_run=dry_run,
            )
            ctx.contract_no = contract_info.get("contractNo") or ""
            ctx.platform_contract_id = str(contract_info.get("contractId") or ctx.platform_contract_id)
        except StepError as e:
            print(f"  ⚠️  查合同失败: {e.reason}，将尝试新建合同")

    # ── P3：无合同时新建合同 ─────────────────────────────────────────────────
    if need_contract and not ctx.contract_no:
        print("\n📝 [P3] 新建合同...")
        _contract_retry_keywords = ("价格模式切换", "切换流程", "创建纸质合同失败", "合同异常")
        _contract_max_retries = 6
        _contract_retry_interval = 15
        for _attempt in range(1, _contract_max_retries + 1):
            try:
                new_contract = create_contract(
                    partner_id=ctx.partner_id,
                    is_overseas=is_overseas,
                    dry_run=dry_run,
                )
                ctx.contract_no           = new_contract.get("contractNo") or ""
                ctx.platform_contract_id  = str(new_contract.get("platformContractId") or "")
                break
            except StepError as e:
                # 供应商异步初始化期间建合同会报"价格模式切换"，等待后重试
                if any(kw in e.reason for kw in _contract_retry_keywords) and _attempt < _contract_max_retries:
                    print(f"  ⚠️  供应商初始化未完成（{e.reason[:60]}...），{_contract_retry_interval}s 后重试"
                          f"（{_attempt}/{_contract_max_retries}）...")
                    if not dry_run:
                        time.sleep(_contract_retry_interval)
                else:
                    print(f"\n❌ [P3] 新建合同失败: {e.reason}", file=sys.stderr)
                    sys.exit(1)

    # ── P4：创建房型 ─────────────────────────────────────────────────────────
    if need_room:
        print("\n🛏  [P4] 创建房型...")
        try:
            room_info = create_room(
                partner_id=ctx.partner_id,
                poi_id=ctx.poi_id,
                room_type=room_type,
                is_overseas=is_overseas,
                dry_run=dry_run,
            )
            ctx.room_info_id = room_info.get("roomInfoId") or ""
            ctx.real_room_id = room_info.get("realRoomId") or ""
            ctx.room_name    = room_info.get("roomName") or ""
        except StepError as e:
            # 若供应商未就绪则重试一次
            if "TDC" in e.reason or "供应商" in e.reason or "不存在" in e.reason:
                print(f"  ⚠️  疑似供应商未就绪，等待30秒后重试...")
                time.sleep(30)
                try:
                    room_info = create_room(
                        partner_id=ctx.partner_id,
                        poi_id=ctx.poi_id,
                        room_type=room_type,
                        is_overseas=is_overseas,
                        dry_run=dry_run,
                    )
                    ctx.room_info_id = room_info.get("roomInfoId") or ""
                    ctx.real_room_id = room_info.get("realRoomId") or ""
                    ctx.room_name    = room_info.get("roomName") or ""
                except StepError as e2:
                    print(f"\n❌ [P4] 创建房型失败: {e2.reason}", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"\n❌ [P4] 创建房型失败: {e.reason}", file=sys.stderr)
                sys.exit(1)

    return ctx

