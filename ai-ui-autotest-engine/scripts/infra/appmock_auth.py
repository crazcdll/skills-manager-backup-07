#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock SSO 认证基础设施 —— 从 mock/appmock_session.py 提取的共享模块。

职责：通过 sso-auth-cli 获取 AppMock 的用户级 Cookie，支持进程内缓存 + 文件缓存
+ 静默取票 + CIBA 大象授权兜底。

被 infra/check_deps.py（基础设施层）和 mock/*.py（业务层）共同使用，
避免基础设施层逆向依赖业务层。
"""

import json
import os
import re
import subprocess
import time

from core.util.paths import ensure_dirs, APPMOCK_SESSION_COOKIE
from core.util.json_utils import write_json_atomic, read_json
from core.errors import AutotestError, soft_fail

# AppMock SSO clientId（sso-auth-cli 认证用）
_APPMOCK_SSO_CLIENT_ID = "e77b9e9d36"

# Cookie 缓存（进程内 + 文件）
_cookie_cache = {"cookie": None, "expires_at": 0}
_COOKIE_CACHE_FILE = APPMOCK_SESSION_COOKIE

# 关键提示词 → 实时透传给用户看到的友好提示
_SSO_HINT_RULES = [
    ("本地服务已启动", "sso-auth-cli 已启动本地授权服务，正在协商认证方式..."),
    ("bc-authorize", "正在向大象推送授权确认请求..."),
    ("已发起授权请求", "已向【大象】推送授权确认消息，请打开大象查看「账号权限管家」并点击「同意」"),
    ("等待授权确认", ""),
]


def _run_sso_auth_cli_streaming(cmd, timeout=180):
    """以流式方式执行 sso-auth-cli，实时透传关键提示。

    Args:
        cmd: 命令行参数列表
        timeout: 超时时间（秒）

    Returns:
        (returncode, combined_output)
        returncode 为 None 表示命令未找到（FileNotFoundError）
        returncode 为 "TIMEOUT" 表示超时
    """
    start = time.time()
    lines = []
    seen_hints = set()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return None, ""

    try:
        while True:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if line == "" and proc.poll() is not None:
                break
            if line:
                lines.append(line.rstrip("\n"))

                # 轮询进度：[CIBA] 等待授权确认... (3/36)
                m = re.search(r"等待授权确认\.\.\.\s*\((\d+)/(\d+)\)", line)
                if m:
                    cur, total = m.group(1), m.group(2)
                    if "polling_started" not in seen_hints:
                        print("已向【大象】推送授权确认消息，请打开大象查看「账号权限管家」并点击「同意」")
                        seen_hints.add("polling_started")
                    print("等待大象授权确认中... (%s/%s，约 %ss)" % (cur, total, int(cur) * 5))
                    continue

                # 其他关键提示词只在首次出现时打印
                for keyword, hint in _SSO_HINT_RULES:
                    if keyword == "等待授权确认":
                        continue
                    if keyword in line and keyword not in seen_hints:
                        seen_hints.add(keyword)
                        if keyword == "已发起授权请求":
                            seen_hints.add("polling_started")
                        if hint:
                            print(hint)
                        break

            if time.time() - start > timeout:
                proc.kill()
                proc.wait()
                return "TIMEOUT", "\n".join(lines)

        proc.wait()
    except Exception:
        proc.kill()
        proc.wait()
        raise

    returncode = proc.returncode
    return returncode, "\n".join(lines)


def _extract_last_json_blob(text):
    """从多行文本中提取最后一个完整 JSON 对象的字符串。"""
    decoder = json.JSONDecoder()
    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("{"):
            candidate = "\n".join(lines[i:])
            try:
                obj, end = decoder.raw_decode(candidate)
                return candidate[:end]
            except json.JSONDecodeError:
                continue
    return text.strip()


def _get_appmock_cookie() -> str:
    """通过 sso-auth-cli 获取 AppMock 的 SSO Session Cookie。

    优先使用进程内缓存 → 文件缓存 → 重新认证。

    Returns:
        Cookie 字符串（如 "e77b9e9d36_ssoid=AT_xxx..."）

    Raises:
        RuntimeError: sso-auth-cli 不可用或认证失败
    """
    now = time.time()

    # 1. 进程内缓存
    if _cookie_cache["cookie"] and _cookie_cache["expires_at"] > now:
        return _cookie_cache["cookie"]

    # 2. 文件缓存
    ensure_dirs()
    if os.path.isfile(_COOKIE_CACHE_FILE):
        try:
            cached = read_json(_COOKIE_CACHE_FILE, default={})
            if cached.get("cookie") and cached.get("expires_at", 0) > now:
                _cookie_cache["cookie"] = cached["cookie"]
                _cookie_cache["expires_at"] = cached["expires_at"]
                return cached["cookie"]
        except Exception:
            pass

    # 3. sso-auth-cli 取票（两阶段策略：静默优先 → 交互式兜底）
    print("正在获取 AppMock 授权（client_id=%s）..." % _APPMOCK_SSO_CLIENT_ID)

    # ── 阶段 A: 静默取票 ──
    returncode, combined = _run_sso_auth_cli_streaming(
        ["sso-auth-cli", _APPMOCK_SSO_CLIENT_ID, "--cookie", "--json", "--auth", "silent"],
        timeout=15,
    )

    if returncode is None:
        raise RuntimeError(
            "sso-auth-cli 未安装。请先安装：\n"
            "  brew install mtsso/tap/sso-auth-cli\n"
            "或参考 https://km.sankuai.com/collabpage/2515785081"
        )

    if returncode != 0:
        # ── 阶段 B: 静默失败，fallback 到 CIBA 大象授权 ──
        print("静默取票未命中，正在向大象推送授权确认...")
        returncode, combined = _run_sso_auth_cli_streaming(
            ["sso-auth-cli", _APPMOCK_SSO_CLIENT_ID, "--force-ciba", "--json"],
            timeout=180,
        )

    if returncode == "TIMEOUT":
        raise RuntimeError("sso-auth-cli 认证超时（180s），请检查大象是否在线并确认授权")

    if returncode != 0:
        if "sub_access_denied" in combined:
            raise RuntimeError(
                "SSO 权限不足。请前往 IAM 申请 AppMock 系统入口权限：\n"
                f"  {combined}"
            )
        raise RuntimeError(f"sso-auth-cli 认证失败 (exit={returncode}): {combined[:500]}")

    # 解析 JSON 输出获取 token 和过期时间
    cookie_str = None
    expires_at = now + 7200  # 默认 2 小时

    # 从实时输出中提取最后一段 JSON
    stdout_text = _extract_last_json_blob(combined)
    try:
        info = json.loads(stdout_text)
        token = info.get("token", "")
        client_id = info.get("client_id", "")
        if token and client_id:
            cookie_str = f"{client_id}_ssoid={token}"
        if info.get("expires_at"):
            expires_at = info["expires_at"] / 1000 - 120
        elif info.get("expires_in_sec"):
            expires_at = now + info["expires_in_sec"] - 120
    except (json.JSONDecodeError, ValueError):
        pass

    # fallback: 从 --cookie 原始输出解析
    if not cookie_str:
        for line in combined.split("\n"):
            line = line.strip()
            if "_ssoid=" in line and not line.startswith("{"):
                cookie_str = line
                break

    if not cookie_str:
        raise RuntimeError(f"sso-auth-cli 输出中未找到有效 Cookie: {combined[:300]}")

    # 写入缓存
    _cookie_cache["cookie"] = cookie_str
    _cookie_cache["expires_at"] = expires_at

    try:
        write_json_atomic(_COOKIE_CACHE_FILE, {"cookie": cookie_str, "expires_at": expires_at})
    except Exception:
        pass

    return cookie_str


def _get_cookie_or_warn() -> str:
    """获取 Cookie，失败时打印警告并返回空字符串（不抛异常）。"""
    try:
        return _get_appmock_cookie()
    except AutotestError as e:
        soft_fail("env", "SSO_COOKIE_FAILED", e)
        print(f"⚠️  SSO Cookie 获取失败: {e}")
        return ""