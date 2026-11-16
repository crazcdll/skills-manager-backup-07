#!/usr/bin/env python3
"""
基础实体 - 查询原始合同编号（contractNo）

支持两种查询路径（二选一）：

路径A：根据供应商ID查询（工具584）
  → 入参：partnerId（业务客户ID）
  → 出参：合同编号列表，取第一条生效合同的 contractNo
  → 适用：用户只知道 partnerId，不在数据池时的兜底查询

路径B：根据平台合同ID查询（Thrift RPC）
  → 入参：platformContractId（工具49/create-partner.py 返回的数字）
  → 出参：contractNo 字符串
  → 适用：已有 platformContractId 的场景

使用方式：
  # 路径A：根据供应商ID查询（推荐，不需要 platformContractId）
  python3 factory/infra/query-contract.py --partner-id 4549866

  # 路径B：根据平台合同ID查询
  python3 factory/infra/query-contract.py --platform-contract-id 18127845

  # 指定泳道（仅路径B支持）
  python3 factory/infra/query-contract.py --platform-contract-id 18127845 --swimlane user-xxx

  # 仅打印参数，不执行
  python3 factory/infra/query-contract.py --partner-id 4549866 --dry-run
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
from typing import Optional

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
query_contract_no = _iface.query_contract_no
query_contract_by_partner_id = _iface.query_contract_by_partner_id


# ── 工具584 响应解析：提取第一条生效合同的 contractNo ─────────────────────────
#
# 真实 results 结构（来自抓包）：
#   [
#     {
#       "itemKey": "客户合同信息列表",
#       "itemType": "table",
#       "value": [
#         {
#           "number": "ZSFW-A9-80181637",   ← 合同编号
#           "id":     "18110975",
#           "status": "1",                  ← 1=正常生效
#           "name":   "住宿服务合同",
#           "type":   "预付合同",
#           ...
#         }
#       ]
#     },
#     {
#       "itemKey": "返回值_1",              ← 合同编号简单数组，最方便提取
#       "itemType": "JSON",
#       "value": ["ZSFW-A9-80181637"]
#     },
#     ...
#   ]

def _extract_contract_no_from_du584(resp: dict) -> Optional[str]:
    """
    从工具584真实响应中提取合同编号。

    优先从 itemKey="返回值_1" 的简单数组取第一条；
    兜底从 itemKey="客户合同信息列表" 的表格中取 status=1 的合同 number 字段。
    """
    try:
        results = resp["data"]["context"][0].get("results", [])
    except (KeyError, IndexError, TypeError):
        return None

    # 构建 itemKey → value 映射
    kv = {r.get("itemKey"): r.get("value") for r in results if isinstance(r, dict)}

    # 路径1：itemKey="返回值_1"，value=["ZSFW-A9-80181637"]（最简单）
    contract_list = kv.get("返回值_1")
    if isinstance(contract_list, list) and contract_list:
        return str(contract_list[0])

    # 路径2：itemKey="客户合同信息列表"，value=[{..., "number": "ZSFW-A9-...", "status": "1"}]
    table = kv.get("客户合同信息列表")
    if isinstance(table, list) and table:
        # 优先取 status=1（正常生效）的合同
        for row in table:
            if isinstance(row, dict) and str(row.get("status")) == "1":
                number = row.get("number")
                if number:
                    return str(number)
        # 兜底：取第一条
        first = table[0]
        if isinstance(first, dict) and first.get("number"):
            return str(first["number"])

    return None


def _extract_all_contracts_from_du584(resp: dict) -> list[dict]:
    """
    从工具584响应中提取所有合同记录列表（用于调试打印）。
    每条记录格式：{"contractId": ..., "contractNo": ..., "status": ..., "name": ..., "type": ...}
    """
    contracts = []
    try:
        results = resp["data"]["context"][0].get("results", [])
        kv = {r.get("itemKey"): r.get("value") for r in results if isinstance(r, dict)}
        table = kv.get("客户合同信息列表")
        if isinstance(table, list):
            for row in table:
                if isinstance(row, dict):
                    contracts.append({
                        "contractId":   row.get("id"),
                        "contractNo":   row.get("number"),
                        "contractName": row.get("name"),
                        "status":       row.get("status"),  # "1"=正常生效
                        "type":         row.get("type"),
                    })
    except (KeyError, IndexError, TypeError):
        pass
    return contracts


# ── 路径A：根据供应商ID查询合同编号（工具584）────────────────────────────────

def query_by_partner_id(partner_id: str, dry_run: bool = False) -> Optional[str]:
    """
    调用工具584，根据 partnerId 查询合同编号，返回 contractNo 字符串。
    失败时打印错误并返回 None。
    """
    print(f"⏳ 调用工具584查询合同（partnerId={partner_id}）...")

    resp = query_contract_by_partner_id(partner_id=partner_id, dry_run=dry_run)

    if dry_run:
        return None

    # 打印原始响应（调试用）
    print(f"\n[工具584 原始响应]")
    print(json.dumps(resp, ensure_ascii=False, indent=2))

    # 检查顶层错误
    if resp.get("code") not in (200, None) and resp.get("code") != 200:
        print(f"\n❌ 工具584调用失败: code={resp.get('code')}, msg={resp.get('message', '')}", file=sys.stderr)
        return None

    # 检查执行错误（status=2 表示失败）
    try:
        ctx = resp["data"]["context"][0]
        status = ctx.get("status")
        if status == 2:
            err_results = ctx.get("results", [])
            err_msg = next(
                (r.get("value") for r in err_results if "ERROR" in (r.get("itemKey") or "")),
                "未知错误"
            )
            print(f"\n❌ 工具584执行失败: {err_msg}", file=sys.stderr)
            return None
    except (KeyError, TypeError, IndexError):
        pass

    # 提取合同编号
    contract_no = _extract_contract_no_from_du584(resp)
    return contract_no


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""查询原始合同编号（支持两种路径）

【路径A】根据供应商ID查询（工具584，推荐）
  --partner-id <partnerId>
      供应商ID（业务客户ID），如 4549866
      直接查询该供应商下所有住宿合同，取合同编号

【路径B】根据平台合同ID查询（Thrift RPC，需要先知道 platformContractId）
  --platform-contract-id <platformContractId>
      平台合同ID（数字），即 create-partner.py 输出的 platformContractId
  --swimlane <泳道名>
      泳道名称（可选）

【公共参数】
  --dry-run          仅打印参数，不实际执行

【输出】
  contractNo  合同编号字符串，如 ZSFW-A9-80181637
              全日房和钟点房上单时必填

【适用场景】
  路径A：用户只有 partnerId（数据池中没有该供应商时的兜底查询）
  路径B：已有 platformContractId 时使用（create-partner.py 创建后的标准流程）

【使用示例】
  python3 factory/infra/query-contract.py --partner-id 4549866
  python3 factory/infra/query-contract.py --platform-contract-id 18127845""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="查询原始合同编号（contractNo）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--partner-id",
        help="[路径A] 供应商ID，调工具584查询合同编号（推荐）",
    )
    group.add_argument(
        "--platform-contract-id", type=int,
        help="[路径B] 平台合同ID，调 Thrift RPC 查询合同编号",
    )
    parser.add_argument(
        "--swimlane", default="",
        help="泳道（仅路径B有效，不传=主干）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印参数，不执行",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="仅输出 JSON 结果，抑制其他打印",
    )
    args = parser.parse_args()

    # ── 路径A：根据供应商ID查询（工具584）──────────────────────────────────
    if args.partner_id:
        if not args.json_only:
            print(f"=== 查询合同编号（工具584）===")
            print(f"  partnerId（业务客户ID）: {args.partner_id}")
            print(f"  业务线                : 住宿")

        contract_no = query_by_partner_id(
            partner_id=args.partner_id,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            return

        if not contract_no:
            print(f"\n⚠️  未能从工具584响应中提取 contractNo。", file=sys.stderr)
            print(f"    请检查 partnerId={args.partner_id} 是否正确，或手动传 --contract-no 参数。", file=sys.stderr)
            sys.exit(1)

        if args.json_only:
            print(json.dumps({"contractNo": contract_no, "partnerId": args.partner_id}, ensure_ascii=False))
        else:
            print(f"\n✅ 合同编号查询成功")
            print(f"  partnerId  : {args.partner_id}")
            print(f"  contractNo : {contract_no}")
            print(f"\n📋 上单时使用：--set \"goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}\"")
        return

    # ── 路径B：根据平台合同ID查询（Thrift RPC）──────────────────────────────
    if not args.json_only:
        print(f"=== 查询原始合同编号（ContractService.getContractIdMapping）===")
        print(f"  platformContractId : {args.platform_contract_id}")
        print(f"  businessLine       : 20（酒店）")
        print(f"  泳道               : {args.swimlane or '主干'}")

    resp = query_contract_no(
        platform_contract_id=args.platform_contract_id,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    if not args.json_only:
        print(f"\n原始响应：")
        print(json.dumps(resp, ensure_ascii=False, indent=2))

    # 提取合同编号
    data = resp if isinstance(resp, dict) else {}
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    contract_no = inner.get("contractNumber") or inner.get("customerNo") or inner.get("contractNo")

    if not contract_no:
        print(f"\n⚠️  未能从响应中提取 contractNo，完整响应见上方。", file=sys.stderr)
        sys.exit(1)

    if args.json_only:
        print(json.dumps({
            "contractNo": contract_no,
            "platformContractId": args.platform_contract_id,
        }, ensure_ascii=False))
    else:
        print(f"\n✅ 合同编号查询成功")
        print(f"  platformContractId : {args.platform_contract_id}")
        print(f"  contractNo         : {contract_no}")
        print(f"\n📋 上单时使用：--set \"goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}\"")


if __name__ == "__main__":
    main()

