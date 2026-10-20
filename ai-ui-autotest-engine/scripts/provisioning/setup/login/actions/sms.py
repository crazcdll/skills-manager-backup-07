"""QAHome 短信原语：查询短信验证码、解析验证码与短信时间、按「本次请求」择码。

三层职责：
  · 查询：经 yooz 代理拉取某手机号的短信列表（`qahome_query_sms`）；
  · 解析：从短信文本解析出验证码，从 `addTimeFormat` 解析出下发时刻；
  · 择码：`select_code_for_request` —— 取码规则的**唯一实现**，把「验证码」绑定到
    「触发它的那次请求」，杜绝重试时误用上一次请求留下的旧码。
"""
import re
import base64
from platform.ssl_helper import get_verify_flag


_YOOZ_QAHOME_PROXY = base64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode() + "/node/api/data/monitor/qahome/sms"
_SMS_CODE_RE = re.compile(r'(\d{4,6})')
_LOGIN_CODE_KEYWORDS = ("登录验证码", "验证码", "请完成验证")

# ── 验证码 ↔ 请求的绑定规则（取码语义的唯一事实来源）──────────────────
# 为什么需要：登录失败会触发重试（动作层重试 / 编排层完整恢复），每次重试都会
# **重新点一次「获取验证码」**；服务端下发新码的同时会
# 作废旧码。若按「最近 N 秒」这种**单向时间窗**取码，重试时会捞到上一次请求留下、
# 已被作废的旧码 —— 提交后页面回显「验证码已过期」，把本可自愈的重试变成硬失败。
# 故取码规则收敛为「**码必须是本次请求之后下发的**」，只剩一个下界：
#   · sms_ts >= 请求时刻 - CODE_REQUEST_CLOCK_SKEW_SECONDS
#     （容忍本地与短信网关的时钟偏差，以及短信时间的秒级精度）
#   · 时间不可解析 → 无法证明归属本次请求 → 一律不采用（fail-closed；
#     绝不能因为解析失败就退回「不校验时间」的宽松分支）
CODE_REQUEST_CLOCK_SKEW_SECONDS = 5.0


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


def iter_login_codes(sms_list):
    """遍历短信列表，产出验证码类短信的 `(code, sms_ts, sms_time_str)`。

    只保留同时满足「命中登录验证码关键词」与「能解析出 4~6 位数字」的短信；
    下发时刻解析失败时 `sms_ts` 为 0（由择码方按 fail-closed 丢弃，见模块顶部）。
    """
    for sms in sms_list or []:
        msg = sms.get("message", "") or ""
        if not any(kw in msg for kw in _LOGIN_CODE_KEYWORDS):
            continue
        matched = _SMS_CODE_RE.search(msg)
        if not matched:
            continue
        sms_time_str = sms.get("addTimeFormat", "")
        yield matched.group(1), _parse_sms_time(sms_time_str), sms_time_str


def select_code_for_request(sms_list, request_ts, *, skew_seconds=CODE_REQUEST_CLOCK_SKEW_SECONDS):
    """从短信列表里挑出**本次请求下发**的验证码（取码规则的唯一实现）。

    判定（见模块顶部「验证码 ↔ 请求的绑定规则」）：
      · 时间可解析且 `sms_ts >= request_ts - skew_seconds` → 候选（本次请求之后下发）；
      · 时间不可解析、或早于请求时刻 → 丢弃并登记原因，绝不退而求其次。
    多候选时取**最早**的一条：同一次请求只会下发一个码，最早者最贴近本次请求，
    避免误取并发请求（如同一账号被其他任务占用）随后下发的码。

    Args:
        sms_list: `qahome_query_sms` 返回的短信列表。
        request_ts: 触发本次验证码请求的时刻（`ops.tap("获取验证码")` 后的 `time.time()`）。

    Returns:
        `(code, sms_time_str, diagnostics)`；无候选时 code / sms_time_str 为 None。
        `diagnostics = {"total": int,                     # 本批短信条数（定位"短信池是否为空"）
                        "code_like": int,                 # 其中验证码类短信条数
                        "stale": [(code, time_str), ...], # 早于本次请求（旧码/并发码）
                        "unparsable": [(code, time_str), ...],  # 下发时刻不可解析
                        "newest_ts": float,               # 本批最新一条验证码短信的下发时刻
                        "skew_seconds": float}`           # 最新码相对本次请求的时差
                        #   skew<0 且绝对值接近常量 → 短信网关与本机存在固定时钟偏差；
                        #   skew>0 → 新码已下发（但可能非本次请求）。
    """
    candidates = []
    stale, unparsable = [], []
    total = len(sms_list or [])
    code_like = 0
    newest_ts = 0.0
    for code, sms_ts, sms_time_str in iter_login_codes(sms_list):
        code_like += 1
        if sms_ts > newest_ts:
            newest_ts = sms_ts
        if sms_ts <= 0:
            unparsable.append((code, sms_time_str))
            continue
        if sms_ts < request_ts - skew_seconds:
            stale.append((code, sms_time_str))
            continue
        candidates.append((sms_ts, code, sms_time_str))
    diagnostics = {
        "total": total,
        "code_like": code_like,
        "stale": stale,
        "unparsable": unparsable,
        "newest_ts": newest_ts,
        # 仅在拿到可解析时刻时才有意义；否则给 0 表示"无从估计"
        "skew_seconds": round(newest_ts - request_ts, 1) if newest_ts > 0 else 0.0,
    }
    if not candidates:
        return None, None, diagnostics
    _, code, sms_time_str = min(candidates)
    return code, sms_time_str, diagnostics
