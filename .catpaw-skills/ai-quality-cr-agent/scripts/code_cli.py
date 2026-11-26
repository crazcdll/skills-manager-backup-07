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
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import urllib.error

# 行号逻辑统一封装模块（同目录导入；导入失败时降级为旧格式化逻辑，
# 不影响 code_cli 主流程 —— 保证零降级原则）
try:
    from line_anchor import format_diff_line
except Exception:  # noqa: BLE001
    def format_diff_line(seg_type, line_obj):
        """降级回退格式化（含 CONTEXT 行号旧行为）"""
        if seg_type == "ADDED":
            return f"+{line_obj.get('destination',''):>4} {line_obj.get('line','')}"
        if seg_type == "REMOVED":
            return f"-{line_obj.get('source',''):>4} {line_obj.get('line','')}"
        return f" {line_obj.get('source',''):>4} {line_obj.get('line','')}"

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
    # 平台权威规模字段透出（file_num/additions/deletions/commit_num），
    # 供 get_pr_diff 采集写入 mode_info（DB 平台权威口径三字段数据源）
    for k in ("file_num", "additions", "deletions", "commit_num"):
        if data.get(k) is not None:
            result[k] = data.get(k)
    # ONES 工作项关联原样透出（PR 关联 issues 列表；解析归 get_pr_diff.extract_ones_info，
    # 此处不做任何归一，归一单一职责在后端 CrResultParser）
    if isinstance(data.get("issues"), list) and data["issues"]:
        result["issues"] = data["issues"]
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
    # 真翻页：①按 path 去重（游标漂移可能返回重复条目，且重复 path 会
    #        导致路径解析子串匹配误判歧义）②安全阀触发时显式标记 truncated
    # ③空页但 isLastPage=false → 标记 incomplete ④逐页核对 fromHash/toHash，
    #        后续页端点与首页不一致 → 翻页中途 PR 已更新，混合列表不可信，标记 incomplete
    changes = []
    from_hash = to_hash = None
    start = 0
    truncated = False
    incomplete = False
    hash_drift = False
    seen_paths = set()
    dup_count = 0
    for _ in range(20):  # 安全阀：最多 20 页（10000 文件）
        data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/changes?start={start}&limit=500", cookies)
        if "error" in data:
            print(json.dumps(data, ensure_ascii=False)); return
        page_from = data.get("fromHash")
        page_to = data.get("toHash")
        if from_hash is None:
            from_hash = page_from
            to_hash = page_to
        elif ((page_from is not None and str(page_from) != str(from_hash))
                or (page_to is not None and str(page_to) != str(to_hash))):
            # 翻页中途端点漂移：前后页来自不同 PR 状态，列表不可信
            incomplete = True
            hash_drift = True
            break
        values = data.get("values", []) or []
        for c in values:
            p = c.get("path")
            path = p.get("toString", "") if isinstance(p, dict) else ""
            if path in seen_paths:
                dup_count += 1
                continue
            seen_paths.add(path)
            changes.append({"path": path, "type": c.get("type", "")})
        if data.get("isLastPage", True) or not values:
            # isLastPage 缺省视为 True（兼容旧响应）；但「有数据且
            # isLastPage 字段缺失」说明响应形状异常，列表完整性未证明，
            # 显式标记 incomplete，不冒充已翻完
            if values and data.get("isLastPage") is None:
                incomplete = True
            # 空页但服务端声明还有下一页（isLastPage=false）→
            # 翻页中途空响应，完整性未证明，同样标记 incomplete
            if not values and data.get("isLastPage") is not True:
                incomplete = True
            break
        nxt = data.get("nextPageStart")
        if not isinstance(nxt, int) or nxt <= start:
            # 游标异常（缺 nextPageStart 或不前进）：完整性未证明
            incomplete = True
            break
        start = nxt
    else:
        truncated = True  # for-else：20 页耗尽仍未 isLastPage
    result = {"fromHash": from_hash, "toHash": to_hash, "totalFiles": len(changes), "changes": changes}
    if truncated:
        result["truncated"] = True
        result["truncatedNote"] = "翻页安全阀（20页/10000文件）触发，文件列表可能不完整"
    if incomplete:
        result["incomplete"] = True
        result["incompleteNote"] = ("分页端点与首页不一致（翻页中途 PR 更新），列表不可信"
                                    if hash_drift else
                                    "分页完整性未证明（isLastPage 缺失/空页非末页/游标异常），列表可能不完整")
    if dup_count:
        result["deduplicated"] = dup_count
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
                        lines.append(format_diff_line("ADDED", line))
                    elif seg_type == "REMOVED":
                        lines.append(format_diff_line("REMOVED", line))
                    else:
                        lines.append(format_diff_line("CONTEXT", line))
    print("\n".join(lines))


def cmd_pr_commits(args, cookies):
    """PR 的 commit 列表（index 0 为最新 commit）"""
    project, repo, pr_id = resolve_pr(args)
    limit = args.limit or 50
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/commits?start=0&limit={limit}", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    commits = []
    for c in data.get("values", []):
        message = (c.get("message") or "").strip().split("\n")[0]
        author = c.get("author", {}) or {}
        commits.append({
            "id": c.get("id"),
            "displayId": c.get("displayId"),
            "message": message,
            "author": author.get("name") or author.get("displayName") or author.get("emailAddress"),
            "authorTimestamp": c.get("authorTimestamp"),
            # 保留原始 parents 结构（merge 检测依赖 len(parents)>=2）。
            # 不在此处过滤缺失 id 的父节点：双父提交若第二父缺 id，过滤后会被伪装成
            # 单父提交绕过 merge 检测；数据不完整交给 walk_incremental_window 兜底回退全量。
            "parents": list(c.get("parents") or []),
        })
    result = {"total": len(commits), "commits": commits}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_compare_changes(args, cookies):
    """两个 commit 之间的文件变更列表（用于增量 CR）

    与 pr-changes 同口径真翻页（单页 limit=500 会静默丢失部分增量范围）；
    去重 + truncated/incomplete 显式标记，消费方（get_pr_diff）按完整性降级处理。
    """
    project, repo, _ = resolve_pr(args, require_pr=False)
    from_hash = args.from_hash
    to_hash = args.to_hash
    changes = []
    start = 0
    truncated = False
    incomplete = False
    seen_paths = set()
    dup_count = 0
    for _ in range(20):  # 安全阀：最多 20 页（10000 文件）
        data = api_request("GET", f"projects/{project}/repos/{repo}/compare/changes?from={from_hash}&to={to_hash}&start={start}&limit=500", cookies)
        if "error" in data:
            print(json.dumps(data, ensure_ascii=False)); return
        values = data.get("values", []) or []
        for c in values:
            p = c.get("path")
            path = p.get("toString", "") if isinstance(p, dict) else ""
            if path in seen_paths:
                dup_count += 1
                continue
            seen_paths.add(path)
            changes.append({"path": path, "type": c.get("type", "")})
        if data.get("isLastPage", True) or not values:
            if values and data.get("isLastPage") is None:
                incomplete = True
            if not values and data.get("isLastPage") is not True:
                incomplete = True
            break
        nxt = data.get("nextPageStart")
        if not isinstance(nxt, int) or nxt <= start:
            incomplete = True
            break
        start = nxt
    else:
        truncated = True
    result = {"fromHash": from_hash, "toHash": to_hash, "totalFiles": len(changes), "changes": changes}
    if truncated:
        result["truncated"] = True
        result["truncatedNote"] = "翻页安全阀（20页/10000文件）触发，增量文件列表可能不完整"
    if incomplete:
        result["incomplete"] = True
        result["incompleteNote"] = "分页完整性未证明（isLastPage 缺失/空页非末页/游标异常），增量文件列表可能不完整"
    if dup_count:
        result["deduplicated"] = dup_count
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_compare_diff(args, cookies):
    """两个 commit 之间某文件的行级 diff（用于增量 CR）"""
    project, repo, _ = resolve_pr(args, require_pr=False)
    encoded_path = urllib.parse.quote(args.file, safe="")
    from_hash = args.from_hash
    to_hash = args.to_hash
    context = args.context or 3
    data = api_request("GET", f"projects/{project}/repos/{repo}/compare/diff/{encoded_path}?from={from_hash}&to={to_hash}&contextLines={context}", cookies)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    if getattr(args, "json", False):
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
                        lines.append(format_diff_line("ADDED", line))
                    elif seg_type == "REMOVED":
                        lines.append(format_diff_line("REMOVED", line))
                    else:
                        lines.append(format_diff_line("CONTEXT", line))
    print("\n".join(lines))


def _valid_history_anchor(anchor):
    """回执锚点仅接受可消费的路径、行号和行类型。"""
    return anchor is None or (
        isinstance(anchor, dict)
        and isinstance(anchor.get("path"), str)
        and (anchor.get("line") is None or type(anchor["line"]) is int)
        and (anchor.get("lineType") is None or isinstance(anchor["lineType"], str)))


def _history_content_digest(value):
    """与 comment_dedup.content_digest 对齐；本地实现以避免循环导入。"""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _history_reply_view(reply):
    """递归构造视图；原始字段始终保存在 source 快照。"""
    result = {"id": reply.get("id"), "author": reply["author"]["name"], "text": reply["text"]}
    if reply.get("comments"):
        result["replies"] = [_history_reply_view(child) for child in reply["comments"]]
    return result


def _merge_history_replies(existing, incoming, notes, channel):
    """有 id 以 str(id) 合并；无 id 无法证明重复，全部保留。"""
    seen = {str(r["id"]): r for r in existing if r["id"] is not None}
    for reply in incoming:
        if reply["id"] is None:
            notes.append("reply_id_missing_not_deduplicated")
            existing.append(reply)
            continue
        key = str(reply["id"])
        previous = seen.get(key)
        if previous is not None:
            if any(previous.get(k) != reply.get(k) for k in ("text", "author")):
                notes.append(channel + "_conflicting_duplicate_id")
            if reply.get("replies"):
                _merge_history_replies(previous.setdefault("replies", []), reply["replies"], notes, channel)
            continue
        # 同一原始回复内部的重复 id 也应检测，但无 id 的记录不能去掉。
        children = reply.pop("replies", [])
        if children:
            reply["replies"] = []
            _merge_history_replies(reply["replies"], children, notes, channel)
        seen[key] = reply
        existing.append(reply)


def _valid_history_comment(comment, replies=False):
    """畸形记录仅在回执模式标为不完整，避免解析异常伪装空历史。"""
    if (not isinstance(comment, dict)
            or (comment.get("id") is not None and type(comment["id"]) not in (int, str))
            or not isinstance(comment.get("text"), str)
            or not isinstance(comment.get("author"), dict)
            or not isinstance(comment["author"].get("name"), str)
            or not _valid_history_anchor(comment.get("anchor"))
            or (comment.get("comments") is not None and not isinstance(comment["comments"], list))):
        return False
    if replies:
        return all(_valid_history_comment(child, replies=True)
                   for child in (comment.get("comments") or []))
    return True


def _comment_history_request(path, cookies, api_version="2.0", source_pages=None):
    """仅用于 opt-in 回执；先保存原始响应，异常不冒充成功的空历史。"""
    try:
        data = api_request("GET", path, cookies, api_version=api_version)
    except Exception as exc:
        if source_pages is not None:
            source_pages.append({"requestError": str(exc)})
        return {"error": [{"message": str(exc)}]}
    if source_pages is not None:
        source_pages.append(data)
    if not isinstance(data, dict):
        return {"error": [{"message": "response is not an object"}]}
    return data


def cmd_pr_comments(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    with_metadata = getattr(args, "with_metadata", False)
    # opt-in 回执须有明确终页且无未完成信号；不证明官方端点覆盖全 PR 历史。
    # 默认 list 路径不受影响。
    notes = []
    pages = {"activities": 0, "assignments": 0}
    source = {"activities": [], "assignments": []} if with_metadata else None
    next_cursor = {"activities": None, "assignments": None}
    activities_complete = False
    activities_nonterminal = False
    assignments_complete = False
    # activities 真翻页：isLastPage/nextPageStart 循环拉全，
    # 历史 PR 评论 >100 条不再截断（发布侧去重依赖完整评论列表）
    all_activities = []
    start = 0
    activities_truncated = False
    for _ in range(20):  # 安全阀：最多 20 页（2000 条 activity）
        path = f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities?start={start}&limit=100"
        pages["activities"] += 1  # 已尝试请求的页数，包含失败页
        data = (_comment_history_request(path, cookies, source_pages=source["activities"]) if with_metadata
                else api_request("GET", path, cookies))
        if "error" in data:
            if with_metadata:
                notes.append("activities_api_error")
                next_cursor["activities"] = start
                break
            print(json.dumps(data, ensure_ascii=False)); return
        values = data.get("values", []) or []
        if with_metadata:
            if data.get("truncated") is True:
                notes.append("activities_response_truncated")
            if data.get("incomplete") is True:
                notes.append("activities_response_incomplete")
            activities_nonterminal = data.get("isLastPage") is False
            if not isinstance(data.get("values"), list):
                notes.append("activities_values_invalid")
                next_cursor["activities"] = start
                break
            values = []
            for activity in data["values"]:
                if (not isinstance(activity, dict)
                        or (activity.get("action") == "COMMENTED"
                            and not _valid_history_comment(activity.get("comment"), replies=True))):
                    notes.append("activities_record_invalid")
                    continue
                values.append(activity)
        all_activities.extend(values)
        if with_metadata:
            if data.get("isLastPage") is True:
                # 合法末页游标仅作提示；异常游标或 nextPage 仍保守拒绝。
                nxt = data.get("nextPageStart")
                if type(nxt) is int and nxt > start:
                    next_cursor["activities"] = nxt
                if ((nxt is not None and not (type(nxt) is int and nxt > start))
                        or data.get("nextPage") is not None):
                    notes.append("activities_next_page_present")
                else:
                    activities_complete = True
                break
            nxt = data.get("nextPageStart")
            # bool 是 int 的子类，必须显式排除；不输出不可用的 cursor。
            if type(nxt) is int and nxt > start:
                next_cursor["activities"] = nxt
            if type(data.get("isLastPage")) is not bool:
                notes.append("activities_pagination_missing_or_invalid")
                break
            if not data["values"]:
                notes.append("activities_empty_nonterminal_page")
                break
            if type(nxt) is not int or nxt <= start:
                notes.append("activities_cursor_missing_or_invalid")
                break
            start = nxt
            next_cursor["activities"] = None
            continue
        if data.get("isLastPage", True) or not values:
            break
        nxt = data.get("nextPageStart")
        if not isinstance(nxt, int) or nxt <= start:
            break
        start = nxt
    else:
        activities_truncated = True  # for-else：20 页耗尽仍未 isLastPage
        if with_metadata:
            notes.append("activities_page_limit")
            next_cursor["activities"] = start
    if activities_truncated:
        # stdout 必须保持纯 JSON 数组（消费方 schema），截断警告走 stderr，不静默
        print("⚠️  activities 翻页安全阀（20页/2000条）触发，评论列表可能不完整", file=sys.stderr)
    comments = []
    by_id = {}
    for a in all_activities:
        if a.get("action") != "COMMENTED":
            continue
        c = a.get("comment") or {}
        if not isinstance(c, dict):
            continue
        anchor = c.get("anchor") if isinstance(c.get("anchor"), dict) else None
        entry = {
            "id": c.get("id"), "author": (c.get("author") or {}).get("name"), "text": c.get("text"),
            "file": anchor.get("path") if anchor else None, "line": anchor.get("line") if anchor else None,
            "lineType": anchor.get("lineType") if anchor else None,
            "replies": [{"id": r.get("id"), "author": (r.get("author") or {}).get("name"), "text": r.get("text")} for r in (c.get("comments") or []) if isinstance(r, dict)],
        }
        if with_metadata:
            unique_replies = []
            _merge_history_replies(unique_replies, [_history_reply_view(r) for r in (c.get("comments") or [])],
                                   notes, "activities")
            entry["replies"] = unique_replies
        if with_metadata and c.get("id") is not None and str(c["id"]) in by_id:
            existing = by_id[str(c["id"])]
            if any(existing.get(key) != entry.get(key) for key in ("text", "author")):
                notes.append("activities_conflicting_duplicate_id")
            # 重复活动不新增顶层记录，也不让 null anchor 丢掉已知锚点。
            for key in ("file", "line", "lineType"):
                if existing.get(key) is None and entry.get(key) is not None:
                    existing[key] = entry[key]
            _merge_history_replies(existing["replies"], entry["replies"], notes, "activities")
            continue  # 仅 opt-in 逐评论 id 去重；无 id 的记录各自保留
        comments.append(entry)
        if c.get("id") is not None:
            by_id[str(c["id"]) if with_metadata else c.get("id")] = entry
    # assignments (line comments)
    # 实测（2026-11-07 PR983）：assignments 的 start/limit 参数被服务端忽略，
    # 单次调用即返回全量分组，不做翻页
    # 两通道同 id 合并：activities 与 assignments 可能包含同一条行内评论。
    # 合并以 assignments 的当前 anchor 为准（反映 resolve/move 后的最新锚点）；
    # assignments anchor 为 null 时保留 activities 原值，不丢锚点。
    # 禁止先按 id 去重 activities 记录——null anchor 的活动记录会顶掉分组锚点。
    path = f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/assignments?path=&states=open,resolved"
    pages["assignments"] += 1
    assign_data = (_comment_history_request(path, cookies, api_version="5.0", source_pages=source["assignments"]) if with_metadata
                   else api_request("GET", path, cookies, api_version="5.0"))
    if with_metadata:
        if assign_data.get("truncated") is True:
            notes.append("assignments_response_truncated")
        if assign_data.get("incomplete") is True:
            notes.append("assignments_response_incomplete")
        if "error" in assign_data:
            notes.append("assignments_api_error")
        elif assign_data.get("isLastPage") is True:
            nxt = assign_data.get("nextPageStart")
            if type(nxt) is int and nxt > 0:
                next_cursor["assignments"] = nxt
            if ((nxt is not None and not (type(nxt) is int and nxt > 0))
                    or assign_data.get("nextPage") is not None):
                notes.append("assignments_next_page_present")
            else:
                assignments_complete = True
        else:
            notes.append("assignments_pagination_missing_or_nonterminal")
            nxt = assign_data.get("nextPageStart")
            if type(nxt) is int and nxt > 0:
                next_cursor["assignments"] = nxt
        if "error" not in assign_data and assign_data.get("isLastPage") is not True and (
                assign_data.get("nextPageStart") is not None
                or assign_data.get("nextPage") is not None):
            notes.append("assignments_next_page_present")
            nxt = assign_data.get("nextPageStart")
            if type(nxt) is int and nxt > 0:
                next_cursor["assignments"] = nxt
        if "error" in assign_data:
            assign_data = {"error": assign_data["error"] or "API error"}
    if assign_data.get("error"):
        print("⚠️  assignments 读取失败，行内评论锚点以 activities 通道兜底: "
              + json.dumps(assign_data["error"], ensure_ascii=False)[:200], file=sys.stderr)
    else:
        values = assign_data.get("values")
        if not isinstance(values, list):
            if with_metadata:
                notes.append("assignments_values_invalid")
            print("⚠️  assignments.values 非列表结构，忽略 assignments 通道", file=sys.stderr)
            values = []
        for item in values:
            if not isinstance(item, dict):
                if with_metadata:
                    notes.append("assignments_group_invalid")
                continue
            cws = item.get("comments")
            if not isinstance(cws, list):
                if with_metadata:
                    notes.append("assignments_comments_invalid")
                continue  # 分组缺 comments 字段：跳过该组，不冒充完整
            for cw in cws:
                if not isinstance(cw, dict):
                    if with_metadata:
                        notes.append("assignments_record_invalid")
                    continue
                comment = cw.get("comment") or {}
                if with_metadata and not _valid_history_comment(cw.get("comment"), replies=True):
                    notes.append("assignments_record_invalid")
                    continue
                # 回执模式：commentAnchor 结构或内部字段畸形时，
                # 位置信息不可信，不能冒充完整历史（仅记 notes，不改默认行为）
                if with_metadata and not _valid_history_anchor(cw.get("commentAnchor")):
                    notes.append("assignments_record_invalid")
                    continue
                if not isinstance(comment, dict):
                    continue
                anchor = cw.get("commentAnchor") if isinstance(cw.get("commentAnchor"), dict) else None
                if (with_metadata and not (anchor and anchor.get("path"))
                        and item.get("path") is not None and not isinstance(item["path"], str)):
                    notes.append("assignments_record_invalid")
                    continue
                assignment = comment.get("assignment") if isinstance(comment.get("assignment"), dict) else {}
                cid = comment.get("id")
                assignment_replies = ([_history_reply_view(r) for r in (comment.get("comments") or [])]
                                      if with_metadata else None)
                entry = by_id.get(str(cid) if with_metadata and cid is not None else cid)
                if entry is not None:
                    if with_metadata and (entry.get("text") != comment.get("text")
                                          or entry.get("author") != comment["author"].get("name")):
                        notes.append("assignments_conflicting_duplicate_id")
                    if with_metadata:
                        _merge_history_replies(entry.setdefault("replies", []), assignment_replies,
                                               notes, "assignments")
                    # 同 id：assignments 当前 anchor 优先（null 保留原值，不丢锚点）
                    if anchor is not None:
                        if anchor.get("path"):
                            entry["file"] = anchor.get("path")
                        if anchor.get("line") is not None:
                            entry["line"] = anchor.get("line")
                        if anchor.get("lineType"):
                            entry["lineType"] = anchor.get("lineType")
                    entry["type"] = "assignment"
                    entry["state"] = assignment.get("state")
                else:
                    entry = {
                        "id": cid, "type": "assignment",
                        "state": assignment.get("state"),
                        "author": (comment.get("author") or {}).get("name"),
                        "text": comment.get("text"),
                        "file": (anchor.get("path") if anchor else None) or item.get("path"),
                        "line": anchor.get("line") if anchor else None,
                        "lineType": anchor.get("lineType") if anchor else None,
                    }
                    if with_metadata:
                        entry["replies"] = []
                        _merge_history_replies(entry["replies"], assignment_replies, notes, "assignments")
                    comments.append(entry)
                    if with_metadata and cid is not None:
                        by_id[str(cid)] = entry
    if with_metadata:
        activities_complete = activities_complete and not any(n.startswith("activities_") for n in notes)
        assignments_complete = assignments_complete and not any(n.startswith("assignments_") for n in notes)
        complete = activities_complete and assignments_complete
        result = {
            "comments": comments, "complete": complete, "incomplete": not complete,
            "budgetExhausted": activities_truncated, "commentsSha256": _history_content_digest(comments),
            "source": source, "sourceSha256": _history_content_digest(source),
            "org": project, "repo": repo, "prId": pr_id,
            "activitiesComplete": activities_complete, "assignmentsComplete": assignments_complete,
            "truncated": (activities_truncated or activities_nonterminal
                          or "activities_response_truncated" in notes
                          or "assignments_response_truncated" in notes
                          or "activities_next_page_present" in notes
                          or assign_data.get("isLastPage") is False
                          or "assignments_next_page_present" in notes),
            "note": "; ".join(dict.fromkeys(notes)) or "complete",
            "pages": pages, "next_cursor": next_cursor,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(comments, ensure_ascii=False, indent=2))


def get_commit_range(project, repo, pr_id, cookies, expected_from=None, expected_to=None):
    """读取当前 PR diff 基准（pr-changes 首页 fromHash/toHash）。

    expected_from/expected_to 传入时执行“发送前比对”（内部做大小写归一）：
      - 与当前值完全一致 → 返回当前 range（compare preflight 通过，仅代表
        发送前读取到的平台状态与调用方冻结值一致，不构成原子保证）
      - 不一致 → 返回 {"mismatch": {...}}（调用方必须显式失败，禁止盲发）
      - 读取失败 → 返回 None（调用方按“无法比对”失败，禁止盲发）
    """
    data = api_request("GET", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/changes?start=0&limit=1", cookies)
    if "error" in data:
        return None
    from_hash = data.get("fromHash")
    to_hash = data.get("toHash")
    if from_hash and to_hash:
        if expected_from or expected_to:
            ef = str(expected_from or "").strip().lower()
            et = str(expected_to or "").strip().lower()
            if (ef and str(from_hash).strip().lower() != ef) or (et and str(to_hash).strip().lower() != et):
                return {"mismatch": {
                    "expected": {"fromHash": expected_from, "toHash": expected_to},
                    "actual": {"fromHash": from_hash, "toHash": to_hash},
                }}
        return {"id": str(pr_id), "sinceRevision": {"id": from_hash}, "untilRevision": {"id": to_hash}}
    return None


def _normalize_hash(v):
    """hash 归一：字符串化并小写（平台返回 40 位十六进制，大小写可能不一致）。"""
    return str(v or "").strip().lower()


def _expected_range_from_args(args):
    """从 CLI 参数提取冻结的 expected range。未传 → (None, None)。"""
    ef = getattr(args, "expected_from", None)
    et = getattr(args, "expected_to", None)
    return _normalize_hash(ef) or None, _normalize_hash(et) or None


def _verify_comment_anchor(project, repo, pr_id, cookies, comment_id, file_path, line, line_type):
    """发送成功后按 commentId 回读 activities + assignments 核验锚点。

    返回 dict：
      verified: True/False（锚点 path/line/lineType 与请求一致才算 True）
      anchor: 命中的锚点字段（未命中/读取失败为 None）
      source: "activities" | "assignments" | "assignments-group" | None
      readError: 读取不可用原因（读取失败/分页截断/异常时非空）
      partial: True 表示核验数据不完整（分页上限/异常），不可声称已验证
    注意：本核验是“发送后回读比对”，不构成对发送原子性的保证。
    """
    result = {"verified": False, "anchor": None, "source": None, "readError": "", "partial": False}
    if not comment_id:
        result["readError"] = "commentId 为空，无法回读核验"
        return result
    want = {
        "path": file_path,
        "line": int(line) if line is not None else None,
        "lineType": (line_type or "ADDED").upper(),
    }
    read_errors = []

    # 通道 1：activities 翻页回读（COMMENTED activity 的 comment.anchor）
    # activities 命中但锚点不符（mismatch/null-anchor/reply）时
    # 不再提前返回——assignments 反映 resolve/move 后的最新锚点，是当前锚点
    # 的权威通道，必须先尝试；两通道都不通过才下结论
    ch1_pending = None  # 通道 1 的候选结论（锚点不符描述）
    try:
        found, act_err, act_partial = _scan_activities_for_comment(
            project, repo, pr_id, cookies, comment_id, want)
        if found:
            if found[1] == "activities":
                result.update({"verified": True, "anchor": found[0], "source": "activities"})
                return result
            # 找到评论但锚点不符（mismatch/null-anchor/reply 命中）→ 记录候选，
            # 继续尝试 assignments
            if isinstance(found[0], dict):
                result["anchor"] = found[0]
            result["source"] = found[1]
            ch1_pending = f"activities 命中但锚点不符（{found[1]}）"
        if act_err:
            read_errors.append(f"activities: {act_err}")
        if act_partial:
            result["partial"] = True
            read_errors.append("activities: 翻页安全阀（20页）触发，数据可能截断")
    except Exception as e:  # noqa: BLE001
        read_errors.append(f"activities: {e}")

    # 通道 2：assignments 分组回读（commentAnchor；实测 start/limit 被服务端忽略）
    try:
        assign_data = api_request(
            "GET",
            f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/assignments?path=&states=open,resolved",
            cookies, api_version="5.0")
        if assign_data.get("error"):
            read_errors.append("assignments: " + json.dumps(assign_data["error"], ensure_ascii=False)[:200])
        else:
            found, asg_err = _scan_assignments_for_comment(assign_data, comment_id, want)
            if found:
                if found[1] == "assignments":
                    result.update({"verified": True, "anchor": found[0], "source": "assignments"})
                else:
                    if isinstance(found[0], dict):
                        result["anchor"] = found[0]
                    result["source"] = found[1]
                    ch1_pending = ch1_pending or f"assignments 命中但锚点不符（{found[1]}）"
                if found[1] == "assignments":
                    return result
            if asg_err:
                read_errors.append(f"assignments: {asg_err}")
    except Exception as e:  # noqa: BLE001
        read_errors.append(f"assignments: {e}")

    if ch1_pending:
        result["readError"] = ch1_pending + ("; " + "; ".join(read_errors) if read_errors else "")
    else:
        result["readError"] = "; ".join(read_errors) or "未在 activities/assignments 中找到该评论"
    return result


def _scan_activities_for_comment(project, repo, pr_id, cookies, comment_id, want=None):
    """在 activities 翻页结果中查找 commentId。

    want 为 dict 时比对锚点（path/line/lineType）；want 为 None 时仅查找
    （全局评论存在性核验用）。

    返回 (found, err, partial)：
      found: (payload, source) 或 None
        - 比对通过/仅查找命中: (anchor_or_comment, "activities")
        - 锚点不符: (anchor, "activities-mismatch")
        - anchor 非 dict: (None, "activities-null-anchor")
        - id 命中 replies（非评论本体，不构成锚点核验通过）: (reply, "activities-reply")
      err:   读取失败描述（API error），成功读取时为 ""
      partial: True 表示安全阀（20 页）触发，数据可能截断
    """
    start = 0
    for _ in range(20):  # 安全阀：最多 20 页（2000 条 activity）
        data = api_request(
            "GET",
            f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities?start={start}&limit=100",
            cookies)
        if "error" in data:
            return None, json.dumps(data["error"], ensure_ascii=False)[:200], False
        values = data.get("values", []) or []
        for a in values:
            c = a.get("comment") or {}
            if not isinstance(c, dict):
                continue
            if str(c.get("id", "")) != str(comment_id):
                # replies 也可能承载该 id（回读防御，正常发送不产生 replies）
                for r in c.get("comments", []) or []:
                    if isinstance(r, dict) and str(r.get("id", "")) == str(comment_id):
                        return (r, "activities-reply"), "", False
                continue
            if want is None:
                return (c, "activities"), "", False
            anchor = c.get("anchor")
            if not isinstance(anchor, dict):
                return (None, "activities-null-anchor"), "", False
            if (anchor.get("path") == want["path"]
                    and anchor.get("line") == want["line"]
                    and (anchor.get("lineType") or "").upper() == want["lineType"]):
                return (anchor, "activities"), "", False
            return (anchor, "activities-mismatch"), "", False
        if data.get("isLastPage", True) or not values:
            return None, "", False
        nxt = data.get("nextPageStart")
        if not isinstance(nxt, int) or nxt <= start:
            return None, "", False
        start = nxt
    # 安全阀触发：遍历 20 页仍未找到，数据可能被截断
    return None, "", True


def _scan_assignments_for_comment(assign_data, comment_id, want):
    """在 assignments 分组响应中查找 commentId 并比对锚点。

    返回 (found, err)：found=(anchor_dict, source) 或 None；err 为结构异常描述。
    防御：values 非列表 / 分组缺 comments / commentAnchor 为 null 等。
    """
    values = assign_data.get("values")
    if not isinstance(values, list):
        return None, "assignments.values 非列表结构"
    for item in values:
        if not isinstance(item, dict):
            continue
        comments = item.get("comments")
        if not isinstance(comments, list):
            continue  # 分组缺 comments 字段：跳过该组，不冒充完整
        for cw in comments:
            if not isinstance(cw, dict):
                continue
            comment = cw.get("comment") or {}
            if str(comment.get("id", "")) != str(comment_id):
                continue
            anchor = cw.get("commentAnchor")
            if not isinstance(anchor, dict):
                anchor = None
            path = (anchor or {}).get("path") or item.get("path")
            line = (anchor or {}).get("line")
            line_type = (anchor or {}).get("lineType")
            if (path == want["path"] and line == want["line"]
                    and (line_type or "").upper() == want["lineType"]):
                return (anchor or {"path": path, "line": line, "lineType": line_type}, "assignments"), ""
            return (anchor, "assignments-mismatch"), ""
    return None, ""


def _is_send_uncertain(err_list):
    """判断 POST 评论的错误是否为“结果未知”（超时/网络中断）。

    这类错误下评论可能已写入。返回 True → 走回读匹配而非盲目重发。
    平台业务错误（4xx/5xx 有响应体）返回 False → 按普通失败处理。
    """
    if not isinstance(err_list, list):
        return False
    text = " ".join(str(e.get("message", "")) for e in err_list if isinstance(e, dict))
    return any(k in text for k in ("timed out", "timeout", "Timeout", "URLError", "Connection", "connection", "reset", "EOF"))


def _probe_existing_comment(project, repo, pr_id, cookies, file_path, line, line_type, text):
    """发送结果未知时回读查找“同锚点同正文”的既有评论。

    返回 {"hit": True, "id": ...} 或 {"hit": False}。
    回读本身失败时返回 {"hit": False, "readError": ...}（不冒充未命中）。
    注意：这是 best-effort 回读匹配，不构成原子保证；未命中不代表评论未写入。
    """
    result = {"hit": False}
    norm_text = (text or "").replace("\r\n", "\n").strip()
    read_errors = []
    # 通道 1：activities
    try:
        start = 0
        for _ in range(20):  # 安全阀
            data = api_request(
                "GET",
                f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities?start={start}&limit=100",
                cookies)
            if "error" in data:
                read_errors.append("activities: " + json.dumps(data["error"], ensure_ascii=False)[:200])
                break
            values = data.get("values", []) or []
            for a in values:
                c = a.get("comment") or {}
                anchor = c.get("anchor") if isinstance(c.get("anchor"), dict) else None
                ctext = (c.get("text") or "").replace("\r\n", "\n").strip()
                if (anchor and anchor.get("path") == file_path
                        and anchor.get("line") == line
                        and (anchor.get("lineType") or "").upper() == line_type
                        and ctext == norm_text):
                    return {"hit": True, "id": c.get("id")}
            if data.get("isLastPage", True) or not values:
                break
            nxt = data.get("nextPageStart")
            if not isinstance(nxt, int) or nxt <= start:
                break
            start = nxt
        else:
            read_errors.append("activities: 翻页安全阀（20页）触发，回读数据可能截断")
    except Exception as e:  # noqa: BLE001
        read_errors.append(f"activities: {e}")
    # 通道 2：assignments
    try:
        assign_data = api_request(
            "GET",
            f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/assignments?path=&states=open,resolved",
            cookies, api_version="5.0")
        if assign_data.get("error"):
            read_errors.append("assignments: " + json.dumps(assign_data["error"], ensure_ascii=False)[:200])
        else:
            values = assign_data.get("values")
            if isinstance(values, list):
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    comments = item.get("comments")
                    if not isinstance(comments, list):
                        continue
                    for cw in comments:
                        if not isinstance(cw, dict):
                            continue
                        comment = cw.get("comment") or {}
                        anchor = cw.get("commentAnchor")
                        if not isinstance(anchor, dict):
                            anchor = None
                        path = (anchor or {}).get("path") or item.get("path")
                        line_v = (anchor or {}).get("line")
                        lt = (anchor or {}).get("lineType")
                        ctext = (comment.get("text") or "").replace("\r\n", "\n").strip()
                        if (path == file_path and line_v == line
                                and (lt or "").upper() == line_type
                                and ctext == norm_text):
                            return {"hit": True, "id": comment.get("id")}
    except Exception as e:  # noqa: BLE001
        read_errors.append(f"assignments: {e}")
    if read_errors:
        result["readError"] = "; ".join(read_errors)
    return result


def _probe_existing_global_comment(project, repo, pr_id, cookies, text):
    """全局评论发送结果未知时回读查找“同正文且无锚点”的既有评论。

    返回 {"hit": True, "id": ...} 或 {"hit": False[, "readError": ...]}。
    best-effort 回读匹配，不构成原子保证；未命中不代表评论未写入。
    """
    result = {"hit": False}
    norm_text = (text or "").replace("\r\n", "\n").strip()
    read_errors = []
    try:
        start = 0
        for _ in range(20):  # 安全阀
            data = api_request(
                "GET",
                f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities?start={start}&limit=100",
                cookies)
            if "error" in data:
                read_errors.append("activities: " + json.dumps(data["error"], ensure_ascii=False)[:200])
                break
            values = data.get("values", []) or []
            for a in values:
                c = a.get("comment") or {}
                if not isinstance(c, dict):
                    continue
                anchor = c.get("anchor")
                ctext = (c.get("text") or "").replace("\r\n", "\n").strip()
                if not isinstance(anchor, dict) and ctext == norm_text:
                    return {"hit": True, "id": c.get("id")}
            if data.get("isLastPage", True) or not values:
                break
            nxt = data.get("nextPageStart")
            if not isinstance(nxt, int) or nxt <= start:
                break
            start = nxt
        else:
            read_errors.append("activities: 翻页安全阀（20页）触发，回读数据可能截断")
    except Exception as e:  # noqa: BLE001
        read_errors.append(f"activities: {e}")
    if read_errors:
        result["readError"] = "; ".join(read_errors)
    return result


def cmd_comment_add(args, cookies):
    project, repo, pr_id = resolve_pr(args)
    payload = {"text": args.text}
    if args.file and args.line:
        expected_from, expected_to = _expected_range_from_args(args)
        commit_range = get_commit_range(
            project, repo, pr_id, cookies,
            expected_from=expected_from, expected_to=expected_to)
        if commit_range and commit_range.get("mismatch"):
            print(json.dumps({
                "error": "commitRange mismatch: PR 已更新或冻结值过期，拒绝盲发",
                "detail": commit_range["mismatch"],
            }, ensure_ascii=False)); return
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
        # 发送超时/网络异常：结果未知。不盲目重发 POST（可能重复评论），
        # 先回读匹配：找到同锚点同正文的评论 → 视为已存在（idempotent hit）；
        # 找不到 → 标记 unknown，由 caller 兜底，不静默丢弃也不重复发送。
        if data.get("error") and _is_send_uncertain(data["error"]):
            probe = _probe_existing_comment(
                project, repo, pr_id, cookies, args.file, args.line,
                (args.line_type or "ADDED").upper(), args.text)
            if probe.get("hit"):
                print(json.dumps({
                    "ok": True, "id": probe["id"], "text": args.text,
                    "recovered": "send-uncertain", "note": "发送结果未知，回读命中同锚点同正文评论",
                }, ensure_ascii=False, indent=2)); return
            unknown_out = {
                "error": "send result unknown (timeout/network), 回读未命中",
                "detail": data["error"],
                "unknown": True,
                "hint": "请勿盲目重发；caller 应回读核验或人工确认后处理",
            }
            if probe.get("readError"):
                unknown_out["probeReadError"] = probe["readError"]
            print(json.dumps(unknown_out, ensure_ascii=False)); return
    else:
        data = api_request("POST", f"projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments", cookies, payload)
        # 全局评论同样不盲目重发：超时/网络异常先回读匹配同正文无锚点评论
        if data.get("error") and _is_send_uncertain(data["error"]):
            probe = _probe_existing_global_comment(project, repo, pr_id, cookies, args.text)
            if probe.get("hit"):
                print(json.dumps({
                    "ok": True, "id": probe["id"], "text": args.text,
                    "recovered": "send-uncertain", "note": "发送结果未知，回读命中同正文无锚点评论",
                }, ensure_ascii=False, indent=2)); return
            unknown_out = {
                "error": "send result unknown (timeout/network), 回读未命中",
                "detail": data["error"],
                "unknown": True,
                "hint": "请勿盲目重发；caller 应回读核验或人工确认后处理",
            }
            if probe.get("readError"):
                unknown_out["probeReadError"] = probe["readError"]
            print(json.dumps(unknown_out, ensure_ascii=False)); return
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)); return
    comment_id = data.get("id")
    if not comment_id:
        # 业务成功要求 id 非空：无 id 无法回读核验/删除，不冒充成功
        print(json.dumps({
            "error": "comment response missing id（业务成功需 id 非空）",
            "response": {k: data.get(k) for k in ("id", "text") if k in data},
        }, ensure_ascii=False)); return
    result = {"ok": True, "id": comment_id, "text": data.get("text")}
    if args.file and args.line:
        # 发送成功后回读核验锚点（读取不可用时如实标注，不冒充已验证）
        verify = _verify_comment_anchor(
            project, repo, pr_id, cookies, comment_id,
            args.file, int(args.line), args.line_type)
        result["anchorVerified"] = verify.get("verified", False)
        if verify.get("anchor") is not None:
            result["anchor"] = verify["anchor"]
        result["anchorSource"] = verify.get("source")
        if verify.get("readError"):
            result["anchorReadError"] = verify["readError"]
        if verify.get("partial"):
            result["anchorPartial"] = True
    else:
        # 全局评论：按 id 回读 activities 核验存在性（读取不可用如实标注，不冒充已验证）
        found, g_err, g_partial = _scan_activities_for_comment(
            project, repo, pr_id, cookies, comment_id, want=None)
        if found and found[1] == "activities":
            result["globalVerified"] = True
        else:
            result["globalVerified"] = False
            if found:
                result["globalReadError"] = f"activities 命中但非评论本体（{found[1]}）"
            elif g_err:
                result["globalReadError"] = g_err
            elif g_partial:
                result["globalReadError"] = "翻页安全阀（20页）触发，回读数据可能截断"
                result["globalPartial"] = True
            else:
                result["globalReadError"] = "未在 activities 中找到该评论"
    print(json.dumps(result, ensure_ascii=False, indent=2))


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
    p = sub.add_parser("pr-commits", help="PR 的 commit 列表"); add_pr_args(p); p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("compare-changes", help="两个 commit 之间的文件变更列表"); add_pr_args(p); p.add_argument("--from", dest="from_hash", required=True, help="新 commit hash（40 位）"); p.add_argument("--to", dest="to_hash", required=True, help="旧 commit hash（40 位）")
    p = sub.add_parser("compare-diff", help="两个 commit 之间某文件的 diff"); add_pr_args(p); p.add_argument("--file", "-f", required=True); p.add_argument("--from", dest="from_hash", required=True, help="新 commit hash（40 位）"); p.add_argument("--to", dest="to_hash", required=True, help="旧 commit hash（40 位）"); p.add_argument("--context", type=int, default=3); p.add_argument("--json", action="store_true")
    p = sub.add_parser("pr-comments", help="查看评论"); add_pr_args(p)
    p.add_argument("--with-metadata", action="store_true", help="输出评论历史完整性回执（默认仍为 JSON list）")
    p = sub.add_parser("pr-reviewers", help="查看 reviewer"); add_pr_args(p)
    p = sub.add_parser("comment-add", help="添加评论"); add_pr_args(p); p.add_argument("--text", "-t", required=True); p.add_argument("--file", "-f"); p.add_argument("--line", "-l", type=int); p.add_argument("--line-type", default="ADDED"); p.add_argument("--file-type", default="TO"); p.add_argument("--expected-from", default=None, help="冻结的 fromHash（发送前与当前值比对，不一致拒绝发送）"); p.add_argument("--expected-to", default=None, help="冻结的 toHash（发送前与当前值比对，不一致拒绝发送）")
    p = sub.add_parser("comment-delete", help="删除评论"); add_pr_args(p); p.add_argument("--comment-id", type=int, required=True); p.add_argument("--version", type=int, default=0)
    p = sub.add_parser("my-reviews", help="列出待我审查的 PR（跨仓库）"); p.add_argument("--role", default="reviewer", help="reviewer|author"); p.add_argument("--state", default="OPEN", help="OPEN|MERGED|DECLINED|ALL"); p.add_argument("--limit", type=int, default=20); p.add_argument("--start", type=int, default=0)
    p = sub.add_parser("user-info", help="当前用户信息")

    args = parser.parse_args()
    if not args.command:
        parser.print_help(); return
    cookies = get_cookies(args.cookie)
    cmds = {"pr-info": cmd_pr_info, "pr-list": cmd_pr_list, "pr-changes": cmd_pr_changes, "pr-diff": cmd_pr_diff, "pr-commits": cmd_pr_commits, "compare-changes": cmd_compare_changes, "compare-diff": cmd_compare_diff, "pr-comments": cmd_pr_comments, "pr-reviewers": cmd_pr_reviewers, "comment-add": cmd_comment_add, "comment-delete": cmd_comment_delete, "my-reviews": cmd_my_reviews, "user-info": cmd_user_info}
    handler = cmds.get(args.command)
    if handler:
        handler(args, cookies)

if __name__ == "__main__":
    main()
