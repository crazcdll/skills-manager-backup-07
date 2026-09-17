import base64
import json
import os
import time

from core.util.json_utils import write_json_atomic, read_json
import zlib

from core.util.paths import (
    CONFIG_DIR, CASES_DIR, ENV_ANSWERS_FILE, ensure_dirs, RUN_DIR, get_active_case,
)

def resolve_case_path(path):
    if not path:
        return ""
    resolved = path if os.path.isabs(path) else os.path.join(CASES_DIR, path)
    real = os.path.realpath(resolved)
    if os.path.commonpath([real, os.path.realpath(RUN_DIR)]) != os.path.realpath(RUN_DIR):
        raise ValueError(f"禁止在 RUN_DIR 之外创建测试运行目录: {resolved}")
    return resolved

def current_case_workspace(root_dir, ctx):
    workspace = ctx.get("current_case", {}).get("workspace_dir", "")
    if not workspace:
        raise ValueError("当前 Case 未初始化工作目录")
    return workspace if os.path.isabs(workspace) else os.path.join(root_dir, workspace)


def active_case_workspace():
    """返回当前激活 Case 的工作目录（绝对路径），无活跃 Case 时返回空串。

    ⚠️ active_case 文件里存的是 **run 目录名**（flow-init --dir 的值，如
    flow01-scroll-semantic），而每个 Case 的实际工作区是 run 目录下的
    case_NN/（记录在 flow-context 的 current_case.workspace_dir）。
    直接用 resolve_case_path(get_active_case()) 得到的是 run 级目录，
    往里写 Case 级产物会与断言策略（ExecutionContext.case_ws）分叉成两份。
    凡是要写 Case 级产物（sidecar/截图等）一律用本函数。
    """
    case_name = get_active_case()
    if not case_name:
        return ""
    run_dir = resolve_case_path(case_name)
    if not run_dir:
        return ""
    # 延迟导入：core.flow.flow_context 反向依赖本模块，顶层导入会形成循环依赖
    from core.flow.flow_context import load_context
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

def read_env_answers():
    """读取 .config/env_answers.json（跨轮持久化的环境答案）。

    返回 dict，不存在时返回空 dict。
    用于 env-required 两轮调用之间自动传递已确认的字段值。
    """
    return read_json(ENV_ANSWERS_FILE, default={})


def save_env_answers(answers: dict):
    """保存 env_answers.json，与已有的答案合并（不覆盖未涉及字段）。"""
    existing = read_env_answers()
    existing.update(answers)
    ensure_dirs()
    write_json_atomic(ENV_ANSWERS_FILE, existing)


def resolve_mis(explicit_mis=None):
    if explicit_mis:
        return str(explicit_mis).strip()
    value = os.environ.get("HOTEL_UI_MIS", "").strip()
    if value:
        return value
    answers = read_env_answers()
    return str(answers.get("mis", "")).strip() if answers.get("mis") else ""


def set_current_user_mis(mis):
    value = str(mis).strip()
    if not value:
        raise ValueError("MIS 不能为空")
    save_env_answers({"mis": value})
    os.environ["HOTEL_UI_MIS"] = value


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


ENV_TYPE_OPTIONS = {"A": "线上", "B": "泳道/域名映射", "C": "alpha 测试", "D": "默认已登录"}

def cmd_save_answers(args):
    """save-answers 命令：持久化环境答案到 env_answers.json。"""
    answers = json.loads(args.answers)
    save_env_answers(answers)
    print(f"\u2705 \u5df2\u6301\u4e45\u5316 {len(answers)} \u4e2a\u7b54\u6848: {list(answers.keys())}")
    if "env_type" in answers:
        v = answers["env_type"]
        print(f"  \u2139\ufe0f env_type={v} \u5bf9\u5e94\u73af\u5883: {ENV_TYPE_OPTIONS.get(v, '?')} \u2014 \u786e\u8ba4\u8fd9\u662f AskQuestion \u7528\u6237\u9009\u62e9\u7684\u7ed3\u679c\uff0c\u800c\u975e AI \u81ea\u884c\u5047\u5b9a")
