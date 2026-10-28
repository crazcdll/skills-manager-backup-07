#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workspace 入口管理：分配 workspace id 并生成入口脚本（`ws-init`）。

设计要点（**无模式**：1 个 Agent 与 N 个 Agent 走完全同一条路径）：

  ① `ws-init` 分配一个 workspace id（uuid）并生成入口脚本
     `~/.local/share/ai-ui-autotest-engine/run/ws/<id>/cli`
  ② 之后**所有命令**都通过该入口执行；入口把 `AI_UITEST_TASK=<id>` 注入进程
  ③ 代码读 `AI_UITEST_TASK` 定位工作区；没有则直接报错（不回落默认值）

运行态放在机器级目录（不在 Skill 内）：Skill 会被多份安装/镜像，且自动更新时
会整目录替换——放里面会丢进度、产生多份分叉的工作区（详见 shared/paths.py）。

为什么用 uuid 而不是可读名字：多个 Agent 并发时，uuid 随机不可猜，
不会出现"记错/写成了别人的名字"而静默跑进别人工作区的情况。
"""
import os
import uuid

from shared.paths import (
    ENV_WORKSPACE,
    SKILL_DIR,
    STATE_HOME,
    WORKSPACES_DIR,
    ensure_dirs,
    get_active_task,
    task_dir,
    workspace_entry_dir,
    workspace_entry_path,
)

_ENTRY_TEMPLATE = """#!/bin/sh
# ai-ui-autotest-engine workspace 入口（由 `cli.py ws-init` 生成，请勿手工修改）
# 用法：{entry} <命令> [参数...]
# 源树零字节码（进程入口层）：-B 覆盖本进程，环境变量被所有子进程继承。
# AI_UITEST_STATE_HOME 写死在入口里：入口在任何 shell 下都能定位到同一个机器级状态目录。
cd "{skill_dir}" || exit 1
PYTHONDONTWRITEBYTECODE=1 AI_UITEST_STATE_HOME="{state_home}" {env}={ws} exec python3 -B scripts/cli.py "$@"
"""


def new_workspace_id() -> str:
    """分配一个新的 workspace id（8 位 uuid 片段，随机不可猜）。"""
    return uuid.uuid4().hex[:8]


# ─── 命令渲染（唯一出口） ──────────────────────────────────────────
# 引擎面向 AI 输出的「待执行命令」必须能直接照抄；而 SOP 宣告式数据仍写作
# `python3 scripts/cli.py X`。渲染器把这层“如何启动引擎”的知识收口到一处：
# 有 workspace → 渲染为入口路径；尚无 workspace → 保持原样（此时唯一可执行的
# 命令就是 `python3 scripts/cli.py ws-init`，不能把提示改成还不存在的入口）。
CLI_INVOCATION = "python3 scripts/cli.py"


def entry_display() -> str:
    """当前 workspace 入口的可执行路径（供 AI 直接照抄）。

    入口在机器级目录（`$STATE/run/ws/<ws>/cli`），**不在 Skill 内**：直接返回
    绝对路径——相对路径会渲染成 `../../../.local/share/...`，既难读又依赖 cwd。
    无 workspace 时回退为直接的 CLI 调用串（此时唯一可执行的是 `ws-init`）。
    """
    ws = get_active_task()
    if not ws:
        return CLI_INVOCATION
    return workspace_entry_path(ws)


def render_text(text: str) -> str:
    """把文本中的 `python3 scripts/cli.py` 统一渲染为当前 workspace 入口（**幂等**）。

    适用于含多处引擎调用的提示文本（如 hook cli_hint）。已渲染过 / 尚无 workspace 时原样返回。
    """
    return str(text).replace(CLI_INVOCATION, entry_display())


def render_cmd(cmd: str) -> str:
    """把一条引擎命令渲染为「经 workspace 入口执行」的形式（**幂等**）。

    支持三种输入：
      · 声明式写法 `python3 scripts/cli.py X` → `<入口> X`（SOP 宣告式数据用这种）
      · 裸命令体 `X`                          → `<入口> X`
      · 已渲染过的形式                        → 原样返回
    """
    text = str(cmd)
    if CLI_INVOCATION in text:
        return render_text(text)
    prefix = entry_display()
    if text.startswith(prefix):
        return text
    return f"{prefix} {text}".strip()


def list_workspaces() -> list:
    """列出当前已存在的 workspace id。"""
    if not os.path.isdir(WORKSPACES_DIR):
        return []
    return sorted(
        name for name in os.listdir(WORKSPACES_DIR)
        if os.path.isdir(os.path.join(WORKSPACES_DIR, name))
    )


def write_entry(ws_id: str) -> str:
    """生成（或覆写）workspace 入口脚本与工作区目录，返回入口脚本绝对路径。"""
    os.makedirs(workspace_entry_dir(ws_id), exist_ok=True)
    os.makedirs(task_dir(ws_id), exist_ok=True)
    path = workspace_entry_path(ws_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_ENTRY_TEMPLATE.format(
            entry=path,
            skill_dir=SKILL_DIR,
            state_home=STATE_HOME,
            env=ENV_WORKSPACE,
            ws=ws_id,
        ))
    os.chmod(path, 0o755)
    return path


def init_workspace() -> dict:
    """分配（或复用）workspace 并生成入口。

    幂等规则：当前进程已带 workspace（说明是通过入口调用的）→ 复用；
    否则新建。
    """
    ensure_dirs()
    current = get_active_task()
    ws_id = current or new_workspace_id()
    others = [w for w in list_workspaces() if w != ws_id]
    path = write_entry(ws_id)
    return {
        "workspace": ws_id,
        "reused": bool(current),
        "entry": path,
        "workspace_dir": task_dir(ws_id),
        "other_workspaces": others,
    }


def cmd_ws_init(args=None) -> dict:
    """`ws-init` 命令：分配 workspace + 生成入口，并打印使用说明。"""
    info = init_workspace()
    if info["reused"]:
        print(f"WORKSPACE 已存在，复用: {info['workspace']}")
    else:
        print(f"WORKSPACE 已分配: {info['workspace']}")
        if info["other_workspaces"]:
            print(f"  ⚠️ 当前还有 {len(info['other_workspaces'])} 个其他 workspace 存在："
                  f"{', '.join(info['other_workspaces'])}")
            print("     若并非有意新建，请改用你自己那个入口继续，不要重复执行 ws-init。")
    print(f"  工作区: {info['workspace_dir']}")
    print(f"  你的入口: {info['entry']}")
    print(f"  后续所有命令都必须通过该入口执行，例如: "
          f"{info['entry']} flow-next")
    print("  请勿重复执行 ws-init（会分配出一个新工作区，之前的进度将不在其中）。")
    return info