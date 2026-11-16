#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-ui-autotest-engine 命名空间包。

约定（迁移后唯一形态）：
  · `scripts/` 只作为 sys.path 根，**不再**放任何包/模块（除入口 shim `cli.py`）；
  · 引擎全部代码住在本包内（`aitest.*`），顶层命名空间只有一个 `aitest`；
  · 好处：任何标准库/三方库的名字都不会被本引擎的目录名 shadow
    （历史事故：`scripts/platform/` 顶掉 stdlib `platform`，
      `setuptools._distutils.compat` 一 `import` 就 `AttributeError` 崩溃）。
  · 新增一级模块必须挂在 `aitest` 下，并在 `dev/check_architecture.py` 的分层表登记。
"""
