#!/usr/bin/env python3
"""
子命令：hotel-testdata hourly

钟点房端到端上单（路径 A/B/C/D 自动 infra → W2 batchCreateGoods → 上线 → 缓存刷新）

与全日房的关键差异：
  - 钟点房仅支持境内（境外无钟点房场景）
  - paymentType 固定为 0（预付），不支持现付担保/非担保
  - --contract-no 参数传合同号（全日房通过 --set 传入）
  - 不支持早餐规则（rpBreakFastModel 固定为 null）
  - 不支持连住规则（rpSerialModel 固定为 null）
  - 不支持收费取消
  - 默认取消政策：免费取消（全日房默认不可取消）
  - 默认售价：8000分（80元）
  - 库存补偿命令用 hour_room_ids（全日房用 day_room_ids）

流程：
  1. 根据用户提供的 ID 推断路径，执行 infra 构造（POI/供应商/合同/房型）
  2. 使用 infra 产出的 partnerId/poiId/roomId/roomName/contractNo 创建钟点房
  3. 自动上线 + 库存补偿 + 缓存刷新

路径推断规则（与 skill w8-infra-bootstrap.md 完全一致）：
  partnerId + poiId 均有 → 路径B
  仅有 partnerId         → 路径D
  仅有 poiId             → 路径C
  什么都没有             → 路径A

用法示例：
  # 全新（路径A）
  hotel-testdata hourly

  # 已有 partnerId + poiId（路径B）
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575

  # 已有基础实体，直接上单（传 --room-id --room-name --contract-no 跳过 infra）
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575 \\
    --room-id 12345 --room-name "钟点房" \\
    --contract-no ZSFW-A9-75178816

  # 已有房型（跳过建房型），仍走 infra 查/建供应商+门店+合同（路径B）
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575 \\
    --room-id 12345 --room-name "钟点房"

  # 6小时钟点房，全天接待
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575 \\
    --contract-no ZSFW-A9-75178816 \\
    --set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6 \\
    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=00:00 \\
    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd=23:59

  # 不可取消钟点房
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575 \\
    --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0

  # dry-run
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575 --dry-run

  # 路径A（全新，优先查数据池）
  hotel-testdata hourly --pool

  # 路径C（只有门店 ID，优先查数据池）
  hotel-testdata hourly --poi-id 1090235108219575 --pool
"""

import argparse
import json
import sys

from hotel_testdata_cli.goods.ops import call_raw, wait_for_goods_id, post_create_ops
from hotel_testdata_cli.infra import save_to_pool
from hotel_testdata_cli.routes.path_a import run_path_a
from hotel_testdata_cli.routes.path_b import run_path_b
from hotel_testdata_cli.routes.path_c import run_path_c
from hotel_testdata_cli.routes.path_d import run_path_d
from hotel_testdata_cli.scripts.registry import get_factory


def _get_mod():
    """懒加载 factory/hourly/create-hourly.py 模块。"""
    return get_factory("hourly")


def _parse_val(v: str, key: str = ""):
    return _get_mod()._try_parse_value(v, key)


def create_hourly(
    partner_id: str,
    poi_id: str,
    room_id: int,
    room_name: str,
    goods_name: str = "",
    contract_no: str = None,
    overrides: dict = None,
    swimlane: str = "",
    dry_run: bool = False,
    skip_constraints: bool = False,
    poll_timeout: int = 120,
) -> str:
    """钒点房全链路创建（直接调 factory 层，无 goods 中间层）。"""
    mod = _get_mod()

    # 1. 加载模板（钒点房模板自动处理 goodsName）
    params = mod.load_template(
        partner_id=partner_id,
        poi_id=poi_id,
        room_id=room_id,
        room_name=room_name,
        goods_name=goods_name,
    )

    # 2. 注入 contractNo
    if contract_no:
        mod._set_nested(
            params,
            "goodsDetailList.0.goodsBaseInfo.contractNo",
            contract_no,
        )

    # 3. 应用 --set 覆盖
    if overrides:
        mod.apply_overrides(params, overrides)

    # 4. 约束校验
    if not skip_constraints:
        try:
            mod.validate_constraints(params)
        except Exception as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    # 5. dry-run
    if dry_run:
        print("\n[dry-run] 钒点房最终参数：")
        print(json.dumps(params, ensure_ascii=False, indent=2))
        return "dry_run"

    # 6. 调用 RPC
    print("\n── Step 5: 创建钒点房（batchCreateGoods）────────────────────────")
    from hotel_testdata_cli.scripts.runner import InvokeError, StepError
    try:
        resp = call_raw(params=params, swimlane=swimlane)
    except InvokeError as e:
        print(f"\n❌ 钒点房创建失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 7. 轮询等待 goodsId
    uuid = ""
    if isinstance(resp.get("data"), str):
        uuid = resp["data"]
    elif isinstance(resp.get("data"), dict):
        uuid = str(resp["data"].get("uuid") or resp["data"].get("taskId") or "")

    goods_id = ""
    if uuid:
        print(f"  ⏳ 获取到 uuid={uuid}，轮询等待任务完成...")
        try:
            goods_id = wait_for_goods_id(
                partner_id=partner_id,
                poi_id=poi_id,
                uuid=uuid,
                swimlane=swimlane,
                timeout_sec=poll_timeout,
            )
        except StepError as e:
            print(f"\n❌ 商品创建失败: {e.reason}", file=sys.stderr)
            sys.exit(1)
    else:
        print("  ⚠️ 未能从响应中取到 uuid，跳过轮询")

    if goods_id:
        print(f"  ✅ 商品创建成功 goodsId={goods_id}")
    else:
        print("  ⚠️ 未获取到 goodsId，商品可能仍在异步处理中")

    # 8. 后置操作：上线 + 缓存刷新（含库存补偿）
    post_create_ops(
        partner_id=partner_id,
        poi_id=poi_id,
        goods_id=goods_id,
        params=params,
        room_id=room_id,
        swimlane=swimlane,
        goods_type=2,  # 钒点房: hour_room_ids
    )

    return goods_id


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """向主解析器注册 hourly 子命令。"""
    p = subparsers.add_parser(
        "hourly",
        help="钟点房端到端上单（仅境内；路径A/B/C/D infra → batchCreateGoods → 上线）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    # ── 基础实体 ID（决定走哪条路径）──────────────────────────────────────
    p.add_argument("--partner-id", default="", help="供应商ID（有则走路径B/D，否则路径A/C）")
    p.add_argument("--poi-id",     default="", help="门店ID（有则走路径B/C，否则路径A/D）")

    # ── 直接提供房型 + 合同（跳过建房型步骤）────────────────────────────
    p.add_argument("--room-id",     default="", help="已有房型ID（与 --room-name 一起传时跳过建房型，仍走 infra 其他步骤）")
    p.add_argument("--room-name",   default="", help="已有房型名称（与 --room-id 配合使用）")
    p.add_argument(
        "--contract-no", default="",
        help="合同号字符串（如 ZSFW-A9-75178816）。\n"
             "⚠️  钟点房合同号必填，缺失会报「合同不能为空」。\n"
             "    若不传，程序会从 infra 查/建合同后自动填入。",
    )

    # ── 门店/供应商参数（路径A/C/D 新建时）────────────────────────────────
    p.add_argument("--city",         default="北京", help="创建门店城市（路径A/D，默认北京）")
    p.add_argument("--partner-type", type=int, default=2,
                   help="供应商类型：2=境内自采预付，9=女娲（钟点房仅支持境内，默认2）")
    p.add_argument("--entity-type",  type=int, default=0,
                   help="实体类型：0=集团，2=单体（通兑超团必传2，默认0）")
    p.add_argument("--currency",     default="CNY", help="币种（默认CNY）")

    # ── 房型参数（新建房型时）──────────────────────────────────────────────
    p.add_argument("--room-type", type=int, default=0,
                   help="房型类型：0=大床间,1=单人间,2=双床间,3=三人间,4=套房（默认0）")

    # ── 数据池（路径A/C 专用）────────────────────────────────────────────────────
    p.add_argument(
        "--pool", action="store_true", default=False,
        help="（路径A/C）优先查数据池：命中则复用，未命中再新建+存数据池。"
             "不加此参数时直接新建并存入数据池。",
    )

    # ── 门店资质（按需）────────────────────────────────────────────────────
    p.add_argument("--add-qualification", action="store_true",
                   help="执行门店资质添加（工具476）[路径B/C按需]")

    # ── 商品参数 ────────────────────────────────────────────────────────────
    p.add_argument("--goods-name", default="", help="商品名称（不传则自动生成 <房型名>-<时间戳>）")
    p.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", dest="set_args",
        help="覆盖任意字段，可多次使用。KEY 为点分路径。\n"
             "例：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6\n"
             "    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=00:00",
    )

    # ── 泳道 / dry-run / 超时 ────────────────────────────────────────────────
    p.add_argument("--swimlane",    default="", help="泳道名（空=主干）")
    p.add_argument("--dry-run",     action="store_true", help="只打印参数，不实际执行")
    p.add_argument("--poll-timeout", type=int, default=120,
                   help="等待 batchCreateGoods 完成的最长秒数（默认120）")
    p.add_argument("--skip-constraints", action="store_true",
                   help="跳过本地约束校验（谨慎使用）")

    p.set_defaults(func=_run)


def _auto_detect_path(args) -> str:
    """根据传入 ID 自动推断路径（与 infra 子命令逻辑一致）。"""
    has_partner = bool(args.partner_id)
    has_poi = bool(args.poi_id)
    if has_partner and has_poi:
        return "b"
    elif has_poi and not has_partner:
        return "c"
    elif has_partner and not has_poi:
        return "d"
    else:
        return "a"


def _parse_set_args(set_args: list, try_parse_fn) -> dict:
    """将 --set KEY=VALUE 列表解析为 {点分路径: 值} dict。"""
    overrides = {}
    for item in set_args:
        if "=" not in item:
            print(f"⚠️  --set 参数格式不对（应为 KEY=VALUE）: {item!r}", file=sys.stderr)
            continue
        key, val = item.split("=", 1)
        overrides[key.strip()] = try_parse_fn(val, key.strip())
    return overrides


def _run(args: argparse.Namespace) -> None:
    # ── 参数卡控：传了 --room-id/--room-name 必须同时有 partner/poi/contract ──
    has_room_id   = bool(args.room_id)
    has_room_name = bool(args.room_name)
    if has_room_id or has_room_name:
        missing = []
        if not has_room_id:       missing.append("--room-id")
        if not has_room_name:     missing.append("--room-name")
        if not args.partner_id:   missing.append("--partner-id")
        if not args.poi_id:       missing.append("--poi-id")
        if not args.contract_no:  missing.append("--contract-no")
        if missing:
            print(
                f"❌ 传入 --room-id/--room-name 时，以下参数必须同时提供：{', '.join(missing)}",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── 解析 --set 参数 ─────────────────────────────────────────────────────
    overrides = _parse_set_args(args.set_args, _parse_val)

    print("\n" + "═" * 60)
    print("🚀 hotel-testdata hourly（钟点房端到端上单）")
    print("═" * 60)
    if args.dry_run:
        print("   ⚠️  dry-run 模式，不会真实调用接口")

    # ── 是否已提供房型（决定 infra 是否需要建房型）──────────────────────────
    has_room = bool(args.room_id) and bool(args.room_name)

    # ── 是否可以完全跳过 infra（partner+poi+room+contract 全有）────────────
    # 钟点房合同号必填，缺少时仍需走 infra 查/建合同
    has_all_ids = (
        bool(args.partner_id)
        and bool(args.poi_id)
        and has_room
        and bool(args.contract_no)
    )

    if has_all_ids:
        # 用户已提供完整基础实体，直接上单（跳过所有 infra 步骤）
        partner_id  = args.partner_id
        poi_id      = args.poi_id
        room_id     = int(args.room_id)
        room_name   = args.room_name
        contract_no = args.contract_no or None
        print(f"  ✅ 已提供完整基础实体（跳过 infra 构造）")
        print(f"     partnerId  : {partner_id}")
        print(f"     poiId      : {poi_id}")
        print(f"     roomId     : {room_id}")
        print(f"     roomName   : {room_name}")
        if contract_no:
            print(f"     contractNo : {contract_no}")
        else:
            print(f"     contractNo : ⚠️  未传入，接口可能报「合同不能为空」")
    else:
        # 需要先执行 infra（路径 A/B/C/D）
        # 若已提供 room-id + room-name，则跳过建房型（need_room=False）
        path = _auto_detect_path(args)
        print(f"  📋 infra 路径: {path.upper()}（自动推断）")
        if has_room:
            print(f"  🛏  已提供房型（跳过建房型）: roomId={args.room_id}, roomName={args.room_name}")

        if path == "b":
            if not args.partner_id or not args.poi_id:
                print("❌ 路径B 需要同时传入 --partner-id 和 --poi-id", file=sys.stderr)
                sys.exit(1)
            ctx = run_path_b(
                partner_id=args.partner_id,
                poi_id=args.poi_id,
                is_overseas=False,   # 钟点房仅境内
                need_contract=True,
                need_room=not has_room,
                room_type=args.room_type,
                add_qualification=args.add_qualification,
                swimlane=args.swimlane,
                dry_run=args.dry_run,
            )

        elif path == "c":
            if not args.poi_id:
                print("❌ 路径C 需要 --poi-id", file=sys.stderr)
                sys.exit(1)
            ctx = run_path_c(
                poi_id=args.poi_id,
                partner_id=args.partner_id,
                is_overseas=False,   # 钟点房仅境内
                need_contract=True,
                need_room=not has_room,
                room_type=args.room_type,
                add_qualification=args.add_qualification,
                partner_type=args.partner_type,
                entity_type=args.entity_type,
                use_pool=args.pool,
                swimlane=args.swimlane,
                dry_run=args.dry_run,
            )

        elif path == "d":
            if not args.partner_id:
                print("❌ 路径D 需要 --partner-id", file=sys.stderr)
                sys.exit(1)
            ctx = run_path_d(
                partner_id=args.partner_id,
                city=args.city,
                is_overseas=False,   # 钟点房仅境内
                need_contract=True,
                need_room=not has_room,
                room_type=args.room_type,
                swimlane=args.swimlane,
                dry_run=args.dry_run,
            )

        else:  # path == "a"
            ctx = run_path_a(
                city=args.city,
                is_overseas=False,   # 钟点房仅境内
                partner_type=args.partner_type,
                entity_type=args.entity_type,
                currency=args.currency,
                need_contract=True,
                need_room=not has_room,
                room_type=args.room_type,
                swimlane=args.swimlane,
                use_pool=args.pool,
                dry_run=args.dry_run,
            )

        if args.dry_run:
            print("\n[dry-run] infra 步骤完成（未执行），跳过商品创建")
            return

        # 从 ctx 中取基础实体参数
        partner_id  = ctx.partner_id
        poi_id      = ctx.poi_id
        contract_no = ctx.contract_no or args.contract_no or None

        # 房型：优先使用命令行传入的（跳过建房型时）
        if has_room:
            room_id   = int(args.room_id)
            room_name = args.room_name
        else:
            room_id   = int(ctx.room_info_id) if ctx.room_info_id else 0
            room_name = ctx.room_name or ""
            if not room_id:
                print("❌ 未能获取 roomInfoId，无法上单", file=sys.stderr)
                sys.exit(1)

        print("\n" + "─" * 60)
        print("  ✅ 基础实体就绪，开始创建钟点房")
        print(f"     partnerId  : {partner_id}")
        print(f"     poiId      : {poi_id}")
        print(f"     roomId     : {room_id}")
        print(f"     roomName   : {room_name}")
        if contract_no:
            print(f"     contractNo : {contract_no}")
        else:
            print(f"     contractNo : ⚠️  无合同，接口可能报「合同不能为空」")
        print("─" * 60)

    # ── 创建钟点房 ──────────────────────────────────────────────────────────
    goods_id = create_hourly(
        partner_id=str(partner_id),
        poi_id=str(poi_id),
        room_id=int(room_id),
        room_name=room_name,
        goods_name=args.goods_name,
        contract_no=contract_no,
        overrides=overrides,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
        skip_constraints=args.skip_constraints,
        poll_timeout=args.poll_timeout,
    )

    if args.dry_run:
        return

    # ── 存入数据池（goods 创建完成后，不阻塞主流程）─────────────────────────
    if not has_all_ids and ctx.need_save_pool:
        _contract_id_for_pool = ctx.platform_contract_id
        if ctx.partner_id and _contract_id_for_pool and ctx.poi_id:
            print("\n💾 存入数据池（goods 创建完成）...")
            try:
                save_to_pool(
                    partner_id=ctx.partner_id,
                    platform_contract_id=_contract_id_for_pool,
                    poi_id=ctx.poi_id,
                    dry_run=args.dry_run,
                )
            except Exception as _e:
                print(f"  ⚠️  存入数据池失败（非阻断）: {_e}")
        else:
            _missing = []
            if not ctx.partner_id:           _missing.append("partnerId")
            if not _contract_id_for_pool:    _missing.append("platformContractId")
            if not ctx.poi_id:               _missing.append("poiId")
            print(f"  ⚠️  缺少字段（{', '.join(_missing)}），跳过存数据池")

    # ── 最终汇总输出 ────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  🎉 钟点房上单完成")
    print("═" * 60)
    print(f"  商品ID (goodsId) : {goods_id or '（未获取到，请检查）'}")
    print(f"  供应商ID         : {partner_id}")
    print(f"  门店ID           : {poi_id}")
    print(f"  房型ID           : {room_id}")
    print(f"  泳道             : {args.swimlane or '主干'}")
    print("═" * 60)

