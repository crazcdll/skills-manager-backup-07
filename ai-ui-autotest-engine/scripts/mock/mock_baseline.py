#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预设 Mock 基线快照与回滚（业务 mockId 保护）。

Flow 中声明的「预设 Mock」通常引用业务方在 AppMock 平台已配置好的 mockId。
走查过程中 Agent 会动态修改这些规则的 response 内容，若收尾只做 reset-env
（仅关闭启用开关，不回滚内容），会导致业务 mockId 被永久改写。因此需要在
执行前快照真实状态，执行后精确回滚。

用法（cli.py 子命令，case 目录从 active_case 自动获取，mis 从 resolve_mis 自动解析）：
  Preflight 阶段（Step 1 之前）：
    python3 scripts/cli.py mock-snapshot --mock-ids 11249367,16727321

  Step 5 收尾阶段（record-stop 之后、reset-env 之前）：
    python3 scripts/cli.py mock-restore

设计原则：
  - 快照内容 = 本次执行开始前的真实服务端状态（response body + 启用状态），
    不是 Flow 文档里"假设"的初始基线，避免文档与实际不一致导致回滚失真。
  - 任一 mockId snapshot 失败视为整体失败（宁可暂停报告，不留快照缺口）。
  - restore 精确回滚 response 内容 + 独立的启用/禁用状态（get 返回 0/1，
    update/on/off 语义是 1/-1，两者不可混用，脚本内部做好映射）。
"""
import json
import os

from core.errors import UsageError
from core.util.json_utils import write_json_atomic, read_json
from core.util.paths import MOCK_BASELINE_DIR, get_active_case
from core.util.case_utils import resolve_mis
from mock.appmock_rules import appmock_get, appmock_update, appmock_on, appmock_off

def _get_case_name() -> str:
    """从 active_case 获取当前用例目录名。"""
    name = get_active_case()
    if not name:
        raise UsageError("未设置 active_case，请先执行 flow-init")
    return name

def _baseline_dir(case_name: str) -> str:
    """快照存储在 .run/mock_baseline/<case_name>/，独立于 cases/ 目录，
    不受 cases/ 目录清理（`cli.py post-clean` / clean_post_test()）影响。
    """
    d = os.path.join(MOCK_BASELINE_DIR, case_name)
    os.makedirs(d, exist_ok=True)
    return d

def _baseline_file(case_name: str, mock_id: str) -> str:
    return os.path.join(_baseline_dir(case_name), f"{mock_id}.json")

def _unwrap_get_result(data: dict) -> dict:
    """appmock_get 在 CLI 成功路径和 yooz 代理 fallback 路径返回结构不一致：

    - CLI 路径：{"code": 0, "data": {...规则详情...}, "meta": ..., "traceId": ...}
    - yooz 代理路径：{...规则详情...}（appmock_rules.py 内部已解包一层）

    这里统一按"是否含 response/status 等规则字段"判断是否需要再解一层 data。
    """
    if not isinstance(data, dict):
        return {}
    if "response" in data or "status" in data:
        return data
    inner = data.get("data")
    if isinstance(inner, dict):
        return inner
    return {}

def cmd_snapshot(args):
    case_name = _get_case_name()
    mis = resolve_mis()
    mock_ids = [m.strip() for m in args.mock_ids.split(",") if m.strip()]
    if not mock_ids:
        raise UsageError("--mock-ids 为空")

    ok_count = 0
    fail_ids = []
    for mock_id in mock_ids:
        raw = appmock_get(mock_id, mis=mis)
        data = _unwrap_get_result(raw)
        if not data or "response" not in data:
            print(f"SNAPSHOT FAIL: mockId={mock_id} 获取规则详情失败或响应体缺失")
            fail_ids.append(mock_id)
            continue
        fpath = _baseline_file(case_name, mock_id)
        write_json_atomic(fpath, data)
        status = data.get("status")
        print(f"SNAPSHOT OK: mockId={mock_id} status={status} -> {fpath}")
        ok_count += 1

    total = len(mock_ids)
    if fail_ids:
        print(f"SNAPSHOT DONE: {ok_count}/{total} 成功，失败: {','.join(fail_ids)}")
        return 1
    print(f"SNAPSHOT DONE: {ok_count}/{total} mockId 已快照")
    return 0

def cmd_restore(args):
    case_name = _get_case_name()
    mis = resolve_mis()
    bdir = _baseline_dir(case_name)
    files = [f for f in os.listdir(bdir) if f.endswith(".json")]
    if not files:
        print(f"RESTORE SKIP: {bdir} 下无快照文件（可能未执行 snapshot 或本次 Flow 无预设 Mock）")
        return 0

    response_only = getattr(args, "response_only", False)
    ok_count = 0
    fail_ids = []
    for fname in files:
        mock_id = fname[:-5]  # 去掉 .json
        fpath = os.path.join(bdir, fname)
        try:
            baseline = read_json(fpath, default={})
        except Exception as e:
            print(f"RESTORE FAIL: mockId={mock_id} 读取快照文件失败: {e}")
            fail_ids.append(mock_id)
            continue

        orig_response = baseline.get("response")
        orig_status = baseline.get("status")  # 0=禁用 1=启用（get 语义）
        orig_status_code = baseline.get("statusCode")

        ok = appmock_update(
            mock_id=mock_id,
            response_body=orig_response,
            status_code=orig_status_code if orig_status_code != 200 else None,
        )
        if not ok:
            print(f"RESTORE FAIL: mockId={mock_id} update 响应体失败")
            fail_ids.append(mock_id)
            continue

        if response_only:
            # Case 间回滚：仅恢复响应体，保持启用状态不变
            # 启用/禁用状态由 B3_mock_enable（启用）和 T0/T2（最终恢复/清理）管理
            print(f"RESTORE OK: mockId={mock_id} response 已恢复（--response-only，启用状态保持不变）")
            ok_count += 1
            continue

        # 完整回滚：独立恢复启用/禁用状态（get 返回 0/1，on/off 语义不同，不可直接传给 update 的 status）
        if orig_status == 0:
            state_ok = appmock_off(mock_id, mis=mis)
        else:
            state_ok = appmock_on(mock_id, mis=mis)
        if not state_ok:
            print(f"RESTORE WARN: mockId={mock_id} 响应体已回滚，但启用状态恢复失败（原状态 status={orig_status}）")
            fail_ids.append(mock_id)
            continue

        print(f"RESTORE OK: mockId={mock_id} response+status 已恢复至执行前状态（status={orig_status}）")
        ok_count += 1

    total = len(files)
    if fail_ids:
        print(f"RESTORE DONE: {ok_count}/{total} 成功，失败: {','.join(fail_ids)}（需人工核对这些 mockId）")
        return 1
    print(f"RESTORE DONE: {ok_count}/{total} 成功，业务 Mock 数据已恢复")
    return 0

