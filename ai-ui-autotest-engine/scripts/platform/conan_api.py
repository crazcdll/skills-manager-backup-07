#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conan（云测）设备 API 客户端 —— 平台访问的唯一出口。

通过 `conan-cli` 子进程封装【占用 / 释放 / 查询】三类设备操作（conan-cli 内部
处理 SSO 登录与 conanKey 换票）。上层（devices/lifecycle/cloud_emulator.py）
只经由本模块访问 Conan，符合"平台访问唯一出口"的分层约束。

为什么走 conan-cli 而非直连 HTTP API：契约一致（`{serialNumber,
remoteConnectAddress, occupationId, ...}`）、免自管 ssoid/conanKey 生命周期，
且与 KM《鸿蒙模拟器》推荐的 🟡 脚本执行路径一致；后续需要平台化时，
把本模块内部换成 HTTP API 即可，上层零改动。

环境变量：
    AI_UITEST_CONAN_BUSINESS_LINE — 占用使用的业务线 ID（不填则用内置默认）
"""
import json
import os
import subprocess
import sys

from shared.errors import InfraError

# conan-cli 占用时必须显式给业务线（否则进入交互式选择，自动化场景会挂起）。
# 默认取"试用业务线"ID，可用环境变量覆盖。
_DEFAULT_BUSINESS_LINE = "193"

_TIMEOUT_OCCUPY = 180
_TIMEOUT_RELEASE = 60
_TIMEOUT_QUERY = 60


class ConanApiError(InfraError):
    """Conan 平台错误。raw 保留原始输出，便于排障。"""

    def __init__(self, message, raw=None):
        super().__init__(message)
        self.raw = raw or message


def business_line_id() -> str:
    """占用使用的业务线 ID（env 覆盖 → 内置默认）。"""
    return os.environ.get("AI_UITEST_CONAN_BUSINESS_LINE") or _DEFAULT_BUSINESS_LINE


def _extract_json(text: str) -> dict:
    """从 conan-cli 输出中提取 JSON 对象。

    conan-cli 会先打印进度行（"- 正在获取认证信息..." 等）再输出 JSON，
    因此取第一个 `{` 到最后一个 `}` 之间的内容解析。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ConanApiError(f"conan-cli 输出中未找到 JSON: {text.strip()[:300]}")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ConanApiError(f"conan-cli JSON 解析失败: {e}; 原文: {text.strip()[:300]}")


def _run(args, timeout) -> dict:
    """执行 conan-cli（JSON 输出模式），返回解析后的 dict。"""
    cmd = ["conan-cli", *[str(a) for a in args], "--output", "json"]
    sys.stderr.write(f"[device:conan] 执行: {' '.join(cmd)} (timeout={timeout}s)\n")
    sys.stderr.flush()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise ConanApiError(
            "未找到 conan-cli，请先安装："
            "npm install -g @ee/conan-cli --registry=http://r.npm.sankuai.com"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ConanApiError(f"conan-cli 超时（{timeout}s）: {' '.join(cmd)}") from e

    text = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    if r.returncode != 0:
        out = text.strip()
        # 认证类失败（SSOID 缺失/过期、conanKey 解密失败等）给出**可执行**的诊断/重登指引，
        # 而不是丢一句裸 exit code —— 实测"取不到 conanKey"多属此类。
        hint = ""
        if any(k in out for k in ("SSOID", "sso", "认证", "登录", "conanKey", "conankey")) \
                or "401" in out or "Unauthorized" in out:
            hint = ("\n提示：疑似 Conan 认证问题，可先诊断 / 重登：\n"
                    "  conan-cli sso status   # 查看认证来源并在线校验 SSOID（失效时自动清理本地 token）\n"
                    "  conan-cli sso login    # 浏览器重新登录（沙箱环境走 CIBA：需在大象 App 确认授权）\n"
                    "  conan-cli sso logout   # 清掉本地 token 后重新登录")
        raise ConanApiError(f"conan-cli 失败（exit={r.returncode}）: {out[:300]}{hint}", raw=text)
    return _extract_json(text)


def occupy(platform: str = "harmony", device_type: str = "emulator",
           count: int = 1, business_line: str = None, numbers: list = None) -> list:
    """占用 Conan 设备，返回标准化后的设备列表。

    Args:
        numbers: 设备序列号白名单（**候选优先**）。非空时 Conan 只从这些候选里
            分配（`--numbers`）；为空/None 时走裸占用（Conan 从全量池分配）
            —— 即"候选为空 / 候选全被占"时的**兜底**。
    Returns:
        list[dict]: 每项 {serial, remoteAddress, occupationId, model, version}
    Raises:
        ConanApiError: 占用失败（含账号无业务线、无空闲设备、conanKey 失效等）
    """
    args = ["device", "occupy", "-p", platform, "-t", device_type,
            "-n", count, "-b", business_line or business_line_id()]
    if numbers:
        args += ["--numbers", ",".join(str(n) for n in numbers)]
    data = _run(args, timeout=_TIMEOUT_OCCUPY)
    devices = []
    for d in (data.get("devices") or []):
        serial = d.get("serialNumber")
        if not serial:
            continue
        devices.append({
            "serial": serial,
            "remoteAddress": d.get("remoteConnectAddress", ""),
            "occupationId": d.get("occupationId"),
            "model": d.get("model", ""),
            "version": d.get("version", ""),
        })
    if not devices:
        raise ConanApiError(f"占用成功但未返回设备: {json.dumps(data, ensure_ascii=False)[:300]}",
                            raw=json.dumps(data, ensure_ascii=False))
    return devices


def release(serials) -> bool:
    """释放指定序列号的设备（幂等；已释放/不存在不报错）。

    `serials` 兼容两种形态：**单个序列号字符串** / 序列号可迭代。
    ⚠️ 必须做这层归一：传字符串时 Python 会**逐字符**迭代，把 CLI 参数拆成一串单字符
    （实测 `conan-cli device release 1 2 7 . 0 . 0 . 1 : 1 0 0 3 0`），使释放不可靠
    （可能释放不到目标设备、或释放到别的设备）。
    """
    if isinstance(serials, str):
        serials = [serials]
    serials = [str(s).strip() for s in (serials or []) if str(s).strip()]
    if not serials:
        return True
    _run(["device", "release", *serials], timeout=_TIMEOUT_RELEASE)

    # 复核：release 接口幂等，且对"不存在的序列号"也不报错 → 仅凭调用成功会得到**假 true**
    # （实测：参数被拆成单字符时未释放到目标设备，调用方却拿到 cloudReleased=true，设备泄漏）。
    # 故以 status() 复查为准：目标序列号确已不在占用列表才算释放成功。
    try:
        still = {d.get("serial") for d in status()}
    except Exception as e:  # noqa: BLE001 —— 复查通道异常按"已释放"处理，不阻断收尾
        sys.stderr.write(f"[device:conan] 释放后复查失败（按已释放处理）: {e}\n")
        return True
    remaining = [s for s in serials if s in still]
    if remaining:
        sys.stderr.write(f"[device:conan] ⚠️ 释放后仍在占用列表: {remaining}（请人工确认）\n")
        return False
    return True


def status() -> list:
    """查询当前用户名下已占用的设备。

    Returns:
        list[dict]: 每项 {serial, remoteAddress, occupationId, platform, occupiedTime}
    """
    data = _run(["device", "status"], timeout=_TIMEOUT_QUERY)
    result = []
    for d in (data.get("devices") or []):
        serial = d.get("serialNumber")
        if not serial:
            continue
        result.append({
            "serial": serial,
            "remoteAddress": d.get("remoteConnectAddress", ""),
            "occupationId": d.get("occupationId"),
            "platform": (d.get("platform") or "").lower(),
            "occupiedTime": d.get("occupiedTime", ""),
        })
    return result
