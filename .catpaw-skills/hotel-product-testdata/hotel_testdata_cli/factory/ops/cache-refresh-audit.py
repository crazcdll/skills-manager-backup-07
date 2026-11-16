#!/usr/bin/env python3
"""
运维操作 - 缓存刷新 / 改价审核

工具：工具1031（HotelCacheUpdateOrPriceAuditService.cacheUpdateOrPriceAudit）
协议：Thrift via DataUnity
支持操作：
  1 - 缓存刷新（商品/SPU/门店/货盘）
  2 - BD改价审核（通过/驳回）
  3 - 商家改价审核（通过/驳回）

使用方式：
  # 缓存刷新 - 商品级别
  python3 cache-refresh-audit.py --op 1 --product-id 2205278640

  # 缓存刷新 - SPU级别（套餐/超团）
  python3 cache-refresh-audit.py --op 1 --spu-id 8426522

  # 缓存刷新 - 门店级别
  python3 cache-refresh-audit.py --op 1 --poi-id 1085918666109517

  # 缓存刷新 - 货盘级别
  python3 cache-refresh-audit.py --op 1 --rp-id 12345

  # BD改价审核 - 通过
  python3 cache-refresh-audit.py --op 2 --product-id 2205278640 --audit-status 3

  # BD改价审核 - 驳回
  python3 cache-refresh-audit.py --op 2 --product-id 2205278640 --audit-status 2

  # 商家改价审核 - 通过
  python3 cache-refresh-audit.py --op 3 --product-id 2205278640

  # 境外缓存刷新
  python3 cache-refresh-audit.py --op 1 --product-id 2205278640 --overseas

  # 查看字段说明
  python3 cache-refresh-audit.py --show-schema

  # 仅打印参数不执行
  python3 cache-refresh-audit.py --op 1 --product-id 123 --dry-run
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
        "ops_interface",
        os.path.join(ROOT, "interface/ops/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_iface = _load_interface()
interface_call     = _iface.call
OP_DESC            = _iface.OP_DESC
AUDIT_STATUS_DESC  = _iface.AUDIT_STATUS_DESC

from scripts.du_runner import get_result, check_ok  # noqa
from scripts.utils import get_operator  # noqa

TOOL_ID = 1031


def _show_schema():
    print("""=== 缓存刷新/改价审核参数说明 ===

工具：工具1031（HotelCacheUpdateOrPriceAuditService.cacheUpdateOrPriceAudit）

【必填参数】
  --operation-type  INT    操作类型
      1 = 缓存刷新（商品/SPU/门店/货盘）
      2 = BD 改价审核（通过或驳回）
      3 = 商家改价审核（通过或驳回）

【目标ID（四选一，根据操作对象传入）】
  --product-id  INT    商品ID（productId/goodsId），缓存刷新商品/改价审核
  --spu-id      INT    SPU ID（套餐/超团），SPU 级别操作
  --poi-id      INT    门店ID，门店级别缓存刷新
  --rp-id       INT    货盘RPID（突破规则ID），货盘级别刷新

【审核参数（operationType=2/3 时必填）】
  --audit-status  INT  2=审核驳回  3=审核通过（默认3）

【可选参数】
  --oversea            境外模式（不传=境内）
  --dry-run            仅打印参数，不执行

【使用示例】
  # 刷新商品缓存
  python3 factory/ops/cache-refresh-audit.py --operation-type 1 --product-id 2205278640

  # 刷新门店缓存
  python3 factory/ops/cache-refresh-audit.py --operation-type 1 --poi-id 1085918666109517

  # BD 改价通过
  python3 factory/ops/cache-refresh-audit.py --operation-type 2 --product-id 2205278640 --audit-status 3

  # SPU 缓存刷新（套餐/超团）
  python3 factory/ops/cache-refresh-audit.py --operation-type 1 --spu-id 8426522
""")


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="缓存刷新 / 改价审核（工具1031）")
    parser.add_argument("--op", required=True, type=int, choices=[1, 2, 3],
                        help="操作类型：1=缓存刷新, 2=BD改价审核, 3=商家改价审核")
    parser.add_argument("--product-id", default=None, type=int, help="商品ID")
    parser.add_argument("--spu-id", default=None, type=int, help="SPU ID（超团/套餐）")
    parser.add_argument("--poi-id", default=None, type=int, help="门店ID")
    parser.add_argument("--rp-id", default=None, type=int, help="货盘RPID")
    parser.add_argument("--audit-status", default=3, type=int, choices=[2, 3],
                        help="审核状态（op=2/3时用）：2=驳回, 3=通过（默认3）")
    parser.add_argument("--overseas", action="store_true", help="境外（缓存刷新时生效）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    # 校验：至少传一个目标ID
    if not any([args.product_id, args.spu_id, args.poi_id, args.rp_id]):
        print("[ERROR] 必须传 --product-id / --spu-id / --poi-id / --rp-id 之一",
              file=sys.stderr)
        sys.exit(1)

    op_label = OP_DESC.get(args.op, str(args.op))
    audit_label = AUDIT_STATUS_DESC.get(args.audit_status, str(args.audit_status))

    print(f"=== {op_label}（工具{TOOL_ID}）===")
    if args.product_id:
        print(f"  productId    : {args.product_id}")
    if args.spu_id:
        print(f"  spuId        : {args.spu_id}")
    if args.poi_id:
        print(f"  poiId        : {args.poi_id}")
    if args.rp_id:
        print(f"  rpId         : {args.rp_id}")
    print(f"  operationType: {args.op}（{op_label}）")
    if args.op in (2, 3):
        print(f"  auditStatus  : {args.audit_status}（{audit_label}）")
    if args.op == 1:
        print(f"  isOversea    : {args.overseas}")

    resp = interface_call(
        operation_type=args.op,
        product_id=args.product_id,
        spu_id=args.spu_id,
        poi_id=args.poi_id,
        rp_id=args.rp_id,
        audit_status=args.audit_status,
        is_oversea=args.overseas,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, op_label)
    raw = get_result(resp, "返回值") or ""

    print(f"\n✅ {op_label}完成")
    print(f"  操作类型 : {args.op}（{op_label}）")
    if args.op in (2, 3):
        print(f"  审核结果 : {args.audit_status}（{audit_label}）")
    print(f"  返回值   : {raw}")


if __name__ == "__main__":
    main()

