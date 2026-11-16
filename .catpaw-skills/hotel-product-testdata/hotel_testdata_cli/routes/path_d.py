#!/usr/bin/env python3
"""
路径D：仅有 partnerId

Steps:
  1. 创建门店（POI）
  2. 私海认领
  3. 绑定门店
  → 公共段 P1～P4
"""

import sys

from hotel_testdata_cli.scripts.runner import StepError
from hotel_testdata_cli.infra import create_poi, claim_poi, bind_partner_poi
from hotel_testdata_cli.routes.base import InfraContext, public_phase


def run_path_d(
    partner_id: str,
    city: str = "北京",
    is_overseas: bool = False,
    need_contract: bool = True,
    need_room: bool = True,
    room_type: int = 0,
    swimlane: str = "",
    dry_run: bool = False,
) -> InfraContext:
    """
    路径D 编排：仅有 partnerId → 新建 POI → 私海认领 → 绑定 → 公共段。

    参数：
        partner_id    - 供应商ID（必填）
        city          - 创建 POI 的城市（默认北京）
        is_overseas   - 是否境外
        need_contract - 是否需要合同
        need_room     - 是否需要创建房型
        room_type     - 房型类型
        swimlane      - 泳道
        dry_run       - 只打印不执行
    """
    print("\n" + "═" * 60)
    print("🟠 [路径D] 仅有 partnerId")
    print("═" * 60)
    print(f"  partnerId : {partner_id}")
    print(f"  城市      : {city}")
    print(f"  泳道      : {swimlane or '主干'}")

    poi_id = ""

    # ── Step1: 创建 POI ────────────────────────────────────────────────────
    print("\n🏨 [Step1] 创建门店...")
    try:
        poi_info = create_poi(city=city, is_overseas=is_overseas, dry_run=dry_run)
        poi_id = poi_info.get("poiId", "")
    except StepError as e:
        print(f"\n❌ 创建门店失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # ── Step2: 私海认领 ────────────────────────────────────────────────────
    print("\n🔐 [Step2] 私海认领...")
    try:
        claim_poi(poi_id=poi_id, dry_run=dry_run)
    except StepError as e:
        print(f"\n❌ 私海认领失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # ── Step3: 绑定门店 ────────────────────────────────────────────────────
    print("\n🔗 [Step3] 绑定门店...")
    try:
        bind_partner_poi(poi_id=poi_id, partner_id=partner_id, dry_run=dry_run)
    except StepError as e:
        print(f"\n❌ 绑定门店失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    ctx = InfraContext(partner_id=partner_id, poi_id=poi_id)

    # ── 公共段 ─────────────────────────────────────────────────────────────
    return public_phase(
        ctx=ctx,
        need_contract=need_contract,
        need_room=need_room,
        is_overseas=is_overseas,
        room_type=room_type,
        swimlane=swimlane,
        dry_run=dry_run,
    )

