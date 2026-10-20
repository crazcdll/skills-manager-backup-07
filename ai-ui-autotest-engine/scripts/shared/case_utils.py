import base64
import json
import os
import time

from shared.json_utils import write_json_atomic, read_json
import zlib

from shared.paths import (
    runs_root, flows_dir, SKILL_DIR, ensure_dirs,
    get_active_run,
)
from shared.intake import read_intake, update_intake
from shared.records import STEPS_FILENAME, SRC_NOTE, StepRecord

def resolve_case_path(path):
    if not path:
        return ""
    root = runs_root()
    resolved = path if os.path.isabs(path) else os.path.join(root, path)
    real = os.path.realpath(resolved)
    if os.path.commonpath([real, os.path.realpath(root)]) != os.path.realpath(root):
        raise ValueError(f"禁止在 run 工作区之外创建目录: {resolved}")
    return resolved

def current_case_workspace(root_dir, ctx):
    workspace = ctx.get("current_case", {}).get("workspace_dir", "")
    if not workspace:
        raise ValueError("当前 Case 未初始化工作目录")
    return workspace if os.path.isabs(workspace) else os.path.join(root_dir, workspace)


def active_case_workspace():
    """返回当前激活 Case 的工作目录（绝对路径），无活跃 Case 时返回空串。

    ⚠️ active_run 文件里存的是 **run 目录名**（flow-init --dir 的值，如
    flow01-scroll-semantic），而每个 Case 的实际工作区是 run 目录下的
    case_NN/（记录在 flow-context 的 current_case.workspace_dir）。
    直接用 resolve_case_path(get_active_run()) 得到的是 run 级目录，
    往里写 Case 级产物会与断言策略（ExecutionContext.case_ws）分叉成两份。
    凡是要写 Case 级产物（sidecar/截图等）一律用本函数。
    """
    case_name = get_active_run()
    if not case_name:
        return ""
    run_dir = resolve_case_path(case_name)
    if not run_dir:
        return ""
    # 延迟导入：core.flow.flow_context 反向依赖本模块，顶层导入会形成循环依赖
    from execution.engine.flow.flow_context import load_context
    ctx = load_context(run_dir)
    if not ctx:
        return ""
    return current_case_workspace(run_dir, ctx)


def active_case_diagnostics_dir():
    """返回当前激活 Case 的 diagnostics 目录（必要时创建）；无活跃 Case 时返回空串。"""
    workspace = active_case_workspace()
    if not workspace:
        return ""
    diag_dir = os.path.join(workspace, "diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    return diag_dir

def resolve_mis(explicit_mis=None):
    """资源 MIS（设备归属 / 报告 user_id）。

    优先级：显式参数 > `HOTEL_UI_MIS` 环境变量 > 本 workspace 的 intake 答案
    > 当前用户身份（`shared.user_identity.current_user_mis`，与信息收集阶段的派生同源）。
    """
    if explicit_mis:
        return str(explicit_mis).strip()
    value = os.environ.get("HOTEL_UI_MIS", "").strip()
    if value:
        return value
    mis = read_intake().get("resource_mis")
    if mis:
        return str(mis).strip()
    # 兜底：intake 尚未生成（如无活跃 run）时回落到当前身份，与派生题同源。
    from shared.user_identity import current_user_mis
    return current_user_mis()


def set_current_user_mis(mis):
    value = str(mis).strip()
    if not value:
        raise ValueError("MIS 不能为空")
    update_intake({"resource_mis": value})
    os.environ["HOTEL_UI_MIS"] = value


def resolve_mock_domain(explicit_mis=None):
    """AppMock 工作域（虚拟 mis）—— 与 resource_mis 恒定分离。

    所有 AppMock 能力（设备端 enable / 规则 / 录制 / 环境 / 泳道 / 域名映射）
    都以本值为 userDomain；**不回落**到 resource_mis（回落即串味）。

    优先级：显式参数 > `HOTEL_UI_MOCK_DOMAIN` 环境变量 > 本 workspace 的 intake 答案。
    """
    if explicit_mis:
        return str(explicit_mis).strip()
    value = os.environ.get("HOTEL_UI_MOCK_DOMAIN", "").strip()
    if value:
        return value
    md = read_intake().get("mock_domain")
    return str(md).strip() if md else ""


def set_mock_domain(mis):
    """写入 AppMock 工作域（虚拟 mis）到 intake + 进程环境。"""
    value = str(mis).strip()
    if not value:
        raise ValueError("mock_domain 不能为空")
    update_intake({"mock_domain": value})
    os.environ["HOTEL_UI_MOCK_DOMAIN"] = value


def _timer_path(case_ws):
    return os.path.join(case_ws, ".timer")

def _timer_start(case_ws):
    os.makedirs(case_ws, exist_ok=True)
    with open(_timer_path(case_ws), "w", encoding="utf-8") as f:
        f.write(str(time.time()))

def _timer_read_and_clear(case_ws):
    path = _timer_path(case_ws)
    try:
        with open(path, encoding="utf-8") as f:
            started = float(f.read())
        os.remove(path)
        return max(0, int((time.time() - started) * 1000))
    except (OSError, ValueError):
        return None

def _infer_ms_from_last_step(case_ws):
    path = os.path.join(case_ws, "steps.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        return rows[-1].get("ms") if rows else None
    except (OSError, json.JSONDecodeError):
        return None

def encode_scheme_payload(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(raw)).decode().rstrip("=")



# ═══════════════════════════════════════════════════════════════════
# 原始用例原文：执行期一次性读取 → 内嵌进 case 日志
#
# 背景：报告需要展示「原始 md 测试用例」。历史做法是记录一个路径、上报时再按
# 路径重读，一旦路径变动/目录被清理/记录不准，内容就丢失。改为：执行期（case-init）
# 把原文直接作为无判定备注写进 case 的 steps.jsonl，上报时只读日志，不再依赖路径。
# ═══════════════════════════════════════════════════════════════════

def _read_text_safe(path):
    """读取文本文件内容，不可读时返回空串。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def resolve_flow_content(flow_source="", name_hints=None):
    """解析原始 Flow .md 的路径与内容（执行期读取，供日志内嵌）。

    解析顺序：
      1) flow_source 指向可读文件 → 直接用（相对路径按 SKILL_DIR 解析）
      2) 否则在 .run/tasks/<task>/inputs/flows/ 按 name_hints（case_id/case_name）匹配文件名
      3) 否则该目录下恰好只有一个 .md → 用它
    返回 (path, content, name)；解析不到返回 ("", "", "")。
    """
    if flow_source:
        path = flow_source if os.path.isabs(flow_source) else os.path.join(SKILL_DIR, flow_source)
        path = os.path.normpath(path)
        content = _read_text_safe(path)
        if content:
            return path, content, os.path.basename(path)

    try:
        md_files = sorted(
            f for f in os.listdir(flows_dir())
            if f.endswith(".md") and os.path.isfile(os.path.join(flows_dir(), f))
        )
    except OSError:
        md_files = []

    for hint in (name_hints or ()):
        hint = str(hint or "").strip()
        if not hint:
            continue
        for f in md_files:
            if hint in f:
                path = os.path.join(flows_dir(), f)
                return path, _read_text_safe(path), f
    if len(md_files) == 1:
        path = os.path.join(flows_dir(), md_files[0])
        return path, _read_text_safe(path), md_files[0]
    return "", "", ""


def append_source_notes(case_workspace, entries):
    """把原始用例原文作为无判定备注写进 case 的 steps.jsonl（幂等）。

    entries: [{"source": "flow_source"|"steps_input", "desc": ..., "note": ...}]
    同 source 已存在则跳过，避免 case-init 重跑产生重复。返回实际写入的 source 列表。
    """
    if not case_workspace or not entries:
        return []
    path = os.path.join(case_workspace, STEPS_FILENAME)
    existing = set()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    src = rec.get("source")
                    if src:
                        existing.add(src)
        except (OSError, UnicodeDecodeError) as e:
            # 惰性导入：shared.errors → exception_reporter → 本模块 会构成循环依赖
            from shared.errors import soft_fail
            soft_fail("infra", "SOURCE_NOTES_READ_FAILED", f"{path}: {e}")

    written = []
    for entry in entries:
        src = entry.get("source")
        if not src or src in existing or not entry.get("note"):
            continue
        StepRecord(
            sid="",
            src=SRC_NOTE,
            type=src,
            desc=entry.get("desc", ""),
            ok=None,
            status="note",
            note=entry["note"],
            extra={"source": src},
        ).append(case_workspace)
        existing.add(src)
        written.append(src)
    return written
