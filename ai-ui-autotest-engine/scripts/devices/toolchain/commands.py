#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`toolchain` 命令：连接工具链只读体检。

只回答一个问题：「我这台机器现在能不能连设备，adb/hdc 分别是从哪来的？」
因此这里**没有任何副作用**：不解压、不下载、不触发 imeituan 安装。
真正的安装入口只有一个 —— `check-deps`。
"""
import sys

from devices.toolchain import bundle
from devices.toolchain.adb import ensure_adb, source_of, version_of
from devices.harmony.hdc import ensure_hdc, hdc_version
from devices.harmony.hdc import source_of as hdc_source_of

_SOURCE_LABELS = {
    "system": "系统 PATH",
    "imeituan": "imeituan 受管",
    "bundled": "Skill 内置包",
    "none": "无",
}


def _human_size(n):
    if not n:
        return "未知"
    return f"{n / (1024 * 1024):.1f} MB"


def _row(name, path, version, source):
    return (f"  {name:<5} 版本 {version or '-':<12} 来源 "
            f"{_SOURCE_LABELS.get(source, source):<14} {path or '-'}")


def cmd_toolchain(_args=None):
    """打印 adb / hdc 来源与内置离线包完整性（只读）。"""
    out = sys.stdout
    out.write("连接工具链体检（只读：不安装、不下载）\n\n")

    adb_bin, _ = ensure_adb(install=False)
    if adb_bin:
        out.write(_row("adb", adb_bin, version_of(adb_bin), source_of(adb_bin)) + "\n")
    else:
        out.write("  adb   未就绪（版本要求 >= 1.0.40）\n")

    hdc_bin, _ = ensure_hdc(install=False)
    if hdc_bin:
        out.write(_row("hdc", hdc_bin, hdc_version(hdc_bin), hdc_source_of(hdc_bin)) + "\n")
    else:
        out.write("  hdc   未就绪（仅 harmony 设备需要）\n")

    info = bundle.info()
    out.write("\n内置 adb 离线包\n")
    out.write(f"  清单版本   {info.get('version') or '未知'}\n")
    out.write(f"  目标平台   {info.get('platform')}\n")
    if info.get("bundle"):
        out.write(f"  压缩包     {info.get('path')}（{_human_size(info.get('size'))}）\n")
    else:
        out.write("  压缩包     清单未声明该平台（当前 Skill 只随包分发 darwin/linux）\n")
    if info.get("bundle_ok"):
        out.write("  完整性     文件存在且大小与清单一致\n")
    else:
        out.write(f"  完整性     校验失败：{info.get('bundle_error')}\n")
    installed = info.get("installed")
    if installed:
        out.write(f"  已安装     {installed['dir']}（版本 {installed['version']}）\n")
    else:
        out.write("  已安装     否（首次连接时会自动解压）\n")

    if not adb_bin and not hdc_bin:
        out.write("\n当前没有可用连接工具：先执行 `check-deps`（唯一的安装入口）。\n")

    return 0
