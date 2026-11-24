#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境配置的**展示白名单**（脱敏口径唯一事实来源）。

报告（`reporting/run_report.py`）与 Console 发现层（`console/discovery.py`）都要把
`flow-context.env` 暴露到各自读模型里；两处各写一份白名单曾导致新增字段后
「报告有、Console 没有」（域名映射 E 环境即如此）。统一收敛到这里。

只放**非敏感**且排查刚需的字段：
  · `type` / `env_name` / `auth_method` —— 环境与登录方式
  · `ptest`                            —— `type=P` 的派生值（只读展示）
  · `bundle_lock`                      —— 锁包清单
  · `swimline`                         —— B 测试泳道的泳道名 + url_pattern
  · `url_mappings`                     —— E 测试域名映射的映射列表
凭证（`credential`）永不进入白名单。
"""

SAFE_ENV_KEYS = frozenset({
    "type", "env_name", "auth_method", "ptest", "bundle_lock",
    "swimline", "url_mappings",
})

__all__ = ["SAFE_ENV_KEYS"]
