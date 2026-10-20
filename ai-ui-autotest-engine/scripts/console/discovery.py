#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发现层：扫描 `.run/tasks/*`（run 状态）与 `.device-pool/leases.json`（设备归属），
构建控制台需要的 run / device 只读模型。**不做任何业务判定**。
"""
import json
import os
import time

from shared.paths import TASKS_DIR, OUTPUT_DIR
from resources.device_pool.lease_store import read_leases

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


def _cases(run_dir, manifest):
    cases = []
    cm = {c.get("case_id"): c for c in (manifest.get("cases") or [])}
    cases_root = os.path.join(run_dir, "cases")
    try:
        names = sorted(n for n in os.listdir(cases_root)
                       if os.path.isdir(os.path.join(cases_root, n)))
    except OSError:
        names = []
    for idx, name in enumerate(names):
        cdir = os.path.join(cases_root, name)
        total, passed, failed = _count_steps(cdir)
        # case_id 从 manifest 推断（顺序对应），缺省用目录名
        cid = ""
        if idx < len(manifest.get("cases") or []):
            cid = (manifest["cases"][idx] or {}).get("case_id", "")
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
            "case_name": (manifest.get("cases") or [{}])[idx].get("case_name", name)
            if idx < len(manifest.get("cases") or []) else name,
            "steps_total": total,
            "steps_pass": passed,
            "steps_fail": failed,
            "status": status,
        })
    return cases


def discover_runs():
    runs = []
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
            state = manifest.get("state") or ("active" if fc_path else "unknown")
            all_done = bool(stages) and all(s["status"] in ("completed", "skipped", "failed")
                                            for s in stages)
            status = "archived" if state == "archived" else (
                "finished" if all_done else "running")
            devices_serial = meta.get("device_serial") or ""
            runs.append({
                "task": ws,
                "run": run_name,
                "active": run_name == run,
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
                "cases": _cases(run_dir, manifest),
                "started_at": manifest.get("created_at") or "",
                "updated_at": _mtime(fc_path),
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


def discover_devices(runs):
    """设备发现：租约（跨 workspace 共享）为主，关联 run 的 flow-context 补平台信息。"""
    leases = read_leases()
    by_serial = {}
    for r in runs:
        serial = r.get("device_serial")
        if serial:
            by_serial[serial] = r
    now = int(time.time())
    devices = []
    for resource_id, lease in leases.items():
        lease = lease or {}
        run_name, task_name = _parse_owner(lease.get("owner", ""))
        run = next((r for r in runs if r["run"] == run_name and r["task"] == task_name), None)
        if run is None and resource_id in by_serial:
            run = by_serial[resource_id]
        hb_age = now - int(lease.get("heartbeat_at", 0) or 0)
        platform = (run or {}).get("platform", "")
        scrcpy_url = (run or {}).get("scrcpy_url", "")
        device_type = lease.get("device_type") or (run or {}).get("device_type", "")
        preview_kind = "scrcpy" if (scrcpy_url and platform == "android") else "screenshot"
        # 设备 adb 地址：sandbox 的租约键是 sandboxId(UUID)，真实 adb 地址在 run 的 flow-context 里；
        # cloud-emulator 的租约键本身就是 ip:port。构造 scrcpy 的 WS 参数（udid）需要它。
        adb_address = (run or {}).get("device_serial") or (resource_id if ":" in resource_id else "")
        devices.append({
            "serial": resource_id,
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
            "status": "active" if hb_age < 120 else ("idle" if hb_age < 900 else "stale"),
            "heartbeat_age": hb_age,
        })
    devices.sort(key=lambda d: (d["status"] != "active", d["platform"], d["serial"]))
    return devices


def discover_sessions(runs):
    """会话（= workspace / task）列表：控制台日志归属的**唯一稳定单元**。

    以 `.run/tasks/*` 为准 —— `task` 从 `ws-init` 起即存在，**不依赖** `flow-init`(run)
    或 `device create`，因此“工作区一建立”就能归属并展示日志；再合并该 task 下
    最新 run 的展示信息（flow_name / status / device_serial）。
    """
    sessions = {}
    for ws, task_path in _iter_tasks():
        sessions[ws] = {
            "task": ws,
            "run": _read_active_run(task_path),
            "flow_name": "",
            "status": "running",
            "device_serial": "",
            "updated_at": _mtime(task_path),
        }
    for r in runs:
        s = sessions.get(r["task"])
        if not s:
            continue
        if r.get("active") or not s["run"]:
            s["run"] = r.get("run") or s["run"]
        s["flow_name"] = s["flow_name"] or r.get("flow_name", "")
        s["status"] = r.get("status", s["status"])
        s["device_serial"] = r.get("device_serial") or s["device_serial"]
        s["updated_at"] = max(s["updated_at"], r.get("updated_at", 0))
    return sorted(sessions.values(), key=lambda s: -s["updated_at"])


def discover():
    runs = discover_runs()
    devices = discover_devices(runs)
    sessions = discover_sessions(runs)
    return runs, devices, sessions


def history(limit=50):
    """历史 run（output/run-<ts>/）列表，只读回看。"""
    items = []
    try:
        for name in sorted(os.listdir(OUTPUT_DIR), reverse=True):
            if not name.startswith("run-"):
                continue
            d = os.path.join(OUTPUT_DIR, name)
            rep = _read_json(os.path.join(d, "report.json"))
            if not isinstance(rep, dict):
                continue
            items.append({
                "id": rep.get("id", name),
                "title": rep.get("title", ""),
                "timestamp": rep.get("timestamp", ""),
                "device": rep.get("device", ""),
                "platform": rep.get("platform", ""),
                "run_status": rep.get("run_status", ""),
                "summary": rep.get("batch_summary", {}),
                "dir": name,
            })
            if len(items) >= limit:
                break
    except OSError:
        pass
    return items
