#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池：租约内核（存储契约 + 池化编排）+ 池化命令。

分层（长期骨架，后端可替换、内核可复用）：

    commands.py      CLI 入口：create / query / release / pool-gc
    device_lease.py  DeviceLeaseManager：acquire / renew / release / status / gc
    lease_store.py   LeaseStore 契约 + LocalFileLeaseStore（本地文件后端）

依赖单向：commands → device_lease → lease_store。编排层只依赖**注入的契约**
（`LeaseStore`、`DeviceLifecycle`），与具体存储后端 / 设备类型解耦。
"""
