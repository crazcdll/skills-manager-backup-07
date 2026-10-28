#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连接工具链路径缓存（**用户级**，跨 workspace 共享）。

adb / hdc 这类连接工具解析出的可执行文件目录，是**机器级事实**，与具体
workspace 无关，因此缓存必须落在用户级位置。放到 workspace 内会带来两个实际踩到的
问题：

  1. `ws-init` 等「尚无 workspace」的命令读取时会直接报错（冷启动即崩溃）；
  2. workspace 收尾 `post-clean` 会整目录删除缓存 → 下一个 workspace 需重新解析，
     自下载的 adb 甚至会被重复下载。

缓存固定为 `~/.local/share/ai-ui-autotest-engine/toolchain/toolchain.json`（与凭据、设备池
同级：均落在**机器级**目录，不被 workspace 清理影响，也不随 Skill 更新/重建丢失；
且多份 Skill 副本共用同一份，不会各探测一遍）。
本模块是读写该缓存的**唯一入口**，
adb 与 hdc 共用；写入口 `update_env` 做增量合并，避免并发写互相覆盖键。
"""
from shared.json_utils import read_json, write_json_atomic
from shared.paths import toolchain_env_path


def read_env() -> dict:
    """读取工具链路径缓存；文件不存在 / 内容损坏时返回空 dict。"""
    data = read_json(toolchain_env_path(), default={})
    return data if isinstance(data, dict) else {}


def update_env(patch: dict) -> None:
    """把若干键**增量合并**进缓存（读-合并-写）。

    adb 与 hdc 共用同一份缓存、且可能在并行 workspace 中并发写：若调用方各自
    `read → 改键 → 整体写回`，就会互相覆盖对方的键（原子写只防「写坏文件」，
    不防「丢更新」）。写入口因此统一为「合并」，调用方只传自己的增量键
    （如 `update_env({"adb_dir": d})`）。
    """
    merged = read_env()
    merged.update(dict(patch or {}))
    # 纯机器缓存、且被每条命令的预检（ensure_adb）内联调用：用静默变体，
    # 既不需要空文件占位，也不能让提示污染命令 stdout。
    write_json_atomic(toolchain_env_path(), merged)
