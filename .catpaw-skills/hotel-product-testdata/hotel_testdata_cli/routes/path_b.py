#!/usr/bin/env python3
"""
路径B：已有 partnerId + poiId

Steps:
  1. 私海认领
  2. 绑定门店
  [按需] POI资质添加
  → 公共段 P1～P4
"""

import sys

from hotel_testdata_cli.scripts.runner import StepError
from hotel_testdata_cli.infra import claim_poi, bind_partner_poi, add_poi_qualification
from hotel_testdata_cli.routes.base import InfraContext, public_phase


def run_path_b(
    partner_id: str,
    poi_id: str,
    is_overseas: bool = False,
    need_contract: bool = True,
    need_room: bool = True,
    room_type: int = 0,
    add_qualification: bool = False,
    swimlane: str = "",
    dry_run: bool = False,
) -> InfraContext:
    """
    路径B 编排：已有 partnerId + poiId → 公共段。

    参数：
        partner_id       - 供应商ID（必填）
        poi_id           - 门店ID（必填）
        is_overseas      - 是否境外（默认境内）
        need_contract    - 是否需要合同（全日房/钟点房=True，非房/超团=False）
        need_room        - 是否需要创建房型
        room_type        - 房型类型（0=大床间，见 create_room）
        add_qualification - 是否执行门店资质添加（工具476）
        swimlane         - 泳道（空字符串=主干）
        dry_run          - True 时只打印不执行
    """
    print("\n" + "═" * 60)
    print("🔵 [路径B] 已有 partnerId + poiId")
    print("═" * 60)
    print(f"  partnerId : {partner_id}")
    print(f"  poiId     : {poi_id}")
    print(f"  泳道      : {swimlane or '主干'}")

    ctx = InfraContext(partner_id=partner_id, poi_id=poi_id)

    # ── Step1: 私海认领 ────────────────────────────────────────────────────
    print("\n🔐 [Step1] 私海认领...")
    try:
        claim_poi(poi_id=poi_id, dry_run=dry_run)
    except StepError as e:
        print(f"\n❌ 私海认领失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # ── Step2: 绑定门店 ────────────────────────────────────────────────────
    print("\n🔗 [Step2] 绑定门店...")
    try:
        bind_partner_poi(poi_id=poi_id, partner_id=partner_id, dry_run=dry_run)
    except StepError as e:
        print(f"\n❌ 绑定门店失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # ── [按需] POI资质添加 ─────────────────────────────────────────────────
    if add_qualification:
        print("\n📋 [按需] 门店资质添加...")
        try:
            add_poi_qualification(poi_id=poi_id, dry_run=dry_run)
        except StepError as e:
            print(f"\n⚠️  门店资质添加失败（非阻断）: {e.reason}")

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

