#!/usr/bin/env python3
"""
基础实体 - 价格模式切换（底价/卖价）

工具：工具906（境内，切换合同价格模式）/ 工具928（境外，切换境外门店价格模式）
协议：HTTP POST DataUnity

价格模式枚举：
  境内（工具906）：
    BASE_PRICE    = 底价模式
    SELLING_PRICE = 卖价模式（默认，通常不需要主动切换）

  境外（工具928）：
    2 = 底价/结算价佣金率
    1 = 卖价/美团价佣金率

使用方式：
  # 境内切换为底价模式
  python3 switch-price-mode.py --contract-id 18127845 --mode BASE_PRICE

  # 境内切换为卖价模式
  python3 switch-price-mode.py --contract-id 18127845 --mode SELLING_PRICE

  # 境外切换为底价模式
  python3 switch-price-mode.py --overseas --partner-id 4553737 --poi-id 123 --mode 2

  # 境外切换为卖价模式
  python3 switch-price-mode.py --overseas --partner-id 4553737 --poi-id 123 --mode 1

  # 仅打印参数
  python3 switch-price-mode.py --contract-id 18127845 --mode BASE_PRICE --dry-run
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
        "infra_interface",
        os.path.join(ROOT, "interface/infra/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
call_switch_price_mode  = _iface.call_switch_price_mode
PRICE_MODE_BASE_PRICE   = _iface.PRICE_MODE_BASE_PRICE
PRICE_MODE_SELLING      = _iface.PRICE_MODE_SELLING

from scripts.du_runner import check_ok  # noqa

TOOL_ID_DOMESTIC = 906
TOOL_ID_OVERSEAS = 928


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""价格模式切换（工具906境内 / 工具928境外）

【说明】
  工具49创建供应商后默认卖价模式，按需切换底价/卖价
  境内使用工具906，境外使用工具928

【境内参数（工具906，不加 --overseas）】
  --contract-id <platformContractId>  必填，create-partner.py 返回的 platformContractId
  --mode <模式>                        必填
      BASE_PRICE    = 底价模式
      SELLING_PRICE = 卖价模式（默认，通常不需主动切换）
  --pricing-power <值>                 可选
  --switch-status-enum <值>            可选

【境外参数（工具928，加 --overseas）】
  --overseas                           Flag，加上则使用工具928境外版本
  --partner-id <partnerId>             必填，供应商ID
  --poi-id <poiId>                     必填，门店ID
  --mode <模式>                        必填
      2 = 底价/结算价佣金率
      1 = 卖价/美团价佣金率

【通用参数】
  --dry-run   仅打印参数，不实际执行

【注意事项】
  ⚠️  用户未提及价格模式时，不要调用本脚本，保持默认卖价
  ⚠️  境外不支持 prepayPriceChangeMode（无卖价参数），用 --mode 1/2

【使用示例】
  # 境内底价
  python3 factory/infra/switch-price-mode.py --contract-id 18127845 --mode BASE_PRICE
  # 境外底价
  python3 factory/infra/switch-price-mode.py --overseas --partner-id 4553737 --poi-id 123 --mode 2""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="价格模式切换（工具906境内/工具928境外）")
    parser.add_argument("--overseas", action="store_true", help="境外（使用工具928）")
    parser.add_argument("--mode", required=True,
                        help="价格模式（境内：BASE_PRICE/SELLING_PRICE；境外：1=卖价/2=底价）")
    # 境内参数
    parser.add_argument("--contract-id", default=None,
                        help="platformContractId（境内必填）")
    parser.add_argument("--pricing-power", default=None,
                        help="pricingPower（境内可选）")
    parser.add_argument("--switch-status-enum", default=None,
                        help="switchStatusEnum（境内可选）")
    # 境外参数
    parser.add_argument("--partner-id", default=None,
                        help="供应商ID（境外必填）")
    parser.add_argument("--poi-id", default=None,
                        help="门店ID（境外必填）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    is_overseas = args.overseas
    tool_id = TOOL_ID_OVERSEAS if is_overseas else TOOL_ID_DOMESTIC

    if is_overseas:
        # 境外参数校验
        if not args.partner_id or not args.poi_id:
            print("[ERROR] 境外模式必须提供 --partner-id 和 --poi-id", file=sys.stderr)
            sys.exit(1)
        mode_desc = "底价/结算价佣金率" if args.mode == "2" else "卖价/美团价佣金率"
        print(f"=== 切换境外门店价格模式（工具{tool_id}）===")
        print(f"  供应商ID    : {args.partner_id}")
        print(f"  门店ID      : {args.poi_id}")
        print(f"  目标模式    : {args.mode}（{mode_desc}）")
    else:
        # 境内参数校验
        if not args.contract_id:
            print("[ERROR] 境内模式必须提供 --contract-id（platformContractId）", file=sys.stderr)
            sys.exit(1)
        mode_desc = "底价" if args.mode == PRICE_MODE_BASE_PRICE else "卖价"
        print(f"=== 切换合同价格模式（工具{tool_id}）===")
        print(f"  platformContractId : {args.contract_id}")
        print(f"  目标模式           : {args.mode}（{mode_desc}）")
        if args.pricing_power:
            print(f"  pricingPower       : {args.pricing_power}")
        if args.switch_status_enum:
            print(f"  switchStatusEnum   : {args.switch_status_enum}")

    resp = call_switch_price_mode(
        mode=args.mode,
        is_overseas=is_overseas,
        contract_id=args.contract_id,
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        pricing_power=args.pricing_power,
        switch_status_enum=args.switch_status_enum,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "价格模式切换")

    if is_overseas:
        mode_desc = "底价/结算价佣金率" if args.mode == "2" else "卖价/美团价佣金率"
        print(f"\n✅ 境外门店价格模式切换成功")
        print(f"  供应商ID   : {args.partner_id}")
        print(f"  门店ID     : {args.poi_id}")
        print(f"  当前模式   : {args.mode}（{mode_desc}）")
    else:
        mode_desc = "底价" if args.mode == PRICE_MODE_BASE_PRICE else "卖价"
        print(f"\n✅ 合同价格模式切换成功")
        print(f"  platformContractId : {args.contract_id}")
        print(f"  当前模式           : {args.mode}（{mode_desc}）")


if __name__ == "__main__":
    main()

