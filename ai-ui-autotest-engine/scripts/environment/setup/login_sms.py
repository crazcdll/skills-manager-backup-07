"""QAHome 短信原语：经 yooz 代理查询短信验证码、解析验证码与短信时间。"""
import re
import base64
from infra.ssl_helper import get_verify_flag


_YOOZ_QAHOME_PROXY = base64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode() + "/node/api/data/monitor/qahome/sms"
_SMS_CODE_RE = re.compile(r'(\d{4,6})')
_LOGIN_CODE_KEYWORDS = ("登录验证码", "验证码", "请完成验证")
def _query_sms_via_yooz(phone, timeout=15):
    try:
        import requests as _req
        resp = _req.post(_YOOZ_QAHOME_PROXY, json={"mobileNo": phone}, timeout=timeout, verify=get_verify_flag())
        data = resp.json()
        if data.get("code") != 0:
            print(f"QAHOME: yooz 代理外层错误 - code={data.get('code')}")
            return []
        inner = data.get("data", {})
        if inner.get("code") != 0:
            print(f"QAHOME: yooz 代理内层错误 - code={inner.get('code')}")
            return []
        result = inner.get("data", {}).get("result", [])
        print(f"QAHOME: 查询到 {len(result)} 条短信 for {phone}")
        return result
    except Exception as e:
        print(f"QAHOME: yooz 代理请求失败 - {e}")
        return []
def qahome_query_sms(phone, timeout=30):
    return _query_sms_via_yooz(phone, timeout=timeout)
def _parse_sms_time(time_str: str) -> float:
    """解析 SMS 时间字符串（如 '2026-09-02 17:43:05'）为时间戳，解析失败返回 0。"""
    if not time_str:
        return 0
    try:
        from datetime import datetime
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp()
    except (ValueError, TypeError):
        return 0
