#!/usr/bin/env python3
"""
AI-CR WebHook 自动接入工具
支持子命令拆分调用：check-admin / apply-admin / check-webhook / create-webhook
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ─── 常量 ────────────────────────────────────────────────────────────────────

BASE_URL = "https://dev.sankuai.com/rest/api/2.0"
WEBHOOK_URL = "https://spt.sankuai.com/api/pr-cr-hook"
AICR_AGENT = "1024_aicragent"
SSO_AUDIENCE = "f32a546874"
SSO_CACHE_FILE = "/tmp/aicr_webhook_sso_cache.txt"
SSO_CACHE_TTL = 1800  # 30 分钟
COOKIE_FILE = os.path.expanduser("~/.openclaw/mcode_cookie.txt")

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "M-APPKEY": "fe_com.sankuai.devtools.cargo.fe",
    "stash-area": "mcode",
    "devtools-host": "dev.sankuai.com",
}


# ─── SSO 认证 ─────────────────────────────────────────────────────────────────

def get_sso_cookie_from_moa():
    """通过 mtsso-moa-local-exchange 获取用户 SSO token"""
    try:
        if os.path.exists(SSO_CACHE_FILE):
            with open(SSO_CACHE_FILE) as f:
                lines = f.read().strip().splitlines()
            if len(lines) == 2:
                cached_ts, cached_token = float(lines[0]), lines[1]
                if time.time() - cached_ts < SSO_CACHE_TTL and cached_token:
                    return cached_token
    except Exception:
        pass

    try:
        probe = subprocess.run(
            ["npx", "mtsso-moa-feature-probe", "--timeout", "5"],
            capture_output=True, text=True, timeout=8,
        )
        if probe.returncode != 0:
            return None
        probe_data = json.loads(probe.stdout.strip())
        if not probe_data.get("ok"):
            return None

        result = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", SSO_AUDIENCE],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip())
        token = data.get("access_token", "")
        if token:
            try:
                with open(SSO_CACHE_FILE, "w") as f:
                    f.write(f"{time.time()}\n{token}")
            except Exception:
                pass
            return token
    except Exception:
        pass
    return None


def get_cookie(token_arg):
    """按优先级获取 Cookie"""
    if token_arg:
        return f"{SSO_AUDIENCE}_ssoid={token_arg}"

    moa_token = get_sso_cookie_from_moa()
    if moa_token:
        return f"{SSO_AUDIENCE}_ssoid={moa_token}"

    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                cookie_content = f.read().strip()
            if cookie_content:
                if "ssoid=" in cookie_content:
                    return cookie_content
                return f"{SSO_AUDIENCE}_ssoid={cookie_content}"
        except Exception:
            pass

    print(json.dumps({"error": "no_auth", "message": "无法自动获取认证，请通过 --token 指定 ssoid"}))
    sys.exit(1)


# ─── API 请求 ─────────────────────────────────────────────────────────────────

def api_request(method, path, cookie, data=None):
    """发送 API 请求，返回 JSON 或 None"""
    url = f"{BASE_URL}/{path.lstrip('/')}"
    headers = dict(HEADERS)
    headers["Cookie"] = cookie

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body) if resp_body.strip() else {}
    except urllib.error.HTTPError as e:
        resp_body = ""
        try:
            resp_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {"error": f"HTTP {e.code}", "detail": resp_body[:500]}
    except Exception as e:
        return {"error": str(e)}


# ─── URL 解析 ─────────────────────────────────────────────────────────────────

def parse_repo_url(url):
    """从 dev.sankuai.com URL 解析 project 和 repo"""
    m = re.search(r"dev\.sankuai\.com/code/repo-detail/([^/]+)/([^/]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def resolve_project_repo(args):
    """从参数中解析 project/repo"""
    project = getattr(args, "project", None)
    repo = getattr(args, "repo", None)
    url = getattr(args, "url", None)

    if url:
        p, r = parse_repo_url(url)
        if p and r:
            project = project or p
            repo = repo or r

    if not project or not repo:
        print(json.dumps({"error": "missing_args", "message": "请指定 --project 和 --repo，或使用 --url"}))
        sys.exit(1)

    return project, repo


# ─── 公共参数 ─────────────────────────────────────────────────────────────────

def add_common_args(parser):
    parser.add_argument("--project", "-p", help="项目名")
    parser.add_argument("--repo", "-r", help="仓库名")
    parser.add_argument("--url", "-u", help="仓库 URL（自动解析 project/repo）")
    parser.add_argument("--token", "-t", help="手动指定 SSO token")


# ─── 子命令：check-admin ─────────────────────────────────────────────────────

def cmd_check_admin(args):
    """查询管理员列表，检查 1024_aicragent 是否已是管理员，输出 JSON"""
    project, repo = resolve_project_repo(args)
    cookie = get_cookie(args.token)

    result = api_request("GET", f"projects/{project}/repos/{repo}/admin", cookie)
    if result is None or "error" in result:
        print(json.dumps({"error": "api_failed", "detail": result}))
        sys.exit(1)

    admin_list = result if isinstance(result, list) else result.get("values", result.get("admins", []))
    admins = []
    is_admin = False

    for admin in admin_list:
        if isinstance(admin, dict):
            # Code 平台 API 返回 { user: { name: "xxx" }, permission: "..." }
            # 兼容两种结构：嵌套 user 对象 / 扁平字段
            if "user" in admin and isinstance(admin.get("user"), dict):
                name = admin["user"].get("name", admin["user"].get("slug", admin["user"].get("username", "")))
            else:
                name = admin.get("name", admin.get("slug", admin.get("username", "")))
            admins.append(name)
            if name == AICR_AGENT:
                is_admin = True
        elif isinstance(admin, str):
            admins.append(admin)
            if admin == AICR_AGENT:
                is_admin = True

    print(json.dumps({
        "project": project,
        "repo": repo,
        "is_admin": is_admin,
        "admins": admins,
    }, ensure_ascii=False))


# ─── 子命令：apply-admin ─────────────────────────────────────────────────────

def cmd_apply_admin(args):
    """向指定审批人申请 REPO_ADMIN 权限，输出 JSON"""
    project, repo = resolve_project_repo(args)
    cookie = get_cookie(args.token)

    if not args.approver:
        print(json.dumps({"error": "missing_approver", "message": "请通过 --approver 指定审批人"}))
        sys.exit(1)

    payload = {
        "reason": "接入AICR web hook",
        "approver": args.approver,
        "permission": "REPO_ADMIN",
        "duration": "permanent",
        "expire": "0",
    }

    result = api_request(
        "PUT",
        f"projects/{project}/repos/{repo}/permissions/approval/apply",
        cookie,
        data=payload,
    )

    if result is None or "error" in result:
        print(json.dumps({"error": "apply_failed", "approver": args.approver, "detail": result}))
        sys.exit(1)

    print(json.dumps({
        "success": True,
        "project": project,
        "repo": repo,
        "approver": args.approver,
        "permission": "REPO_ADMIN",
        "duration": "permanent",
    }, ensure_ascii=False))


# ─── 子命令：check-webhook ───────────────────────────────────────────────────

def cmd_check_webhook(args):
    """查询现有 webhook，检查 AI-CR hook 是否已存在，输出 JSON"""
    project, repo = resolve_project_repo(args)
    cookie = get_cookie(args.token)

    result = api_request("GET", f"projects/{project}/repos/{repo}/integrations/webhooks", cookie)
    if result is None or "error" in result:
        print(json.dumps({"error": "api_failed", "detail": result}))
        sys.exit(1)

    webhooks = result if isinstance(result, list) else result.get("values", [])
    existing = False
    for wh in webhooks:
        if isinstance(wh, dict) and WEBHOOK_URL in wh.get("url", ""):
            existing = True
            break

    print(json.dumps({
        "project": project,
        "repo": repo,
        "webhook_exists": existing,
        "webhook_count": len(webhooks),
        "target_url": WEBHOOK_URL,
    }, ensure_ascii=False))


# ─── 子命令：create-webhook ──────────────────────────────────────────────────

def cmd_create_webhook(args):
    """创建 AI-CR WebHook，输出 JSON"""
    project, repo = resolve_project_repo(args)
    cookie = get_cookie(args.token)

    payload = {
        "url": WEBHOOK_URL,
        "events": ["pull_request_events", "draft_pull_request_events"],
        "description": "AI-CR 自动代码审查",
    }

    result = api_request(
        "POST",
        f"projects/{project}/repos/{repo}/integrations/webhooks",
        cookie,
        data=payload,
    )

    if result is None or "error" in result:
        print(json.dumps({"error": "create_failed", "detail": result}))
        sys.exit(1)

    print(json.dumps({
        "success": True,
        "project": project,
        "repo": repo,
        "webhook_url": WEBHOOK_URL,
        "events": ["pull_request_events", "draft_pull_request_events"],
    }, ensure_ascii=False))


# ─── 主入口 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI-CR WebHook 自动接入工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # check-admin
    p_check = subparsers.add_parser("check-admin", help="查询管理员列表，检查 1024_aicragent 权限")
    add_common_args(p_check)

    # apply-admin
    p_apply = subparsers.add_parser("apply-admin", help="申请 REPO_ADMIN 权限")
    add_common_args(p_apply)
    p_apply.add_argument("--approver", "-a", required=True, help="审批人 MIS")

    # check-webhook
    p_check_wh = subparsers.add_parser("check-webhook", help="查询现有 webhook")
    add_common_args(p_check_wh)

    # create-webhook
    p_create = subparsers.add_parser("create-webhook", help="创建 AI-CR WebHook")
    add_common_args(p_create)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "check-admin": cmd_check_admin,
        "apply-admin": cmd_apply_admin,
        "check-webhook": cmd_check_webhook,
        "create-webhook": cmd_create_webhook,
    }

    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
