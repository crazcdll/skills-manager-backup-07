#!/usr/bin/env python3
"""
基础实体 - 门店私海认领

工具：工具534（门店私海认领）
协议：HTTP POST DataUnity
接口：门店私海认领

将门店从私海认领到指定 EmpId（默认 crstest=2196240）。

使用方式：
  # 认领单个门店（默认 empId=2196240）
  python3 claim-poi.py --poi-id 1085918666109517

  # 仅打印参数
  python3 claim-poi.py --poi-id 123 --dry-run
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
call_claim_poi = _iface.call_claim_poi

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 534


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具534 - 门店私海认领

【说明】
  将门店从私海认领到指定 EmpId（crstest=2196240）
  是供应商绑定门店（工具777）的前置步骤

【必填参数】
  --poi-id <poiId>
      门店ID（create-poi.py 输出的 mtPoiId）

【可选参数】
  --emp-id <EmpId>
      认领人 EmpId
      默认值：2196240（crstest），不建议修改

  --dry-run
      仅打印参数，不实际执行

【输出】
  认领结果（成功/失败）

【使用示例】
  python3 factory/infra/claim-poi.py --poi-id 1085927256096396""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="门店私海认领（工具534）")
    parser.add_argument("--poi-id", required=True, help="门店ID（mtPoiId）")
    parser.add_argument("--emp-id", default="2196240",
                        help="认领人EmpId（默认：2196240=crstest）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    print(f"=== 门店私海认领（工具{TOOL_ID}）===")
    print(f"  门店ID  : {args.poi_id}")
    print(f"  EmpId   : {args.emp_id}")

    resp = call_claim_poi(
        poi_id=args.poi_id,
        emp_id=args.emp_id,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "门店私海认领")

    print(f"\n✅ 门店私海认领成功")
    print(f"  门店ID : {args.poi_id}")
    print(f"  EmpId  : {args.emp_id}")



if __name__ == "__main__":
    main()

