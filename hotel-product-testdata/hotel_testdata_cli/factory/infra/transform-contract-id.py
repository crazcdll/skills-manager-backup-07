#!/usr/bin/env python3
"""
基础实体 - 合同ID互查

工具：工具465（客户平台_合同ID互查）
协议：HTTP GET DataUnity
接口：业务合同ID（originalContractId）与平台合同ID（platformContractId）双向互查
      同时返回合同编号字符串（contractNumber，如 ZSFW-A9-75178816）

使用方式：
  # 用 platformContractId 查 originalContractId + contractNumber（合同编号字符串）
  python3 transform-contract-id.py --platform-contract-id 18127845

  # 用 originalContractId（业务合同ID）反查 platformContractId + contractNumber
  python3 transform-contract-id.py --original-contract-id 12345678

  # 仅打印参数
  python3 transform-contract-id.py --platform-contract-id 18127845 --dry-run
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
        "infra_interface",
        os.path.join(ROOT, "interface/infra/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
call_transform_contract_id = _iface.call_transform_contract_id

from scripts.du_runner import get_result, check_ok  # noqa

TOOL_ID = 465


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具465 - 合同ID互查

【说明】
  业务合同ID（originalContractId）与平台合同ID（platformContractId）双向互查
  同时返回合同编号字符串（contractNumber，如 ZSFW-A9-75178816）
  两个 ID 参数二选一传入，查询对应的另一个

【参数（二选一传）】
  --platform-contract-id <platformContractId>
      平台合同ID（工具49创建供应商返回的 platformContractId，数字格式）

  --original-contract-id <originalContractId>
      业务合同ID（反查时使用）

【可选参数】
  --biz-line <业务线>
      默认：3（住宿）
      枚举：1=到餐, 2=到综, 3=住宿, 4=门票
      ⚠️ 此 bizLine 是工具465内部枚举，与 DataUnity bizLine=20 不同

  --dry-run
      仅打印参数，不实际执行

【输出】
  平台合同ID  - platformContractId（数字）
  合同编号    - contractNumber（字符串，如 ZSFW-A9-75178816，全日房/钟点房上单用此值）
  客户合同ID  - originalContractId（业务合同ID）

【使用示例】
  # platformContractId → contractNumber（合同编号字符串）
  python3 factory/infra/transform-contract-id.py --platform-contract-id 18127845

  # originalContractId → platformContractId + contractNumber
  python3 factory/infra/transform-contract-id.py --original-contract-id 12345678""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="合同ID互查（工具465）")
    parser.add_argument("--platform-contract-id", default=None,
                        help="平台合同ID（工具49返回的 platformContractId），与 --original-contract-id 二选一")
    parser.add_argument("--original-contract-id", default=None,
                        help="业务合同ID，与 --platform-contract-id 二选一")
    parser.add_argument("--biz-line", default="3",
                        help="业务线（默认：3=住宿；枚举：1=到餐,2=到综,3=住宿,4=门票）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    if not args.platform_contract_id and not args.original_contract_id:
        print("[ERROR] --platform-contract-id 和 --original-contract-id 至少填写一个",
              file=sys.stderr)
        sys.exit(1)

    biz_line_map = {"1": "到餐", "2": "到综", "3": "住宿", "4": "门票"}
    biz_label = biz_line_map.get(args.biz_line, args.biz_line)

    print(f"=== 合同ID互查（工具{TOOL_ID}）===")
    if args.platform_contract_id:
        print(f"  平台合同ID（platformContractId） : {args.platform_contract_id}")
    if args.original_contract_id:
        print(f"  业务合同ID（originalContractId） : {args.original_contract_id}")
    print(f"  业务线                           : {args.biz_line}（{biz_label}）")

    resp = call_transform_contract_id(
        original_contract_id_str=args.original_contract_id,
        platform_contract_id_str=args.platform_contract_id,
        biz_line=args.biz_line,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "合同ID互查")

    platform_id     = get_result(resp, "平台合同ID")
    contract_number = get_result(resp, "合同编号")
    original_id     = get_result(resp, "客户合同ID")

    print(f"\n✅ 合同ID互查成功")
    if platform_id:
        print(f"  platformContractId : {platform_id}")
    if contract_number:
        print(f"  contractNumber     : {contract_number}  ← 全日房/钟点房上单使用此值")
    if original_id:
        print(f"  originalContractId : {original_id}")


if __name__ == "__main__":
    main()

