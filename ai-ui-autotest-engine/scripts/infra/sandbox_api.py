#!/usr/bin/env python3
"""Sandbox 云模拟器 API 客户端。

封装经 yooz-server 代理转发的 CatPaw Sandbox OpenAPI 调用（create/install/
destroy/query 等）。API Key 在 Skill 内部维护（拆分字母+join），每次请求
通过 apiKey 参数传递给 yooz-server 进行鉴权，服务端不再持有硬编码密钥。

环境变量：
    YOOZ_SERVER_URL — yooz-server 地址（默认从内置编码解析）
"""
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

import base64 as _b64

from infra.ssl_helper import SSL_CONTEXT
from core.errors import InfraError

_YOOZ_DEFAULT = _b64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode()
YOOZ_BASE = os.environ.get("YOOZ_SERVER_URL", _YOOZ_DEFAULT)

_SANDBOX_API_KEY_PARTS = [
    'c', 'k', '_', 'r', 'T', '-', 'X', 'N', 'G', '-',
    'a', 'g', 'P', '2', 'l', 'W', 'g', '2', 'N', 'L',
    '9', 'L', 'B', '-', 'z', 'I', 'U', '2', '_', '6',
    '6', 'G', 'K', 'q', 'q',
]
SANDBOX_API_KEY = ''.join(_SANDBOX_API_KEY_PARTS)

class SandboxApiError(InfraError):
    """Sandbox API 错误。raw 保留服务端原始返回（含内层 data 详情），避免仅丢出 msg 丢失排障上下文。"""
    def __init__(self, message, raw=None):
        super().__init__(message)
        self.raw = raw or message

def _unwrap(json_obj: dict) -> dict:
    """yooz-server 返回 { message, code, data: { code, msg, data } }，解包内层 data。"""
    inner = json_obj.get("data") or json_obj
    if inner.get("code") != 0:
        raise SandboxApiError(inner.get("msg") or json.dumps(inner)[:300], raw=json.dumps(json_obj, ensure_ascii=False))
    return inner.get("data")

def _do_request(req: urllib.request.Request, path: str, timeout: int) -> dict:
    method = req.get_method()
    sys.stderr.write(f"[device:api] {method} {path} (timeout={timeout}s)...\n")
    sys.stderr.flush()
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        raise SandboxApiError(f"API {path} HTTP {e.code}: {raw[:300]}", raw=raw)
    except (urllib.error.URLError, socket.timeout) as e:
        raise SandboxApiError(f"API {path} request error: {e}")
    elapsed = time.time() - t0
    sys.stderr.write(f"[device:api] {method} {path} 完成 ({elapsed:.1f}s)\n")
    sys.stderr.flush()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise SandboxApiError(f"API {path} parse error: {raw[:200]}")

    return _unwrap(parsed)

def api_post(path: str, body: dict, timeout: int = 30) -> dict:
    body_with_key = {**body, "apiKey": SANDBOX_API_KEY}
    url = f"{YOOZ_BASE}{path}"
    payload = json.dumps(body_with_key).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _do_request(req, path, timeout)

def api_get(path: str, params: dict, timeout: int = 30) -> dict:
    params_with_key = {**params, "apiKey": SANDBOX_API_KEY}
    qs = urllib.parse.urlencode(params_with_key)
    url = f"{YOOZ_BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={}, method="GET")
    return _do_request(req, path, timeout)
