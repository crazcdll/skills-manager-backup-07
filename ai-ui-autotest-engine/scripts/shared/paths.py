#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-ui-autotest-engine 统一路径管理（作用域分层）。

作用域：

  mis 级        SKILL_DIR/.device-pool/          设备池租约（跨 workspace 共享，不被清理）
  用户级        SKILL_DIR/.credentials/          凭据缓存（跨 workspace）
  用户级        SKILL_DIR/.toolchain/             连接工具链路径缓存（adb/hdc，跨 workspace）
  workspace 级  SKILL_DIR/.run/tasks/<ws>/       工作区：config / inputs / tmp / runs
  run 级        …/tasks/<ws>/runs/<run>/         运行级文件（record_data / dumps / …）
  case 级       …/runs/<run>/cases/<case>/       步骤产物
  全局          SKILL_DIR/output/                报告归档

workspace 身份（**无模式**：1 个 Agent 与 N 个 Agent 走完全同一条路径）：
  ① `ws-init` 分配 workspace id（uuid）并生成入口脚本 `.run/ws/<id>/cli`
  ② 之后所有命令通过该入口执行；入口把 `AI_UITEST_TASK=<id>` 注入进程
  ③ 代码读 `AI_UITEST_TASK` 定位工作区；**没有则报错**（不回落默认值，
     避免任何“静默落到共享目录”的可能）

清理：`post-clean` 删除本 workspace 的工作区目录与入口（生命周期一致，不留残留）；
`preflight-clean` 仅清空内容（用于同一 workspace 内重置/重试）。
均不影响其他并行 workspace。
"""
import os
import shutil
import sys

# 本文件位于 <skill>/scripts/<pkg>/paths.py，向上 3 层即 Skill 根目录。
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── 全局 ─────────────────────────────────────────
RUN_DIR = os.path.join(SKILL_DIR, ".run")                   # 运行态根
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")              # 产物归档
DEVICE_POOL_DIR = os.path.join(SKILL_DIR, ".device-pool")   # mis 级：设备池（跨 workspace）
CREDENTIALS_DIR = os.path.join(SKILL_DIR, ".credentials")   # 用户级：凭据缓存（跨 workspace）
TOOLCHAIN_DIR = os.path.join(SKILL_DIR, ".toolchain")       # 用户级：连接工具链路径缓存（跨 workspace）
CONSOLE_DIR = os.path.join(SKILL_DIR, ".console")           # 机器级：统一控制台服务（跨 workspace，常驻、不随收尾清理）
TASKS_DIR = os.path.join(RUN_DIR, "tasks")                  # workspace 工作区根
WORKSPACES_DIR = os.path.join(RUN_DIR, "ws")                # workspace 入口根（<id>/cli）
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
SKILL_MD_PATH = os.path.join(SKILL_DIR, "SKILL.md")

# 注入 workspace 身份的环境变量（由 `.run/ws/<id>/cli` 入口脚本设置）
ENV_WORKSPACE = "AI_UITEST_TASK"


# ═══════════════════════════════════════════════════════════════════
# workspace 身份
# ═══════════════════════════════════════════════════════════════════

def get_active_task() -> str:
    """当前 workspace 标识（env `AI_UITEST_TASK`），无则空串。"""
    return os.environ.get(ENV_WORKSPACE, "").strip()


def require_active_task() -> str:
    """需要 workspace 的命令调用：无 workspace 直接报错（UsageError）。

    不回落默认值：回落会让多个 Agent 静默共用同一个工作区。
    """
    task = get_active_task()
    if not task:
        from shared.errors import UsageError  # 延迟导入：避开 paths ↔ errors 导入环
        raise UsageError(
            "未指定 workspace：请先执行 `python3 scripts/cli.py ws-init`，"
            "之后统一使用它输出的入口脚本执行所有命令"
        )
    return task


def workspace_entry_dir(task_id: str = None) -> str:
    """workspace 入口目录：`.run/ws/<workspace-id>/`。"""
    return os.path.join(
        WORKSPACES_DIR, ((task_id or "").strip() or require_active_task())
    )


def workspace_entry_path(task_id: str = None) -> str:
    """workspace 入口脚本：`.run/ws/<workspace-id>/cli`（由 `ws-init` 生成）。"""
    return os.path.join(workspace_entry_dir(task_id), "cli")


# ═══════════════════════════════════════════════════════════════════
# workspace 级路径
# ═══════════════════════════════════════════════════════════════════

def task_dir(task_id: str = None) -> str:
    """workspace 工作区根：`.run/tasks/<workspace-id>/`。"""
    return os.path.join(TASKS_DIR, ((task_id or "").strip() or require_active_task()))


def task_config_dir(task_id: str = None) -> str:
    """workspace 级配置目录（本 workspace 的配置类文件）。"""
    return os.path.join(task_dir(task_id), "config")


def task_inputs_dir(task_id: str = None) -> str:
    """workspace 级输入目录（Flow .md / CASES 等）。"""
    return os.path.join(task_dir(task_id), "inputs")


def flows_dir(task_id: str = None) -> str:
    """Flow .md 存放目录（原 `.run-input/flows/`）。"""
    return os.path.join(task_inputs_dir(task_id), "flows")


def steps_input_dir(task_id: str = None) -> str:
    """steps-input / CASES 中间产物目录（原 `.run/tmp/`）。"""
    return os.path.join(task_dir(task_id), "tmp")


def runs_root(task_id: str = None) -> str:
    """run 工作区根：`…/tasks/<task>/runs/`。"""
    return os.path.join(task_dir(task_id), "runs")


def active_run_file(task_id: str = None) -> str:
    """本 workspace 的 run 指针文件。"""
    return os.path.join(task_dir(task_id), "active_run")


def appmock_cookie_path() -> str:
    """AppMock SSO Cookie 缓存：`SKILL_DIR/.credentials/appmock_session_cookie.json`。

    它是**用户级凭据**（同一个用户在取同一张票），不是 workspace 状态：
    放在全局位置，多个并行 workspace 共用，且不依赖 workspace 存在。
    """
    return os.path.join(CREDENTIALS_DIR, "appmock_session_cookie.json")


def toolchain_env_path() -> str:
    """连接工具链路径缓存：`SKILL_DIR/.toolchain/toolchain.json`（用户级，跨 workspace）。

    adb/hdc 解析出的目录是机器级事实，必须落在用户级位置：既有 `ws-init` 这类
    「尚无 workspace」的命令要读，也不能被 workspace 收尾清理带走（详见
    shared/toolchain_env.py）。故意不依赖 workspace。
    """
    return os.path.join(TOOLCHAIN_DIR, "toolchain.json")


def check_deps_result_path(task_id: str = None) -> str:
    return os.path.join(task_dir(task_id), "check_deps_result.json")


def capabilities_path(task_id: str = None) -> str:
    """设备能力探测结果（`…/tasks/<ws>/capabilities.json`，workspace 级）。

    与 intake 同级：它描述"这台设备实测能干/不能干什么"，是**输入前提**
    而非 run 产物；同 workspace 多 run 复用，device setup 每次重探覆盖。
    """
    return os.path.join(task_dir(task_id), "capabilities.json")


def intake_path(task_id: str = None) -> str:
    """信息收集结果（Question Framework）：`…/tasks/<ws>/intake.json`（workspace 级）。

    它是「输入」而非「run 产物」：同 workspace 多 run 复用，且不受 run 级清理影响。
    """
    return os.path.join(task_dir(task_id), "intake.json")


def mis_heartbeat_marker_path(task_id: str = None) -> str:
    """虚拟 mis 命令级心跳的限流标记（workspace 级）：`…/tasks/<ws>/.mis_heartbeat`。

    内容为上次心跳的 epoch 秒；心跳是网络调用，不宜每条命令一次，故按时间限流。
    """
    return os.path.join(task_dir(task_id), ".mis_heartbeat")


# ═══════════════════════════════════════════════════════════════════
# run 选择（T1）
# ═══════════════════════════════════════════════════════════════════

def get_active_run() -> str:
    """当前 run 标识：读本 workspace 的 `active_run`（由 `flow-init --dir` 写入），
    无 workspace 或无 run 则空串。

    run 不承担隔离职责（一 workspace 一 run），因此不提供 env 覆盖入口。
    """
    if not get_active_task():
        return ""
    try:
        with open(active_run_file(), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def set_active_run(run_id: str):
    """写入本 workspace 的 `active_run`（`flow-init` 使用）。"""
    os.makedirs(task_dir(), exist_ok=True)
    p = active_run_file()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(run_id).strip())
    os.replace(tmp, p)


def run_dir(run_id: str = None) -> str:
    """run 工作区目录：`…/tasks/<task>/runs/<run-id>/`。"""
    rid = (run_id or get_active_run()).strip()
    if not rid:
        raise RuntimeError(
            "无活跃 run：请先执行 flow-init（写入 <task>/active_run）"
        )
    return os.path.join(runs_root(), rid)


def run_file(name: str, run_id: str = None) -> str:
    """run 工作区内的运行级文件路径（不含目录创建）。"""
    return os.path.join(run_dir(run_id), name)


# ─── 运行级（执行期）文件：随 run 隔离 ───
def record_data_path(run_id: str = None) -> str:
    return run_file("record_data.json", run_id)


def recording_active_path(run_id: str = None) -> str:
    return run_file("recording_active", run_id)


def inspect_tree_cache_path(run_id: str = None) -> str:
    return run_file("inspect_tree.json", run_id)


def inspect_tree_parsed_path(run_id: str = None) -> str:
    return run_file("inspect_tree_parsed.txt", run_id)


def auto_url_mapping_ids_path(run_id: str = None) -> str:
    return run_file("auto_url_mapping_ids.json", run_id)


def ptest_mock_id_path(run_id: str = None) -> str:
    return run_file("ptest_mock_id.json", run_id)


def dumps_dir(run_id: str = None) -> str:
    return run_file("dumps", run_id)


def mock_baseline_dir(run_id: str = None) -> str:
    return run_file("mock_baseline", run_id)


def active_run_context_path():
    """当前 run 的 flow-context.json 路径，不存在则返回 None。"""
    if not get_active_run():
        return None
    path = run_file("flow-context.json")
    return path if os.path.isfile(path) else None


# ═══════════════════════════════════════════════════════════════════
# 目录准备与清理（作用域 = 本 workspace）
# ═══════════════════════════════════════════════════════════════════

def ensure_dirs():
    """确保全局根存在；已指定 workspace 时同时确保其工作区目录存在。"""
    for d in (RUN_DIR, TASKS_DIR, WORKSPACES_DIR, DEVICE_POOL_DIR,
              CREDENTIALS_DIR, TOOLCHAIN_DIR, CONSOLE_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)
    if not get_active_task():
        return
    for d in (task_dir(), task_config_dir(), task_inputs_dir(),
              flows_dir(), steps_input_dir(), runs_root()):
        os.makedirs(d, exist_ok=True)


def _clear_dir(d):
    if os.path.isdir(d):
        for name in os.listdir(d):
            item = os.path.join(d, name)
            try:
                if os.path.isfile(item) or os.path.islink(item):
                    os.remove(item)
                elif os.path.isdir(item):
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass


def preflight_clean():
    """清空【本 workspace】工作区内容（不影响其他并行 workspace）。"""
    _clear_dir(task_dir())
    ensure_dirs()
    sys.stderr.write(f"[paths] preflight-clean 完成（workspace={get_active_task()}）\n")


def clean_post_test():
    """收尾：删除【本 workspace】的工作区目录与入口（不留残留）。"""
    task = require_active_task()
    shutil.rmtree(task_dir(), ignore_errors=True)
    shutil.rmtree(workspace_entry_dir(task), ignore_errors=True)
    sys.stderr.write(f"[paths] post-clean 完成（workspace={task} 已回收）\n")


def get_steps_input_dir() -> str:
    """steps-input 目录（本 workspace），供 SKILL.md 引用。"""
    ensure_dirs()
    return steps_input_dir()


def get_flows_dir() -> str:
    """Flow .md 目录（本 workspace），供 SKILL.md 引用。"""
    ensure_dirs()
    return flows_dir()


def resolve_input_path(raw: str) -> str:
    """解析 CLI `--input` 取值（作用域对齐）：

    - 绝对路径 → 原样；
    - **裸文件名**（无目录分隔）→ 本 workspace 的 steps-input 目录（`.run/tasks/<ws>/tmp/`）；
    - 含目录的相对路径 → 相对 SKILL_DIR。
    """
    raw = str(raw)
    if os.path.isabs(raw):
        return raw
    if os.sep not in raw and "/" not in raw:
        return os.path.join(steps_input_dir(), raw)
    return os.path.normpath(os.path.join(SKILL_DIR, raw))


# ═══════════════════════════════════════════════════════════════════
# 设备池（mis 级、跨 task）
# ═══════════════════════════════════════════════════════════════════

def device_pool_leases_path() -> str:
    """设备池租约文件：`SKILL_DIR/.device-pool/leases.json`。

    由 `resources.device_pool.lease_store.LocalFileLeaseStore` 作为默认存储后端。
    该目录在 `ensure_dirs()` 中创建，**不在** preflight/post-clean 清理范围
    （清理只作用于本 workspace）。
    """
    return os.path.join(DEVICE_POOL_DIR, "leases.json")


# ═══════════════════════════════════════════════════════════════════
# 统一控制台服务（机器级、跨 workspace、常驻）
# ═══════════════════════════════════════════════════════════════════

def console_dir() -> str:
    """控制台服务根目录：`SKILL_DIR/.console/`。

    与 `.device-pool/` 同构（机器级、跨 workspace、**不在** preflight/post-clean
    清理范围）：服务必须常驻并跨会话共享，因此不能落在会被收尾删除的 workspace 内。
    """
    return CONSOLE_DIR


def console_server_json() -> str:
    """服务名片（pid/port/token/url/version），`ensure` 据此判定是否已启动。"""
    return os.path.join(CONSOLE_DIR, "server.json")


def console_lock_path() -> str:
    """`ensure` 临界区锁（flock）：串行化「探测 + 启动」，避免并发 ensure 同时拉起服务。"""
    return os.path.join(CONSOLE_DIR, "server.lock")


def console_singleton_lock_path() -> str:
    """服务进程级**单例锁**（flock）：由服务进程**全程持有**至退出。

    拿不到锁 = 已有实例在跑 → 本进程立即退出。单例由此在**服务进程层硬保证**，
    不依赖 `server.json`；名片缺失/陈旧也不会再出现第二个实例。
    """
    return os.path.join(CONSOLE_DIR, "singleton.lock")


def console_server_log() -> str:
    """服务进程 stdout/stderr 落盘文件。"""
    return os.path.join(CONSOLE_DIR, "server.log")


def console_ingest_path(task: str = None) -> str:
    """CLI 原始 stdout/stderr 遥测落盘（append-only JSONL，服务端 tail 消费）。

    **workspace 级**（`.run/tasks/<task>/console-ingest.jsonl`）—— 它是 run 产物，
    必须随 `post-clean` 一起回收，**不能**放进常驻的 `.console/`（那会跨 run 无限累积）。
    无 task（workspace 之外执行，如 ws-init/console）→ 返回 ""（调用方跳过，不产生遥测）。
    """
    if not task:
        return ""
    return os.path.join(task_dir(task), "console-ingest.jsonl")


def iter_console_ingest_paths() -> list:
    """枚举所有 workspace 的遥测 ingest 文件（控制台 tailer 的发现入口）。

    只枚举「当前存在」的文件；被 `post-clean` 删除的，tailer 会自动剔除其读取偏移。
    """
    try:
        names = sorted(os.listdir(TASKS_DIR))
    except OSError:
        return []
    out = []
    for n in names:
        p = os.path.join(TASKS_DIR, n, "console-ingest.jsonl")
        if os.path.isfile(p):
            out.append(p)
    return out


def console_token_path() -> str:
    """稳定访问令牌（**持久化**）：服务重启沿用同一 token，保证链接长期有效。"""
    return os.path.join(CONSOLE_DIR, "token")
