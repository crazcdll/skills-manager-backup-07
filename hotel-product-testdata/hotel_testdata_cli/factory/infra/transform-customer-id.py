#!/usr/bin/env python3
"""
基础实体 - 客户ID互查

工具：工具464（客户ID互查）
协议：HTTP GET DataUnity
接口：业务客户ID（partnerId/originCustomerId）与平台客户ID（platformCustomerId）双向互查

使用方式：
  # 用 partnerId（业务客户ID）查 platformCustomerId
  python3 transform-customer-id.py --origin-customer-id 4553737

  # 用 platformCustomerId 反查 partnerId（业务客户ID）
  python3 transform-customer-id.py --platform-customer-id 18107422

  # 仅打印参数
  python3 transform-customer-id.py --origin-customer-id 4553737 --dry-run
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
call_transform_customer_id = _iface.call_transform_customer_id

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 464


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具464 - 客户ID互查

【说明】
  业务客户ID（partnerId/originCustomerId）与平台客户ID（platformCustomerId）双向互查
  两个 ID 参数二选一传入，查询对应的另一个

【参数（二选一传）】
  --origin-customer-id <partnerId>
      业务客户ID（工具49创建供应商返回的 partnerId）

  --platform-customer-id <platformCustomerId>
      平台客户ID（工具49创建供应商返回的 platformContractId 对应的客户ID）

【可选参数】
  --biz-line <业务线>
      默认：3（住宿）
      枚举：1=到餐, 2=到综, 3=住宿, 4=门票
      ⚠️ 此 bizLine 是工具464内部枚举，与 DataUnity bizLine=20 不同

  --dry-run
      仅打印参数，不实际执行

【输出】
  platformCustomerId - 平台客户ID
  originCustomerId   - 业务客户ID（partnerId）

【使用示例】
  # partnerId → platformCustomerId
  python3 factory/infra/transform-customer-id.py --origin-customer-id 4553737

  # platformCustomerId → partnerId
  python3 factory/infra/transform-customer-id.py --platform-customer-id 18107422""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="客户ID互查（工具464）")
    parser.add_argument("--origin-customer-id", default=None,
                        help="业务客户ID（partnerId），与 --platform-customer-id 二选一")
    parser.add_argument("--platform-customer-id", default=None,
                        help="平台客户ID，与 --origin-customer-id 二选一")
    parser.add_argument("--biz-line", default="3",
                        help="业务线（默认：3=住宿；枚举：1=到餐,2=到综,3=住宿,4=门票）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    if not args.origin_customer_id and not args.platform_customer_id:
        print("[ERROR] --origin-customer-id 和 --platform-customer-id 至少填写一个",
              file=sys.stderr)
        sys.exit(1)

    biz_line_map = {"1": "到餐", "2": "到综", "3": "住宿", "4": "门票"}
    biz_label = biz_line_map.get(args.biz_line, args.biz_line)

    print(f"=== 客户ID互查（工具{TOOL_ID}）===")
    if args.origin_customer_id:
        print(f"  业务客户ID（partnerId） : {args.origin_customer_id}")
    if args.platform_customer_id:
        print(f"  平台客户ID             : {args.platform_customer_id}")
    print(f"  业务线                 : {args.biz_line}（{biz_label}）")

    resp = call_transform_customer_id(
        origin_customer_id_str=args.origin_customer_id,
        platform_customer_id_str=args.platform_customer_id,
        biz_line=args.biz_line,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "客户ID互查")

    platform_id = get_result(resp, "platformCustomerId")
    origin_id   = get_result(resp, "originCustomerId")

    print(f"\n✅ 客户ID互查成功")
    if platform_id:
        print(f"  platformCustomerId : {platform_id}")
    if origin_id:
        print(f"  originCustomerId   : {origin_id}（partnerId）")


if __name__ == "__main__":
    main()

