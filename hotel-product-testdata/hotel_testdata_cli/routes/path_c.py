#!/usr/bin/env python3
"""
路径C：仅有 poiId

Steps:
  0. （use_pool=True）先查数据池找 partnerId
          命中  → 进 Step1（私海认领 + 绑定门店）
          未命中 → 进 Step0b
     （use_pool=False，默认）直接进 Step0b
  0b.(新建路径)私海认领 → 创建供应商（内含门店绑定）→ 标记 need_save_pool=True（goods 创建后存入数据池）
  1. （数据池命中路径）私海认领 → 绑定门店
  [按需] POI资质添加
  → 公共段 P1～P4

注意：新建路径时 create_partner 本身已传入 poi_id 完成绑定，无需再调 bind_partner_poi；
     数据池命中时复用老供应商，需要在 Step1 做私海认领 + bind_partner_poi 把新 POI 绑上去。
"""

import sys

from hotel_testdata_cli.scripts.runner import StepError
from hotel_testdata_cli.infra import (
    create_partner,
    claim_poi,
    bind_partner_poi,
    add_poi_qualification,
    query_data_pool,
)
from hotel_testdata_cli.routes.base import InfraContext, public_phase


def run_path_c(
    poi_id: str,
    partner_id: str = "",             # 若已知供应商ID，直接传入，跳过 Step0 全部逻辑
    is_overseas: bool = False,
    need_contract: bool = True,
    need_room: bool = True,
    room_type: int = 0,
    add_qualification: bool = False,
    partner_type: int = 2,
    entity_type: int = 0,
    use_pool: bool = False,           # True=先查数据池，命中则复用；False=直接新建
    swimlane: str = "",
    dry_run: bool = False,
) -> InfraContext:
    """
    路径C 编排：仅有 poiId。

    use_pool 控制是否查数据池（对应 --pool 参数）：
      True  → 先查数据池找 partnerId
                命中  → from_path_a_new=False，Step1 执行私海认领+绑定门店
                未命中 → 私海认领 → 创建供应商（内含绑定）→ need_save_pool=True，from_path_a_new=True
      False → 私海认领 → 创建供应商（内含绑定）→ need_save_pool=True，from_path_a_new=True

    若调用方已传入 partner_id（如 infra --path c --partner-id xxx），
    则跳过 Step0 全部逻辑，直接执行私海认领+绑定门店。

    参数：
        poi_id            - 门店ID（必填）
        partner_id        - 如已知供应商ID，直接传入（可选，跳过 Step0 全部逻辑）
        is_overseas       - 是否境外（默认境内）
        need_contract     - 是否需要合同（全日房/钟点房=True，非房/超团=False）
        need_room         - 是否需要创建房型
        room_type         - 房型类型（0=大床间）
        add_qualification - 是否执行门店资质添加（工具476）
        partner_type      - 供应商类型（2=境内，3=境外）
        entity_type       - 实体类型（0=集团，2=单体）
        use_pool          - True=先查数据池，命中则复用；False=直接新建（默认False）
        swimlane          - 泳道（空=主干）
        dry_run           - True 时只打印不执行
    """
    print("\n" + "═" * 60)
    print("🟡 [路径C] 仅有 poiId")
    print("═" * 60)
    print(f"  poiId     : {poi_id}")
    print(f"  泳道      : {swimlane or '主干'}")
    print(f"  查数据池  : {'是' if use_pool else '否'}")

    from_path_a_new = False
    platform_contract_id = ""
    need_save_pool = False

    # ── Step0 / Step0b：数据池查询 or 新建路径 ────────────────────────────────
    if not partner_id:
        # use_pool=True 时先查数据池
        if use_pool:
            pool = query_data_pool(is_overseas=is_overseas, dry_run=dry_run)
            if pool.get("partner_id"):
                # ── 数据池命中：直接复用 ──────────────────────────────────────
                partner_id           = pool["partner_id"]
                platform_contract_id = pool.get("platform_contract_id", "")
                print(f"\n✅ [Step0] 数据池命中，复用供应商 partnerId={partner_id}")

        # 数据池未命中 或 use_pool=False → 新建路径（Step0b）
        if not partner_id:
            # Step0b-1: 私海认领（必须在创建供应商之前）
            if use_pool:
                print("\n🏗  [Step0] 数据池未命中，开始新建路径...")
            print("\n🔐 [Step0b-1] 私海认领...")
            try:
                claim_poi(poi_id=poi_id, dry_run=dry_run)
            except StepError as e:
                print(f"\n❌ 私海认领失败: {e.reason}", file=sys.stderr)
                sys.exit(1)

            # Step0b-2: 创建供应商
            print("\n🏗  [Step0b-2] 创建供应商...")
            try:
                partner_info = create_partner(
                    poi_id=poi_id,
                    partner_type=partner_type,
                    entity_type=entity_type,
                    is_overseas=is_overseas,
                    dry_run=dry_run,
                )
                partner_id           = partner_info.get("partnerId", "")
                platform_contract_id = str(partner_info.get("platformContractId", ""))
                from_path_a_new = True
            except StepError as e:
                print(f"\n❌ 创建供应商失败: {e.reason}", file=sys.stderr)
                sys.exit(1)

            # Step0b-3: 标记需要存入数据池（由 fullday 在 goods 创建后统一执行）
            need_save_pool = True

    ctx = InfraContext(
        partner_id=partner_id,
        poi_id=poi_id,
        platform_contract_id=platform_contract_id,
        from_path_a_new=from_path_a_new,
        need_save_pool=need_save_pool,
    )

    # ── Step1/Step2：仅对“复用已有供应商”的情况执行（新建路径 create_partner 已内含绑定）───
    # 新建路径（from_path_a_new=True）：Step0b 已完成 私海认领+创建供应商（内含绑定），此处跳过
    # 其他情况（数据池命中 或 调用方直接传入 partner_id）：需要对新 POI 执行 私海认领+绑定门店
    if not from_path_a_new:
        # 数据池命中路径：Step1 = 私海认领，Step2 = 绑定门店
        print("\n🔐 [Step1] 私海认领...")
        try:
            claim_poi(poi_id=poi_id, dry_run=dry_run)
        except StepError as e:
            print(f"\n❌ 私海认领失败: {e.reason}", file=sys.stderr)
            sys.exit(1)

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

