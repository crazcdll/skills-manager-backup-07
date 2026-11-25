#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一控制台服务（机器级、跨 workspace、常驻）。

一个共享的本地 Web 服务，供用户在一个页面里：
  · 同时观看多台设备（Android sandbox / 鸿蒙云模拟器）的实时画面；
  · 观看测试执行过程中的结构化日志与动态输出。

设计约束：零新增依赖（只用 Python 标准库 + 已依赖的 websocket-client）；
对测试主流程**零干扰**（服务未启动则所有埋点直接短路不启用）。
"""
