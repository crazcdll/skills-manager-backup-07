#!/usr/bin/env python3
"""
运维操作 - 批量上线 / 下线商品

接口：MeGoodsFacade#batchOnlineSwitch
协议：Thrift RPC
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade
method：batchOnlineSwitch

对应前端请求：
  POST /api/gw/v1/product/goods/batchOnlineSwitch
  body: {"partnerId":4550589,"poiId":"1085927256096396","goodsIds":[600000632131],"status":2}

status 枚举：
  2 - 上线（恢复上线/发布上线）
  3 - 下线

使用方式：
  # 上线单个商品
  python3 online-switch.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000632131 --status 2

  # 上线多个商品
  python3 online-switch.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000632131 600000632132 --status 2

  # 下线商品
  python3 online-switch.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000632131 --status 3

  # 仅打印参数不执行（dry-run）
  python3 online-switch.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000632131 --status 2 --dry-run
"""

import argparse
import importlib.util as ilu
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
call_online_switch  = _iface.call_online_switch
SWITCH_STATUS_DESC  = _iface.SWITCH_STATUS_DESC


def _show_schema():
    print("""=== 批量上线/下线商品（online-switch）参数说明 ===

【必填参数】
  --partner-id    INT    供应商ID（partnerId）
  --poi-id        STR    门店ID（poiId，字符串格式）
  --goods-ids     INT+   商品ID列表，空格分隔，如：600000632131 600000632132
  --status        INT    操作类型（枚举见下）

【status 枚举】
  2  上线（恢复上线 / 发布上线）
  3  下线

【可选参数】
  --swimlane      STR    泳道名称（不传=主干）
  --dry-run              仅打印参数，不执行

【注意事项】
  ⚠️ 上线时商品必须有库存（最近90天内至少30天同时有价格和库存），
     否则报错"最近90天内至少30天同时有价格和库存"。
     此时需先运行 factory/inventory/update-inventory.py 开房并设置库存。
  ⚠️ 对应前端请求：POST /api/gw/v1/product/goods/batchOnlineSwitch

【使用示例】
  # 上线单个商品
  python3 factory/ops/online-switch.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000632131 --status 2

  # 批量上线多个商品
  python3 factory/ops/online-switch.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000632131 600000632132 --status 2

  # 下线商品
  python3 factory/ops/online-switch.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000632131 --status 3
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="批量上线 / 下线商品（MeGoodsFacade#batchOnlineSwitch）")
    parser.add_argument("--partner-id", required=True, type=int, help="供应商ID（partnerId）")
    parser.add_argument("--poi-id",     required=True,            help="门店ID（poiId，字符串）")
    parser.add_argument("--goods-ids",  required=True, type=int, nargs="+",
                        help="商品ID列表，空格分隔，如 600000632131 600000632132")
    parser.add_argument("--status",     required=True, type=int, choices=[2, 3],
                        help="2=上线，3=下线")
    parser.add_argument("--swimlane",   default="", help="泳道（默认主干）")
    parser.add_argument("--dry-run",    action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    label = SWITCH_STATUS_DESC.get(args.status, str(args.status))

    print(f"=== 批量{label}商品（batchOnlineSwitch）===")
    print(f"  partnerId : {args.partner_id}")
    print(f"  poiId     : {args.poi_id}")
    print(f"  goodsIds  : {args.goods_ids}")
    print(f"  status    : {args.status}（{label}）")
    print(f"  swimlane  : {args.swimlane or '主干'}")

    resp = call_online_switch(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        goods_ids=args.goods_ids,
        status=args.status,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    # 判断结果：外层 success=true 只表示接口调用无异常，业务结果在 data 内
    import json as _json
    print(f"\n原始返回：\n{_json.dumps(resp, ensure_ascii=False, indent=2)}")

    data = resp.get("data") or {}
    success_count = data.get("successCount", 0)
    fail_count    = data.get("failCount", 0)
    details       = data.get("details") or []

    if fail_count > 0 or success_count == 0:
        print(f"\n❌ 批量{label}失败（successCount={success_count}, failCount={fail_count}）", file=sys.stderr)
        for d in details:
            gid    = d.get("goodsId", "?")
            name   = d.get("goodsName", "")
            reason = d.get("reason", "")
            code   = d.get("code", "")
            print(f"  goodsId={gid}  name={name}  code={code}  reason={reason}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅ 批量{label}成功（successCount={success_count}）")
    for d in details:
        print(f"  goodsId={d.get('goodsId')}  {d.get('goodsName', '')}")


if __name__ == "__main__":
    main()

