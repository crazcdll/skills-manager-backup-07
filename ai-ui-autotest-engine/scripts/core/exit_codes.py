#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程退出码 —— 全仓库唯一权威定义。

只有 CLI 边界（cli_utils.run_with_guard）与本模块可以决定进程退出码；
业务/核心层一律通过抛出 core.errors.AutotestError 表达失败，不得 sys.exit。

取值约定（POSIX 惯例 + argparse 对齐）：

    OK            0   成功
    ERROR         1   通用运行时失败（默认）
    USAGE         2   参数 / 用法错误（与 argparse 默认退出码一致）
    ABORT         3   环境或前置不可用，快速失败收尾（SOP abort 语义）
    FLOW_CONFLICT 4   步骤重跑冲突 / 流程状态非法

各 AutotestError 子类的 exit_code 由本表派生，见 core/errors.py。
"""

OK = 0
ERROR = 1
USAGE = 2
ABORT = 3
FLOW_CONFLICT = 4
