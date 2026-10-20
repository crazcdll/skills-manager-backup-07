#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""控制台服务常量（唯一事实来源）。"""

CONSOLE_VERSION = 1

# 端口：高位、非知名端口，几乎不与常见开发端口冲突；被占用则顺延。
DEFAULT_PORT = 39021
PORT_SCAN_RANGE = 20          # 39021..39040
BIND_HOST = "127.0.0.1"       # 只监听本机（自用，不做局域网共享）

TOKEN_BYTES = 24              # server.json 中一次性访问令牌
HEALTH_TIMEOUT = 0.5          # 健康探测超时（秒）
STARTUP_TIMEOUT = 8.0         # ensure 等待服务就绪的时间上限（秒）

DISCOVERY_INTERVAL_SEC = 2.0      # 扫描 run/device 的周期
TAIL_INTERVAL_SEC = 0.5           # tail 日志文件的周期
SSE_HEARTBEAT_SEC = 15            # SSE 心跳间隔
SERVER_HEARTBEAT_SEC = 15         # 服务名片（server.json）心跳：误删 .console 可自愈

PREVIEW_INTERVAL_SEC = 1.2        # 截图轮询帧间隔（秒）
PREVIEW_MAX_FPS = 5               # 单设备预览帧率上限
MJPEG_BOUNDARY = "catpawframe"

EVENT_RING_MAX = 8000             # 内存事件环形缓冲长度
