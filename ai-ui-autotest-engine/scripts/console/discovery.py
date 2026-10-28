#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发现层：扫描 `$STATE/run/tasks/*`（run 状态）与服务端设备池（设备归属），
构建控制台需要的 run / device 只读模型。**不做任何业务判定**。
"""
import json
import os
import sys
import time

from shared.paths import TASKS_DIR, OUTPUT_DIR
from console import config

# flow-context.env 允许暴露的字段（脱敏白名单，对齐报告侧 SAFE_ENV_KEYS）
_SAFE_ENV_KEYS = ("type", "env_name", "auth_method", "ptest", "bundle_lock", "swimline")


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _iter_tasks():
    try:
        for name in sorted(os.listdir(TASKS_DIR)):
            path = os.path.join(TASKS_DIR, name)
            if os.path.isdir(path):
                yield name, path
    except OSError:
        return


def _read_active_run(task_path):
    try:
        with open(os.path.join(task_path, "active_run"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _norm_stages(sop):
    stages = (sop or {}).get("stages", []) if isinstance(sop, dict) else []
    out = []
    for s in stages:
        if not isinstance(s, dict):
            continue
        out.append({
            "id": s.get("id", ""),
            "desc": s.get("desc", ""),
            "layer": s.get("layer", ""),
            "case_index": s.get("case_index"),
            "status": s.get("status", "pending"),
            "started_at": s.get("started_at"),
            "completed_at": s.get("completed_at"),
            "failed_at": s.get("failed_at"),
            "skip_reason": s.get("skip_reason"),
            "error": s.get("error"),
        })
    return out


def _count_steps(case_dir):
    """统计某 case 的 steps.jsonl 通过/失败数。"""
    total = passed = failed = 0
    path = os.path.join(case_dir, "steps.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                total += 1
                if rec.get("ok") == 1:
                    passed += 1
                elif rec.get("ok") == 0:
                    failed += 1
    except OSError:
        pass
    return total, passed, failed


def _cases(run_dir, manifest, fc=None):
    cases = []
    # cases 目录名是 case_tag（case_01），case_id 可能是中文/带斜杠的业务 id；
    # 因此必须按 flow-context 的 case_tag 映射，不能用「目录顺序 ↔ manifest 顺序」猜。
    by_tag = {}
    for item in (fc or {}).get("cases_manifest") or []:
        tag = (item or {}).get("case_tag") or ""
        if tag:
            by_tag[tag] = item
    entries = manifest.get("cases") or []
    cases_root = os.path.join(run_dir, "cases")
    try:
        names = sorted(n for n in os.listdir(cases_root)
                       if os.path.isdir(os.path.join(cases_root, n)))
    except OSError:
        names = []
    for idx, name in enumerate(names):
        cdir = os.path.join(cases_root, name)
        total, passed, failed = _count_steps(cdir)
        item = by_tag.get(name) or (entries[idx] if idx < len(entries) else {})
        cid = (item or {}).get("case_id", "")
        status = "pending"
        if failed:
            status = "failed"
        elif total and passed == total:
            status = "passed"
        elif total:
            status = "running"
        cases.append({
            "index": idx,
            "dir": name,
            "case_id": cid or name,
            "case_name": (item or {}).get("case_name", name),
            "steps_total": total,
            "steps_pass": passed,
            "steps_fail": failed,
            "status": status,
        })
    return cases


def discover_runs():
    runs = []
    now = time.time()
    for ws, task_path in _iter_tasks():
        run = _read_active_run(task_path)
        candidate_dirs = []
        if run:
            candidate_dirs.append((run, os.path.join(task_path, "runs", run)))
        runs_root = os.path.join(task_path, "runs")
        try:
            for name in sorted(os.listdir(runs_root)):
                d = os.path.join(runs_root, name)
                if os.path.isdir(d) and name != run:
                    candidate_dirs.append((name, d))
        except OSError:
            pass

        for run_name, run_dir in candidate_dirs:
            fc_path = os.path.join(run_dir, "flow-context.json")
            fc = _read_json(fc_path)
            if not isinstance(fc, dict):
                continue
            meta = fc.get("meta", {}) or {}
            env = fc.get("env", {}) or {}
            manifest = _read_json(os.path.join(run_dir, "audit", "run-manifest.json"), {}) or {}
            stages = _norm_stages(fc.get("sop"))
            cur = next((s["id"] for s in stages if s["status"] == "running"), "")
            if not cur:
                cur = next((s["id"] for s in reversed(stages) if s["status"] == "completed"), "")
            # 运行状态：manifest.state 优先，否则按 sop 判定
            # 注意：`active_run` 是一个**只写不清**的指针（flow-init 写入、收尾不删除），
            # 所以不能只靠它判断“活跃”；这里用产物 mtime 做存活判据：
            # 超过 SESSION_STALL_SEC 没有更新 → stalled（崩溃/中断的运行不会永久显示 running）。
            state = manifest.get("state") or ("active" if fc_path else "unknown")
            all_done = bool(stages) and all(s["status"] in ("completed", "skipped", "failed")
                                            for s in stages)
            updated_at = _mtime(fc_path)
            fresh = (now - updated_at) <= config.SESSION_STALL_SEC
            status = "archived" if state == "archived" else (
                "finished" if all_done else ("running" if fresh else "stalled"))
            devices_serial = meta.get("device_serial") or ""
            runs.append({
                "task": ws,
                "run": run_name,
                "batch_id": meta.get("batch_id", ""),
                "active": run_name == run and fresh,
                "flow_name": meta.get("flow_name") or run_name,
                "device_type": meta.get("device_type", ""),
                "platform": meta.get("platform", ""),
                "app": meta.get("app", ""),
                "device_serial": devices_serial,
                "scrcpy_url": meta.get("scrcpyUrl", "") or "",
                "session_id": meta.get("session_id", "") or "",
                "env": {k: env.get(k) for k in _SAFE_ENV_KEYS if env.get(k) is not None},
                "status": status,
                "current_stage": cur,
                "stages": stages,
                "cases": _cases(run_dir, manifest, fc),
                "started_at": manifest.get("created_at") or "",
                "updated_at": updated_at,
                "run_dir": run_dir,
            })
    # active 优先、更新时间倒序
    runs.sort(key=lambda r: (not r["active"], -r["updated_at"]))
    return runs


def _parse_owner(owner):
    """owner = `<run>#<task>`（见 device_lease.lease_owner）。"""
    if not owner:
        return "", ""
    if "#" in owner:
        run, task = owner.split("#", 1)
        return run, task
    return owner, ""


def _ts(iso_text):
    """ISO 时间串 → epoch 秒（解析失败返回 0）。"""
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(
            str(iso_text or "").replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return 0


def _server_devices():
    """服务端设备池全量（权威口径）。

    后端不可达时**向上抛异常**，由调用方决定是沿用上一轮快照还是回退为空：
    在这里默默返回 [] 会让设备面板在一次网络超时后整页闪空，看起来像“池子没了”。
    """
    from resources.device_pool.pool_api import list_devices
    rows = []
    for provider in ("sandbox", "conan"):
        data = list_devices(provider=provider, page_size=500)
        rows.extend(data.get("rows") or [])
    return rows


_STATE_TO_STATUS = {
    "in_use": "active",
    "idle": "idle",
    "external": "idle",
    "draining": "draining",
    "quarantined": "quarantined",
    "broken": "broken",
}


def discover_devices(runs):
    """设备发现：以服务端 `device_registry` 为准，关联 run 的 flow-context 补展示信息。

    不再读本地租约文件：它只包含"本机这个 workspace"的租约，看不到别人占了什么，
    用它渲染设备面板会长期给出错误结论（空闲实则被占）。
    """
    by_serial = {}
    for r in runs:
        serial = r.get("device_serial")
        if serial:
            by_serial[serial] = r
    now = int(time.time())
    devices = []
    for row in _server_devices():
        serial = str(row.get("device_id") or "")
        if not serial:
            continue
        run_name, task_name = _parse_owner(row.get("lease_owner") or "")
        run = next((r for r in runs if r["run"] == run_name and r["task"] == task_name), None)
        if run is None:
            run = by_serial.get(serial)
        platform = row.get("platform") or (run or {}).get("platform", "")
        scrcpy_url = (run or {}).get("scrcpy_url", "")
        device_type = "cloud-emulator" if row.get("provider") == "conan" else "sandbox"
        preview_kind = "scrcpy" if (scrcpy_url and platform == "android") else "screenshot"
        # sandbox 的 device_id 是 UUID，真实 adb 地址在 connect_address；conan 两者相同。
        adb_address = (row.get("connect_address")
                       or (run or {}).get("device_serial")
                       or (serial if ":" in serial else ""))
        hb_age = max(0, now - _ts(row.get("last_used_at") or row.get("updated_at")))
        state = str(row.get("state") or "idle")
        devices.append({
            "serial": serial,
            "device_type": device_type,
            "platform": platform,
            "app": (run or {}).get("app", ""),
            "task": task_name,
            "run": run_name,
            "flow_name": (run or {}).get("flow_name", ""),
            "session_id": (run or {}).get("session_id", ""),
            "current_stage": (run or {}).get("current_stage", ""),
            "scrcpy_url": scrcpy_url,
            "adb_address": adb_address,
            "preview_kind": preview_kind,
            "state": state,
            "owner": row.get("lease_owner") or "",
            "lease_expires_at": row.get("lease_expires_at"),
            "status": _STATE_TO_STATUS.get(state, state),
            "heartbeat_age": hb_age,
        })
    devices.sort(key=lambda d: (d["status"] != "active", d["platform"], d["serial"]))
    return devices


def discover_sessions(runs):
    """会话（= workspace / task）列表：控制台日志归属的**唯一稳定单元**。

    以 `$STATE/run/tasks/*` 为准 —— `task` 从 `ws-init` 起即存在，**不依赖** `flow-init`(run)
    或 `device create`，因此“工作区一建立”就能归属并展示日志；再合并该 task 下
    最新 run 的展示信息（flow_name / status / device_serial）。
    """
    sessions = {}
    now = time.time()
    for ws, task_path in _iter_tasks():
        ts = _mtime(task_path)
        sessions[ws] = {
            "task": ws,
            "run": _read_active_run(task_path),
            "flow_name": "",
            # 默认不是 running：没有 run 的工作区（ws-init 后没跑起来/已收尾）只按最近活跃时间判定，
            # 否则历史空目录会永久计入「活跃会话」。
            "status": "running" if now - ts <= config.SESSION_STALL_SEC else "idle",
            "device_serial": "",
            "updated_at": ts,
        }
    # runs 已按 active 优先、更新时间倒序；每个 task 只取第一个（最新/最活跃）作为代表，
    # 避免更旧的 run 反过来覆盖状态。
    merged = set()
    for r in runs:
        s = sessions.get(r["task"])
        if not s or r["task"] in merged:
            continue
        merged.add(r["task"])
        if r.get("active") or not s["run"]:
            s["run"] = r.get("run") or s["run"]
        s["flow_name"] = s["flow_name"] or r.get("flow_name", "")
        s["status"] = r.get("status", s["status"])
        s["device_serial"] = r.get("device_serial") or s["device_serial"]
        s["updated_at"] = max(s["updated_at"], r.get("updated_at", 0))
    return sorted(sessions.values(), key=lambda s: -s["updated_at"])


def discover():
    """一次性快照（容错版）：设备后端不可达时设备为空。

    ⚠️ 控制台服务不用它 —— 它需要「设备刷新失败沿用上一轮快照」，
    因此 `console/server.py` 自己按两个节奏分别调用三个 discover_* 函数。
    """
    runs = discover_runs()
    try:
        devices = discover_devices(runs)
    except Exception as e:  # noqa: BLE001 —— 兼容入口：读不到设备就当没有
        sys.stderr.write(f"[console] 设备发现失败: {e}\n")
        devices = []
    sessions = discover_sessions(runs)
    return runs, devices, sessions


def history(limit=50):
    """历史 run（`$STATE/reports/<batch>/<run>/`）列表，只读回看。

    以目录级 `meta.json` 为主契约（不解析目录名）；旧扁平布局不做兼容。
    """
    items = []
    try:
        batches = sorted(os.listdir(OUTPUT_DIR), reverse=True)
    except OSError:
        return items
    for batch in batches:
        if batch.startswith("."):
            continue
        bdir = os.path.join(OUTPUT_DIR, batch)
        if not os.path.isdir(bdir):
            continue
        try:
            run_names = sorted(os.listdir(bdir), reverse=True)
        except OSError:
            continue
        for name in run_names:
            if name.startswith("."):
                continue
            rdir = os.path.join(bdir, name)
            if not os.path.isdir(rdir):
                continue
            meta = _read_json(os.path.join(rdir, "meta.json"))
            rep = _read_json(os.path.join(rdir, "report.json"))
            if not isinstance(meta, dict) and not isinstance(rep, dict):
                continue
            meta = meta if isinstance(meta, dict) else {}
            rep = rep if isinstance(rep, dict) else {}
            items.append({
                "id": meta.get("report_id") or rep.get("id") or f"{batch}/{name}",
                "batch_id": meta.get("batch_id") or batch,
                "run_id": meta.get("run_id") or name,
                "run_name": meta.get("run_name") or name,
                "title": meta.get("title") or rep.get("title", ""),
                "timestamp": meta.get("timestamp") or rep.get("timestamp", ""),
                "device": meta.get("device") or rep.get("device", ""),
                "platform": meta.get("platform") or rep.get("platform", ""),
                "run_status": meta.get("run_status") or rep.get("run_status", ""),
                "summary": meta.get("batch_summary") or rep.get("batch_summary", {}),
                "archive_dir": meta.get("archive_dir", ""),
                "dir": os.path.join(batch, name),
                "updated_at": _mtime(rdir),
            })
    items.sort(key=lambda item: (item["updated_at"], item["timestamp"]), reverse=True)
    return items[:limit]
