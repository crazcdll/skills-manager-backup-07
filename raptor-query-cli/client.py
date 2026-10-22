"""
Raptor API 客户端
"""
import os
import time
import random
import logging
from typing import Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_API = "http://cat.service.sankuai.com/raptor"  # internal: .sankuai.com intranet, HTTP allowed
DEFAULT_TIMEOUT = 30

# 限流重试参数（code=1005）
_RATE_LIMIT_INITIAL_BACKOFF = 3    # 初始退避 3s：QPM=180 最低回血 3/s，3s 得 9 个令牌
_RATE_LIMIT_MULTIPLIER = 2         # 倍数 2x：3s → 6s → 12s
_RATE_LIMIT_MAX_BACKOFF = 15       # 最大退避 15s：回血 ~45 个令牌，接近 burst 容量
_RATE_LIMIT_MAX_RETRIES = 3        # 最多重试 3 次：总最坏等待 21s，覆盖 78% 的限流场景

def _load_token(env_key: str, conf_key: str = None, mws_service: str = None) -> str:
    """
    Token 加载优先级：
    1. 环境变量（env_key）
    2. 实时从 mws-discover-service 拉取（不缓存到本地文件）
    """
    # 1. 环境变量
    val = os.environ.get(env_key, "").strip()
    if val:
        return val
    # 2. 实时从远程 API 拉取
    _key = conf_key or env_key
    if mws_service:
        try:
            import urllib.request, ssl, json as _json
            mws_url = os.environ.get("MWS_DISCOVER_URL", "http://mws-discovery.cloud.test.sankuai.com").rstrip("/")
            url = f"{mws_url}/v1/tokens/{mws_service}"
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = _json.loads(resp.read())
                remote_val = data.get("tokens", {}).get(_key, "").strip()
                if remote_val:
                    return remote_val
        except Exception:
            pass
    return ""

DEFAULT_TOKEN = _load_token("RAPTOR_API_TOKEN", mws_service="raptor-prod")


class RaptorError(Exception):
    """Raptor API 异常"""
    def __init__(self, message: str, code: int = None, error_type: str = None):
        self.message = message
        self.code = code
        self.error_type = error_type  # 'rate_limit' | 'kv_limit' | None
        super().__init__(message)


def _rate_limit_error_msg() -> str:
    """根据是否使用自定义 Token 返回差异化的限流失败提示"""
    if os.environ.get("RAPTOR_API_TOKEN", "").strip():
        # 用户设置了自定义 token，触发的是该 token 的 QPM 限额
        return "Raptor API 限流（使用的是环境变量 RAPTOR_API_TOKEN 中的 Token），请稍后重试。"
    # 未设置环境变量，使用的是 MWS 共享 token，多用户竞争同一配额
    return (
        "Raptor API 限流（MWS 共享 Token 配额已满）。"
        "建议配置自定义 Token 以获得独立配额：export RAPTOR_API_TOKEN=xxx\n"
        "申请方式：https://km.sankuai.com/collabpage/2712642356"
    )


class RaptorClient:
    """Raptor API 客户端"""
    
    def __init__(self, token: str = None, api_base: str = None, timeout: int = DEFAULT_TIMEOUT):
        # 支持环境变量覆盖
        self.token = token or DEFAULT_TOKEN
        self.api_base = api_base or os.environ.get("RAPTOR_API", DEFAULT_API)
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带重试的 session"""
        session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def _make_url(self, path: str) -> str:
        return f"{self.api_base}{path}?token={self.token}"

    def _do_post(self, path: str, body: Dict = None, params: Dict = None) -> Dict[str, Any]:
        """执行一次 POST，不含重试逻辑"""
        url = self._make_url(path)
        resp = self.session.post(url, json=body, params=params, timeout=self.timeout)
        resp.raise_for_status()

        # 检查响应是否为 JSON（网关异常等场景可能返回非 JSON）
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            # 不标记 code=1005，避免被误判为限流触发重试
            raise RaptorError(
                f"API 返回非 JSON 响应 (Content-Type: {content_type})，请稍后重试"
            )

        data = resp.json()

        # 错误处理
        code = data.get("code", 0)
        if code != 10000 and code != 0:
            msg = data.get("message", "Unknown error")
            error_map = {
                10403: "认证失败，请检查 token",
                10404: "权限不足",
            }
            if code == 1005:
                # 区分 KV 超限 vs QPM 限流
                if "single request kv" in msg.lower():
                    raise RaptorError(
                        "查询数据量超限（单次请求 KV 上限）。请缩短时间范围后重试。"
                        "秒级指标建议查询不超过 30 分钟。"
                        "参考文档：https://km.sankuai.com/collabpage/2734210184",
                        code=1005,
                        error_type="kv_limit",
                    )
                raise RaptorError("rate_limit", code=1005, error_type="rate_limit")
            raise RaptorError(error_map.get(code, f"API error: {code} - {msg}"), code)

        return data

    def post(self, path: str, body: Dict = None, params: Dict = None) -> Dict[str, Any]:
        """发送 POST 请求，检测 code=1005 后按指数退避 + full jitter 自动重试"""
        backoff = _RATE_LIMIT_INITIAL_BACKOFF
        network_retried = False  # 网络抖动（Timeout/ConnectionError）最多重试 1 次
        for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
            try:
                return self._do_post(path, body=body, params=params)
            except RaptorError as e:
                if e.code == 1005 and e.error_type == "kv_limit":
                    # KV 超限：不重试，直接将清晰错误信息透传给调用方
                    raise
                if e.code == 1005 and attempt < _RATE_LIMIT_MAX_RETRIES:
                    # QPM 限流：full jitter 指数退避重试
                    sleep_sec = random.uniform(0, backoff)
                    logger.debug(
                        f"限流 (attempt {attempt + 1}/{_RATE_LIMIT_MAX_RETRIES})，"
                        f"退避 {sleep_sec:.1f}s（base={backoff}s）"
                    )
                    time.sleep(sleep_sec)
                    backoff = min(backoff * _RATE_LIMIT_MULTIPLIER, _RATE_LIMIT_MAX_BACKOFF)
                    continue
                # 重试耗尽或非限流错误：给出最终提示
                if e.code == 1005:
                    raise RaptorError(_rate_limit_error_msg(), code=1005)
                raise
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # 网络抖动：最多重试 1 次，不复用限流计数器
                if not network_retried:
                    network_retried = True
                    logger.debug(f"网络异常，重试一次：{e}")
                    continue
                err_msg = f"请求超时 (>{self.timeout}s)" if isinstance(e, requests.exceptions.Timeout) else "网络连接失败，请检查网络"
                raise RaptorError(err_msg)
            except Exception as e:
                raise RaptorError(f"请求异常: {e}")

    def get(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """发送 GET 请求"""
        url = self._make_url(path)
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RaptorError(f"GET 请求异常: {e}")
