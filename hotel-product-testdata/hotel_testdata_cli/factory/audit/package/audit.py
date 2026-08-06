#!/usr/bin/env python3
"""
审核 - 套餐审核（Package/SPU）

流程：
  直接调用 RPC 接口完成审核：
  appkey : com.sankuai.hotel.biz.platform
  service: com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method : completeAuditTask

参数（spuId、processId 由命令行传入，其余固定）：
  spuType     : 0
  taskDefKey  : "day_trip_unified_audit_task"
  auditResult : 1（通过）/ 0（驳回）
  submitType  : 1
  auditType   : 2
  auditMore   : false
  auditNotes  : []

使用方式：
  # 审核通过（默认）
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984

  # 审核驳回
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984 --action reject

  # dry-run（只打印不执行）
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984 --dry-run
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from scripts.runner import invoke, InvokeError  # noqa


APPKEY   = "com.sankuai.hotel.biz.platform"
SERVICE  = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
METHOD   = "completeAuditTask"

# 固定参数
FIXED_TASK_DEF_KEY  = "day_trip_unified_audit_task"
FIXED_SUBMIT_TYPE   = 1
FIXED_AUDIT_TYPE    = 2
FIXED_AUDIT_MORE    = False
FIXED_AUDIT_NOTES   = []
FIXED_SPU_TYPE      = 0


def _show_schema():
    print("""=== 套餐审核（audit/package）参数说明 ===

【必填参数】
  --spu-id        INT    套餐 spuId（由 factory/package/create-package.py 创建后获得）
  --process-id    STR    BPM 流程实例ID（processId，从大象推送消息或 BPM 任务中获取）

【可选参数】
  --action        STR    审核动作（默认 pass）
                           pass    通过（默认，auditResult=1）
                           reject  驳回（auditResult=0）
  --dry-run              只打印 RPC 参数，不实际调用

【审核方式】
  直接调用 RPC 接口：
    appkey : com.sankuai.hotel.biz.platform
    service: MeResourceFacade
    method : completeAuditTask
  无需 BPM Cookie，无需浏览器，一步完成。

【固定参数】
  spuType     = 0
  taskDefKey  = "day_trip_unified_audit_task"
  submitType  = 1
  auditType   = 2
  auditMore   = false
  auditNotes  = []

【使用示例】
  # 审核通过
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984

  # 审核驳回
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984 --action reject

  # dry-run
  python3 factory/audit/package/audit.py --spu-id 8426522 --process-id 2144917984 --dry-run
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="套餐审核（直接 RPC 方式）")
    parser.add_argument("--spu-id",     required=True, type=int, help="套餐 spuId（整型）")
    parser.add_argument("--process-id", required=True, type=str, help="BPM 流程实例ID（processId）")
    parser.add_argument("--action", choices=["pass", "reject"], default="pass",
                        help="审核动作: pass=通过(auditResult=1), reject=驳回(auditResult=0)（默认pass）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印 RPC 参数，不实际调用")
    args = parser.parse_args()

    audit_result = 1 if args.action == "pass" else 0
    action_text  = "通过" if args.action == "pass" else "驳回"

    # 构造 RPC 参数
    rpc_params = {
        "spuId":       args.spu_id,
        "spuType":     FIXED_SPU_TYPE,
        "processId":   args.process_id,
        "taskDefKey":  FIXED_TASK_DEF_KEY,
        "auditResult": audit_result,
        "submitType":  FIXED_SUBMIT_TYPE,
        "auditType":   FIXED_AUDIT_TYPE,
        "auditMore":   FIXED_AUDIT_MORE,
        "auditNotes":  FIXED_AUDIT_NOTES,
    }

    print("=" * 60, file=sys.stderr)
    print(f"  酒店套餐审核 - 直接 RPC 方式", file=sys.stderr)
    print(f"  套餐ID   : {args.spu_id}", file=sys.stderr)
    print(f"  processId: {args.process_id}", file=sys.stderr)
    print(f"  审核动作 : {action_text}（auditResult={audit_result}）", file=sys.stderr)
    print(f"  appkey  : {APPKEY}", file=sys.stderr)
    print(f"  service : {SERVICE}", file=sys.stderr)
    print(f"  method  : {METHOD}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # ---- 调用 RPC ----
    try:
        result = invoke(
            appkey=APPKEY,
            service=SERVICE,
            method=METHOD,
            params=rpc_params,
            dry_run=args.dry_run,
            progress_hint=f"套餐审核 spuId={args.spu_id} processId={args.process_id}，动作={action_text}",
        )
    except InvokeError as e:
        print(f"\n[FAIL] 套餐审核失败: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] RPC 调用异常: {e}", file=sys.stderr)
        sys.exit(1)

    # ---- 输出结构化结果 ----
    output = {
        "spuId":       args.spu_id,
        "processId":   args.process_id,
        "action":      args.action,
        "auditResult": audit_result,
        "rpcResult":   result,
    }
    print(json.dumps(output, ensure_ascii=False))

    print("\n" + "=" * 60, file=sys.stderr)
    if args.dry_run:
        print("  [dry-run] 未实际执行", file=sys.stderr)
    else:
        print(f"  套餐审核完成 ✓", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  套餐ID    : {args.spu_id}", file=sys.stderr)
    print(f"  审核动作  : {action_text}", file=sys.stderr)
    print(f"  auditResult: {audit_result}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()

