#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 资源池层（`resources`）。

承载"跨 run / 跨 task 共享的资源占用协调"，与具体资源类型解耦：

- `device_pool`    设备池（本地租约，mis 级）
- `account_pool`   账号池（平台化，规划中）

依赖方向：`resources` → `devices` / `provisioning` / `platform` / `shared`（单向）。
"""
