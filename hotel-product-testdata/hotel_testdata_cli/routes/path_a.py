#!/usr/bin/env python3
"""
路径A：完全空白（无任何 ID）

支持两种模式，通过 use_pool 参数区分：

  ┌─ use_pool=True（查数据池）──────────────────────────────────────────────┐
  │  数据池查询                                                             │
  │    └─ 命中 → 只取partnerId → ⛔询问用户确认                            │
  │               ├─ 确认使用 → Step1建POI → Step2私海认领 → Step3绑定门店  │
  │               │             → 公共段P2（查/建合同 → P4建房型）→ 上单    │
  │               └─ 拒绝/新建 → Step1建POI → Step2私海认领 → Step3建供应商 │
  │                              → 公共段 → 上单 → 存数据池（goods创建后）  │
  │    └─ 未命中 → Step1建POI → Step2私海认领 → Step3建供应商               │
  │                └─ 公共段 → 上单 → 存数据池（goods创建后）               │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─ use_pool=False（不查数据池，默认）──────────────────────────────────────┐
  │  Step1建POI → Step2私海认领 → Step3建供应商                             │
  │  └─ 公共段（P1→P3→P4）→ 上单 → 存数据池（goods创建后）                 │
  └─────────────────────────────────────────────────────────────────────────┘
"""

import sys

from hotel_testdata_cli.infra import (
    create_poi,
    claim_poi,
    bind_partner_poi,
    create_partner,
    query_data_pool,
)
from hotel_testdata_cli.routes.base import InfraContext, public_phase
from hotel_testdata_cli.scripts.runner import StepError


def run_path_a(
    city: str = "北京",
    is_overseas: bool = False,
    partner_type: int = 2,
    entity_type: int = 0,
    currency: str = "CNY",
    need_contract: bool = True,
    need_room: bool = True,
    room_type: int = 0,
    swimlane: str = "",
    use_pool: bool = False,
    dry_run: bool = False,
) -> InfraContext:
    """
    路径A：全新构造（可选查数据池）。

    参数：
        city          - 创建 POI 的城市（默认北京）
        is_overseas   - 是否境外
        partner_type  - 供应商类型（2=境内，3=境外，9=女娲）
        entity_type   - 0=集团，2=单体（通兑超团需2）
        currency      - 币种（默认CNY）
        need_contract - 是否需要合同
        need_room     - 是否需要创建房型
        room_type     - 房型类型
        swimlane      - 泳道
        use_pool      - True=先查数据池，命中则只取partnerId供用户确认后复用，未命中再全新构造
        dry_run       - 只打印不执行
    """
    print("\n" + "═" * 60)
    if use_pool:
        print("🟢 [路径A] 全新构造（优先查数据池）")
    else:
        print("🟢 [路径A] 全新构造（不查数据池）")
    print("═" * 60)
    print(f"  城市      : {city}")
    print(f"  境外      : {is_overseas}")
    print(f"  泳道      : {swimlane or '主干'}")
    print(f"  查数据池  : {'是' if use_pool else '否'}")

    # ── 数据池查询分支（use_pool=True）─────────────────────────────────────
    if use_pool:
        pool = query_data_pool(is_overseas=is_overseas, dry_run=dry_run)
        pool_partner_id = pool.get("partner_id", "")
        if pool_partner_id:
            # 命中：只取 partnerId，询问用户是否使用
            print(f"\n✅ [数据池命中] 找到可用供应商：partnerId = {pool_partner_id}")
            print("⚠️  请确认是否使用该 partnerId？（将新建门店并与其绑定）")
            try:
                answer = input("  输入 y 使用，其他任意键新建供应商: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""

            if answer == "y":
                # 用户确认：新建POI → 私海认领 → 绑定门店 → 公共段 P2
                print(f"\n✅ [确认使用] partnerId={pool_partner_id}，开始新建门店并绑定...")

                # Step1: 创建 POI
                print("\n🏨 [Step1] 创建门店...")
                poi_id = ""
                try:
                    poi_info = create_poi(city=city, is_overseas=is_overseas, dry_run=dry_run)
                    poi_id = poi_info.get("poiId", "")
                except StepError as e:
                    print(f"\n❌ 创建门店失败: {e.reason}", file=sys.stderr)
                    sys.exit(1)

                # Step2: 私海认领
                print("\n🔐 [Step2] 私海认领...")
                try:
                    claim_poi(poi_id=poi_id, dry_run=dry_run)
                except StepError as e:
                    print(f"\n❌ 私海认领失败: {e.reason}", file=sys.stderr)
                    sys.exit(1)

                # Step3: 绑定门店
                print("\n🔗 [Step3] 绑定门店...")
                try:
                    bind_partner_poi(poi_id=poi_id, partner_id=pool_partner_id, dry_run=dry_run)
                except StepError as e:
                    print(f"\n❌ 绑定门店失败: {e.reason}", file=sys.stderr)
                    sys.exit(1)

                ctx = InfraContext(
                    partner_id=pool_partner_id,
                    poi_id=poi_id,
                    from_path_a_new=False,
                )
                return public_phase(
                    ctx=ctx,
                    need_contract=need_contract,
                    need_room=need_room,
                    is_overseas=is_overseas,
                    room_type=room_type,
                    swimlane=swimlane,
                    dry_run=dry_run,
                )
            else:
                print("\n⚠️  [用户选择新建] 开始全新构造供应商...")
        else:
            print("\n⚠️  [数据池未命中] 开始全新构造...")

    # ── 全新构造（use_pool=False 或数据池未命中）──────────────────────────

    # ── Step1: 创建 POI ────────────────────────────────────────────────────
    print("\n🏨 [Step1] 创建门店...")
    poi_id = ""
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

    # ── Step3: 创建供应商（异步）─────────────────────────────────────────────
    print("\n🏗  [Step3] 创建供应商（异步，约1分钟后就绪）...")
    partner_id = ""
    platform_contract_id = ""
    try:
        partner_info = create_partner(
            poi_id=poi_id,
            partner_type=partner_type,
            entity_type=entity_type,
            is_overseas=is_overseas,
            currency=currency,
            dry_run=dry_run,
        )
        partner_id           = partner_info.get("partnerId", "")
        platform_contract_id = str(partner_info.get("platformContractId") or "")
    except StepError as e:
        print(f"\n❌ 创建供应商失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    ctx = InfraContext(
        partner_id=partner_id,
        poi_id=poi_id,
        platform_contract_id=platform_contract_id,
        from_path_a_new=True,
        need_save_pool=True,   # goods 创建后由 fullday 统一存入数据池
    )

    # ── 公共段（P1等待+查合同→P3建合同→P4建房型）─────────────────────────
    return public_phase(
        ctx=ctx,
        need_contract=need_contract,
        need_room=need_room,
        is_overseas=is_overseas,
        room_type=room_type,
        swimlane=swimlane,
        dry_run=dry_run,
    )

