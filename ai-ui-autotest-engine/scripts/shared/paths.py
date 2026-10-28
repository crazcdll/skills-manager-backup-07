#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-ui-autotest-engine 统一路径管理（作用域分层）。

作用域（`$STATE` = `~/.local/share/ai-ui-autotest-engine`，可用 `AI_UITEST_STATE_HOME` 覆盖）：

  机器级（`$STATE/`，跨安装 / 跨项目唯一）
      device-pool/   本机辅助文件（预热台账；设备租约在服务端）
      console/       统一控制台服务状态（常驻、全机唯一）
      credentials/   AppMock SSO 凭据（同一用户同一张票）
      toolchain/     连接工具链路径缓存（adb/hdc）
      cache/         制品缓存（安装包，跨安装复用）
      run/           运行态根：tasks/<ws>/（工作区）+ ws/<ws>/cli（入口）
      reports/       报告归档（<batch>/<run>/）
  workspace 级  `$STATE/run/tasks/<ws>/`         工作区：config / inputs / tmp / runs
  run 级        …/tasks/<ws>/runs/<run>/         运行级文件（record_data / dumps / …）
  case 级       …/runs/<run>/cases/<case>/       步骤产物

⚠️ 所有状态（常驻服务、凭据、缓存、运行态、报告）**必须**放在 Skill 目录之外：
Skill 会被多份安装/镜像（`~/.catpaw/skills`、各项目的 `.claude/skills`、
`.catpaw/skills/skills-market` 等），落在 SKILL_DIR 内会导致：
  · 每份副本各存一份（凭据/缓存/租约不共享，甚至互相覆盖）；
  · Skill 自动更新/重装时目录被整体替换（缓存丢、登录丢、正在跑的 workspace 断、历史报告丢）；
  · 常驻服务的心跳会在目录被删后立刻重建（「删不掉的幽灵目录」）。

workspace 身份（**无模式**：1 个 Agent 与 N 个 Agent 走完全同一条路径）：
  ① `ws-init` 分配 workspace id（uuid）并生成入口脚本 `~/.local/share/ai-ui-autotest-engine/run/ws/<id>/cli`
  ② 之后所有命令通过该入口执行；入口把 `AI_UITEST_TASK=<id>` 注入进程
  ③ 代码读 `AI_UITEST_TASK` 定位工作区；**没有则报错**（不回落默认值，
     避免任何“静默落到共享目录”的可能）

清理：`post-clean` 删除本 workspace 的工作区目录与入口（生命周期一致，不留残留）；
`preflight-clean` 仅清空内容（用于同一 workspace 内重置/重试）。
均不影响其他并行 workspace。
"""
import json
import os
import re
import shutil
import sys
import time

# 本文件位于 <skill>/scripts/<pkg>/paths.py，向上 3 层即 Skill 根目录。
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 机器级运行态根（**不在 Skill 目录内**，可用 AI_UITEST_STATE_HOME 覆盖）。
STATE_HOME = os.path.abspath(
    os.environ.get("AI_UITEST_STATE_HOME", "").strip()
    or os.path.join(os.path.expanduser("~/.local/share"), "ai-ui-autotest-engine")
)

# ─── 全局 ─────────────────────────────────────────
RUN_DIR = os.path.join(STATE_HOME, "run")                   # 机器级：运行态根（workspace / run）
OUTPUT_DIR = os.path.join(STATE_HOME, "reports")            # 机器级：报告归档
DEVICE_POOL_DIR = os.path.join(STATE_HOME, "device-pool")   # 机器级：预热台账等辅助文件（不存租约）
CREDENTIALS_DIR = os.path.join(STATE_HOME, "credentials")   # 机器级：AppMock SSO 凭据（跨安装 / 跨 workspace）
TOOLCHAIN_DIR = os.path.join(STATE_HOME, "toolchain")       # 机器级：连接工具链路径缓存（adb/hdc）
DEPS_DIR = os.path.join(STATE_HOME, "deps")                 # 机器级：运行期依赖（已安装时间戳）
CONSOLE_DIR = os.path.join(STATE_HOME, "console")           # 机器级：统一控制台服务（跨安装唯一、常驻、不随收尾清理）
TASKS_DIR = os.path.join(RUN_DIR, "tasks")                  # workspace 工作区根
WORKSPACES_DIR = os.path.join(RUN_DIR, "ws")                # workspace 入口根（<id>/cli）
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
SKILL_MD_PATH = os.path.join(SKILL_DIR, "SKILL.md")

# 注入 workspace 身份的环境变量（由 `…/run/ws/<id>/cli` 入口脚本设置）
ENV_WORKSPACE = "AI_UITEST_TASK"
# 当前运行平台（android/harmony/ios）：由 active context 同步，供 imeituan_run
# 等低层执行器判断是否启用 Android/ADB 专属恢复逻辑。
ENV_PLATFORM = "AI_UITEST_PLATFORM"
# workspace 级本地传输端口：所有平台统一分配；当前仅 Android ADB 适配器使用，
# 未来 hdc/WDA 等传输需要本地端口时可直接复用。
ENV_TRANSPORT_PORT = "AI_UITEST_TRANSPORT_PORT"


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
    """workspace 入口目录：`…/run/ws/<workspace-id>/`（机器级）。"""
    return os.path.join(
        WORKSPACES_DIR, ((task_id or "").strip() or require_active_task())
    )


def workspace_entry_path(task_id: str = None) -> str:
    """workspace 入口脚本：`…/run/ws/<workspace-id>/cli`（由 `ws-init` 生成）。"""
    return os.path.join(workspace_entry_dir(task_id), "cli")


# ═══════════════════════════════════════════════════════════════════
# workspace 级路径
# ═══════════════════════════════════════════════════════════════════

def task_dir(task_id: str = None) -> str:
    """workspace 工作区根：`$STATE/run/tasks/<workspace-id>/`。"""
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
    """steps-input / CASES 中间产物目录。"""
    return os.path.join(task_dir(task_id), "tmp")


def runs_root(task_id: str = None) -> str:
    """run 工作区根：`…/tasks/<task>/runs/`。"""
    return os.path.join(task_dir(task_id), "runs")


def active_run_file(task_id: str = None) -> str:
    """本 workspace 的 run 指针文件。"""
    return os.path.join(task_dir(task_id), "active_run")


def appmock_cookie_path() -> str:
    """AppMock SSO Cookie 缓存：`~/.local/share/ai-ui-autotest-engine/credentials/appmock_session_cookie.json`。

    它是**机器级凭据**（同一个用户在同一台机器上取的是同一张票），不是 workspace 状态：
    放在机器级位置，所有 Skill 安装与并行 workspace 共用，不随 Skill 更新/重装丢失。
    """
    return os.path.join(CREDENTIALS_DIR, "appmock_session_cookie.json")


def toolchain_env_path() -> str:
    """连接工具链路径缓存：`~/.local/share/ai-ui-autotest-engine/toolchain/toolchain.json`。

    adb/hdc 解析出的目录是机器级事实：既有 `ws-init` 这类「尚无 workspace」的命令要读，
    也不能被 workspace 收尾清理带走，又不该在每份 Skill 副本里各探测一遍
    （详见 shared/toolchain_env.py）。故意不依赖 workspace。
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


# ═══════════════════════════════════════════════════════════════════
# 报告目录分配（并发安全）
# ═══════════════════════════════════════════════════════════════════

# 批次标识：同一次编排的所有 shard 共享（CLI 注入）；未注入时回退平台报告 id。
ENV_BATCH_ID = "AI_UITEST_BATCH_ID"


def safe_component(value, fallback: str = "") -> str:
    """把任意标识规整为单层安全目录名（禁止 `/` 与 `..`）。"""
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip(".-")
    return text[:80] or fallback


def report_batch_id() -> str:
    """本次执行的批次标识：显式 env → 平台报告 id → 时间戳+随机后缀。"""
    explicit = (
        os.environ.get(ENV_BATCH_ID, "").strip()
        or os.environ.get("AI_UITEST_REPORT_ID", "").strip()
    )
    return safe_component(explicit, "") or (
        f"batch-{time.strftime('%Y%m%dT%H%M%S')}-{os.urandom(2).hex()}"
    )


def allocate_run_output_dir(batch_id: str, run_id: str) -> str:
    """分配 `reports/<batch>/<run>[-rN]/`，**不覆盖历史轮次**。

    并发安全：`os.mkdir` 独占创建；同一 run 重试时自动落到 `-r2/-r3`。
    同一 workspace 重跑 flow-init（尚未落盘）会复用已有目录，避免产生空壳；
    已落盘的目录永不复用——那会覆盖历史证据。
    """
    batch = safe_component(batch_id, "batch")
    run = safe_component(run_id, "run")
    base = os.path.join(OUTPUT_DIR, batch)
    os.makedirs(base, exist_ok=True)

    reused = _reusable_output_dir(batch, run)
    if reused:
        return reused

    for attempt in range(1, 100):
        name = run if attempt == 1 else f"{run}-r{attempt}"
        path = os.path.join(base, name)
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            continue
    raise RuntimeError(f"报告目录分配失败：{base}/{run}（已存在 99 个轮次）")


def _reusable_output_dir(batch_id: str, run_id: str) -> str:
    """同一 workspace 的 flow-init 重跑：沿用上一轮目录（批次一致时）。"""
    if get_active_run() != run_id:
        return ""
    try:
        with open(run_file("flow-context.json", run_id), encoding="utf-8") as f:
            meta = (json.load(f) or {}).get("meta") or {}
    except (OSError, ValueError):
        return ""
    if meta.get("batch_id") != batch_id:
        return ""
    path = str(meta.get("batch_output_dir") or "")
    if not path or not os.path.isdir(path):
        return ""
    # 只有「什么都没产出」的空目录才复用（纯 flow-init 重跑，避免留下空壳）。
    # 一旦目录里已有 case 报告 / frames / 归档，就说明上一轮已经跑过：
    # 复用会让旧的 case report.json 通过 run_id 校验，污染新一轮证据。
    if os.listdir(path):
        return ""
    expected_parent = os.path.abspath(os.path.join(OUTPUT_DIR, batch_id))
    return path if os.path.dirname(os.path.abspath(path)) == expected_parent else ""


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


def preflight_clean(cleanup=None):
    """清空【本 workspace】工作区内容（不影响其他并行 workspace）。"""
    from shared.transport_port import release_transport_port
    release_transport_port(cleanup=cleanup)
    _clear_dir(task_dir())
    ensure_dirs()
    sys.stderr.write(f"[paths] preflight-clean 完成（workspace={get_active_task()}）\n")


def clean_post_test(cleanup=None):
    """收尾：删除【本 workspace】的工作区目录与入口（不留残留）。"""
    task = require_active_task()
    from shared.transport_port import release_transport_port
    release_transport_port(task, cleanup=cleanup)
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
    - **裸文件名**（无目录分隔）→ 本 workspace 的 steps-input 目录（`$STATE/run/tasks/<ws>/tmp/`）；
    - 含目录的相对路径 → 相对 SKILL_DIR。
    """
    raw = str(raw)
    if os.path.isabs(raw):
        return raw
    if os.sep not in raw and "/" not in raw:
        return os.path.join(steps_input_dir(), raw)
    return os.path.normpath(os.path.join(SKILL_DIR, raw))


# ═══════════════════════════════════════════════════════════════════
# 设备池（用户级、跨安装 / 跨 task）
# ═══════════════════════════════════════════════════════════════════

# 设备归属的权威在服务端 `device_registry`（见 resources/device_pool/pool_api.py），
# 本地不再保存任何"谁占了哪台"的副本：多机 / 多会话下本地视图必然不一致，
# 用它做分配判断会把同一台设备发给两个 run。DEVICE_POOL_DIR 仅保留给早期的
# 设备级缓存（如探测结果），不参与租约。


# ═══════════════════════════════════════════════════════════════════
# 统一控制台服务（机器级、跨安装唯一、常驻）
# ═══════════════════════════════════════════════════════════════════

def console_dir() -> str:
    """控制台服务根目录：`~/.local/share/ai-ui-autotest-engine/console/`。

    **机器级、跨安装唯一**：同一台机器上不管从哪个 Skill 副本启动，都落到同一目录，
    因此单例锁 / 名片 / token 天然全局唯一，不会出现多个常驻实例互相覆盖名片。
    也**不在** preflight/post-clean 清理范围（服务常驻并跨会话共享）。
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

    **workspace 级**（`$STATE/run/tasks/<task>/console-ingest.jsonl`）—— 它是 run 产物，
    必须随 `post-clean` 一起回收，**不能**放进常驻的 `$STATE/console/`（那会跨 run 无限累积）。
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
