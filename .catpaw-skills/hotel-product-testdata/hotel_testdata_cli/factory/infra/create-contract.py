#!/usr/bin/env python3
"""
基础实体 - 创建纸质合同（住宿客户）

工具：工具447（住宿客户-添加纸质合同）
协议：HTTP POST DataUnity
接口：datamanagement.nibcus.test.sankuai.com/api/partnerandcontract/createPaperContract

功能：为指定供应商创建并审核纸质合同，返回合同编号（contractNo）。
      创建成功后可直接用于全日房/钟点房上单的 contractNo 字段。

使用方式：
  # 最简用法（只传供应商ID，其余使用默认值）
  python3 factory/infra/create-contract.py --partner-id <partnerId>

  # 指定合同名称和价格模式
  python3 factory/infra/create-contract.py --partner-id <partnerId> --contract-name 测试合同 --price-mod 9

  # 境外供应商
  python3 factory/infra/create-contract.py --partner-id <partnerId> --overseas

  # 仅打印参数，不执行
  python3 factory/infra/create-contract.py --partner-id <partnerId> --dry-run
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

from scripts.du_runner import run_tool, get_result, check_ok  # noqa
from scripts.utils import get_operator  # noqa

TOOL_ID = 447

def _default_contract_name() -> str:
    """生成默认合同名称：skill构造合同_yyyyMMddHHmmss"""
    return f"skill构造合同_{datetime.now().strftime('%Y%m%d%H%M%S')}"


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具447 - 住宿客户-添加纸质合同

【必填参数】
  --partner-id <partnerId>
      供应商ID（业务客户ID），如 4559222

【可选参数】
  --contract-name <名称>
      合同名称
      默认值：skill构造合同_<yyyyMMddHHmmss>

  --price-mod <模式>
      价格模式（枚举值）
        8  卖价模式（默认）：由商家决定卖价，美团和商家协定后决定好佣金或佣金率
        9  底价模式：由商家决定底价，美团决定卖价，最终和商家结算原始底价
      默认值：8

  --contract-type <类型>
      合同类型（枚举值）
        2  团购+预订合同（默认）
        1  直连合同
        4  现付合同
        5  预付包销合同
      默认值：2

  --is-audit <0|1>
      是否审核
        1  是（合同创建后自动走审核流程，推荐）
        0  否
      默认值：1

  --overseas
      Flag，加上则为境外供应商（默认境内）

  --dry-run
      仅打印参数，不实际执行

【输出】
  contractNo  合同编号字符串，如 ZSFW-A9-80181637（全日房/钟点房上单必填）

【使用示例】
  python3 factory/infra/create-contract.py --partner-id 4559222
  python3 factory/infra/create-contract.py --partner-id 4559222 --price-mod 9
  python3 factory/infra/create-contract.py --partner-id 4559222 --contract-type 4 --contract-name 现付测试合同
  python3 factory/infra/create-contract.py --partner-id 4559222 --overseas""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="创建纸质合同（工具447）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--partner-id", required=True, help="供应商ID（必填）")
    parser.add_argument(
        "--contract-name", default=None,
        help="合同名称（默认：skill构造合同_<yyyyMMddHHmmss>）",
    )
    parser.add_argument(
        "--price-mod", default="8",
        choices=["8", "9"],
        help="价格模式：8=卖价模式（默认），9=底价模式",
    )
    parser.add_argument(
        "--contract-type", default="2",
        choices=["1", "2", "4", "5"],
        help="合同类型：2=团购+预订（默认），1=直连，4=现付，5=预付包销",
    )
    parser.add_argument(
        "--is-audit", default="1",
        choices=["0", "1"],
        help="是否审核：1=是（默认），0=否",
    )
    parser.add_argument("--overseas", action="store_true", help="境外供应商（默认境内）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    parser.add_argument("--json-only", action="store_true", help="仅输出 JSON 结果，抑制其他打印")
    args = parser.parse_args()

    is_overseas = args.overseas
    contract_name = args.contract_name or _default_contract_name()

    _CONTRACT_TYPE_LABEL = {"1": "直连", "2": "团购+预订", "4": "现付", "5": "预付包销"}
    if not args.json_only:
        print(f"=== 创建纸质合同（工具{TOOL_ID}）===")
        print(f"  供应商ID    : {args.partner_id}")
        print(f"  合同名称    : {contract_name}")
        print(f"  价格模式    : {args.price_mod}（{'卖价' if args.price_mod == '8' else '底价'}模式）")
        print(f"  合同类型    : {args.contract_type}（{_CONTRACT_TYPE_LABEL.get(args.contract_type, args.contract_type)}）")
        print(f"  是否审核    : {args.is_audit}（{'是' if args.is_audit == '1' else '否'}）")
        print(f"  境内/境外   : {'境外' if is_overseas else '境内'}")

    # ── 调用工具447 ──────────────────────────────────────────────────────────
    resp = run_tool(
        tool_id=TOOL_ID,
        overrides={
            "partnerId":    args.partner_id,
            "contractName": contract_name,
            "priceMod":     int(args.price_mod),
            "contractType": int(args.contract_type),
            "isAudit":      int(args.is_audit),
            "oversea":      is_overseas,
        },
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    if not args.json_only:
        print(f"\n[工具{TOOL_ID} 原始响应]")
        print(json.dumps(resp, ensure_ascii=False, indent=2))

    # ── 校验执行结果 ──────────────────────────────────────────────────────────
    check_ok(resp, "创建合同")

    # ── 提取合同编号 ──────────────────────────────────────────────────────────
    # 出参：itemKey="response"，value 为业务 JSON 字符串
    # 业务响应结构（参考真实出参）：
    # {
    #   "code": 10000,
    #   "data": [ { "contractNum": "ZSFW-A9-...", ... } ]
    # }
    raw_response = get_result(resp, "response")
    contract_no = None
    contract_id = None
    platform_contract_id = None

    if raw_response:
        try:
            biz = raw_response if isinstance(raw_response, dict) else json.loads(raw_response)

            # 业务层错误检查：code=0 或 code=10000 均视为成功
            biz_code = biz.get("code")
            if biz_code is not None and biz_code not in (0, 10000):
                biz_msg = biz.get("msg") or biz.get("message") or str(biz)
                print(f"\n❌ 创建合同失败（业务错误 code={biz_code}）: {biz_msg}", file=sys.stderr)
                sys.exit(1)

            # 出参结构：{"code":0,"data":{"contractNum":"ZSFW-A9-xxx","platformContractId":"xxx"},"msg":"添加成功"}
            data = biz.get("data")
            if isinstance(data, dict):
                contract_no = data.get("contractNum") or data.get("contractNo")
                platform_contract_id = data.get("platformContractId")
                contract_id = data.get("id") or platform_contract_id
            elif isinstance(data, list) and data:
                first = data[0]
                contract_no = first.get("contractNum") or first.get("contractNo")
                platform_contract_id = first.get("platformContractId")
                contract_id = first.get("id") or platform_contract_id
            # 兜底：直接从 biz 顶层取
            if not contract_no:
                contract_no = biz.get("contractNum") or biz.get("contractNo")
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    if not contract_no:
        if not args.json_only:
            print(f"\n⚠️  合同创建成功但未能从 response 中提取 contractNo，请查看上方完整响应")
        sys.exit(1)

    if args.json_only:
        print(json.dumps({
            "contractNo":         contract_no,
            "platformContractId": platform_contract_id,
            "partnerId":          args.partner_id,
        }, ensure_ascii=False))
    else:
        print(f"\n✅ 合同创建成功")
        print(f"  partnerId           : {args.partner_id}")
        print(f"  contractNo          : {contract_no}")
        if platform_contract_id:
            print(f"  platformContractId  : {platform_contract_id}")
        print(f"  价格模式            : {args.price_mod}（{'卖价' if args.price_mod == '8' else '底价'}模式）")
        print(f"  合同类型            : {args.contract_type}（{_CONTRACT_TYPE_LABEL.get(args.contract_type, args.contract_type)}）")
        print(f"\n📋 上单时使用：--set \"goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}\"")


if __name__ == "__main__":
    main()

