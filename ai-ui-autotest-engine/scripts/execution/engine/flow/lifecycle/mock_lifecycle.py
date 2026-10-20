#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""场景 Mock 生命周期 —— case 级启用/关闭状态机（唯一实现）。

设计不变量（唯一目标）：
    任一时刻，AppMock 上「由引擎开启」的场景规则集合 == 当前 case 声明的 mockId 集合。

为什么要 case 级（而非批级）：
    AppMock 对同一请求「命中即短路」——多条规则命中同一接口时只生效一条，其余静默
    失效。批级一次全开会让「同一接口、不同用例不同响应」的两个业务 mock 互相遮蔽，
    被遮蔽的 case 静默拿到错数据。因此场景 Mock 的开关必须跟随 case 收敛。

两类冲突的处置：
  · 跨 case（A 用 mockA、B 用 mockB，同接口）：由状态机保证——任一时刻只有当前 case
    的集合 ON，绝不共存；
  · case 内（同一个 case 声明了同一接口的两个 mockId）：规则层无法区分 → 预检 fail-fast。

数据：
    BASELINE : {mockId: {rule, method, response, status, statusCode}}  预检一次性快照
    ON       : 引擎当前开着谁（flow-context.meta.mock_on），全程差量维护
"""
import os

from shared.errors import MockError, UsageError
from shared.json_utils import read_json, write_json_atomic
from shared.paths import mock_baseline_dir, get_active_run
from shared.case_utils import resolve_case_path, resolve_mock_domain
from platform.appmock.rules import (
    appmock_get, appmock_on, appmock_off, appmock_update,
)
from execution.engine.flow.flow_context import load_context, save_context

_BASELINE_FILENAME = "mock-baseline.json"


# ═══════════════════════════════════════════════════════════════════
# 存储 / 读取
# ═══════════════════════════════════════════════════════════════════

def _active_run_dir():
    run = get_active_run()
    if not run:
        raise UsageError("未设置 active_run，请先执行 flow-init")
    return resolve_case_path(run)


def _baseline_path():
    d = mock_baseline_dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, _BASELINE_FILENAME)


def _load_baseline():
    data = read_json(_baseline_path(), default={})
    return data if isinstance(data, dict) else {}


def _save_baseline(data):
    write_json_atomic(_baseline_path(), data)


def _case_mock_ids(ctx):
    """{case_index: [mockId, ...]} —— 来自 cases_manifest（flow-init 时按 case 派生）。"""
    out = {}
    for m in ctx.get("cases_manifest", []):
        out[m.get("index")] = [str(x) for x in (m.get("mock_ids") or [])]
    return out


def _mock_union(per_case):
    union = []
    for ids in per_case.values():
        for mid in ids:
            if mid not in union:
                union.append(mid)
    return union


# ═══════════════════════════════════════════════════════════════════
# 预检：快照 U + 同 case 冲突检测 + 清场（把 U 全部置 OFF，进入确定初始态）
# ═══════════════════════════════════════════════════════════════════

def preflight(run_dir):
    ctx = load_context(run_dir)
    if ctx is None:
        raise UsageError("flow-context.json 不存在，需先执行 flow-init")

    per_case = _case_mock_ids(ctx)
    union = _mock_union(per_case)
    if not union:
        ctx.setdefault("meta", {})["mock_union"] = []
        ctx["meta"]["mock_on"] = []
        save_context(run_dir, ctx)
        print("MOCK-PREFLIGHT OK: 无场景 Mock，跳过")
        return 0

    mis = resolve_mock_domain()
    baseline = {}
    for mid in union:
        detail = appmock_get(mid, mis=mis)
        if not detail or detail.get("response") is None:
            raise MockError(
                f"mock 快照失败: mockId={mid}（取不到规则详情/response）"
                f"—— 宁可中止，也不留快照缺口"
            )
        baseline[mid] = {
            "rule": detail.get("rule"),
            "method": detail.get("method"),
            "response": detail.get("response"),
            "status": detail.get("status"),
            "statusCode": detail.get("statusCode"),
        }

    # case 内同接口冲突：两个 mockId 的 (rule, method) 相同 → 规则层无法区分，必有一方被遮蔽
    conflicts = []
    for ci, ids in per_case.items():
        seen = {}
        for mid in ids:
            key = (baseline[mid].get("rule"), baseline[mid].get("method"))
            if key in seen:
                conflicts.append((ci, seen[key], mid, key[0]))
            else:
                seen[key] = mid
    if conflicts:
        detail = "；".join(
            f"case[{ci}] mockId {a} 与 {b} 命中同一接口 rule={rule!r}"
            for ci, a, b, rule in conflicts
        )
        raise MockError(
            f"场景 Mock 声明冲突（同一 case 内同接口多规则，无法区分）：{detail}。"
            f"请合并为一条规则，或拆分为不同 case"
        )

    # 清场：把 U 里所有规则置 OFF —— 消除上一轮残留，保证本批从确定初始态开始
    off_failed = []
    for mid in union:
        if not appmock_off(mid, mis=mis):
            off_failed.append(mid)
    if off_failed:
        print(f"MOCK-PREFLIGHT WARN: 清场失败（后续 apply 会重试启用）: {', '.join(off_failed)}")

    _save_baseline(baseline)
    ctx.setdefault("meta", {})["mock_union"] = union
    ctx["meta"]["mock_on"] = []
    save_context(run_dir, ctx)
    print(f"MOCK-PREFLIGHT OK: 快照 {len(union)} 个 mockId，已清场")
    return 0


# ═══════════════════════════════════════════════════════════════════
# case 级收敛：ON := M(case)（差量开关 + body 回基线）
# ═══════════════════════════════════════════════════════════════════

def apply_case(run_dir, case_index):
    ctx = load_context(run_dir)
    if ctx is None:
        raise UsageError("flow-context.json 不存在，需先执行 flow-init")

    per_case = _case_mock_ids(ctx)
    if case_index not in per_case:
        raise UsageError(f"case-index {case_index} 不存在")
    m_cur = per_case[case_index]
    baseline = _load_baseline()
    mis = resolve_mock_domain()
    on = list(ctx.get("meta", {}).get("mock_on", []))

    # ① 关：上一 case 开了、本 case 不需要的
    for mid in list(on):
        if mid not in m_cur:
            if not appmock_off(mid, mis=mis):
                raise MockError(f"mock off 失败: mockId={mid}（case {case_index} 隔离失败）")
            on.remove(mid)

    # ② 开：本 case 声明的（body 先回基线，再确保 ON）
    for mid in m_cur:
        base = baseline.get(mid) or {}
        if base.get("response") is not None:
            sc = base.get("statusCode")
            appmock_update(
                mock_id=mid,
                response_body=base.get("response"),
                status_code=sc if sc not in (None, 200) else None,
            )
        if not appmock_on(mid, mis=mis):
            raise MockError(f"mock on 失败: mockId={mid}")
        if mid not in on:
            on.append(mid)

    # ③ ON := M(case)
    ctx.setdefault("meta", {})["mock_on"] = on
    save_context(run_dir, ctx)
    print(f"MOCK-APPLY OK: case={case_index} on={m_cur}")
    return 0


# ═══════════════════════════════════════════════════════════════════
# 收尾：把 U 恢复到执行前状态（response + 启用态）
# ═══════════════════════════════════════════════════════════════════

def restore_all(run_dir):
    baseline = _load_baseline()
    if not baseline:
        print("MOCK-RESTORE SKIP: 无基线快照")
        return 0

    mis = resolve_mock_domain()
    ok = True
    for mid, base in baseline.items():
        if base.get("response") is not None:
            sc = base.get("statusCode")
            if not appmock_update(
                mock_id=mid,
                response_body=base.get("response"),
                status_code=sc if sc not in (None, 200) else None,
            ):
                ok = False
                print(f"MOCK-RESTORE WARN: mockId={mid} response 恢复失败")
        st = base.get("status")
        if st == 0:
            ok = appmock_off(mid, mis=mis) and ok
        else:
            ok = appmock_on(mid, mis=mis) and ok

    ctx = load_context(run_dir)
    if ctx is not None:
        ctx.setdefault("meta", {})["mock_on"] = []
        save_context(run_dir, ctx)
    print(f"MOCK-RESTORE {'DONE' if ok else 'PARTIAL'}: {len(baseline)} 个 mockId 已恢复基线")
    return 0 if ok else 1


# ═══════════════════════════════════════════════════════════════════
# CLI 入口（handler(args) 形态）
# ═══════════════════════════════════════════════════════════════════

def cmd_mock_preflight(args):
    return preflight(_active_run_dir())


def cmd_mock_apply(args):
    return apply_case(_active_run_dir(), args.case_index)


def cmd_mock_restore(args):
    return restore_all(_active_run_dir())
