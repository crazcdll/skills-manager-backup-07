#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cr_report.py — AI-CR Local 上报脚本（DB + 大象群播，两路并行）

封装 Step 6D：
  - DB 接口上报（主路径）：HTTP POST → cr_task 表
  - 大象群聊推送（并行）：全局群 + 团队群（可选）
  - 多维表格降级（DB 失败时）：citadel-database addData

两路并行执行，互不阻塞，各自重试，全部失败静默。

用法见 --help。
"""
import argparse
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ── 环境清理 ──────────────────────────────────────────────────────────────
for _var in ("M_SPANID", "M_TRACEID", "M_SPANNAME", "M_PARENT_SPANID"):
    os.environ.pop(_var, None)

# ── 大象 Bot 凭证（与 PR-CR 共用同一 bot） ────────────────────────────────
AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151
TOKEN_URL           = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL            = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"

# ── DB 接口配置（与 PR-CR 一致） ──────────────────────────────────────────
DEFAULT_HOST    = "spt.sankuai.com"
DEFAULT_SCHEME  = "https"

# ── 多维表格降级配置 ──────────────────────────────────────────────────────
DEFAULT_TABLE_ID = "2751197605"

# ── 重试配置 ───────────────────────────────────────────────────────────────
MAX_RETRIES    = 4
RETRY_INTERVAL = 2  # seconds


# ═══════════════════════════════════════════════════════════════════════════
# 大象群聊推送
# ═══════════════════════════════════════════════════════════════════════════

def _b64url(data) -> str:
    """Base64 URL encode, accepts str or bytes."""
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _get_dx_token():
    """使用 client_secret_jwt 方式获取大象 API token。"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": AICR_BOT_APP_ID,
        "sub": AICR_BOT_APP_ID,
        "aud": TOKEN_URL,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 300,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")))
    p = _b64url(json.dumps(payload, separators=(",", ":")))
    signing_input = f"{h}.{p}".encode()
    sig = hmac.new(AICR_BOT_APP_SECRET.encode(), signing_input, hashlib.sha256).digest()
    jwt_token = f"{h}.{p}.{_b64url(sig)}"

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt_token,
        "client_id": AICR_BOT_APP_ID,
        "scope": "client_id:xm-xai",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        return data["access_token"]


def _send_group_msg(token, gid, text):
    """向大象群发送文本消息。"""
    payload = json.dumps({
        "gid": gid,
        "sendMsgInfo": {
            "type": "text",
            "body": json.dumps({"text": text})
        }
    }).encode()
    req = urllib.request.Request(
        SEND_URL, data=payload, method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _send_to_group_with_fresh_token(gid, message):
    """向单个群发送消息，每次重试前重新获取 token。返回 (success, error_msg)。"""
    last_err = ""
    for i in range(MAX_RETRIES):
        try:
            token = _get_dx_token()
            _send_group_msg(token, gid, message)
            return True, ""
        except Exception as e:
            last_err = str(e)
            if i < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL)
    return False, last_err


def _build_dx_message(args):
    """构建大象群聊推送消息文本（Local-CR 版，对标 Agent Skill 格式）。"""
    # 构建 P0/P1 问题摘要（compact，仅保留关键问题）
    top_issues = ""
    if args.issues_summary:
        summary = args.issues_summary.replace('\\n', '\n')
        top_issues = f"\n⚠️ 关键问题：\n{summary}\n"

    msg = (
        f"【AI-CR Local】 {args.repo} {args.source_branch}\n"
        f"{args.conclusion}  P0={args.p0} P1={args.p1} P2={args.p2} P3={args.p3}\n"
        f"操作者： {args.operator_mis}  触发人： {args.operator_mis}\n"
        f"范围: 🟦全量\n"
        f"{top_issues}"
        f"\n📄 详细报告： {args.doc_url or '（无）'}"
    )
    msg = msg.replace('\n', '\r\n')
    return msg


def task_daxiang(args):
    """大象群聊推送（全局群 + 可选团队群）。"""
    message = _build_dx_message(args)

    # 安全校验：必须以 【AI-CR 开头
    if not message.startswith("【AI-CR"):
        return {"status": "failed", "groups_pushed": [],
                "error": "消息未以【AI-CR开头，拒绝发送"}

    groups_pushed = []
    groups_failed = []

    # 全局群
    ok, g_err = _send_to_group_with_fresh_token(AICR_GLOBAL_GID, message)
    if ok:
        groups_pushed.append("global")
    else:
        groups_failed.append(f"global: {g_err}")

    # 团队群（如果有）
    if args.team_chat_group_id:
        try:
            team_gid = int(args.team_chat_group_id)
            ok_t, t_err = _send_to_group_with_fresh_token(team_gid, message)
            if ok_t:
                groups_pushed.append("team")
            else:
                groups_failed.append(f"team: {t_err}")
        except ValueError:
            groups_failed.append("team(invalid_gid)")

    if groups_pushed:
        return {"status": "success", "groups_pushed": groups_pushed,
                "error": "; ".join(groups_failed) if groups_failed else ""}
    return {"status": "failed", "groups_pushed": [],
            "error": f"所有群推送失败: {', '.join(groups_failed)}"}


# ═══════════════════════════════════════════════════════════════════════════
# DB 接口上报
# ═══════════════════════════════════════════════════════════════════════════

def _load_issues(issues_file):
    """从 JSON 文件加载 issue 列表，返回 list[dict]。"""
    if not issues_file:
        return []
    try:
        with open(issues_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def build_cr_result(args):
    """构造 cr_result_json，对齐 ai-quality-cr-agent 的 cr_result 结构。

    字段：conclusion / counts / is_sdd / text_code_consistency_rate /
          skill_version / km_url / review_time / repo / issues
    """
    import datetime as dt
    result = {}
    if args.conclusion:
        result["conclusion"] = args.conclusion
    counts = {}
    for level in ("p0", "p1", "p2", "p3"):
        val = getattr(args, level)
        if val is not None:
            counts[level] = val
    if counts:
        result["counts"] = counts
    # is_sdd: --is-sdd → True, --no-sdd → False, 默认 None
    if args.is_sdd is not None:
        result["is_sdd"] = args.is_sdd
    if args.skill_version:
        result["skill_version"] = args.skill_version
    if args.doc_url:
        result["km_url"] = args.doc_url
    if args.repo:
        result["repo"] = args.repo
    if args.source_branch:
        result["branch"] = args.source_branch
    result["review_time"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # issues 明细：从 --issues-file 读取 JSON 数组，直接透传
    issues = _load_issues(getattr(args, "issues_file", None))
    if issues:
        result["issues"] = issues
    return result if result else None


def build_payload(args):
    """构造 DB API payload。"""
    payload = {"pr_url": args.pr_url}
    if args.author_mis is not None:
        payload["author_mis"] = args.author_mis
    if args.source_branch is not None:
        payload["source_branch"] = args.source_branch
    if args.target_branch is not None:
        payload["target_branch"] = args.target_branch
    if args.trigger_source is not None:
        payload["trigger_source"] = args.trigger_source
    if args.trigger_event is not None:
        payload["trigger_event"] = args.trigger_event
    cr_result = build_cr_result(args)
    if cr_result is not None:
        payload["cr_result_json"] = cr_result
    return payload


def submit_db(host, payload, scheme="http", no_proxy=False):
    """调用 DB API，返回 (status_code, response_body)。"""
    url = f"{scheme}://{host}/api/aicr/submit-task"
    data = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json; charset=utf-8"}
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler) if no_proxy else urllib.request.build_opener()

    last_err = ""
    for i in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=data, method="POST", headers=headers)
            with opener.open(req, timeout=15) as resp:
                return resp.status, resp.read().decode("utf-8")
        except Exception as e:
            last_err = str(e)
            if i < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL)
    return -1, last_err


def task_db(args):
    """DB 接口上报。"""
    if args.trigger_source is None:
        args.trigger_source = os.getenv("X_AI_SOURCE", "agent").lower()

    payload = build_payload(args)
    status, body = submit_db(args.host, payload, args.scheme, args.no_proxy)

    if status == 200:
        try:
            data = json.loads(body)
            return {"status": "success", "id": data.get("id"), "raw": body}
        except (ValueError, KeyError):
            return {"status": "success", "raw": body}
    return {"status": "failed", "http_status": status, "error": body}


# ═══════════════════════════════════════════════════════════════════════════
# 多维表格降级
# ═══════════════════════════════════════════════════════════════════════════

def task_table_fallback(args):
    """多维表格降级写入（DB 失败时执行）。"""
    import datetime as dt

    # 时间戳（必须 13 位毫秒）
    date_ms = int(dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)

    # 数据行
    row = [
        date_ms,                          # 日期
        "",                                # PR链接（空）
        args.repo,                         # 仓库
        args.source_branch,                # 分支名
        args.operator_mis,                 # 使用者
        args.org_id or "",                 # 组织架构
        args.conclusion,                   # 结论
        str(args.p0 or 0),                 # P0
        str(args.p1 or 0),                 # P1
        args.doc_url or "",                # 学城链接
        args.skill_version or "ai-cr-forlocal",  # Skill版本
    ]

    # 调用 oa-skills citadel-database addData
    try:
        result = subprocess.run(
            ["oa-skills", "citadel-database", "addData",
             "--tableId", DEFAULT_TABLE_ID,
             "--data", json.dumps([row])],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"status": "success", "raw": result.stdout}
        return {"status": "failed", "error": result.stderr}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 主函数：两路并行
# ═══════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description="AI-CR Local 上报脚本（DB + 大象群播，两路并行）"
    )

    # 基础参数
    p.add_argument("--pr-url", default="", help="PR 链接（Local-CR 传空）")
    p.add_argument("--author-mis", default=None, help="操作者 mis")
    p.add_argument("--source-branch", default=None, help="本地分支名")
    p.add_argument("--target-branch", default=None, help="对比基线分支")
    p.add_argument("--repo", default=None, help="仓库名")
    p.add_argument("--operator-mis", default=None, help="操作者 mis（同 author-mis）")
    p.add_argument("--conclusion", default=None, help="CR 结论 emoji")
    p.add_argument("--p0", type=int, default=0)
    p.add_argument("--p1", type=int, default=0)
    p.add_argument("--p2", type=int, default=0)
    p.add_argument("--p3", type=int, default=0)
    p.add_argument("--file-count", default="N", help="涉及文件数")
    p.add_argument("--issues-summary", default="", help="P0/P1 问题摘要文本")
    p.add_argument("--doc-url", default="", help="学城文档 URL")
    p.add_argument("--issues-file", default=None, help="issues 明细 JSON 文件路径（JSON 数组，直接写入 cr_result_json）")
    p.add_argument("--skill-version", default="ai-cr-forlocal")
    p.add_argument("--org-id", default="", help="组织架构 orgId")
    p.add_argument("--team-chat-group-id", default="", help="团队群 ID（空则只推全局群）")

    # DB 参数
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--trigger-source", default=None)
    p.add_argument("--trigger-event", default="sdlc_forlocal")
    p.add_argument("--scheme", default=DEFAULT_SCHEME, choices=["http", "https"])
    p.add_argument("--no-proxy", action="store_true")
    p.add_argument("--no-sdd", action="store_false", dest="is_sdd", default=False)
    p.add_argument("--is-sdd", action="store_true", default=None)

    # 功能开关
    p.add_argument("--no-daxiang", action="store_true", help="跳过大象群播")
    p.add_argument("--no-db", action="store_true", help="跳过 DB 上报")
    p.add_argument("--no-table-fallback", action="store_true", help="跳过多维表格降级")
    p.add_argument("-q", "--quiet", action="store_true", help="静默模式")

    args = p.parse_args()

    # operator_mis 默认取 author_mis
    if not args.operator_mis:
        args.operator_mis = args.author_mis or ""

    results = {}

    # 并行执行 DB + 大象群播
    tasks = {}
    if not args.no_db:
        tasks["db"] = task_db
    if not args.no_daxiang:
        tasks["daxiang"] = task_daxiang

    if tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(fn, args): name for name, fn in tasks.items()}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = {"status": "failed", "error": str(e)}

    # DB 失败 → 多维表格降级
    if not args.no_db and not args.no_table_fallback:
        db_result = results.get("db", {})
        if db_result.get("status") != "success":
            results["table_fallback"] = task_table_fallback(args)

    # 输出结果
    if not args.quiet:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    # 退出码：全部失败才返回 1
    any_success = any(r.get("status") == "success" for r in results.values())
    sys.exit(0 if any_success else 1)


if __name__ == "__main__":
    main()
