#!/usr/bin/env python3
"""将 trade-stability-issue-report 的 S1-S5 处置数据幂等上报到稳定性平台。

用法：python3 scripts/report_final.py <state_file>

上报内容为 S1-S5 的结构化对齐字段 + 完整状态快照 raw_state（不组装、不上报
Markdown 报告全文）；完整处置报告由 NoCode 搭建的报告详情页基于数据库字段渲染。

上报目标为美团内网授权域名（*.database.sankuai.com）的稳定性平台数据库，
不向任何外部域名传输数据。

上报成功后自动完成 S6 状态归档（S6_REPORT → completed，状态推进 S7_DONE）。

密钥解析优先级（高 → 低）：
1. 环境变量 TRADE_STABILITY_REPORT_TOKEN / USER_MIS / USER_NAME
2. scripts/report_config.json（本地配置，已入 .gitignore，不入仓库；
   其中 supabase_anon_key 为平台前端公开分发的匿名密钥，非机密凭证）
3. 上报人 MIS 自动从本地登录配置（~/.openclaw/openclaw.json 等）识别
"""

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# 稳定性平台数据库内网接口（美团内网授权域名，非外部服务）。
API_URL = (
    "https://dbcli-qsr0edmrt1cbdr9g.database.sankuai.com"
    "/rest/v1/issue_investigation?on_conflict=issue_id"
)
# 报告详情页链接（上报到数据库 report_url 字段，并用于用户侧精简输出）。
REPORT_DETAIL_URL_TEMPLATE = (
    "https://api-guidance-portal.mynocode.host"
    "/flbyw9_8182b99#/investigation/{issue_id}"
)
# 访问凭证不入仓库、不硬编码：通过环境变量或本地配置文件注入。
# supabase_anon_key 为平台前端公开分发的匿名密钥（anon key，非机密凭证，
# 仅具备内网数据库受限读写权限），命名明确标识其公开属性。
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "report_config.json"
)
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

STEP_NAMES = [
    "S1_INFO_FETCH",
    "S2_CHANGE_QUERY",
    "S3_CHANGE_STOP",
    "S4_DIAGNOSIS",
    "S5_REMEDIATION",
]

# 上报字段枚举约束（仅允许以下取值；信号类型为三类：告警/TT工单/反馈）
VALID_SIGNAL_TYPES = ("告警", "TT工单", "反馈")
VALID_BUSINESS_LINES = ("餐", "综", "酒", "景")

# 常见别名归一化映射（归一到枚举值后再校验/上报）
# 反馈 = 用户投诉、客诉、C端反馈、产研反馈、测试反馈、用户反馈等合并类
SIGNAL_TYPE_ALIASES = {
    "告警": "告警", "监控告警": "告警", "raptor告警": "告警", "alert": "告警",
    "tt工单": "TT工单", "tt": "TT工单", "工单": "TT工单", "tt工单反馈": "TT工单",
    "反馈": "反馈", "用户反馈": "反馈", "客诉": "反馈", "客诉反馈": "反馈",
    "投诉": "反馈", "用户投诉": "反馈", "c端反馈": "反馈", "产研反馈": "反馈",
    "测试反馈": "反馈", "complaint": "反馈", "feedback": "反馈",
}
BUSINESS_LINE_ALIASES = {
    "餐": "餐", "meishi": "餐", "food": "餐", "餐饮": "餐", "到餐": "餐", "美食": "餐",
    "综": "综", "gc": "综", "综合": "综", "到家": "综",
    "酒": "酒", "hotel": "酒", "酒店": "酒", "住宿": "酒",
    "景": "景", "travel": "景", "门票": "景", "旅游": "景", "度假": "景",
}


def normalize_signal_type(value):
    """归一化信号类型到枚举值（告警/TT工单/反馈），无法识别返回空串。"""
    return SIGNAL_TYPE_ALIASES.get(str(value or "").strip().lower(), "")


def normalize_business_line(value):
    """归一化业务线到枚举值（餐/综/酒/景），无法识别返回空串。"""
    return BUSINESS_LINE_ALIASES.get(str(value or "").strip().lower(), "")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def detect_default_mis():
    """依次从本地常见配置中识别当前用户 MIS。"""
    # 1. OpenClaw 配置
    data = _read_json(os.path.expanduser("~/.openclaw/openclaw.json"))
    if data and (data.get("X-User-Id") or "").strip():
        return data["X-User-Id"].strip()
    # 2. NoCode CLI 登录信息
    data = _read_json(os.path.expanduser("~/.nocode/nocode_cli_auth.json"))
    if data and (data.get("misId") or "").strip():
        return data["misId"].strip()
    # 3. git 配置邮箱前缀（如 bijietao@meituan.com）
    try:
        import subprocess
        email = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if "@" in email:
            return email.split("@", 1)[0].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def resolve_setting(env_name, config_key, config, default=""):
    """环境变量 > report_config.json > 默认值。"""
    value = os.getenv(env_name, "").strip()
    if value:
        return value
    value = str(config.get(config_key) or "").strip()
    if value:
        return value
    return default


def step_output(state, name):
    return state.get("steps", {}).get(name, {}).get("output", {}) or {}


def normalize_s1_fields(state):
    """将 S1 output 中 signal_type / business_line 归一化到枚举值（原地修改）。

    归一结果随 raw_state 上报并写回状态文件，保证数据库取值恒为枚举值。
    """
    s1_output = step_output(state, "S1_INFO_FETCH")
    signal_type = normalize_signal_type(s1_output.get("signal_type"))
    business_line = normalize_business_line(s1_output.get("business_line"))
    if signal_type:
        s1_output["signal_type"] = signal_type
    if business_line:
        s1_output["business_line"] = business_line
    return state


def validate_final_report(state):
    if not state.get("issue_id"):
        raise ValueError("issue_id 不能为空")

    steps = state.get("steps", {})
    incomplete = [
        name for name in STEP_NAMES
        if steps.get(name, {}).get("status") != "completed"
    ]
    if incomplete:
        raise ValueError(f"S1-S5 尚未全部完成: {', '.join(incomplete)}")

    # 枚举校验（先归一化别名，无法识别则拒绝上报）
    s1_output = step_output(state, "S1_INFO_FETCH")
    signal_type = normalize_signal_type(s1_output.get("signal_type"))
    if not signal_type:
        raise ValueError(
            f"signal_type 非法: {s1_output.get('signal_type')!r}，"
            f"仅允许 {' / '.join(VALID_SIGNAL_TYPES)}"
        )
    business_line = normalize_business_line(s1_output.get("business_line"))
    if not business_line:
        raise ValueError(
            f"business_line 非法: {s1_output.get('business_line')!r}，"
            f"仅允许 {' / '.join(VALID_BUSINESS_LINES)}"
        )


def mark_s6_completed(state, report_url):
    """在状态副本上标记 S6_REPORT 完成并推进 S7_DONE（不写盘）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    steps = state.setdefault("steps", {})
    s6 = steps.setdefault("S6_REPORT", {})
    if not s6.get("started_at"):
        s6["started_at"] = now
    s6["status"] = "completed"
    s6["completed_at"] = now
    s6["guard_passed"] = True
    output = s6.get("output") or {}
    output["report_uploaded"] = True
    output["detail_url"] = report_url
    s6["output"] = output
    state["current_state"] = "S7_DONE"
    state["updated_at"] = now
    return state


def build_payload(state, reporter_mis, reporter_name):
    s1 = step_output(state, "S1_INFO_FETCH")
    s2 = step_output(state, "S2_CHANGE_QUERY")
    s3 = step_output(state, "S3_CHANGE_STOP")
    s4 = step_output(state, "S4_DIAGNOSIS")
    s5 = step_output(state, "S5_REMEDIATION")
    now = datetime.now(timezone.utc).isoformat()
    report_url = REPORT_DETAIL_URL_TEMPLATE.format(issue_id=state["issue_id"])

    return {
        "issue_id": state["issue_id"],
        "report_url": report_url,
        "signal_raw": state.get("signal_raw", ""),
        "signal_type": s1.get("signal_type", ""),
        "business_line": s1.get("business_line", ""),
        "bundle_name": s1.get("bundle_name", ""),
        "page_name": s1.get("page_name", ""),
        "problem_time": s1.get("problem_time") or None,
        "tech_stack": s1.get("tech_stack", ""),
        "project_id": str(s1.get("project_id", "")),
        "current_state": "S7_DONE",
        "status": "completed",
        "conclusion_validity": s4.get("conclusion_validity", ""),
        "root_cause_type": s4.get("root_cause_type", ""),
        "root_cause_detail": s4.get("root_cause_detail", ""),
        "stop_loss_advice": s2.get("stop_loss_advice", ""),
        "stop_loss_status": s3.get("operation_status", ""),
        "fix_type": s5.get("fix_type") or s5.get("remediation_type", ""),
        "responsible_person": s4.get("responsible_person", ""),
        "report_markdown": "",
        "raw_state": state,
        "reporter_mis": reporter_mis,
        "reporter_name": reporter_name,
        "created_at": state.get("created_at") or now,
        "updated_at": state.get("updated_at") or now,
        "completed_at": state.get("updated_at") or now,
        "is_deleted": False,
    }


def upload_once(payload, report_token):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": report_token,
            "Authorization": f"Bearer {report_token}",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"unexpected HTTP status: {response.status}")


def upload_with_retry(payload, report_token):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            upload_once(payload, report_token)
            return
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, OSError) as error:
            last_error = error
            body = ""
            if isinstance(error, urllib.error.HTTPError):
                try:
                    body = error.read().decode("utf-8", "replace")[:500]
                except OSError:
                    pass
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS ** attempt
                print(
                    f"[report-upload] 第 {attempt} 次尝试失败: {error}{(' ' + body) if body else ''}，"
                    f"{wait}s 后重试…",
                    file=sys.stderr,
                )
                time.sleep(wait)
    raise RuntimeError(f"上报失败（已重试 {MAX_RETRIES} 次）: {last_error}")


def main():
    parser = argparse.ArgumentParser(
        description="S1-S5 处置数据上报（完整报告由 NoCode 详情页基于数据库字段渲染）"
    )
    parser.add_argument("state_file", help="最终状态 JSON 文件")
    args = parser.parse_args()

    config = load_config()
    report_token = resolve_setting(
        "TRADE_STABILITY_REPORT_TOKEN", "supabase_anon_key", config, ""
    )
    if not report_token:
        raise RuntimeError(
            "缺少上报凭证：请设置环境变量 TRADE_STABILITY_REPORT_TOKEN，"
            "或在 scripts/report_config.json 中配置 supabase_anon_key 字段"
            "（平台公开匿名密钥；该文件已加入 .gitignore，不入仓库）"
        )
    reporter_mis = resolve_setting("USER_MIS", "user_mis", config, detect_default_mis())
    reporter_name = resolve_setting("USER_NAME", "user_name", config, "")

    with open(args.state_file, "r", encoding="utf-8") as file:
        state = json.load(file)

    validate_final_report(state)
    # 在状态副本上预完成 S6 归档（用于上报 payload 的 raw_state 快照），
    # 上报成功后再将同一份最终状态写回状态文件。
    report_url = REPORT_DETAIL_URL_TEMPLATE.format(issue_id=state["issue_id"])
    final_state = mark_s6_completed(copy.deepcopy(state), report_url)
    # 归一化 signal_type / business_line 到枚举值（写入 raw_state 与 payload）
    normalize_s1_fields(final_state)
    payload = build_payload(final_state, reporter_mis, reporter_name)
    upload_with_retry(payload, report_token)

    with open(args.state_file, "w", encoding="utf-8") as file:
        json.dump(final_state, file, indent=2, ensure_ascii=False)

    print(
        f"[report-upload] success issue_id={payload['issue_id']} "
        f"reporter={reporter_mis or 'unknown'}"
    )
    print(f"[report-upload] detail_url={payload['report_url']}")
    print("[report-upload] S6_REPORT 已自动完成，状态推进到 S7_DONE")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, urllib.error.URLError) as error:
        print(f"[report-upload] failed: {error}", file=sys.stderr)
        sys.exit(1)
