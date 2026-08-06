#!/usr/bin/env python3
"""
基础实体 - 供应商绑定门店

工具：工具777（供应商绑定门店）
协议：HTTP POST DataUnity
接口：供应商绑定门店

将供应商与门店进行绑定，绑定类型固定为"供应商ID"。

使用方式：
  # 绑定供应商与门店
  python3 bind-partner-poi.py --poi-id 1085918666109517 --partner-id 4553737

  # 仅打印参数
  python3 bind-partner-poi.py --poi-id 123 --partner-id 456 --dry-run
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
call_bind_partner_poi = _iface.call_bind_partner_poi

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 777


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具777 - 供应商绑定门店

【说明】
  将供应商与门店进行绑定（绑定类型：供应商ID）

【必填参数】
  --poi-id <poiId>
      美团门店ID（create-poi.py 输出的 mtPoiId）

  --partner-id <partnerId>
      供应商ID（create-partner.py 输出的 partnerId）

【可选参数】
  --dry-run
      仅打印参数，不实际执行

【输出】
  绑定结果（成功/失败）


【使用示例】
  python3 factory/infra/bind-partner-poi.py \\
    --poi-id 1085927256096396 --partner-id 4553737""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="供应商绑定门店（工具777）")
    parser.add_argument("--poi-id", required=True, help="美团门店ID（mtPoiId）")
    parser.add_argument("--partner-id", required=True, help="供应商ID（partnerId）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    print(f"=== 供应商绑定门店（工具{TOOL_ID}）===")
    print(f"  美团门店ID  : {args.poi_id}")
    print(f"  供应商ID    : {args.partner_id}")
    print(f"  绑定类型    : 供应商ID（固定）")

    resp = call_bind_partner_poi(
        poi_id=args.poi_id,
        partner_id=args.partner_id,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "供应商绑定门店")

    print(f"\n✅ 供应商绑定门店成功")
    print(f"  门店ID     : {args.poi_id}")
    print(f"  供应商ID   : {args.partner_id}")


if __name__ == "__main__":
    main()

