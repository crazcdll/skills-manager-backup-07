import json
import os
import shutil
import time

from core.util.json_utils import write_json_atomic, read_json

def audit_dir(base_dir):
    return os.path.join(base_dir, "audit")

def manifest_path(base_dir):
    return os.path.join(audit_dir(base_dir), "run-manifest.json")

def events_path(base_dir):
    return os.path.join(audit_dir(base_dir), "run-events.jsonl")

def create_run_manifest(base_dir, ctx):
    """写入运行清单（run-manifest.json）。

    只记录运行标识/状态/用例清单等审计元信息；不再记录 steps-input 的路径与哈希
    —— 原始用例原文由 case-init 随日志落盘（case_utils.append_source_notes），
    报告按日志读取，无需按路径回查。
    """
    data = {
        "run_id": ctx["meta"]["batch_run_id"],
        "state": "active",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "flow_name": ctx["meta"]["flow_name"],
        "expected_cases": len(ctx.get("cases_manifest", [])),
        "cases": [{"case_id": c["case_id"], "case_name": c["case_name"]} for c in ctx.get("cases_manifest", [])],
    }
    write_json_atomic(manifest_path(base_dir), data)
    append_event(base_dir, "run.initialized", {"expected_cases": data["expected_cases"]})

def append_event(base_dir, event, details=None, severity="info"):
    """向 run-events.jsonl 追加一条事件记录，作为所有时间线数据的唯一写入接口。

    参数:
        base_dir: 运行根目录
        event: 事件类型，建议命名 event_type（如 engine.device.created、ai.image_checked）
        details: 事件详情 dict
        severity: 严重程度 info/warn/error/fatal
    """
    os.makedirs(audit_dir(base_dir), exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event,
        "severity": severity,
        "details": details or {},
    }
    with open(events_path(base_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def register_evidence(base_dir, evidence_type, method, status, artifacts=None, details=None, stage="", case_index=None):
    """注册一条证据记录到 run-events.jsonl（不再双写 evidence-manifest.json）。

    evidence 本质是一种事件类型，通过 event=evidence.registered 表示。
    所有字段直接写入 details 中，不再额外维护一个独立文件。
    """
    details = dict(details or {})
    if artifacts:
        details["artifacts"] = [
            os.path.relpath(p, base_dir) if os.path.isabs(p) else p
            for p in artifacts if p
        ]
    details["evidence_type"] = evidence_type
    details["method"] = method
    details["evidence_status"] = status
    details["stage"] = stage
    if case_index is not None:
        details["case_index"] = case_index
    append_event(base_dir, "evidence.registered", details, severity="info")
    return details

def verified_evidence(base_dir, evidence_type):
    """查询 JSONL 中已验证的 evidence 记录（替代旧版 evidence-manifest.json 查询）。"""
    from core.util.json_utils import read_jsonl
    items = read_jsonl(events_path(base_dir))
    return [
        e for e in items
        if e.get("event") == "evidence.registered"
        and e.get("details", {}).get("evidence_type") == evidence_type
        and e.get("details", {}).get("evidence_status") == "verified"
    ]

def _sanitize_archive(archive_dir):
    for _root, _dirs, _files in os.walk(archive_dir):
        for _name in _files:
            if _name != "flow-context.json":
                continue
            _p = os.path.join(_root, _name)
            try:
                _ctx = read_json(_p, None)
                if _ctx and isinstance(_ctx.get("env"), dict):
                    if _ctx["env"].get("_password_raw") is not None:
                        _ctx["env"]["_password_raw"] = "***"
                        write_json_atomic(_p, _ctx)
            except Exception:
                pass

def archive_run(base_dir, output_dir):
    """整目录归档：将 .run/ 完整复制到 output/run/，返回归档目录路径。"""
    from core.util.paths import RUN_DIR

    archive_dir = os.path.join(output_dir, "run")

    # 先在原位置更新 manifest 状态并追加事件，再整目录复制
    manifest = read_json(manifest_path(base_dir), {})
    manifest["state"] = "archived"
    manifest["archived_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json_atomic(manifest_path(base_dir), manifest)
    append_event(base_dir, "run.archived", {"archive_dir": archive_dir})

    # 整目录批量复制 .run/ → output/run/
    if os.path.isdir(RUN_DIR):
        shutil.copytree(RUN_DIR, archive_dir, dirs_exist_ok=True)
        # 清理归档中的瞬态文件
        for transient in ("active_case",):
            _path = os.path.join(archive_dir, transient)
            if os.path.exists(_path):
                os.remove(_path)
        for _root, _dirs, _files in os.walk(archive_dir):
            for _name in _files:
                if _name == ".timer":
                    os.remove(os.path.join(_root, _name))

    _sanitize_archive(archive_dir)

    return archive_dir