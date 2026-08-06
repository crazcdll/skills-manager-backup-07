#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
美团 Code 平台 CLI — 通过 REST API 操作 Pull Request。
支持：查看 PR 详情、文件变更、Diff、评论（全局/行级）、Review 等。
Cookie 从浏览器 CDP 自动获取，或手动指定。
"""

import argparse
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import urllib.error

BASE_URL = os.getenv("CODE_BASE_URL", "https://dev.sankuai.com")
CDP_URL = os.getenv("CDP_URL", "http://localhost:9222")

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def get_cookies_from_cdp():
    try:
        import http.client
        host_port = CDP_URL.replace("http://", "").replace("https://", "")
        host, port = host_port.split(":") if ":" in host_port else (host_port, "9222")
        conn = http.client.HTTPConnection(host, int(port), timeout=3)
        conn.request("GET", "/json/list")
        tabs = json.loads(conn.getresponse().read())
        target = None
        for t in tabs:
            if "dev.sankuai.com" in t.get("url", ""):
                target = t
                break
        if not target and tabs:
            target = tabs[0]
        if not target:
            return None
        ws_url = target["webSocketDebuggerUrl"]
        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=5)
            ws.send(json.dumps({"id": 1, "method": "Network.getCookies", "params": {"urls": [BASE_URL]}}))
            result = json.loads(ws.recv())
            ws.close()
            cookies = result.get("result", {}).get("cookies", [])
            return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        except ImportError:
            return None
    except Exception:
        return None


_SSO_CACHE_FILE = "/tmp/cr_sso_token_cache.txt"
_SSO_CACHE_TTL = 1800  # 30 分钟


def get_sso_cookie():
    """
    通过 mtsso-moa-local-exchange 获取用户 SSO token 并转换为 Cookie 格式。
    仅在本地 MOA 支持换票（feature-probe ok=true）时生效，否则静默返回 None。
    适用于 CatClaw 沙箱环境；CatPaw/CatDesk 环境 probe 返回 false，自动跳过。
    Token 缓存 30 分钟，避免每次 CR 重复换票。
    """
    import subprocess
    import time

    # 读取缓存（有效期内直接复用）
    try:
        if os.path.exists(_SSO_CACHE_FILE):
            with open(_SSO_CACHE_FILE) as f:
                lines = f.read().strip().splitlines()
            if len(lines) == 2:
                cached_ts, cached_token = float(lines[0]), lines[1]
                if time.time() - cached_ts < _SSO_CACHE_TTL and cached_token:
                    return f"f32a546874_ssoid={cached_token}"
    except Exception:
        pass

    try:
        # Step 1: 探测本地 MOA 是否支持换票（超时 5s，不阻塞主流程）
        probe = subprocess.run(
            ["npx", "mtsso-moa-feature-probe", "--timeout", "5"],
            capture_output=True, text=True, timeout=8
        )
        if probe.returncode != 0:
            return None
        probe_data = json.loads(probe.stdout.strip())
        if not probe_data.get("ok"):
            return None  # CatPaw/CatDesk 等不支持的环境，静默跳过

        # Step 2: 获取用户身份 token，audience = dev.sankuai.com 的 client_id
        result = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", "f32a546874"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip())
        token = data.get("access_token", "")
        if token:
            # 写入缓存
            try:
                with open(_SSO_CACHE_FILE, "w") as f:
                    f.write(f"{time.time()}\n{token}")
            except Exception:
                pass
            return f"f32a546874_ssoid={token}"
    except Exception:
        pass
    return None


def get_cookies(args_cookie=None):
    if args_cookie:
        return args_cookie
    env_cookie = os.getenv("CODE_COOKIE")
    if env_cookie:
        return env_cookie
    # SSO 无感登录（CatClaw 沙箱优先，其他环境自动跳过）
    sso_cookie = get_sso_cookie()
    if sso_cookie:
        return sso_cookie
    cookie_file = os.getenv("CODE_COOKIE_FILE", "/tmp/code_cookies.txt")
    if os.path.exists(cookie_file):
        with open(cookie_file) as f:
            c = f.read().strip()
            if c:
                return c
    # 持久化 Cookie 文件兜底（优先于 CDP，适用于 CatPaw IDE / 无浏览器环境）
    persistent_cookie_file = os.path.expanduser("~/.openclaw/mcode_cookie.txt")
    if os.path.exists(persistent_cookie_file):
        with open(persistent_cookie_file) as f:
            c = f.read().strip()
            if c:
                return c
    cdp_cookie = get_cookies_from_cdp()
    if cdp_cookie:
        return cdp_cookie
    print("Error: No cookies. 请将 dev.sankuai.com 的 Cookie 粘贴到 ~/.openclaw/mcode_cookie.txt（一次配置，永久生效）。", file=sys.stderr)
    sys.exit(1)


def api_request(method, path, cookies, data=None, api_version="2.0"):
    url = f"{BASE_URL}/rest/api/{api_version}/{path.lstrip('/')}"
    body = json.dumps(data).encode("utf-8") if data else None
    headers = {"Cookie": cookies, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw, strict=False) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body_text, strict=False)
            return {"error": err.get("errors", [{"message": f"HTTP {e.code}"}])}
        except:
            return {"error": [{"message": f"HTTP {e.code}: {body_text[:200]}"}]}
    except Exception as e:
        return {"error": [{"message": str(e)}]}


def parse_pr_url(url):
    m = re.search(r'/code/repo-detail/([^/]+)/([^/]+)/pr/(\d+)', url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r'^([^/]+)/([^#]+)#(\d+)$', url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    return None, None, None


def resolve_pr(args, require_pr=True):
    if hasattr(args, "url") and args.url:
        p, r, pr = parse_pr_url(args.url)
        if p:
            return p, r, pr
    project = getattr(args, "project", None)
    repo = getattr(args, "repo", None)
    pr_id = getattr(args, "pr_id", None)
    if not project or not repo:
        print("Error: specify --project/--repo or --url", file=sys.stderr)
        sys.exit(1)
    if require_pr and not pr_id:
        print("Error: specify --pr-id or --url", file=sys.stderr)
        sys.exit(1)
    return project, repo, pr_id


def cmd_pr_info(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}?withIssues=true", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    result = {
        "id": data.get("id"), "title": data.get("title"),
        "description": data.get("description", ""), "state": data.get("state"),
        "author": data.get("author", {}).get("user", {}).get("name"),
        "authorDisplayName": data.get("author", {}).get("user", {}).get("displayName"),
        "fromRef": data.get("fromRef", {}).get("displayId"),
        "toRef": data.get("toRef", {}).get("displayId"),
        "createdDate": data.get("createdDate"), "updatedDate": data.get("updatedDate"),
        "reviewers": [{"name": r.get("user", {}).get("name"), "displayName": r.get("user", {}).get("displayName"), "status": r.get("status")} for r in data.get("reviewers", [])],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_pr_list(args, cookies):
    project, repo, _ = resolve_pr(args, require_pr=False)
    state = (args.state or "OPEN").upper()
    limit = args.limit or 10
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests?state={state}&limit={limit}&order=NEWEST", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    prs = [{"id": pr.get("id"), "title": pr.get("title"), "state": pr.get("state"), "author": pr.get("author", {}).get("user", {}).get("name"), "fromRef": pr.get("fromRef", {}).get("displayId"), "toRef": pr.get("toRef", {}).get("displayId")} for pr in data.get("values", [])]
    print(json.dumps(prs, ensure_ascii=False, indent=2))


def cmd_pr_changes(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/changes?start=0&limit=500", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    changes = [{"path": c.get("path", {}).get("toString", ""), "type": c.get("type", "")} for c in data.get("values", [])]
    result = {"fromHash": data.get("fromHash"), "toHash": data.get("toHash"), "totalFiles": len(changes), "changes": changes}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_pr_diff(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    encoded_path = urllib.parse.quote(args.file, safe="")
    context = args.context or 3
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/diff/{encoded_path}?contextLines={context}", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2)); return
    lines = []
    for diff in data.get("diffs", []):
        src = diff.get("source", {}).get("toString", "")
        dst = diff.get("destination", {}).get("toString", "")
        lines.append(f"--- a/{src}")
        lines.append(f"+++ b/{dst}")
        for hunk in diff.get("hunks", []):
            lines.append(f"@@ -{hunk.get('sourceLine',0)},{hunk.get('sourceSpan',0)} +{hunk.get('destinationLine',0)},{hunk.get('destinationSpan',0)} @@")
            for seg in hunk.get("segments", []):
                seg_type = seg.get("type", "")
                for line in seg.get("lines", []):
                    if seg_type == "ADDED":
                        lines.append(f"+{line.get('destination',''):>4} {line.get('line','')}")
                    elif seg_type == "REMOVED":
                        lines.append(f"-{line.get('source',''):>4} {line.get('line','')}")
                    else:
                        lines.append(f" {line.get('source',''):>4} {line.get('line','')}")
    print("\n".join(lines))


def cmd_pr_comments(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities?start=0&limit=100", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    comments = []
    for a in data.get("values", []):
        if a.get("action") == "COMMENTED":
            c = a.get("comment", {})
            anchor = c.get("anchor", {})
            comments.append({
                "id": c.get("id"), "author": c.get("author", {}).get("name"), "text": c.get("text"),
                "file": anchor.get("path") if anchor else None, "line": anchor.get("line") if anchor else None,
                "lineType": anchor.get("lineType") if anchor else None,
                "replies": [{"id": r.get("id"), "author": r.get("author", {}).get("name"), "text": r.get("text")} for r in c.get("comments", [])],
            })
    # assignments (line comments)
    assign_data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/assignments?path=&states=open,resolved", cookies, api_version="5.0")
    if not assign_data.get("error"):
        for a in assign_data.get("values", []):
            anchor = a.get("anchor", {})
            comments.append({
                "id": a.get("id"), "type": "assignment", "state": a.get("state"),
                "author": a.get("author", {}).get("name"), "text": a.get("text"),
                "file": anchor.get("path"), "line": anchor.get("line"), "lineType": anchor.get("lineType"),
            })
    print(json.dumps(comments, ensure_ascii=False, indent=2))


def get_commit_range(project, repo, pr_id, cookies):
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/changes?start=0&limit=1", cookies)
    if "error" in data:
        return None
    from_hash = data.get("fromHash")
    to_hash = data.get("toHash")
    if from_hash and to_hash:
        return {"id": str(pr_id), "sinceRevision": {"id": from_hash}, "untilRevision": {"id": to_hash}}
    return None


def cmd_comment_add(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    payload = {"text": args.text}
    if args.file and args.line:
        commit_range = get_commit_range(project, repo, pr_id, cookies)
        if not commit_range:
            print(json.dumps({"error": "Failed to get commitRange"}, ensure_ascii=False)); return
        payload["type"] = "assignment"
        payload["anchor"] = {
            "path": args.file, "line": int(args.line),
            "fileType": (args.file_type or "TO").upper(),
            "lineType": (args.line_type or "ADDED").upper(),
            "ignoreWhiteSpace": False, "commitRange": commit_range,
        }
        data = api_request("POST", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments", cookies, payload, api_version="5.0")
    else:
        data = api_request("POST", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments", cookies, payload)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    print(json.dumps({"ok": True, "id": data.get("id"), "text": data.get("text")}, ensure_ascii=False, indent=2))


def cmd_comment_delete(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    data = api_request("DELETE", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments/{args.comment_id}?version={args.version or 0}", cookies)
    if data and data.get("error"):
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(json.dumps({"ok": True, "deleted": args.comment_id}, ensure_ascii=False))


def cmd_pr_reviewers(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/reviewers", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    reviewers = data if isinstance(data, list) else data.get("values", [])
    result = [{"name": r.get("user", {}).get("name"), "displayName": r.get("user", {}).get("displayName"), "status": r.get("status")} for r in reviewers]
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_my_reviews(args, cookies):
    """列出待我审查的 PR（跨仓库），按创建时间降序排列"""
    role = (args.role or "reviewer").lower()
    state = (args.state or "OPEN").upper()
    limit = args.limit or 20
    start = args.start or 0
    order = "create_date_desc"

    params = (
        f"role={role}&start={start}&limit={limit}"
        f"&withAttributes=true&state={state}&order={order}"
        f"&mode=1&withIssues=true&withTopic=true&mustWithComment=false"
    )
    data = api_request("GET", f"pull-requests?{params}", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False))
        return

    prs = []
    for pr in data.get("values", []):
        from_ref = pr.get("fromRef", {})
        to_ref = pr.get("toRef", {})
        repo_obj = from_ref.get("repository", {})
        project_key = repo_obj.get("project", {}).get("key", "")
        repo_slug = repo_obj.get("slug", "")
        author_obj = pr.get("author", {}).get("user", {})
        attrs = pr.get("attributes", {})

        reviewers = []
        for r in pr.get("reviewers", []):
            u = r.get("user", {})
            reviewers.append({
                "name": u.get("name"),
                "displayName": u.get("displayName"),
                "status": r.get("status"),
                "approved": r.get("approved"),
            })

        issues = [{"name": i.get("name", ""), "url": i.get("url", "")} for i in pr.get("issues", [])]

        created_ts = pr.get("createdDate")
        updated_ts = pr.get("updatedDate")

        prs.append({
            "id": pr.get("id"),
            "title": (pr.get("title") or "").strip(),
            "state": pr.get("state"),
            "project": project_key,
            "repo": repo_slug,
            "url": f"{BASE_URL}/code/repo-detail/{project_key}/{repo_slug}/pr/{pr.get('id')}",
            "author": author_obj.get("name"),
            "authorDisplayName": author_obj.get("displayName"),
            "fromRef": from_ref.get("displayId"),
            "toRef": to_ref.get("displayId"),
            "fileNum": pr.get("file_num"),
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "commitNum": pr.get("commit_num"),
            "commentCount": attrs.get("commentCount"),
            "reviewExpired": attrs.get("reviewExpired"),
            "reviewers": reviewers,
            "issues": issues,
            "createdDate": created_ts,
            "updatedDate": updated_ts,
        })

    result = {
        "total": data.get("size"),
        "start": data.get("start"),
        "limit": data.get("limit"),
        "isLastPage": data.get("isLastPage"),
        "nextPageStart": data.get("nextPageStart"),
        "values": prs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_user_info(args, cookies):
    data = api_request("GET", "ssoUser?withCertificateDisplayType=true", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    print(json.dumps({"name": data.get("name"), "displayName": data.get("displayName"), "email": data.get("emailAddress"), "id": data.get("id")}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="美团 Code 平台 CLI")
    parser.add_argument("--cookie", help="手动指定 cookie")
    sub = parser.add_subparsers(dest="command")

    def add_pr_args(p):
        p.add_argument("--url", help="PR URL")
        p.add_argument("--project", "-p", help="项目名")
        p.add_argument("--repo", "-r", help="仓库名")
        p.add_argument("--pr-id", type=int, help="PR 编号")

    p = sub.add_parser("pr-info", help="查看 PR 详情"); add_pr_args(p)
    p = sub.add_parser("pr-list", help="列出 PR"); add_pr_args(p); p.add_argument("--state", default="OPEN"); p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("pr-changes", help="文件变更列表"); add_pr_args(p)
    p = sub.add_parser("pr-diff", help="文件 diff"); add_pr_args(p); p.add_argument("--file", "-f", required=True); p.add_argument("--context", type=int, default=3); p.add_argument("--json", action="store_true")
    p = sub.add_parser("pr-comments", help="查看评论"); add_pr_args(p)
    p = sub.add_parser("pr-reviewers", help="查看 reviewer"); add_pr_args(p)
    p = sub.add_parser("comment-add", help="添加评论"); add_pr_args(p); p.add_argument("--text", "-t", required=True); p.add_argument("--file", "-f"); p.add_argument("--line", "-l", type=int); p.add_argument("--line-type", default="ADDED"); p.add_argument("--file-type", default="TO")
    p = sub.add_parser("comment-delete", help="删除评论"); add_pr_args(p); p.add_argument("--comment-id", type=int, required=True); p.add_argument("--version", type=int, default=0)
    p = sub.add_parser("my-reviews", help="列出待我审查的 PR（跨仓库）"); p.add_argument("--role", default="reviewer", help="reviewer|author"); p.add_argument("--state", default="OPEN", help="OPEN|MERGED|DECLINED|ALL"); p.add_argument("--limit", type=int, default=20); p.add_argument("--start", type=int, default=0)
    p = sub.add_parser("user-info", help="当前用户信息")

    args = parser.parse_args()
    if not args.command:
        parser.print_help(); return
    cookies = get_cookies(args.cookie)
    cmds = {"pr-info": cmd_pr_info, "pr-list": cmd_pr_list, "pr-changes": cmd_pr_changes, "pr-diff": cmd_pr_diff, "pr-comments": cmd_pr_comments, "pr-reviewers": cmd_pr_reviewers, "comment-add": cmd_comment_add, "comment-delete": cmd_comment_delete, "my-reviews": cmd_my_reviews, "user-info": cmd_user_info}
    handler = cmds.get(args.command)
    if handler:
        handler(args, cookies)

if __name__ == "__main__":
    main()
