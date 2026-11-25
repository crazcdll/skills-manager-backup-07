#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引擎唯一进程入口（thin shim）。

为什么保留这一层：
  · 引擎代码全部收在命名空间包 `aitest` 内，`scripts/` 只承担「sys.path 根」的角色；
  · 顶层命名空间只有 `aitest` 一个名字 → 任何标准库/三方库都不会被引擎目录名 shadow
    （历史事故：`scripts/platform/` 顶掉 stdlib `platform`，只要依赖图里有人
     `import platform`，启动即 `AttributeError: module 'platform' has no attribute ...`）；
  · sys.path 只在这里改一次。包内模块（dev 独立脚本除外）不得自行拼路径。

用法保持不变（SKILL.md / SOP 里的命令无需改动）：
    python3 scripts/cli.py <command> [args...]
"""
import os
import sys

# 源树零字节码（进程入口层）：`-B` 不继承给子进程，环境变量才继承。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from aitest.cli import main  # noqa: E402  （必须在 sys.path 调整之后）

if __name__ == "__main__":
    main()
