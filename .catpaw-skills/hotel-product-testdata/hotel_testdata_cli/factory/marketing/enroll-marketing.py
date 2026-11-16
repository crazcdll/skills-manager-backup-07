#!/usr/bin/env python3
"""
营销运营 - 生意助手/全域通报名

工具：工具1037（ProductMakeService.createProductAsync）
协议：Thrift via DataUnity（异步）
前置：供应商+门店已存在（方式一），或产品ID已知（方式二）

configKey 枚举：
  notUpscale                 生意助手（仅生意助手，不上全域通）
  upscaleFixed               全域通一口价（最常用）
  upscaleDiscount            全域通折扣
  upscaleFixedDiscountMixed  全域通一口价折扣混合

两种报名方式（互斥）：
  方式一：供应商+门店报名（新建Goods报名）
  方式二：指定产品ID报名（对已有产品报名）

⚠️ 工具1037为异步接口，结果由【供应链商品测试数据助手】大象推送。

使用方式：
  # 方式一：供应商+门店报名全域通一口价（最常用）
  python3 enroll-marketing.py \
      --mode 1 \
      --partner-id 4549232 \
      --poi-id 1085918666100285 \
      --config-key upscaleFixed

  # 方式一：报名生意助手
  python3 enroll-marketing.py \
      --mode 1 \
      --partner-id 4549232 --poi-id 1085918666100285 \
      --config-key notUpscale

  # 方式二：指定产品ID报名
  python3 enroll-marketing.py \
      --mode 2 \
      --product-id 2205278640 \
      --config-key upscaleFixed

  # 查看字段说明
  python3 enroll-marketing.py --show-schema

  # 仅打印参数不执行
  python3 enroll-marketing.py --mode 1 \
      --partner-id 123 --poi-id 456 --dry-run
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
        "marketing_interface",
        os.path.join(ROOT, "interface/marketing/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_iface = _load_interface()
interface_call  = _iface.call
CONFIG_KEY_DESC = _iface.CONFIG_KEY_DESC

from scripts.du_runner import get_result, get_status  # noqa
from scripts.utils import get_operator  # noqa


def _show_schema():
    print("""=== 生意助手/全域通报名参数说明 ===

工具：工具1037（ProductMakeService.createProductAsync）⚠️ 异步接口

【configKey 枚举（必填）】
  notUpscale                  生意助手（仅生意助手，不含全域通）
  upscaleFixed                全域通一口价（最常用）
  upscaleDiscount             全域通折扣
  upscaleFixedDiscountMixed   全域通一口价折扣混合

【两种报名方式（二选一）】
  方式一：指定供应商+门店（新建 Goods 报名）
    --partner-id    STR  [必填]  供应商ID
    --poi-id        STR  [必填]  门店ID

  方式二：指定已有产品报名
    --product-id    STR  [必填]  产品ID（境内全日房商品ID）

【公共必填参数】
  --config-key    STR  报名类型（见上方枚举）

【使用示例】
  # 方式一：供应商+门店报名全域通一口价
  python3 factory/marketing/enroll-marketing.py \\
    --config-key upscaleFixed \\
    --partner-id 4549232 --poi-id 1085918666100285

  # 方式二：对已有产品报名生意助手
  python3 factory/marketing/enroll-marketing.py \\
    --config-key notUpscale \\
    --product-id 2205278640
""")


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="生意助手/全域通报名")
    parser.add_argument("--mode", required=True, choices=["1", "2"],
                        help="报名方式：1=供应商+门店, 2=指定产品ID")
    parser.add_argument("--config-key", default="upscaleFixed",
                        choices=list(CONFIG_KEY_DESC.keys()),
                        help="报名类型（默认 upscaleFixed=全域通一口价）")
    # 方式一参数
    parser.add_argument("--partner-id", default=None, help="[方式一] 供应商ID")
    parser.add_argument("--poi-id", default=None, help="[方式一] 门店ID")
    # 方式二参数
    parser.add_argument("--product-id", default=None, help="[方式二] 产品ID")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    operator = get_operator()
    config_label = CONFIG_KEY_DESC.get(args.config_key, args.config_key)

    # 参数校验
    if args.mode == "1":
        if not args.partner_id or not args.poi_id:
            print("[ERROR] 方式一必须传 --partner-id 和 --poi-id", file=sys.stderr)
            sys.exit(1)
        print(f"=== 生意助手/全域通报名（方式一：供应商+门店）工具1037 ===")
        print(f"  partnerId : {args.partner_id}")
        print(f"  poiId     : {args.poi_id}")
        print(f"  configKey : {args.config_key}（{config_label}）")
    else:
        if not args.product_id:
            print("[ERROR] 方式二必须传 --product-id", file=sys.stderr)
            sys.exit(1)
        print(f"=== 生意助手/全域通报名（方式二：产品ID）工具1037 ===")
        print(f"  productId : {args.product_id}")
        print(f"  configKey : {args.config_key}（{config_label}）")

    print(f"  ⚠️  异步接口，报名结果将由大象推送")

    resp = interface_call(
        mode=int(args.mode),
        config_key=args.config_key,
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        product_id=args.product_id,
        mis=operator,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    st  = get_status(resp)
    err = get_result(resp, "DATA_UNITY_EXECUTE_ERROR_MESSAGE") or ""
    raw = get_result(resp, "返回值") or ""

    if st == 2 or "失败" in err:
        print(f"\n[ERROR] 报名失败: {err}")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(f"\n✅ 报名成功，结果将由【供应链商品测试数据助手】通过大象推送")
    print(f"\n{'='*50}")
    print(f"  📋 构造结果汇总（营销报名）")
    print(f"{'='*50}")
    if args.mode == "1":
        print(f"  方式     : 供应商+门店")
        print(f"  partnerId: {args.partner_id}")
        print(f"  poiId    : {args.poi_id}")
    else:
        print(f"  方式     : 指定产品")
        print(f"  productId: {args.product_id}")
    print(f"  configKey: {args.config_key}（{config_label}）")
    print(f"  返回值   : {raw}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

