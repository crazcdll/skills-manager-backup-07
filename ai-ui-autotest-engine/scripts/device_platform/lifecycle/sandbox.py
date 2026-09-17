#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SandboxDeviceLifecycle — 云模拟器设备生命周期实现。

通过 yooz-server API 管理云模拟器实例的创建、销毁、查询。
App 安装通过 yooz proxy API 远程触发（不经过本地 adb install）。

放在 platform/lifecycle/（而非 platform/android/lifecycle/）：本实现内部
全部是与操作系统无关的 HTTP API 调用，"当前只支持 Android"是 yooz-server
后端镜像能力的限制，不是本类的代码限制——与 LocalDeviceLifecycle 同理，
device_type 支持哪些 platform 由 platform/registry.py::_DEVICE_TYPE_REGISTRY
统一声明，本文件不应因为目录位置而误导"仅支持某平台"的架构假象。
"""
import json
import sys
import time

from device_platform.base import DeviceLifecycle, PlatformOps
from infra.sandbox_api import api_post, api_get, SandboxApiError
from infra.session import imeituan_location_off


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

    def install_app(self, ops: PlatformOps, artifact_url: str,
                    device_id: str = None) -> bool:
        """通过 yooz proxy API 远程安装应用。

        Args:
            ops: PlatformOps 实例（sandbox 安装不直接使用 ops，但保持接口一致）
            artifact_url: 应用文件 URL
            device_id: sandbox 实例 ID（必填）
        """
        if not device_id:
            raise ValueError("sandbox install_app 需要 device_id (sandbox_id)")
        try:
            api_post("/node/api/data/monitor/sandbox/install",
                     {"sandboxId": device_id, "appUrl": artifact_url},
                     timeout=130)
            return True
        except SandboxApiError:
            return False

    def release(self, device_info: dict) -> bool:
        """销毁云模拟器实例。"""
        sandbox_id = device_info.get("sandboxId") or device_info.get("sandbox_id")
        if not sandbox_id:
            return False
        try:
            api_post("/node/api/data/monitor/sandbox/destroy",
                     {"sandboxId": sandbox_id})
            return True
        except SandboxApiError as e:
            sys.stderr.write(f"[device:lifecycle] 销毁失败: {e}\n")
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
                "scrcpyUrl": domain.get("scrcpy", ""),
                "ip": domain.get("ip", ""),
                "adbPort": domain.get("adbPort", 8080),
            })
        return instances

    def cleanup_user_devices(self, user_mis: str) -> dict:
        """销毁用户名下的所有存活云模拟器实例。

        先尝试关闭模拟定位（GPS mock 系统级设置），再逐个销毁实例。
        """
        # 关闭模拟定位（仅在有 imeituan session 时有意义，静默容错）
        try:
            r = imeituan_location_off()
            if r.get("ok"):
                sys.stderr.write("[device:lifecycle] ✅ 模拟定位已关闭\n")
            else:
                sys.stderr.write(f"[device:lifecycle] ℹ️ 模拟定位关闭跳过（可能未开启）: {r.get('detail', '')}\n")
        except Exception as e:
            sys.stderr.write(f"[device:lifecycle] ⚠️ 模拟定位关闭异常: {e}\n")

        instances = self.query_user_devices(user_mis)
        released = []
        errors = []
        for inst in instances:
            sid = inst.get("sandboxId")
            addr = inst.get("adbAddress")
            try:
                api_post("/node/api/data/monitor/sandbox/destroy",
                         {"sandboxId": sid})
                released.append(sid)
                sys.stderr.write(f"[device:lifecycle] ✅ 已销毁 {sid} ({addr})\n")
            except SandboxApiError as e:
                errors.append({"sandboxId": sid, "error": str(e)})
                sys.stderr.write(f"[device:lifecycle] ⚠️ 销毁 {sid} 失败: {e}\n")
        return {"released": released, "errors": errors}
