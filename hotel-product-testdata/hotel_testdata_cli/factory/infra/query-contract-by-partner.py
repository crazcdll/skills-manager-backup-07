#!/usr/bin/env python3
"""
基础实体 - 根据供应商ID查询最新审核通过的合同（Thrift RPC）

适用场景：
  已知 partnerId，查询该供应商下最新审核通过的生效合同，取 contractNum 用于上单。
  用于路径B（指定客户+门店）、路径C（仅有门店）、路径D（仅有供应商）场景中的合同就绪环节。

与 query-contract.py 的区别：
  - query-contract.py：根据 platformContractId（平台合同ID，数字）查单条合同编号
  - query-contract-by-partner.py：根据 partnerId（供应商/客户ID）查最新审核通过合同

接口信息：
  service : com.meituan.hotel.contract.thrift.service.IMtaContractService
  method  : getLastAuditPassContract
  appkey  : com.sankuai.hotel.biz.contract
  入参    : (Integer partnerId)
  出参    : TMtaContractInfoResult { data.basicInfo.contractNum }
  说明    : 返回该供应商最新审核通过（auditStatus=3）的合同

使用方式：
  # 查询供应商下最新生效合同，返回 contractNo
  python3 factory/infra/query-contract-by-partner.py --partner-id <partnerId>

  # 指定泳道
  python3 factory/infra/query-contract-by-partner.py --partner-id <partnerId> --swimlane user-xxx

  # 仅打印参数，不执行
  python3 factory/infra/query-contract-by-partner.py --partner-id <partnerId> --dry-run

输出：
  contractNo   合同编号字符串（如 ZSFW-A9-24044462），全日房/钟点房上单必填
  contractId   合同ID（数字或UUID）
  无合同 → 打印提示，退出码 1，由调用方决定是否执行 create-contract.py
"""

import argparse
import json
import sys
import os
from typing import Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


# ── 接口常量 ──────────────────────────────────────────────────────────────────

_APPKEY  = "com.sankuai.hotel.biz.contract"
_SERVICE = "com.meituan.hotel.contract.thrift.service.IMtaContractService"
_METHOD  = "getLastAuditPassContract"


# ── 出参解析：从 getLastAuditPassContract 响应中提取 basicInfo ─────────────────
#
# 响应结构（来自真实调用）：
# {
#   "status": 0,
#   "message": "执行成功",
#   "data": {
#     "basicInfo": {
#       "id": 5436580,
#       "partnerId": 4559222,
#       "contractNum": "ZSFW-A9-24044462",   ← 上单合同编号
#       "contractType": 2,
#       "auditStatus": 3,                    ← 3=审核通过
#       "onlineStatus": 1,                   ← 1=上线
#       "contractId": "uuid-...",            ← 合同ID（UUID）
#       ...
#     }
#   },
#   "success": true
# }

def _extract_basic_info(resp: dict) -> Optional[dict]:
    """从 getLastAuditPassContract 响应中提取 basicInfo。"""
    data = resp.get("data")
    if isinstance(data, dict):
        basic = data.get("basicInfo")
        if isinstance(basic, dict):
            return basic
    return None


# ── 核心查询函数 ──────────────────────────────────────────────────────────────

def query_contracts_by_partner(
    partner_id: str,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    调用 IMtaContractService#getLastAuditPassContract。

    返回该供应商最新审核通过的生效合同（auditStatus=3）。

    参数：
        partner_id - 供应商ID（业务客户ID）
        swimlane   - 泳道（空字符串=主干）
        dry_run    - True 时只打印不执行

    返回：接口原始响应 dict
    """
    from scripts.runner import invoke  # noqa

    return invoke(
        appkey=_APPKEY,
        service=_SERVICE,
        method=_METHOD,
        swimlane=swimlane,
        timeout_ms=15000,
        dry_run=dry_run,
        raise_on_biz_error=False,
        progress_hint=f"查询最新审核通过合同（partnerId={partner_id}）...",
        parameter_values=[
            str(int(partner_id)),   # 参数1：partnerId（Integer）
        ],
        parameter_types=[
            "java.lang.Integer",
        ],
    )


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""根据供应商ID查询最新审核通过的合同（Thrift RPC）

【接口】
  service : com.meituan.hotel.contract.thrift.service.IMtaContractService
  method  : getLastAuditPassContract
  appkey  : com.sankuai.hotel.biz.contract

【必填参数】
  --partner-id <partnerId>
      供应商ID（业务客户ID），如 4559222

【可选参数】
  --swimlane <泳道名>      泳道名称（不传=主干）
  --dry-run               仅打印参数，不实际执行
  --json-only             仅输出 JSON 结果，抑制其他打印

【输出】
  contractNo   合同编号字符串，如 ZSFW-A9-24044462（全日房/钟点房上单必填）
  contractId   合同ID（数字或UUID）
  auditStatus  3=审核通过
  onlineStatus 1=上线

【无合同处理】
  无审核通过合同时退出码 1，提示调用 create-contract.py 新建合同。

【使用示例】
  python3 factory/infra/query-contract-by-partner.py --partner-id 4559222
  python3 factory/infra/query-contract-by-partner.py --partner-id 4559222 --swimlane user-test
  python3 factory/infra/query-contract-by-partner.py --partner-id 4559222 --json-only""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="根据供应商ID查询最新审核通过的合同",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--partner-id", required=True,
        help="供应商ID（业务客户ID）",
    )
    parser.add_argument(
        "--swimlane", default="",
        help="泳道名称（不传=主干）",
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

    if not args.json_only:
        print("=== 查询最新审核通过合同（IMtaContractService#getLastAuditPassContract）===")
        print(f"  partnerId : {args.partner_id}")
        print(f"  泳道      : {args.swimlane or '主干'}")

    # ── 调用接口 ──────────────────────────────────────────────────────────────
    resp = query_contracts_by_partner(
        partner_id=args.partner_id,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    # ── 打印原始响应 ──────────────────────────────────────────────────────────
    if not args.json_only:
        print(f"\n[接口原始响应]")
        print(json.dumps(resp, ensure_ascii=False, indent=2))

    # ── 检查接口级错误 ────────────────────────────────────────────────────────
    # getLastAuditPassContract 返回结构：{"status":0, "data":{...}, "success":true}
    status  = resp.get("status")
    success = resp.get("success")
    if success is False or (status is not None and int(status) != 0):
        err_msg = resp.get("message", "未知错误")
        print(f"\n❌ 接口返回错误: status={status}, msg={err_msg}", file=sys.stderr)
        sys.exit(1)

    # ── 提取 basicInfo ────────────────────────────────────────────────────────
    basic_info = _extract_basic_info(resp)

    if not basic_info:
        if args.json_only:
            print(json.dumps({"contractNo": None, "partnerId": args.partner_id}, ensure_ascii=False))
        else:
            print(f"\n⚠️  该供应商下暂无审核通过的合同（partnerId={args.partner_id}）")
            print(f"   请执行 create-contract.py 新建合同：")
            print(f"   python3 factory/infra/create-contract.py --partner-id {args.partner_id}")
        sys.exit(1)

    # ── 提取合同关键字段 ──────────────────────────────────────────────────────
    contract_no   = basic_info.get("contractNum")
    contract_id   = basic_info.get("id") or basic_info.get("contractId")
    audit_status  = basic_info.get("auditStatus")
    online_status = basic_info.get("onlineStatus")
    contract_type = basic_info.get("contractType")
    contract_name = basic_info.get("contractName", "-")

    if not contract_no:
        print(f"\n⚠️  未能从响应中提取 contractNo，完整响应见上方", file=sys.stderr)
        sys.exit(1)

    is_valid = (str(audit_status) == "3" and str(online_status) == "1")

    if args.json_only:
        print(json.dumps({
            "contractNo":   contract_no,
            "contractId":   contract_id,
            "partnerId":    args.partner_id,
            "auditStatus":  audit_status,
            "onlineStatus": online_status,
            "contractType": contract_type,
            "contractName": contract_name,
            "isValid":      is_valid,
        }, ensure_ascii=False))
    else:
        status_note = "（生效合同 ✅）" if is_valid else "（⚠️ 非完全生效合同，请确认是否可用）"
        print(f"\n✅ 合同查询成功{status_note}")
        print(f"  partnerId    : {args.partner_id}")
        print(f"  contractNo   : {contract_no}")
        print(f"  contractName : {contract_name}")
        print(f"  contractType : {contract_type}")
        print(f"  auditStatus  : {audit_status}  (3=审核通过)")
        print(f"  onlineStatus : {online_status}  (1=上线)")
        if contract_id:
            print(f"  contractId   : {contract_id}")
        print(f"\n📋 上单时使用：--set \"goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}\"")


if __name__ == "__main__":
    main()

