#!/usr/bin/env python3
"""
基础实体 - 住宿门店资质添加

工具：工具476（住宿-门店资质添加）
协议：HTTP POST DataUnity
接口：POST http://datamanagement.nibcus.test.sankuai.com/api/hotel/poiSaveQualitification

使用方式：
  # 为指定门店添加资质
  python3 add-poi-qualification.py --poi-id 1085918666109517

  # 仅打印参数
  python3 add-poi-qualification.py --poi-id 123 --dry-run
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
call_add_poi_qualification = _iface.call_add_poi_qualification

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 476


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具476 - 住宿门店资质添加

【说明】
  为门店添加资质（住宿客户平台），使门店满足上单的资质要求。
  与工具498（供应商门店资质审核）不同，本工具是直接向门店写入资质数据，
  两者互相独立，按需分别执行。

【必填参数】
  --poi-id <poiId>
      门店ID（美团 mtPoiId）

【可选参数】
  --dry-run
      仅打印参数，不实际执行

【输出】
  接口返回值（response JSON）

【使用示例】
  python3 factory/infra/add-poi-qualification.py --poi-id 1085927256096396""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="住宿门店资质添加（工具476）")
    parser.add_argument("--poi-id",  required=True, help="门店ID（美团 mtPoiId）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    print(f"=== 住宿门店资质添加（工具{TOOL_ID}）===")
    print(f"  门店ID : {args.poi_id}")

    resp = call_add_poi_qualification(
        poi_id=args.poi_id,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "住宿门店资质添加")

    response_val = get_result(resp, "response")
    print(f"\n✅ 住宿门店资质添加成功")
    print(f"  门店ID  : {args.poi_id}")
    if response_val:
        print(f"  返回值  : {response_val}")


if __name__ == "__main__":
    main()

