#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""制品契约与「目标包去留」纯决策 —— 安装链路的目标版本比对唯一事实来源。

本模块属 devices/interfaces/（纯数据契约层）：只依赖标准库，**不 import
devices/execution 等上层**，保证「设备安装决策」是可单测的纯函数。

解决的问题（旧实现的两个根因）：
  1. 「是否可测性构建」的判据只有鸿蒙 `bm dump` 提供（provisionType/debug），
     Android 拿不到 → 用三元布尔表达"可确认/不可确认"，语义含混；
  2. 目标版本比对在「versionCode 数值比较」与「versionName 字符串精确相等」
     之间来回回退，制品文件名与配置漂移时会误判 → 每轮重装。

这里用 `BuildKind`（三值枚举）+ `ArtifactSpec.version_key()`（同口径数值元组）
把两件事都收敛成显式数据，`decide_app_action()` 是唯一决策入口。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class BuildKind(str, Enum):
    """已装包的构建类型。

    - TESTABILITY：可测性(debug/test)构建（鸿蒙 `appProvisionType=debug`）。
    - RELEASE：正式(release/os_integration)构建。
    - UNKNOWN：无法确认（如 Android 的 `dumpsys package` 不含该信息）。
    """

    TESTABILITY = "testability"
    RELEASE = "release"
    UNKNOWN = "unknown"


def _as_int(value) -> Optional[int]:
    """宽松转 int：解析不出（None/非数字）时返回 None。"""
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def version_key_of(version_code, version_name) -> Optional[Tuple[int, ...]]:
    """把 (version_code, version_name) 归一为可比较的数值元组（同口径）。

    优先 `version_code`（数值即 (code,)）；否则把 `version_name` 里的连续数字
    段解析为元组（如 "12.66.400" → (12, 66, 400)）。都解析不出返回 None
    （不可比较）——调用方据此保守重装，而不是误判"版本一致"。

    注意：调用方必须对 spec 与 installed **都**走本函数，才能保证两侧口径一致。
    """
    code = _as_int(version_code)
    if code is not None:
        return (code,)
    if version_name is None or str(version_name).strip() == "":
        return None
    parts = re.findall(r"\d+", str(version_name))
    if not parts:
        return None
    return tuple(int(p) for p in parts)


@dataclass
class ArtifactSpec:
    """目标制品契约（从 references/apk_sources.json 的目标条目构造）。"""

    package: str
    url: Optional[str]
    version_code: Optional[int]
    version_name: Optional[str]
    requires_testability_build: bool

    def version_key(self) -> Optional[Tuple[int, ...]]:
        """目标版本的比较键（与已装包同口径，见 `version_key_of`）。"""
        return version_key_of(self.version_code, self.version_name)


@dataclass
class AppAction:
    """目标包去留决策结果。action ∈ {"reuse", "install", "reinstall"}。"""

    action: str
    reason: str


def decide_app_action(spec: ArtifactSpec, installed: dict, build_kind: BuildKind) -> AppAction:
    """决定目标包是复用 / 安装 / 卸载重装（纯函数，无副作用）。

    判定顺序（能复用就复用，避免无谓重装）：
      1. 未安装 → install；
      2. 目标要求可测性构建，而设备上是正式构建 → reinstall；
      3. 目标要求可测性构建，而构建类型不可确认 → reinstall（保守对齐目标制品）；
      4. 版本比较：目标版本不可解析 → reinstall；已装版本落后 → reinstall；
         否则（已是目标版本或更新 / 已装版本不可解析）→ reuse。
    """
    if not installed.get("installed"):
        return AppAction("install", "未安装")

    if spec.requires_testability_build and build_kind is BuildKind.RELEASE:
        return AppAction("reinstall", "已装非可测性构建")
    if spec.requires_testability_build and build_kind is BuildKind.UNKNOWN:
        return AppAction("reinstall", "构建类型不可确认，保守对齐目标制品")

    target_key = spec.version_key()
    if target_key is None:
        return AppAction("reinstall", "目标版本不可解析，无法比对")

    installed_key = version_key_of(installed.get("versionCode"), installed.get("versionName"))
    if installed_key is not None and installed_key < target_key:
        return AppAction(
            "reinstall",
            f"版本落后（当前 {installed.get('versionName')} vs 目标 {spec.version_name}）",
        )
    return AppAction("reuse", "已是目标版本或更新")
