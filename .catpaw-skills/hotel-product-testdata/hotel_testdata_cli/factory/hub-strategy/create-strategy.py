#!/usr/bin/env python3
"""
商品构造 - 创建并发布货盘规则

服务：com.sankuai.hotelcrs.supply.hub
接口：HubStrategyFacade#createStrategy + HubStrategyFacade#updateStrategyStatus
协议：Thrift RPC 直调（同步）

流程：
  Step 1：createStrategy（strategyStatus=0，草稿）→ 返回 strategyId
  Step 2：updateStrategyStatus（strategyStatus=1）→ 发布上线，系统自动生成套餐

前置：已有 S3 文件下载链接（由 factory/resource/upload-to-s3.py 上传后返回）

──────────────────────────────────────────────────────────
两种模式：

  模式一：突破全渠道（默认，不传 --delete-channels）
    channelBreakType=2，向所有渠道开放

  模式二：删除渠道（传 --delete-channels）
    channelBreakType=5，channels 传入要删除的渠道码列表
    不传 --channels 时，默认删除全部 6 个渠道

可删除的渠道码：
  2783_2_1003_1007_4006   酒店搜索主流程/美团App/酒店民宿/POI详情页/酒店套餐
  2783_2_63_163_4605      酒店搜索主流程/美团App/门票/POI详情页/门票+酒店
  2783_1010_1011_1015_4606 酒店搜索主流程/美团团购小程序/酒店民宿/POI详情页/景点游玩门票酒店套餐
  2783_16_1016_1019_4024  酒店搜索主流程/点评App/酒店民宿/POI详情页/酒店套餐
  2783_16_64_165_4607     酒店搜索主流程/点评App/门票/POI详情页/景点游玩酒店套餐
  2783_1021_1630_1631_4646 酒店搜索主流程/点评小程序/景点游玩/POI详情页/景酒套餐
──────────────────────────────────────────────────────────

使用方式：
  # 模式一：突破全渠道（默认）
  python3 create-strategy.py \\
    --strategy-name "早餐货盘规则" \\
    --file-url "https://msstest.sankuai.com/biz-platform-goods-copy/palletize_xxx.csv?..."

  # 模式二：删除全部 6 个渠道（不传 --channels，使用默认全量）
  python3 create-strategy.py \\
    --strategy-name "早餐货盘规则" \\
    --file-url "https://..." \\
    --delete-channels

  # 模式二：删除指定渠道
  python3 create-strategy.py \\
    --strategy-name "早餐货盘规则" \\
    --file-url "https://..." \\
    --delete-channels \\
    --channels "2783_2_1003_1007_4006,2783_16_1016_1019_4024"

  # 指定泳道 / dry-run
  python3 create-strategy.py \\
    --strategy-name "早餐货盘规则" \\
    --file-url "https://..." \\
    --swimlane user-xxx --dry-run

  # 查看字段说明
  python3 create-strategy.py --show-schema
"""

import argparse
import importlib.util as ilu
import json
import sys
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


def _load_interface():
    spec = ilu.spec_from_file_location(
        "hub_strategy_interface",
        os.path.join(ROOT, "interface/hub-strategy/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_channels(raw: str) -> list:
    """将逗号分隔的渠道码解析为列表"""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _show_schema():
    schema_path = os.path.join(_SCRIPT_DIR, "schema.json")
    with open(schema_path, encoding="utf-8") as f:
        print(json.dumps(json.load(f), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="创建并发布货盘规则（createStrategy → updateStrategyStatus）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    req = parser.add_argument_group("必填参数")
    req.add_argument("--strategy-name", required=True, help="货盘规则名称")
    req.add_argument("--file-url",      required=True, help="S3 文件下载链接（upload-to-s3.py 返回的 download_url）")

    opt = parser.add_argument_group("可选参数")
    opt.add_argument(
        "--delete-channels",
        action="store_true",
        help="删除渠道模式（channelBreakType=5）。不传=突破全渠道（channelBreakType=2）",
    )
    opt.add_argument(
        "--channels", default=None,
        metavar="CODE1,CODE2,...",
        help=(
            "配合 --delete-channels 使用：要删除的渠道码，逗号分隔。"
            "不传时默认删除全部 6 个渠道。"
            "示例：2783_2_1003_1007_4006,2783_16_1016_1019_4024"
        ),
    )
    opt.add_argument("--strategy-desc", default="",    help="规则描述（默认为空）")
    opt.add_argument("--swimlane",      default="",    help="泳道名称（默认主干）")
    opt.add_argument("--dry-run",       action="store_true", help="仅打印参数，不执行 RPC")
    opt.add_argument("--show-schema",   action="store_true", help="打印字段说明后退出")

    args = parser.parse_args()

    if args.show_schema:
        _show_schema()
        return

    iface = _load_interface()

    # 解析渠道参数
    channels = None
    if args.delete_channels:
        if args.channels:
            channels = _parse_channels(args.channels)
        else:
            # 未指定具体渠道，默认删除全部 6 个（取 CHANNELS 的所有渠道码）
            channels = list(iface.CHANNELS.keys())

    # ── 打印概览 ──────────────────────────────────────────────────────────────
    print("=" * 60)
    print("  📋  创建货盘规则")
    print("=" * 60)
    print(f"  规则名称 : {args.strategy_name}")
    print(f"  fileUrl  : {args.file_url}")
    if channels:
        print(f"  渠道模式 : 删除渠道（channelBreakType=5）")
        for ch in channels:
            desc = iface.CHANNELS.get(ch, "")
            print(f"             {ch}" + (f"  # {desc}" if desc else ""))
    else:
        print(f"  渠道模式 : 突破全渠道（channelBreakType=2）")
    print(f"  泳道     : {args.swimlane or '主干'}")
    print("=" * 60)

    # ── Step 1：创建货盘规则 ──────────────────────────────────────────────────
    resp = iface.create_strategy(
        strategy_name=args.strategy_name,
        file_url=args.file_url,
        strategy_desc=args.strategy_desc,
        channels=channels,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    strategy_id = (
        resp.get("strategyId")
        or resp.get("id")
        or (resp.get("data") if isinstance(resp.get("data"), (int, str)) else None)
    )
    if isinstance(strategy_id, dict):
        strategy_id = strategy_id.get("strategyId") or strategy_id.get("id")

    if not strategy_id:
        print(f"\n❌ 未从响应中提取到 strategyId，原始响应：{resp}", file=sys.stderr)
        sys.exit(1)

    strategy_id = int(strategy_id)
    print(f"\n  ✅ 货盘规则创建成功  strategyId = {strategy_id}")

    # ── Step 2：发布上线 ──────────────────────────────────────────────────────
    print(f"\n  🚀  发布上线（strategyStatus=1）...")
    iface.update_strategy_status(
        strategy_id=strategy_id,
        strategy_status=1,
        swimlane=args.swimlane,
        dry_run=False,
    )

    print("\n" + "=" * 60)
    print("  ✅ 货盘规则创建并发布成功")
    print("=" * 60)
    print(f"  strategyId : {strategy_id}")
    print("  ⚠️  房转套餐将由系统自动生成，请稍后（~30s）查询套餐 ID")
    print("=" * 60)


if __name__ == "__main__":
    main()

