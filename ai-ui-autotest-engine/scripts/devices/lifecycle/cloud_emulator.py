#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CloudEmulatorDeviceLifecycle — Conan 云模拟器设备生命周期实现。

对齐 KM《鸿蒙 HPX 打包类型与 imeituan-cli device install 安装矩阵》(2783208642)：
Conan 云模拟器经 `conan-cli device occupy -p <platform> -t emulator` 占用，返回
`serialNumber`（hdc `-t` 目标）与 `remoteConnectAddress`（hdc `-s` 远程 server）。

与 sandbox（yooz 云模拟器：实例常驻、复用优先、不销毁）不同：Conan 占用是
**消耗型资源**（每人 10 台上限、短期占用会到期），因此本实现额外提供 `release()`，
由收尾阶段显式归还占用；对应的设备形态 form 恒为 emulator（见 registry），
App 安装走 `bm install` 直装非 enterprise 的**可测性(debug) HAP**（HarmonyOps.install_app：
release 包缺 MSI 能力，登录会静默卡 Loading；HAP 先落设备侧缓存目录，避免重复重传 1.4G）。

本文件只承载 Conan 占用/释放这一段；平台/设备类型无关的分发仍由
registry + shared/context 负责。
"""
import sys

from devices.base import DeviceLifecycle, PlatformOps
from platform import conan_api


class CloudEmulatorDeviceLifecycle(DeviceLifecycle):
    """Conan 云模拟器生命周期实现。"""

    def __init__(self, platform: str):
        self._platform = platform

    @property
    def device_type(self) -> str:
        return "cloud-emulator"

    def acquire(self, user_mis: str) -> dict:
        """占用一台 Conan 云模拟器（候选优先，候选耗尽则裸占用兜底）。

        **候选模型**：候选 = device_registry 中 `device_type=cloud-emulator` 的记录；
        空闲候选 = 候选 − Conan `status`（本账号已占用）。有候选时让 Conan 只从
        候选里分配（`--numbers`）；候选为空 / 全被占则不带白名单裸占用（兜底）。
        占用状态始终以 Conan 实时返回为准，**我方不维护其占用状态**。

        Returns:
            dict: {serial, sandboxId, remoteAddress, occupationId, model, version}
                serial       — hdc `-t` 目标，同时作为设备池身份（sandboxId）
                remoteAddress— hdc `-s` 远程 hdc server 地址
        Raises:
            platform.conan_api.ConanApiError: 占用失败
        """
        numbers = self._free_candidates()
        devices = conan_api.occupy(platform=self._platform, device_type="emulator",
                                   count=1, numbers=numbers or None)
        d = devices[0]
        return {
            "serial": d["serial"],
            "sandboxId": d["serial"],
            "remoteAddress": d.get("remoteAddress", ""),
            "occupationId": d.get("occupationId"),
            "model": d.get("model", ""),
            "version": d.get("version", ""),
        }

    def _free_candidates(self) -> list:
        """计算空闲候选 = 候选(device_registry) − Conan 已占用(status)。

        任何一步失败都退化为空列表（调用方走裸占用兜底），不阻断占用主流程。
        """
        try:
            from platform.sandbox_api import list_registry_devices
            # 口径必须是 provider=conan + state=external（候选态）。
            # 旧的 device_type 过滤在单表改造后已失效：服务端会忽略未知参数，
            # 把整池 sandbox 行当成 conan 候选返回（`--numbers` 传错 UUID 直接占用失败）。
            rows = list_registry_devices(provider="conan", state="external",
                                         platform=self._platform, pageSize="200")
            candidates = [r.get("device_id") for r in rows if r.get("device_id")]
        except Exception as e:  # noqa: BLE001 —— 读候选失败不阻断占用
            sys.stderr.write(f"[device:create] 读取候选失败（忽略，走兜底占用）: {e}\n")
            return []
        if not candidates:
            return []
        try:
            occupied = {d.get("serial") for d in conan_api.status()}
        except Exception as e:  # noqa: BLE001 —— 查占用失败不阻断占用
            sys.stderr.write(f"[device:create] 查询 Conan 占用失败（忽略，走兜底占用）: {e}\n")
            return []
        free = [c for c in candidates if c not in occupied]
        sys.stderr.write(
            f"[device:create] {self._platform} 候选 {len(candidates)} 台，空闲 {len(free)} 台\n")
        return free

    def install_app(self, ops: PlatformOps, artifact_url: str, device_id: str = None) -> bool:
        """透传给 PlatformOps.install_app()：模拟器 form 走 `bm install` 直装可测性(debug) HAP。"""
        return ops.install_app(artifact_url)

    def query_user_devices(self, user_mis: str) -> list:
        """查询用户名下已占用的 Conan 设备（供设备池复用判定）。"""
        result = []
        for d in conan_api.status():
            # Conan status 是账号级全量（含鸿蒙 / iOS 云真机），必须按本次 platform 过滤，
            # 否则会把别的平台的已占用设备当成“自己已占用”，污染复用判定。
            if d.get("platform") and d["platform"] != self._platform:
                continue
            result.append({
                "sandboxId": d["serial"],
                "serial": d["serial"],
                "remoteAddress": d.get("remoteAddress", ""),
                "occupationId": d.get("occupationId"),
                # Conan status 无 state 字段：已占用即视为 running
                "state": "running",
                # occupiedTime 为人类可读串（"30 分钟"），不做年龄判定 → age=0，不误判 stale
                "started_at": "",
            })
        return result
