#!/usr/bin/env python3
"""
审核 - 非房商品 / 礼包审核（xGoods / gift）

非房和礼包底层走同一个 RPC 接口，合并在此脚本统一处理。

流程：
  直接调用 RPC 接口完成审核：
  appkey : com.sankuai.qatool.productmanage
  service: com.meituan.nibqa.tdm.api.service.ProductMakeService
  method : auditProduct

参数：
  configKey : "xGoods"（固定）
  xgoodsId  : 非房商品ID / 礼包对应的非房商品ID（必填）
  partnerId : 供应商ID（必填）
  shopId    : 门店ID（必填）

使用方式：
  # 非房审核
  python3 factory/audit/gift/audit.py --xgoods-id 2254524687 --partner-id 4553812 --shop-id 67101

  # 礼包审核（参数相同）
  python3 factory/audit/gift/audit.py --xgoods-id 1046613 --partner-id 4553812 --shop-id 67101

  # dry-run（只打印不执行）
  python3 factory/audit/gift/audit.py --xgoods-id 2254524687 --partner-id 4553812 --shop-id 67101 --dry-run
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from scripts.runner import invoke, InvokeError  # noqa


APPKEY   = "com.sankuai.qatool.productmanage"
SERVICE  = "com.meituan.nibqa.tdm.api.service.ProductMakeService"
METHOD   = "auditProduct"

FIXED_CONFIG_KEY = "xGoods"


def _show_schema():
    print("""=== 非房/礼包审核（audit/gift）参数说明 ===

【必填参数】
  --xgoods-id     INT    非房商品ID（非房）或礼包对应的非房商品ID（礼包）
  --partner-id    INT    供应商ID（partnerId）
  --shop-id       INT    门店ID（shopId / poiId）

【可选参数】
  --dry-run              只打印 RPC 参数，不实际调用

【审核方式】
  直接调用 RPC 接口（非房和礼包共用同一接口）：
    appkey : com.sankuai.qatool.productmanage
    service: ProductMakeService
    method : auditProduct
  无需 BPM Cookie，无需浏览器，一步完成。

【固定参数】
  configKey = "xGoods"

【使用示例】
  # 非房审核
  python3 factory/audit/gift/audit.py --xgoods-id 2254524687 --partner-id 4553812 --shop-id 67101

  # 礼包审核
  python3 factory/audit/gift/audit.py --xgoods-id 1046613 --partner-id 4553812 --shop-id 67101

  # dry-run
  python3 factory/audit/gift/audit.py --xgoods-id 2254524687 --partner-id 4553812 --shop-id 67101 --dry-run
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="酒店非房/礼包审核（直接 RPC 方式）")
    parser.add_argument("--xgoods-id",  required=True, type=int,
                        help="非房商品ID 或 礼包对应的非房商品ID（整型）")
    parser.add_argument("--partner-id", required=True, type=int, help="供应商ID（partnerId，整型）")
    parser.add_argument("--shop-id",    required=True, type=int, help="门店ID（shopId，整型）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印 RPC 参数，不实际调用")
    args = parser.parse_args()

    # 构造 RPC 参数
    rpc_params = {
        "configKey": FIXED_CONFIG_KEY,
        "xgoodsId":  args.xgoods_id,
        "partnerId": args.partner_id,
        "shopId":    args.shop_id,
    }

    print("=" * 60, file=sys.stderr)
    print(f"  酒店非房/礼包审核 - 直接 RPC 方式", file=sys.stderr)
    print(f"  xgoodsId : {args.xgoods_id}", file=sys.stderr)
    print(f"  partnerId: {args.partner_id}", file=sys.stderr)
    print(f"  shopId   : {args.shop_id}", file=sys.stderr)
    print(f"  appkey   : {APPKEY}", file=sys.stderr)
    print(f"  service  : {SERVICE}", file=sys.stderr)
    print(f"  method   : {METHOD}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # ---- 调用 RPC ----
    try:
        result = invoke(
            appkey=APPKEY,
            service=SERVICE,
            method=METHOD,
            params=rpc_params,
            dry_run=args.dry_run,
            progress_hint=f"非房/礼包审核 xgoodsId={args.xgoods_id}",
        )
    except InvokeError as e:
        print(f"\n[FAIL] 审核失败: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] RPC 调用异常: {e}", file=sys.stderr)
        sys.exit(1)

    # ---- 输出结构化结果 ----
    output = {
        "xgoodsId":  args.xgoods_id,
        "partnerId": args.partner_id,
        "shopId":    args.shop_id,
        "rpcResult": result,
    }
    print(json.dumps(output, ensure_ascii=False))

    print("\n" + "=" * 60, file=sys.stderr)
    if args.dry_run:
        print("  [dry-run] 未实际执行", file=sys.stderr)
    else:
        print(f"  审核完成 ✓", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  xgoodsId  : {args.xgoods_id}", file=sys.stderr)
    print(f"  partnerId : {args.partner_id}", file=sys.stderr)
    print(f"  shopId    : {args.shop_id}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()

