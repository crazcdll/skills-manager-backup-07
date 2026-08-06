#!/usr/bin/env python3
"""
基础实体 - 供应商门店资质审核

工具：工具498（供应商门店资质审核）
协议：HTTP POST DataUnity
接口：供应商门店资质审核

使用方式：
  # 对指定门店进行资质审核（通过）
  python3 audit-poi-qualification.py --poi-id 1085918666109517

  # 仅打印参数
  python3 audit-poi-qualification.py --poi-id 123 --dry-run
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
call_audit_poi_qualification = _iface.call_audit_poi_qualification

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 498


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具498 - 供应商门店资质审核

【说明】
  供应商绑定门店后，对门店进行资质审核（通过）
  此步骤是上单的必要前置，必须在创建商品前完成

【必填参数】
  --poi-id <poiId>
      门店ID（mtPoiId）

【可选参数】
  --audit-type <类型>
      审核类型
      默认值：供应商门店资质审核（固定，不建议修改）

  --audit-result <结果>
      审核结果
      默认值：通过（固定，不建议修改）

  --dry-run
      仅打印参数，不实际执行

【输出】
  审核结果

【使用示例】
  python3 factory/infra/audit-poi-qualification.py --poi-id 1085927256096396""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="供应商门店资质审核（工具498）")
    parser.add_argument("--poi-id", required=True, help="门店ID（mtPoiId）")
    parser.add_argument("--audit-type", default="供应商门店资质审核",
                        help="审核类型（默认：供应商门店资质审核）")
    parser.add_argument("--audit-result", default="通过",
                        help="审核结果（默认：通过）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    print(f"=== 供应商门店资质审核（工具{TOOL_ID}）===")
    print(f"  门店ID      : {args.poi_id}")
    print(f"  审核类型    : {args.audit_type}")
    print(f"  审核结果    : {args.audit_result}")

    resp = call_audit_poi_qualification(
        poi_id=args.poi_id,
        audit_type=args.audit_type,
        audit_result=args.audit_result,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "供应商门店资质审核")

    print(f"\n✅ 供应商门店资质审核成功")
    print(f"  门店ID     : {args.poi_id}")
    print(f"  审核结果   : {args.audit_result}")


if __name__ == "__main__":
    main()

