#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SandboxDeviceLifecycle — 云模拟器设备生命周期实现。

通过 yooz-server API 管理云模拟器实例的创建、查询。
App 安装通过 yooz proxy API 远程触发（不经过本地 adb install）。

放在 devices/lifecycle/（而非 devices/android/lifecycle/）：本实现内部
全部是与操作系统无关的 HTTP API 调用，"当前只支持 Android"是 yooz-server
后端镜像能力的限制，不是本类的代码限制——与 LocalDeviceLifecycle 同理，
device_type 支持哪些 platform 由 devices/registry.py::_DEVICE_TYPE_REGISTRY
统一声明，本文件不应因为目录位置而误导"仅支持某平台"的架构假象。
"""
import json
import sys
import time

from devices.base import DeviceLifecycle, PlatformOps
from platform.sandbox_api import api_post, api_get, SandboxApiError


class SandboxDeviceLifecycle(DeviceLifecycle):
    """云模拟器设备生命周期实现。"""

    @property
    def device_type(self) -> str:
        return "sandbox"

    def acquire(self, user_mis: str) -> dict:
        """创建云模拟器实例（异步：create 拿 taskId → 轮询 status 直到 running）。

        云手机创建接口只有异步模式，create 立即返回 taskId，实例信息需轮询
        任务状态接口获取。按 taskId 轮询而非扫描用户实例列表，可精确匹配本次
        创建的实例（避免命中残留实例），并在 state=error 时立即拿到失败原因。

        Returns:
            dict: {sandboxId, serial, scrcpyUrl, ip, adbPort}
        Raises:
            SandboxApiError: 创建请求未被受理、创建失败或超时
        """
        resp = api_post("/node/api/data/monitor/sandbox/create",
                        {"user_id": user_mis}, timeout=30)
        task_id = (resp or {}).get("taskId")
        if not task_id:
            raise SandboxApiError(f"创建请求未被受理（响应无 taskId）: {resp}")
        sys.stderr.write(f"[device:create] 任务已提交 taskId={task_id}\n")
        sys.stderr.flush()

        _transient_errors = 0
        for i in range(60):
            time.sleep(3)
            try:
                task = api_get("/node/api/data/monitor/sandbox/status",
                               {"taskId": task_id}, timeout=20) or {}
                _transient_errors = 0
            except SandboxApiError as e:
                _transient_errors += 1
                sys.stderr.write(f"[device:create] 轮询 {i+1}/60 查询失败（{_transient_errors}/5）: {e}\n")
                sys.stderr.flush()
                if _transient_errors >= 5:
                    raise SandboxApiError(f"轮询连续 {_transient_errors} 次失败: {e}")
                continue

            state = task.get("state", "")
            sys.stderr.write(f"[device:create] 轮询 {i+1}/60 state={state}\n")
            sys.stderr.flush()

            if state == "error":
                raise SandboxApiError(f"创建失败: {task.get('error') or task}")
            if state == "running":
                domain = task.get("domain") or {}
                ip = domain.get("ip", "")
                adb_port = domain.get("adbPort", 8080)
                return {
                    "sandboxId": task.get("sandboxID", ""),
                    "serial": f"{ip}:{adb_port}",
                    "scrcpyUrl": domain.get("scrcpy", ""),
                    "ip": ip,
                    "adbPort": adb_port,
                }

        raise SandboxApiError(f"创建超时（180s，taskId={task_id}）")

    @property
    def uses_local_artifact(self) -> bool:
        """sandbox 走平台侧制品通道：制品不经本地 ⇒ L1 制品缓存不适用。"""
        return False

    def install_app(self, ops: PlatformOps, artifact_url: str,
                    device_id: str = None) -> bool:
        """通过 yooz proxy API 远程安装应用（**平台侧制品通道**）。

        制品不经本地：yooz-server 自己从 `appUrl` 下载 → 上传到平台 S3 → 让实例
        从 S3 安装（见 yooz-server `POST /sandbox/install`）。因此**本通道不适用 L1
        制品缓存**（`shared/artifact_cache.py` 只服务“本地制品 → 设备”的通道）：
        要让它也只搬一次字节，优化层次在服务端（按 `appUrl` 缓存 getUrl，避免每次 run
        重复“下载 + 上传”），而不是在这里加本地下载。

        Args:
            ops: PlatformOps 实例（sandbox 安装不直接使用 ops，但保持接口一致）
            artifact_url: 应用文件 URL
            device_id: sandbox 实例 ID（必填）
        """
        if not device_id:
            raise ValueError("sandbox install_app 需要 device_id (sandbox_id)")
        sys.stderr.write(
            "[device:install] 平台侧制品通道：由 yooz-server 下载并投递到实例"
            "（不经本地制品缓存）\n")
        try:
            api_post("/node/api/data/monitor/sandbox/install",
                     {"sandboxId": device_id, "appUrl": artifact_url},
                     timeout=130)
            return True
        except SandboxApiError:
            return False

    def query_user_devices(self, user_mis: str) -> list:
        """查询用户名下的所有存活云模拟器实例。"""
        data = api_get("/node/api/data/monitor/sandbox/query",
                       {"user_id": user_mis})
        raw_sandboxes = (data or {}).get("sandboxes") or []
        instances = []
        for s in raw_sandboxes:
            domain = s.get("domain")
            if isinstance(domain, str):
                try:
                    domain = json.loads(domain)
                except Exception:
                    domain = {}
            sid = s.get("sandboxID", "?")
            addr = f"{domain.get('ip', '?')}:{domain.get('adbPort', 8080)}"
            instances.append({
                "sandboxId": sid,
                "adbAddress": addr,
                "state": s.get("state", ""),
                "started_at": s.get("startedAt", "") or s.get("started_at", ""),
                "scrcpyUrl": domain.get("scrcpy", ""),
                "ip": domain.get("ip", ""),
                "adbPort": domain.get("adbPort", 8080),
            })
        return instances
