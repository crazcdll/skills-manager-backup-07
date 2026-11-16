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

DISCOVERY_INTERVAL_SEC = 2.0      # 扫描 run/session 的周期（纯本地文件，便宜）
# 设备池快照周期：每轮要打 2 次 /device/list（HTTP + 两次 DB 聚合），比本地扫描贵得多。
# 设备面板晚 10s 看到别人领机对控制台完全够用；改小只会白白压服务端。
DEVICE_DISCOVERY_INTERVAL_SEC = 10.0
TAIL_INTERVAL_SEC = 0.5           # tail 日志文件的周期
SSE_HEARTBEAT_SEC = 15            # SSE 心跳间隔
SERVER_HEARTBEAT_SEC = 15         # 服务名片（server.json）心跳：误删可自愈（只写机器级 console 目录）

# 会话/运行的"存活窗口"：超过该时长没有任何文件更新，即视为已停滞（不再计入活跃）。
# 设备有租约心跳可判定存活，run/会话没有心跳，只能用产物 mtime 作为代理信号；
# 取 15 分钟是为了覆盖 hook 等待 AI 决策等长空窗，同时避免崩溃/中断的运行永久显示 running。
SESSION_STALL_SEC = 900

PREVIEW_INTERVAL_SEC = 1.2        # 截图轮询帧间隔（秒）
PREVIEW_MAX_FPS = 5               # 单设备预览帧率上限
MJPEG_BOUNDARY = "catpawframe"

EVENT_RING_MAX = 8000             # 内存事件环形缓冲长度
