#!/usr/bin/env python3
"""
商品构造 - 查询货盘规则生成的套餐记录（spuId）

服务：com.sankuai.hotelcrs.supply.hub
接口：HubStrategyFacade#queryGoods2SpuRecordByPage
协议：Thrift RPC 直调（同步）

前置：已有 strategyId（由 factory/hub-strategy/create-strategy.py 创建并发布后返回）

说明：
  货盘规则发布后，系统异步生成套餐，通常需要 30~60 秒。
  有效套餐条件：spuId 非 0 非 null 且 status=1

使用方式：
  # 查询 strategyId=21560 的套餐
  python3 query-spu.py --strategy-id 21560

  # 自动等待并轮询（最多等 120 秒）
  python3 query-spu.py --strategy-id 21560 --wait

  # 指定泳道 / dry-run
  python3 query-spu.py --strategy-id 21560 --swimlane user-xxx
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
import time

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询货盘规则生成的套餐记录（queryGoods2SpuRecordByPage）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--strategy-id", required=True, type=int, help="货盘规则 ID（create-strategy.py 返回）")
    parser.add_argument("--page",        default=1,    type=int, help="页码（默认 1）")
    parser.add_argument("--page-size",   default=10,   type=int, help="每页条数（默认 10）")
    parser.add_argument("--wait",  action="store_true",  help="自动轮询等待套餐生成（最多 120 秒，每 10 秒一次）")
    parser.add_argument("--swimlane",    default="",       help="泳道名称（默认主干）")

    args = parser.parse_args()
    iface = _load_interface()

    print("=" * 60)
    print("  🔍  查询货盘规则套餐记录")
    print("=" * 60)
    print(f"  strategyId : {args.strategy_id}")
    print(f"  泳道       : {args.swimlane or '主干'}")
    print("=" * 60)

    max_attempts = 12 if args.wait else 1  # --wait 时最多等 120 秒（12 次 × 10s）
    interval = 10

    for attempt in range(1, max_attempts + 1):
        try:
            resp = iface.query_goods2spu(
                strategy_id=args.strategy_id,
                page=args.page,
                page_size=args.page_size,
                swimlane=args.swimlane,
            )
        except Exception as e:
            print(f"\n❌ 查询失败: {e}", file=sys.stderr)
            sys.exit(1)

        # 从响应中提取套餐列表
        # resp 结构：{"code":200, "data": "<json string>", ...}
        # 内层 json 结构：{"code":10000, "data": {"transferResult":[...]}}
        def _extract_records(r: dict) -> list:
            layer = r
            for _ in range(3):  # 最多解包 3 层
                if isinstance(layer, str):
                    try:
                        layer = json.loads(layer)
                    except Exception:
                        break
                if isinstance(layer, dict):
                    if "transferResult" in layer:
                        return layer["transferResult"]
                    # 继续往下找 "data"
                    layer = layer.get("data") or {}
            return []

        records = _extract_records(resp)

        # 过滤有效套餐
        valid = [r for r in records if r.get("spuId") and r.get("spuId") != 0 and r.get("status") == 1]

        if valid:
            print(f"\n{'=' * 60}")
            print(f"  ✅ 找到 {len(valid)} 个有效套餐（status=1）")
            print(f"{'=' * 60}")
            for r in valid:
                print(f"  spuId      : {r.get('spuId')}")
                print(f"  goodsId    : {r.get('goodsId')}")
                print(f"  status     : {r.get('status')}")
                print(f"  strategyId : {r.get('strategyId')}")
                print("  ─" * 30)
            print(f"\n  🎯 房转套餐 spuId = {valid[0].get('spuId')}")
            print(f"{'=' * 60}")
            return

        if records:
            print(f"  第{attempt}次：查到 {len(records)} 条记录但无有效套餐（status≠1 或 spuId=0）")
        else:
            print(f"  第{attempt}次：暂无记录（套餐正在生成中...）")

        if attempt < max_attempts:
            print(f"  {interval} 秒后重试...")
            time.sleep(interval)

    print(f"\n⚠️  {max_attempts * interval} 秒内未查到有效套餐，请稍后手动重试：")
    print(f"  python3 factory/hub-strategy/query-spu.py --strategy-id {args.strategy_id}")
    print(f"\n  原始响应：\n{json.dumps(resp, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()

