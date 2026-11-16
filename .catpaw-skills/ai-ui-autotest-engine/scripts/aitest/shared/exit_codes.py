#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程退出码 —— 全仓库唯一权威定义。

只有 CLI 边界（cli_utils.run_with_guard）与本模块可以决定进程退出码；
业务/核心层一律通过抛出 shared.errors.AutotestError 表达失败，不得 sys.exit。

取值约定（POSIX 惯例 + argparse 对齐）：

    OK            0   成功
    ERROR         1   通用运行时失败（默认）/ 查询类命令的「未命中」等负面结论
    USAGE         2   参数 / 用法错误（与 argparse 默认退出码一致）
    ABORT         3   环境或前置不可用，快速失败收尾（SOP abort 语义）
    FLOW_CONFLICT 4   步骤重跑冲突 / 流程状态非法
    HANDOFF       5   动作类命令未完成、已交接给调用方决策（需换策略，不是错误）

「1 与 5 的区别」：1 是「执行完成但结论为负」（如 find-text 未命中）；
5 是「动作没做成，已把上下文交出去等决策」（如 tap-text 命中但不可点击、
锚点找不到）—— 后者不是错误，调用方应换策略重试，而不是排查设备。

各 AutotestError 子类的 exit_code 由本表派生，见 shared/errors.py。
"""

OK = 0
ERROR = 1
USAGE = 2
ABORT = 3
FLOW_CONFLICT = 4
HANDOFF = 5
