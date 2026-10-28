#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行期依赖：清单化安装/复核 + 机器级「已安装时间戳」。

为什么要有这份清单
  · 版本区间、import 名、资源大小原本散落在 check-deps 里，改一处漏一处；
    `references/deps/manifest.json` 现在是唯一事实来源。
  · 清单带 `updated_at`：**依赖集合一变，这个时间就跟着改**。安装成功后把该时间写进
    机器级状态（`$STATE/deps/state.json`，跨 workspace / 跨 Skill 副本共享），下次
    前置检查一比对就知道要不要重装 —— 不需要对文件算 sha256，也不比较文件 mtime
    （mtime 会随分发/解包变化，跨机器比较必然误报）。

判定规则
  · 清单 updated_at == 已安装时间戳 → 只做轻量复核（import + 文件大小），跳过安装；
  · 不一致（首次安装 / Skill 升级改了依赖）→ 按新清单**重新安装** Python 包
    （pip --upgrade）并复核资源大小；
  · 只有全部通过才更新时间戳；失败保留旧值，下次继续重试（不会假装已就绪）。

分工
  · 本模块 = 运行期依赖（pip 包、apk 等静态资源）；
  · `devices/toolchain/bundle.py` = 连接工具链二进制（flock 互斥 + 原子替换 +
    解压后可用性探测），语义不同，不要合并。
"""
import importlib
import json
import os
import subprocess
import sys
import time

from shared import paths
from shared.json_utils import read_json, write_json_atomic

MANIFEST_PATH = os.path.join(paths.REFERENCES_DIR, "deps", "manifest.json")
STATE_PATH = os.path.join(paths.DEPS_DIR, "state.json")

_PIP_TIMEOUT = 300


# ═══════════════════════════════════════════════════════════════════
# 清单
# ═══════════════════════════════════════════════════════════════════

def read_manifest():
    """读取依赖清单；缺失 / 非法时抛 RuntimeError（调用方决定降级方式）。"""
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise RuntimeError(f"依赖清单不存在: {MANIFEST_PATH}（{e.strerror}）")
    except ValueError as e:
        raise RuntimeError(f"依赖清单不是合法 JSON: {MANIFEST_PATH}（{e}）")
    if not isinstance(data, dict):
        raise RuntimeError(f"依赖清单格式非法: {MANIFEST_PATH}")
    return data


def manifest_updated_at():
    """清单的依赖更新时间戳（依赖集合变化时由维护者同步修改）。"""
    try:
        return str(read_manifest().get("updated_at") or "")
    except RuntimeError:
        return ""


def python_requirements():
    """[(pkg, spec, import_name)]：清单声明的 Python 依赖。

    清单不可读时返回空列表：前置检查不该因此整体崩掉，缺清单属于「分发问题」。
    """
    try:
        raw = read_manifest().get("python") or {}
    except RuntimeError:
        return []
    reqs = []
    for pkg, meta in raw.items():
        meta = meta if isinstance(meta, dict) else {}
        reqs.append((pkg,
                     meta.get("spec") or "",
                     meta.get("import") or pkg.replace("-", "_")))
    return reqs


def resource_names():
    """清单声明的静态资源名（如 adb-keyboard-apk）。"""
    try:
        return list((read_manifest().get("resources") or {}).keys())
    except RuntimeError:
        return []


# ═══════════════════════════════════════════════════════════════════
# 机器级已安装时间戳
# ═══════════════════════════════════════════════════════════════════

def load_state():
    data = read_json(STATE_PATH, default={})
    return data if isinstance(data, dict) else {}


def save_state(state):
    write_json_atomic(STATE_PATH, state)


# ═══════════════════════════════════════════════════════════════════
# Python 包
# ═══════════════════════════════════════════════════════════════════

def pip_command(requirements, upgrade=False):
    """一次性安装多条依赖的 pip 命令（只启动一次 pip）。

    `--disable-pip-version-check` 省掉一次多余查询；`--no-input` 避免非交互 Shell
    卡在确认提示；超时/重试收紧，内网无镜像时快速失败而不是挂着。内网镜像走 pip
    自身的环境变量（PIP_INDEX_URL / PIP_EXTRA_INDEX_URL），代码不硬编码地址。
    """
    cmd = [sys.executable, "-m", "pip", "install", "-q",
           "--disable-pip-version-check", "--no-input",
           "--timeout", "30", "--retries", "1"]
    if upgrade:
        cmd.append("--upgrade")
    return cmd + list(requirements)


def _importable(import_name):
    try:
        importlib.import_module(import_name)
        return True
    except Exception:  # noqa: BLE001 —— 任何导入失败都按「不可用」处理
        return False


def ensure_python_packages(log=None, upgrade=False):
    """检查并按需**一次性**安装 Python 包。

    Args:
        log:     可选 `log(msg)` 进度回调
        upgrade: True = 按清单对**全部**声明执行 pip --upgrade（依赖集合变了才走，
                 让新的版本区间真正生效）；False = 只补装当前缺失的包。

    Returns:
        [{"name", "ok", "detail", "hint", "required"}]，name 形如 `py:requests`
    """
    say = log or (lambda _m: None)
    reqs = python_requirements()
    states = {}
    pending = []
    for pkg, spec, import_name in reqs:
        if _importable(import_name):
            states[pkg] = (True, "已安装")
        else:
            states[pkg] = (False, "未安装")
            pending.append((pkg, spec, import_name))

    if reqs and upgrade:
        targets = list(reqs)                      # 清单变了：整组重装
    else:
        targets = pending                         # 只补缺
    if targets:
        specs = [f"{pkg}{spec}" for pkg, spec, _imp in targets]
        say(f"{'按新清单重装' if upgrade else '安装缺失的'} Python 依赖：{'、'.join(specs)}")
        try:
            subprocess.run(pip_command(specs, upgrade=upgrade),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=_PIP_TIMEOUT, check=True)
        except Exception as e:  # noqa: BLE001 —— 失败原因交给 hint 呈现
            say(f"pip 安装失败：{e}")
        for pkg, _spec, import_name in targets:
            if not _importable(import_name):
                states[pkg] = (False, "自动安装失败")
            elif pkg in states and states[pkg][1] == "已安装" and upgrade:
                states[pkg] = (True, "已按清单重装")
            else:
                states[pkg] = (True, "已自动安装")

    return [{"name": f"py:{pkg}", "ok": ok, "detail": detail, "required": True,
             "hint": None if ok else f"手动执行：pip3 install -U {pkg}"}
            for pkg, (ok, detail) in states.items()]


# ═══════════════════════════════════════════════════════════════════
# 静态资源
# ═══════════════════════════════════════════════════════════════════

def verify_resource(name):
    """校验随包分发的静态资源（清单 `resources.<name>`）。

    只做「存在 + 大小」，不算哈希、也不比文件 mtime（分发/解包会改 mtime，
    跨机器比较必然误报）。「资源是否换过」由清单 `updated_at` 表达：它变了才会
    重新安装/复核，没变就直接跳过。

    Returns:
        dict: {"name", "ok", "detail", "hint", "path", "required"}（非致命）
    """
    try:
        meta = (read_manifest().get("resources") or {}).get(name) or {}
    except RuntimeError as e:
        return {"name": name, "ok": False, "detail": str(e), "path": None,
                "required": False,
                "hint": "确认 references/deps/manifest.json 随 Skill 完整分发"}

    rel = meta.get("path")
    if not rel:
        return {"name": name, "ok": False, "detail": f"清单未声明资源 {name}",
                "path": None, "required": False,
                "hint": "在 references/deps/manifest.json 的 resources 中补声明"}

    path = os.path.join(paths.SKILL_DIR, rel)
    expected = meta.get("size")
    if not os.path.isfile(path):
        detail = "文件不存在"
    else:
        actual = os.path.getsize(path)
        detail = "" if (not expected or actual == expected) else \
            f"大小不符（期望 {expected}，实际 {actual}）"
        if not detail:
            return {"name": name, "ok": True, "path": path, "hint": None,
                    "required": False,
                    "detail": f"{path}（{actual} 字节，与清单一致）"}
    return {"name": name, "ok": False, "path": path, "required": False,
            "detail": f"{path}：{detail}",
            "hint": f"重新分发 {rel}，并同步 references/deps/manifest.json 的 size"}


# ═══════════════════════════════════════════════════════════════════
# 统一入口
# ═══════════════════════════════════════════════════════════════════

def ensure_deps(log=None):
    """按清单安装/复核全部运行期依赖，并维护机器级时间戳。

    Returns:
        [{"name", "ok", "detail", "hint", "required"}]：
        `deps-manifest` 一条（说明本次是「跳过」还是「重装」），
        随后是 py:* 与各资源项。
    """
    say = log or (lambda _m: None)
    man_ts = manifest_updated_at()
    installed_ts = str(load_state().get("updated_at") or "")
    stale = man_ts != installed_ts

    items = []
    if stale:
        items.append({
            "name": "deps-manifest", "ok": True, "required": False, "hint": None,
            "detail": (f"依赖清单更新于 {man_ts or '未知'}（已安装 {installed_ts or '无记录'}），"
                       "按新清单重装/复核"),
        })
        say(f"依赖集合已变化（{installed_ts or '无记录'} → {man_ts or '未知'}），重新安装依赖")
    else:
        items.append({
            "name": "deps-manifest", "ok": True, "required": False, "hint": None,
            "detail": f"依赖清单更新于 {man_ts}，与已安装记录一致（跳过重复安装）",
        })

    items.extend(ensure_python_packages(log=say, upgrade=stale))
    for name in resource_names():
        items.append(verify_resource(name))

    if stale:
        if all(i["ok"] for i in items):
            save_state({"updated_at": man_ts,
                        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            say("依赖已按新清单就绪，已记录安装时间戳")
        else:
            say("依赖未全部就绪，保留旧时间戳，下次继续重试")
    return items
