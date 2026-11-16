#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""场景 Mock 生命周期 —— 规则库母本 → 运行域副本 + case 级开关状态机。

四条不变量（任一条不满足即中止，绝不带缺口执行）：

1. **母本只读**：规则库里的规则在执行期永不写；
2. **执行期只消费副本**：所有开关只操作运行域副本，写入侧由
   `platform.appmock.ownership.require_runtime_rule` 拦截母本 id；
3. **副本内容 == 母本内容**：克隆由服务端完成并读回自证（`appmock_clone`），
   自证不通过即视为克隆失败；
4. **mockId 与域无关**：mockId 全局唯一，母本读取不需要知道它属于我们的
   存储域还是用户自己的域——一律按 id 直取，落到本次运行域消费。

职责划分（分层不越界）：

  引擎   —— 声明哪些母本进哪个 case、克隆到哪个运行域、什么时候开/关；
  服务端 —— 规则内容的唯一契约（多形态字段整体搬运 + 读回自证）。

为什么引擎不搬字段：AppMock 规则内容是**多形态**的（全量响应 response、
部分 Mock 的 jsonPath patch、部分 Mock V2 的 formData、纯请求注入
requestHeader/requestParam）。引擎一旦逐字段列举就必然漂移——历史上的
`response` 单形态假设把「部分 Mock」误判成读不到规则，即使放过去也会
克隆成「命中了但什么都不 mock」的空壳。

运行域（`mis acquire` 领取的虚拟 MIS）是设备端 AppMock（规则 / 录制 /
环境 / 泳道）的唯一 userDomain，用完归还；并发 shard 各持不同运行域
⇒ 规则集合物理隔离。
"""
import os

from aitest.shared.errors import MockError, UsageError
from aitest.shared.json_utils import read_json, write_json_atomic
from aitest.shared.paths import mock_state_dir, get_active_run
from aitest.shared.case_utils import (
    current_runtime_domain, resolve_case_path, resolve_runtime_domain,
)
from aitest.integrations.appmock.rules import (
    appmock_clone, appmock_off, appmock_on, appmock_stop_all,
)
from aitest.integrations.appmock.ownership import MOCK_MAP_FILENAME
from aitest.execution.engine.flow.flow_context import load_context, save_context

# 副本元信息里对外的稳定字段（其余为服务端诊断字段，原样保留）
_RULE_RECORD_FIELDS = (
    "rule", "method", "type", "shape", "contentFields",
    "reused", "sourceFingerprint",
)


# ═══════════════════════════════════════════════════════════════════
# 存储 / 读取
# ═══════════════════════════════════════════════════════════════════

def _active_run_dir():
    run = get_active_run()
    if not run:
        raise UsageError("未设置 active_run，请先执行 flow-init")
    return resolve_case_path(run)


def _state_path():
    d = mock_state_dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, MOCK_MAP_FILENAME)


def _load_state():
    data = read_json(_state_path(), default={})
    return data if isinstance(data, dict) else {}


def _save_state(data):
    write_json_atomic(_state_path(), data)


def _case_mock_ids(ctx):
    """{case_index: [mockId, ...]} —— 来自 cases_manifest（flow-init 派生）。"""
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
# 物化：母本 → 运行域副本（服务端克隆 + 自证）
# ═══════════════════════════════════════════════════════════════════

def _record(cloned):
    """服务端克隆结果 → 落盘记录（runtime_id 必需，其余为诊断元信息）。"""
    record = {"runtime_id": str(cloned.get("mockId") or "").strip()}
    for key in _RULE_RECORD_FIELDS:
        record[key] = cloned.get(key)
    return record


def _clone_many(mock_ids, runtime_domain):
    """逐条把母本克隆到运行域，返回 {mockId: record}；任一失败即整体失败。

    **串行**执行，顺序 = union 顺序。理由：两个母本可能命中同一条 rule，而
    运行域里同 rule 只允许一条副本（平台按 rule 命中，多规则会互相遮蔽）。
    并发会让「最终副本内容是哪个」变成竞态；串行 + apply 阶段按 case 再刷一次，
    语义确定：**当前 case 声明的那条母本，一定在案发前刚被刷进副本**。
    """
    records, failed = {}, []
    for mid in mock_ids:
        cloned = appmock_clone(mid, mis=runtime_domain)
        if cloned.get("error"):
            failed.append(f"mockId={mid}: {cloned['error']}")
            continue
        record = _record(cloned)
        if not record["runtime_id"]:
            failed.append(f"mockId={mid}: 克隆未返回运行域 mockId")
            continue
        records[mid] = record
    if failed:
        raise MockError(
            "场景 Mock 物化失败（母本读取 / 克隆 / 自证任一步不通过）："
            + "；".join(failed)
        )
    return records


def _detect_conflicts(per_case, records):
    """同 case 内两个母本命中同一 (rule, method) → 规则层无法区分，必有一方被遮蔽。

    必须在物化**之后**做：rule/method 以平台侧真实匹配串为准（服务端克隆时读到的
    母本字段），不在引擎里二次推导，避免「引擎以为的 rule」与「平台实际匹配的 rule」
    出现第二份事实。
    """
    conflicts = []
    for ci, ids in per_case.items():
        seen = {}
        for mid in ids:
            record = records.get(mid) or {}
            key = (str(record.get("rule") or ""), record.get("method"))
            if key in seen:
                conflicts.append((ci, seen[key], mid, key[0]))
            else:
                seen[key] = mid
    return conflicts


def preflight(run_dir):
    """B0：物化每个 case 声明的母本到运行域 → 同 case 冲突检测 → 运行域清场。"""
    ctx = load_context(run_dir)
    if ctx is None:
        raise UsageError("flow-context.json 不存在，需先执行 flow-init")

    per_case = _case_mock_ids(ctx)
    union = _mock_union(per_case)
    meta = ctx.setdefault("meta", {})
    if not union:
        meta.update({"mock_union": [], "mock_on": [], "mock_map": {},
                     "mock_runtime_domain": ""})
        save_context(run_dir, ctx)
        print("MOCK-PREFLIGHT OK: 无场景 Mock，跳过物化")
        return 0

    runtime_domain = resolve_runtime_domain()
    records = _clone_many(union, runtime_domain)

    conflicts = _detect_conflicts(per_case, records)
    if conflicts:
        detail = "；".join(
            f"case[{ci}] mockId {a} 与 {b} 命中同一接口 rule={rule!r}"
            for ci, a, b, rule in conflicts
        )
        raise MockError(
            f"场景 Mock 声明冲突（同一 case 内同接口多规则，无法区分）：{detail}。"
            f"请合并为一条规则，或拆分为不同 case"
        )

    # 运行域清场：本域是本次 run 独占的，进入确定初始态（残留在复用号上的规则一律关闭）
    if not appmock_stop_all(mis=runtime_domain):
        raise MockError(f"运行域清场失败（stop-all domain={runtime_domain}）")

    _save_state({"runtime_domain": runtime_domain, "rules": records})
    meta["mock_union"] = union
    meta["mock_on"] = []
    meta["mock_map"] = {mid: records[mid]["runtime_id"] for mid in union}
    meta["mock_runtime_domain"] = runtime_domain
    save_context(run_dir, ctx)
    shapes = ", ".join(
        f"{mid}→{records[mid]['runtime_id']}({records[mid].get('shape')})"
        for mid in union
    )
    print(f"MOCK-PREFLIGHT OK: 物化 {len(union)} 条母本到运行域 {runtime_domain}，"
          f"副本均已自证与母本一致，已清场 [{shapes}]")
    return 0


# ═══════════════════════════════════════════════════════════════════
# case 级收敛：运行域 ON := M(case)
# ═══════════════════════════════════════════════════════════════════

def apply_case(run_dir, case_index):
    ctx = load_context(run_dir)
    if ctx is None:
        raise UsageError("flow-context.json 不存在，需先执行 flow-init")

    per_case = _case_mock_ids(ctx)
    if case_index not in per_case:
        raise UsageError(f"case-index {case_index} 不存在")
    declared = per_case[case_index]
    meta = ctx.setdefault("meta", {})
    mock_map = meta.get("mock_map") or {}
    missing = [mid for mid in declared if not mock_map.get(mid)]
    if missing:
        raise MockError(
            f"case {case_index} 声明的 mockId 未物化到运行域: {missing}"
            f"—— 预检未覆盖或物化失败，禁止带缺口执行"
        )

    runtime_domain = resolve_runtime_domain()
    target = [mock_map[mid] for mid in declared]
    on = list(meta.get("mock_on") or [])

    # ① 关：上一 case 开了、本 case 不需要的
    for runtime_id in list(on):
        if runtime_id not in target:
            if not appmock_off(runtime_id, mis=runtime_domain):
                raise MockError(f"mock off 失败: mockId={runtime_id}（case {case_index} 隔离失败）")
            on.remove(runtime_id)

    # ② 开：先把母本最新内容幂等刷进副本（服务端保证同 rule 复用 + 自证），再确保 ON。
    #    不能省这一步：N:1 共享同一 rule 时，副本内容必须由「当前 case 声明的母本」决定。
    for source_id, runtime_id in zip(declared, target):
        cloned = appmock_clone(source_id, mis=runtime_domain)
        if cloned.get("error"):
            raise MockError(
                f"运行域副本刷新失败: case={case_index} source={source_id}: {cloned['error']}"
            )
        refreshed_id = str(cloned.get("mockId") or "").strip()
        if refreshed_id != runtime_id:
            raise MockError(
                f"运行域副本漂移: case={case_index} source={source_id} "
                f"预检映射 runtime={runtime_id}，本次克隆得到 {refreshed_id}。"
                f"运行域可能被外部改动，请重跑 mock-preflight"
            )
        if not appmock_on(runtime_id, mis=runtime_domain):
            raise MockError(f"mock on 失败: mockId={runtime_id}")
        if runtime_id not in on:
            on.append(runtime_id)

    meta["mock_on"] = on
    save_context(run_dir, ctx)
    print(f"MOCK-APPLY OK: case={case_index} source={declared} runtime={target}")
    return 0


# ═══════════════════════════════════════════════════════════════════
# 收尾：运行域清场（域用完即归还号池，不恢复历史状态）
# ═══════════════════════════════════════════════════════════════════

def restore_all(run_dir):
    runtime_domain = current_runtime_domain()
    if not runtime_domain:
        print("MOCK-RESTORE SKIP: 无运行域租约")
        return 0

    ok = appmock_stop_all(mis=runtime_domain)
    ctx = load_context(run_dir)
    if ctx is not None:
        ctx.setdefault("meta", {})["mock_on"] = []
        save_context(run_dir, ctx)
    print(f"MOCK-RESTORE {'DONE' if ok else 'PARTIAL'}: 运行域 {runtime_domain} 已清场")
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
