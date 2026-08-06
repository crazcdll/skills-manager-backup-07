#!/usr/bin/env python3
"""
基础实体 - 通过原始客户ID（partnerId）查询业务客户ID（customerId）

接口：com.sankuai.nibcus.inf.idmapping.client.service.CustomerIdMappingService
      #getCustomerIdByOriginCustomerIdAndBusinessLine
appkey：com.sankuai.nibcus.inf.idmapping

背景：
  工具49（createHotelCustomer）返回的是 partnerId，这是「原始客户ID」。
  上单时部分接口（如非房、套餐）实际需要的是「业务客户ID」（customerId）。
  本脚本完成 partnerId → customerId 的映射查询，并将结果更新回数据池打标。

使用方式：
  # 基本查询
  python3 factory/infra/query-customer-id.py --origin-customer-id 4554162

  # 查询后同时用 testdata-cli tag 更新数据池中的 customerId
  python3 factory/infra/query-customer-id.py \\
      --origin-customer-id 4554162 \\
      --contract-id 18127845 \\
      --poi-id 1090252288211865 \\
      --tag

  # 指定泳道
  python3 factory/infra/query-customer-id.py --origin-customer-id 4554162 --swimlane user-xxx

  # 仅打印参数，不执行
  python3 factory/infra/query-customer-id.py --origin-customer-id 4554162 --dry-run
"""

import argparse
import importlib.util as ilu
import json
import subprocess
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
query_customer_id_by_origin = _iface.query_customer_id_by_origin


def _get_mis() -> str:
    """获取当前操作人 MIS"""
    try:
        from scripts.utils import get_operator  # noqa
        return get_operator()
    except Exception:
        return os.environ.get("USER", "")


def _run_testdata_tag(
    customer_id: int,
    contract_id: int,
    poi_id: int,
    mis: str,
    dry_run: bool = False,
) -> bool:
    """
    调用 testdata-cli tag 将 customerId 写入数据池（customer-contract-poi 联合打标）。

    参数：
        customer_id  - 业务客户ID（查询结果）
        contract_id  - 平台合同ID（platformContractId）
        poi_id       - 门店ID
        mis          - 操作人 MIS，用作 --occupier
        dry_run      - True 时只打印不执行

    返回：True=成功，False=失败
    """
    cmd = [
        "testdata-cli", "tag",
        "--subject-type", "customer-contract-poi",
        "--customer-id",  str(customer_id),
        "--contract-id",  str(contract_id),
        "--poi-id",       str(poi_id),
        "--biz-line",     "20",
        "--occupier",     mis,
    ]

    import sys as _sys
    _sys.stdout.flush()   # 确保父进程的 print 先刷出，避免与子进程输出交错
    print(f"\n📦 写入数据池（testdata-cli tag）：")
    print(f"  customer-id  : {customer_id}  ← 本次查询到的 customerId")
    print(f"  contract-id  : {contract_id}")
    print(f"  poi-id       : {poi_id}")
    print(f"  occupier     : {mis}")
    _sys.stdout.flush()

    if dry_run:
        print(f"\n[dry-run] 将执行命令：")
        print(f"  {' '.join(cmd)}")
        return True

    try:
        result = subprocess.run(cmd, capture_output=False, text=True, timeout=60)
        if result.returncode == 0:
            print(f"✅ 数据池更新成功")
            return True
        else:
            print(f"❌ testdata-cli tag 执行失败（exit={result.returncode}）")
            return False
    except FileNotFoundError:
        print(f"⚠️  testdata-cli 未安装或不在 PATH 中，跳过数据池更新。")
        print(f"   如需手动执行，运行：")
        print(f"   {' '.join(cmd)}")
        return False
    except Exception as e:
        print(f"❌ 执行 testdata-cli tag 异常: {e}")
        return False


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""查询业务客户ID（CustomerIdMappingService.getCustomerIdByOriginCustomerIdAndBusinessLine）

【必填参数】
  --origin-customer-id <partnerId>
      原始客户ID，即工具49（createHotelCustomer）返回的 partnerId

【可选参数】
  --contract-id <platformContractId>
      平台合同ID（工具49返回），配合 --tag 时必填

  --poi-id <poiId>
      门店ID，配合 --tag 时必填

  --tag
      查询成功后，自动调用 testdata-cli tag 将 customerId 写入数据池
      需同时传 --contract-id 和 --poi-id

  --swimlane <泳道名>
      泳道名称，不传则走主干
      默认值：空（主干）

  --dry-run
      仅打印参数，不实际执行

【输出】
  customerId  业务客户ID（Long），上单时传入 customerId 字段

【背景说明】
  工具49（createHotelCustomer）返回的是 partnerId，属于「原始客户ID」。
  非房（xGoods）、套餐等上单接口实际需要的是「业务客户ID」（customerId）。
  两者通过 CustomerIdMappingService 进行映射转换，业务线ID固定为 20（酒店）。

【使用示例】
  # 仅查询 customerId
  python3 factory/infra/query-customer-id.py --origin-customer-id 4554162

  # 查询后写入数据池
  python3 factory/infra/query-customer-id.py \\
      --origin-customer-id 4554162 \\
      --contract-id 18127845 \\
      --poi-id 1090252288211865 \\
      --tag""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="通过原始客户ID（partnerId）查询业务客户ID（customerId）"
    )
    parser.add_argument(
        "--origin-customer-id", required=True, type=int,
        help="原始客户ID，即工具49返回的 partnerId",
    )
    parser.add_argument(
        "--contract-id", type=int, default=None,
        help="平台合同ID（配合 --tag 时必填）",
    )
    parser.add_argument(
        "--poi-id", type=int, default=None,
        help="门店ID（配合 --tag 时必填）",
    )
    parser.add_argument(
        "--tag", action="store_true", default=False,
        help="查询成功后，自动调用 testdata-cli tag 写入数据池",
    )
    parser.add_argument(
        "--swimlane", default="",
        help="泳道（不传=主干）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印参数，不执行",
    )
    args = parser.parse_args()

    # --tag 时校验 contract-id / poi-id 必填
    if args.tag and (args.contract_id is None or args.poi_id is None):
        parser.error("使用 --tag 时必须同时传 --contract-id 和 --poi-id")

    print(f"=== 查询业务客户ID（CustomerIdMappingService）===")
    print(f"  originCustomerId : {args.origin_customer_id}")
    print(f"  businessLineId   : 3（酒店，CustomerIdMappingService 枚举值）")
    print(f"  泳道             : {args.swimlane or '主干'}")

    resp = query_customer_id_by_origin(
        origin_customer_id=args.origin_customer_id,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        if args.tag:
            mis = _get_mis()
            _run_testdata_tag(
                customer_id=0,   # dry-run 时用占位值
                contract_id=args.contract_id,
                poi_id=args.poi_id,
                mis=mis,
                dry_run=True,
            )
        return

    # 打印完整响应（调试用）
    print(f"\n原始响应：")
    print(json.dumps(resp, ensure_ascii=False, indent=2))

    # 提取 customerId
    # 接口实际响应结构：{"code":"SUCCESS","message":"成功","customerId":<Long>}
    # 文档示例结构：{"result": <customerId: Long>, "success": true}
    customer_id = None
    if isinstance(resp, dict):
        # 优先取 customerId 字段（实际接口返回结构）
        raw = resp.get("customerId")
        if raw is not None:
            try:
                customer_id = int(raw)
            except (ValueError, TypeError):
                pass
        # 兜底1：result 字段（文档示例结构）
        if customer_id is None:
            raw = resp.get("result")
            if raw is not None:
                try:
                    customer_id = int(raw)
                except (ValueError, TypeError):
                    pass
        # 兜底2：data 字段（DataUnity 外层包装）
        if customer_id is None and isinstance(resp.get("data"), (int, str)):
            try:
                customer_id = int(resp["data"])
            except (ValueError, TypeError):
                pass

    if customer_id is None:
        print(f"\n⚠️  未能从响应中提取 customerId，完整响应见上方。")
        sys.exit(1)

    print(f"\n✅ 业务客户ID查询成功")
    print(f"  originCustomerId (partnerId) : {args.origin_customer_id}")
    print(f"  customerId                   : {customer_id}")

    # ── 写入数据池 ───────────────────────────────────────────────────────────
    if args.tag:
        mis = _get_mis()
        tag_ok = _run_testdata_tag(
            customer_id=customer_id,
            contract_id=args.contract_id,
            poi_id=args.poi_id,
            mis=mis,
            dry_run=False,
        )
        if not tag_ok:
            sys.exit(1)


if __name__ == "__main__":
    main()

