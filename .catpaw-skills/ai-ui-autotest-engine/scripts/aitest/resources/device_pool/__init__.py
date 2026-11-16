#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池：服务端租约编排 + 池化命令。

分层（长期骨架，后端可替换、内核可复用）：

    commands.py      CLI 入口：create / query / release（对账由服务端自动执行，无客户端入口）
    device_lease.py  DevicePool：claim / bind / renew / release / report / list
    pool_api.py      服务端客户端（唯一的网络出口，无本地回退）

依赖单向：commands → device_lease → pool_api。

**租约权威在服务端**（单表 `device_registry`，单行 CAS + fence 乐观锁）。
本地不保存"谁占了哪台"，只在本 run 的 flow-context 里记自己的
`sandbox_id / lease_fence / lease_expires_at`，用于心跳节流与围栏校验。
"""
