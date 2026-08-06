#!/usr/bin/env python3
"""
美境设计师 V3 公共模块

抽取 generate.py / poll.py 共享的 HTTP 请求、认证刷新、错误处理等逻辑。
"""

from __future__ import annotations

import sys
import json
import shutil
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import ssl
from dataclasses import dataclass


# ─── 常量 ────────────────────────────────────────────────────────

BASE_URL = "https://aidesign.meituan.com/design/gateway/v3/chat"
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


# ─── 凭证数据类 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Credentials:
    """从 `meigen status --json` 解析的认证凭证。"""
    mis_id: str
    access_token: str
    token_type: str  # env / mtsso / ciba
    token_valid: bool
    client_id: str = ""


# ─── 认证错误 ──────────────────────────────────────────────────────

class AuthError(Exception):
    """认证失败错误，可触发 token 刷新重试。"""

    def __init__(self, resp: dict) -> None:
        self.resp = resp
        data = resp.get("data", {}) or {}
        msg = data.get("msg", resp.get("msg", ""))
        super().__init__(f"认证失败: {msg}")


# ─── 错误输出 ──────────────────────────────────────────────────────

def fail(msg: str) -> None:
    """输出错误 JSON Line 到 stdout（带 _action=failed）并退出。

    stdout JSON 是宿主 agent 的权威信息源（stderr 仅供人类排查）。
    _action=failed 与 generate.py/poll.py 的 JSON Lines 协议统一，
    宿主 agent 按 _action 分发处理，读 msg 提示用户。
    """
    print(json.dumps({"status": "failed", "_action": "failed", "msg": msg}, ensure_ascii=False), flush=True)
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# ─── 凭证获取（FR-021/FR-022）───────────────────────────────────────

def _run_meigen(*args: str) -> str:
    """执行 meigen 子命令并返回 stdout。失败抛 AuthError。"""
    cli = shutil.which("meigen")
    if not cli:
        fail("未找到 meigen 命令，请先安装 meigen-cli（npm install -g @meigen/meigen-cli）")
    cmd = [cli, *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        fail(f"meigen {' '.join(args)} 执行超时")
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip() or "未知错误"
        fail(f"meigen {' '.join(args)} 失败: {err}")
    return result.stdout.strip()


def get_credentials() -> Credentials:
    """通过 `meigen status --json` 获取当前凭证（FR-021/FR-022）。

    脚本启动时调用一次，避免依赖外部 --mis-id 参数。
    返回值不可变（dataclass frozen=True）。
    """
    raw = _run_meigen("status", "--json")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fail(f"meigen status --json 返回非 JSON: {raw[:200]}")
    return Credentials(
        mis_id=data.get("mis_id") or "",
        access_token=data.get("token") or "",
        token_type=data.get("token_type") or "",
        token_valid=bool(data.get("token_valid")),
        client_id=data.get("client_id") or "",
    )


def ensure_login() -> None:
    """检查 `meigen status --json` 的 token_valid 状态。

    token 有效：直接返回。
    token 失效：脚本不主动调用 `meigen login`，因为 CIBA 模式可能阻塞等待用户在「大象」App 授权，
    而 stdin 在脚本子进程中不可用，会导致登录失败。改为 fail 退出，让宿主 agent 把错误回显给用户，
    提示用户在终端手动运行 `meigen login` 完成授权。
    """
    creds = get_credentials()
    if creds.token_valid:
        return
    fail(
        "token 已失效，且脚本无法自动完成登录（可能需要在「大象」App 确认授权）。"
        "请在终端手动运行 `meigen login --json` 完成认证后重试。"
    )


# ─── HTTP 请求 ──────────────────────────────────────────────────────

def request(
    method: str,
    path: str,
    access_token: str,
    body: dict | None = None,
    query: dict | None = None,
) -> dict:
    """发送 HTTP 请求到 V3 接口，返回 JSON 响应体。

    Raises:
        AuthError: 认证失败（HTTP 状态码 401，或 body 中 status=401 / data.code=30001，
                   兼容顶层 code=30001 的旧形态）
    """
    client_id = get_credentials().client_id or "2a7394863a"
    url = f"{BASE_URL}{path}"
    if query:
        filtered = {k: v for k, v in query.items() if v is not None}
        if filtered:
            url = f"{url}?{urllib.parse.urlencode(filtered)}"

    headers = {
        "Cookie": f"{client_id}_ssoid={access_token}",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # HTTP 200 但 body 非 JSON（网关维护页/空响应/HTML 错误页等）
            fail(f"响应非 JSON: {raw[:200]}")
    except urllib.error.HTTPError as e:
        # HTTP 4xx/5xx：先解析 body，命中认证失败则抛 AuthError 触发刷新重试
        body: dict = {}
        try:
            body = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            pass
        if _is_auth_failure(e.code, body):
            raise AuthError(body)
        fail(f"HTTP {e.code} - {e.reason}. Body: {str(body)[:500]}")
    except urllib.error.URLError as e:
        fail(f"网络错误 - {e.reason}")
    except TimeoutError:
        fail("请求超时")

    if _is_auth_failure(None, result):
        raise AuthError(result)

    data = result.get("data")
    data_code = data.get("code") if isinstance(data, dict) else None
    code = result.get("code", data_code)
    if code not in (0, None):
        if isinstance(data, dict):
            msg = data.get("msg", result.get("msg", result.get("message", "未知错误")))
        else:
            msg = result.get("msg", result.get("message", "未知错误"))
        fail(f"接口错误 (code={code}): {msg}")

    return result


def _is_auth_failure(http_status: int | None, body: dict) -> bool:
    """判断响应是否为认证失败。

    覆盖三种形态：
    - HTTP 401
    - body 顶层 status=401（实际线上返回体，字段在 data 内）
    - body 中 code=30001（顶层或 data 内，兼容旧形态）
    """
    if http_status == 401:
        return True
    if not isinstance(body, dict):
        return False
    if body.get("status") == 401:
        return True
    data = body.get("data")
    data_code = data.get("code") if isinstance(data, dict) else None
    return body.get("code") == 30001 or data_code == 30001


# ─── Token 刷新（兼容旧调用 + 401 重试）─────────────────────────────

def refresh_token() -> str | None:
    """通过 `meigen login` 重新获取 token（不传 --mis-id，依赖 auto 降级链）。

    注意：CIBA 模式下 meigen login 会阻塞等待用户在「大象」App 授权，最多 3 分钟。
    若 30 秒内未返回 token，认为进入交互式授权流程，直接返回 None 让上层 fail 退出，
    由宿主 agent 提示用户手动登录（避免脚本无意义阻塞）。
    """
    try:
        cli = shutil.which("meigen")
        if not cli:
            return None
        result = subprocess.run(
            [cli, "login"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        token = result.stdout.strip()
        return token if token and result.returncode == 0 else None
    except Exception:
        return None


def get_access_token() -> str:
    """脚本启动时获取 access_token。

    调用 ensure_login() 确保 token 有效，再通过 get_credentials() 读取。
    """
    ensure_login()
    creds = get_credentials()
    if not creds.access_token:
        fail("获取 token 失败，请运行 meigen login 完成认证")
    return creds.access_token


def get_mis_id() -> str:
    """脚本启动时获取当前用户的 mis_id（FR-022）。"""
    creds = get_credentials()
    if not creds.mis_id:
        fail("获取 mis_id 失败，请运行 meigen login 完成认证")
    return creds.mis_id