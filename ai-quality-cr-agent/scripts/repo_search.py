#!/usr/bin/env python3
"""
美团 MCode 仓库代码搜索 CLI
无需 git clone，通过 Bitbucket REST API + Cookie 认证直接搜索任意仓库。
Cookie 自动从沙箱 Chromium 浏览器登录态获取。

安装后直接通过 skill 目录调用，或将本文件路径加入 PATH：
  python3 /path/to/code-repo-search/repo_search.py -r tuangou/price-display -k SkuId --ext .java

用法示例：
  python3 repo_search.py -r <org/repo> -k MyClassName --ext .java
  python3 repo_search.py -r <org/repo> -k "get.*Price" --regex --ext .java
  python3 repo_search.py -r <org/repo> -k myField --ext .java --context 3
  python3 repo_search.py -r <org/repo> -k someConfigKey --ext .xml,.yaml --json
"""

import argparse
import concurrent.futures
from http.client import HTTPException
import json
import math
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

GIT_BASE_URL = os.getenv("GIT_BASE_URL", "https://dev.sankuai.com")


class RepoSearchError(RuntimeError):
    """Raised when a repository search response is unavailable or malformed."""

# 全局 SSL context（跳过证书校验，适配内网）
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ──────────────────────────────────────────────
# Cookie 获取：优先级与 code_cli.py 对齐
# 命令行 > 环境变量 > MOA SSO 无感换票 > Cookie 文件 > CDP 浏览器
# ──────────────────────────────────────────────
CDP_URL = os.getenv("CDP_URL", "http://localhost:9222")
_SSO_CACHE_FILE = "/tmp/cr_sso_token_cache.txt"
_SSO_CACHE_TTL = 1800  # 30 分钟


def _get_sso_cookie():
    """通过 mtsso-moa-local-exchange 获取 SSO token（CatClaw/1024 沙箱优先）。"""
    import subprocess

    # 读取缓存
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
        probe = subprocess.run(
            ["npx", "mtsso-moa-feature-probe", "--timeout", "5"],
            capture_output=True, text=True, timeout=8
        )
        if probe.returncode != 0:
            return None
        probe_data = json.loads(probe.stdout.strip())
        if not probe_data.get("ok"):
            return None

        result = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", "f32a546874"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip())
        token = data.get("access_token", "")
        if token:
            try:
                with open(_SSO_CACHE_FILE, "w") as f:
                    f.write(f"{time.time()}\n{token}")
            except Exception:
                pass
            return f"f32a546874_ssoid={token}"
    except Exception:
        pass
    return None


def _get_cookies_from_cdp():
    """通过 CDP 从沙箱 Chromium 获取 dev.sankuai.com Cookie。"""
    try:
        import http.client
        host_port = CDP_URL.replace("http://", "").replace("https://", "")
        host, port = host_port.split(":") if ":" in host_port else (host_port, "9222")
        conn = http.client.HTTPConnection(host, int(port), timeout=3)
        conn.request("GET", "/json/list")
        tabs = json.loads(conn.getresponse().read())
        target = None
        for t in tabs:
            if "dev.sankuai.com" in t.get("url", "") or "sankuai.com" in t.get("url", ""):
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
            ws.send(json.dumps({"id": 1, "method": "Network.getCookies",
                                "params": {"urls": [GIT_BASE_URL]}}))
            result = json.loads(ws.recv())
            ws.close()
            cookies = result.get("result", {}).get("cookies", [])
            return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        except ImportError:
            return None
    except Exception:
        return None


def get_cookies(manual=None):
    """Cookie 获取，优先级与 code_cli.py 完全对齐。"""
    if manual:
        return manual
    env_cookie = os.getenv("CODE_COOKIE")
    if env_cookie:
        return env_cookie
    # MOA SSO 无感换票（CatClaw/1024 沙箱优先）
    sso_cookie = _get_sso_cookie()
    if sso_cookie:
        return sso_cookie
    # Cookie 文件
    cookie_file = os.getenv("CODE_COOKIE_FILE", "/tmp/code_cookies.txt")
    if os.path.exists(cookie_file):
        with open(cookie_file) as f:
            c = f.read().strip()
            if c:
                return c
    # 持久化 Cookie 文件
    persistent_cookie_file = os.path.expanduser("~/.openclaw/mcode_cookie.txt")
    if os.path.exists(persistent_cookie_file):
        with open(persistent_cookie_file) as f:
            c = f.read().strip()
            if c:
                return c
    # CDP 浏览器兜底
    cdp_cookie = _get_cookies_from_cdp()
    if cdp_cookie:
        return cdp_cookie
    print("Error: 无法获取 Cookie。请设置 CODE_COOKIE 环境变量，或确保沙箱 Chromium 已登录 dev.sankuai.com",
          file=sys.stderr)
    sys.exit(1)


# ──────────────────────────────────────────────
# Bitbucket REST API 封装
# ──────────────────────────────────────────────
def api_get(path, cookies, timeout=15):
    url = f"{GIT_BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Cookie": cookies, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RepoSearchError(f"API 请求失败: HTTP {exc.code}") from exc
    except (HTTPException, OSError, ValueError) as exc:
        raise RepoSearchError(f"API 请求失败: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise RepoSearchError(f"API 响应顶层不是对象: {type(data).__name__}")
    if data.get("error") or data.get("errors"):
        raise RepoSearchError("API 返回 error/errors，拒绝作为搜索结果")
    return data


REPO_FILES_CACHE_TTL = 1800  # 30 分钟
REPO_FILES_CACHE_VERSION = 2


def _cache_path(project, repo, branch):
    """文件列表缓存路径。"""
    safe_repo = repo.replace("/", "_")
    return f"/tmp/cr_repo_files_{project}_{safe_repo}_{branch}.txt"


def list_repo_files(project, repo, branch, cookies, exts=None, path_prefix=None):
    """用 /files 接口一次性拿全量文件路径列表，支持扩展名和路径过滤。
    同仓库同分支的文件列表会缓存到 /tmp，30 分钟内命中缓存跳过 API 调用。
    """
    cache_file = _cache_path(project, repo, branch)

    # 尝试命中缓存
    cached_files = None
    try:
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                data = json.load(f)
            timestamp = data.get("ts") if isinstance(data, dict) else None
            paths = data.get("files") if isinstance(data, dict) else None
            if (isinstance(data, dict) and data.get("version") == REPO_FILES_CACHE_VERSION
                    and type(timestamp) in (int, float) and math.isfinite(timestamp)
                    and 0 <= time.time() - timestamp < REPO_FILES_CACHE_TTL
                    and isinstance(paths, list)
                    and all(isinstance(path, str) and path for path in paths)):
                cached_files = paths
                print(f"[cache] 命中文件列表缓存({len(cached_files)} 个文件)，跳过 API 调用",
                      file=sys.stderr)
    except Exception:
        pass

    if cached_files is None:
        # 缓存未命中，走 API 拉取
        files = []
        start = 0
        while True:
            data = api_get(
                f"/rest/api/1.0/projects/{project}/repos/{repo}/files"
                f"?at={urllib.parse.quote(branch)}&limit=1000&start={start}",
                cookies,
                timeout=30,
            )
            values = data.get("values")
            if not isinstance(values, list):
                raise RepoSearchError("文件列表 API 缺少合法 values 数组")
            if any(not isinstance(item, str) or not item for item in values):
                raise RepoSearchError("文件列表 API values 含非字符串路径")
            files.extend(values)
            is_last_page = data.get("isLastPage")
            if not isinstance(is_last_page, bool):
                raise RepoSearchError("文件列表 API 缺少合法 isLastPage 字段")
            if is_last_page:
                break
            next_start = data.get("nextPageStart")
            if type(next_start) is not int or next_start <= start:
                raise RepoSearchError("文件列表 API 缺少合法 nextPageStart 字段")
            start = next_start

        # 写入缓存
        try:
            with open(cache_file, "w") as f:
                json.dump({"version": REPO_FILES_CACHE_VERSION,
                           "ts": time.time(), "files": files}, f)
        except Exception:
            pass
    else:
        files = cached_files

    if path_prefix:
        files = [f for f in files if f.startswith(path_prefix)]
    if exts:
        exts_set = set(exts)
        files = [f for f in files if any(f.endswith(e) for e in exts_set)]
    return files


def read_repo_file_lines(project, repo, ref, file_path, cookies):
    """读取指定分支或提交的完整文件；file_path 为仓库返回的原始路径。"""
    encoded_path = urllib.parse.quote(file_path, safe="/")
    data = api_get(
        f"/rest/api/1.0/projects/{project}/repos/{repo}/browse/{encoded_path}"
        f"?at={urllib.parse.quote(ref)}&limit=5000",
        cookies,
        timeout=15,
    )
    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list):
        raise RepoSearchError("文件内容 API 缺少合法 lines 数组")
    if (data.get("isLastPage") is False or data.get("truncated")
            or ("isLastPage" in data and type(data["isLastPage"]) is not bool)
            or ("isLastPage" not in data and len(raw_lines) >= 5000)):
        raise RepoSearchError("文件内容响应不完整，需按分页或其他完整读取方式重试")
    if any(not isinstance(line, dict) or not isinstance(line.get("text"), str)
           for line in raw_lines):
        raise RepoSearchError("文件内容 API lines 含非法行数据")
    return [line["text"] for line in raw_lines]


def search_in_file(project, repo, branch, file_path, keyword, cookies,
                   use_regex=False, context_lines=0):
    """读取单个文件内容，返回 (路径, [hit_dict, ...])；失败抛异常。
    hit_dict: {"line": int, "text": str, "context_before": [...], "context_after": [...]}
    """
    try:
        lines = read_repo_file_lines(project, repo, branch, file_path, cookies)

        if use_regex:
            pattern = re.compile(keyword)
            match_fn = lambda line: bool(pattern.search(line))
        else:
            match_fn = lambda line: keyword in line

        hits = []
        for i, line in enumerate(lines):
            if match_fn(line):
                hit = {"line": i + 1, "text": line}
                if context_lines > 0:
                    hit["context_before"] = [
                        {"line": j + 1, "text": lines[j]}
                        for j in range(max(0, i - context_lines), i)
                    ]
                    hit["context_after"] = [
                        {"line": j + 1, "text": lines[j]}
                        for j in range(i + 1, min(len(lines), i + 1 + context_lines))
                    ]
                hits.append(hit)
        return file_path, hits
    except RepoSearchError:
        raise
    except Exception as exc:
        raise RepoSearchError(f"文件搜索失败: {type(exc).__name__}") from exc


# ──────────────────────────────────────────────
# 预过滤无关文件
# ──────────────────────────────────────────────
def _prefilter_irrelevant(files):
    """预过滤测试/资源/配置/生成代码等无关文件（仅对 .java 场景）。"""
    EXCLUDE_PATTERNS = [
        "/test/",
        "/tests/",
        "/resources/",
        "/configs/",
        "/config/",
        "/generated/",
    ]
    result = []
    for f in files:
        if f.endswith("Test.java"):
            continue
        if any(p in f for p in EXCLUDE_PATTERNS):
            continue
        result.append(f)
    return result


# ──────────────────────────────────────────────
# 主逻辑
# ──────────────────────────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="MCode 仓库代码搜索 — 无需 git clone，Cookie 认证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜 Java 文件中的类/字段引用
  python3 repo_search.py -r <org/repo> -k MyClassName --ext .java

  # 正则搜索 + 显示上下文
  python3 repo_search.py -r <org/repo> -k "get.*Price" --regex --ext .java --context 3

  # 限定子目录
  python3 repo_search.py -r <org/repo> -k myField \\
    --ext .java --path your-service/src/main/java

  # JSON 输出（AI 程序化消费）
  python3 repo_search.py -r <org/repo> -k MyInterface --ext .java --json
        """
    )
    parser.add_argument("--cookie", help="手动指定 cookie")
    parser.add_argument("--project", "-p", help="项目/org 名，如 tuangou")
    parser.add_argument("--repo", "-r", required=True,
                        help="仓库名，如 price-display 或 tuangou/price-display")
    parser.add_argument("--keyword", "-k", required=True, help="搜索关键词")
    parser.add_argument("--branch", "-b", default="master", help="分支，默认 master")
    parser.add_argument("--ext",
                        help="文件扩展名过滤，逗号分隔，如 .java,.kt；不填搜所有文件")
    parser.add_argument("--path", dest="path_prefix",
                        help="限定子目录前缀，如 price-display-service/src/main")
    parser.add_argument("--workers", type=int, default=40, help="并发线程数，默认 40")
    parser.add_argument("--regex", action="store_true", help="关键词按正则表达式匹配")
    parser.add_argument("--context", "-C", type=int, default=0,
                        help="显示命中行前后 N 行上下文（类似 grep -C）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")

    args = parser.parse_args(argv)
    if args.workers <= 0:
        parser.error("--workers 必须为正整数")
    if args.context < 0:
        parser.error("--context 不能小于 0")
    if args.regex:
        try:
            re.compile(args.keyword)
        except re.error:
            parser.error("--keyword 不是合法正则表达式")

    project = args.project
    repo = args.repo
    if not project and "/" in (repo or ""):
        project, repo = repo.split("/", 1)
    if not project or not repo:
        print("Error: 请指定 --project/-p 和 --repo/-r，或用 org/repo 格式", file=sys.stderr)
        sys.exit(1)

    cookies = get_cookies(args.cookie)
    branch = args.branch or "master"
    keyword = args.keyword
    exts = None
    if args.ext:
        exts = [e if e.startswith(".") else f".{e}" for e in args.ext.split(",")]

    # Step 1: 列文件
    t0 = time.time()
    print(f"[1/2] 列举 {project}/{repo} @{branch} 文件列表...", file=sys.stderr)
    try:
        files = list_repo_files(project, repo, branch, cookies,
                                exts=exts, path_prefix=args.path_prefix)
    except RepoSearchError as exc:
        print(f"[repo_search] 文件列表失败: {exc}", file=sys.stderr)
        return 1

    # 预过滤无关文件（仅对 .java 文件场景）
    if exts and ".java" in exts:
        before = len(files)
        files = _prefilter_irrelevant(files)
        after = len(files)
        excluded = before - after
        print(f"[filter] 过滤前 {before} 个文件，过滤后 {after} 个文件"
              f"（排除 {excluded} 个 test/resources/config）", file=sys.stderr)

    mode_label = "正则" if args.regex else "精确"
    print(f"[1/2] 共 {len(files)} 个文件（{time.time()-t0:.1f}s），"
          f"开始{mode_label}搜索 '{keyword}'...", file=sys.stderr)

    # Step 2: 并发搜索
    results = []
    errors = []
    t1 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(search_in_file, project, repo, branch, f, keyword, cookies,
                      args.regex, args.context): f
            for f in files
        }
        for fut in concurrent.futures.as_completed(futs):
            try:
                path, hits = fut.result()
                error = ""
            except RepoSearchError as exc:
                path, hits, error = futs[fut], [], str(exc)
            except Exception as exc:
                path, hits, error = futs[fut], [], type(exc).__name__
            if error:
                errors.append((path, error))
                continue
            if hits:
                results.append((path, hits))
    print(f"[2/2] 搜索完成，耗时 {time.time()-t1:.1f}s，命中 {len(results)} 个文件",
          file=sys.stderr)

    if errors:
        for path, error in sorted(errors):
            print(f"[error] {path}: {error}", file=sys.stderr)
        print(f"[repo_search] {len(errors)} 个文件搜索失败，结果不完整，已拒绝输出成功结果",
              file=sys.stderr)
        return 1

    # JSON 输出
    if args.json:
        print(json.dumps(
            [{"file": p, "hits": h} for p, h in results],
            ensure_ascii=False, indent=2,
        ))
        return 0

    if not results:
        print(f"未找到 '{keyword}' 的引用")
        return 0

    print(f"\n找到 {len(results)} 个文件引用 '{keyword}':\n")
    for path, hits in sorted(results):
        print(f"📄 {path}")
        for hit in hits:
            # 打印上下文前行
            for ctx in hit.get("context_before", []):
                print(f"  {ctx['line']:5d}  {ctx['text'].rstrip()}")
            # 打印命中行（高亮标记）
            print(f"  {hit['line']:5d}▶ {hit['text'].rstrip()}")
            # 打印上下文后行
            for ctx in hit.get("context_after", []):
                print(f"  {ctx['line']:5d}  {ctx['text'].rstrip()}")
            if args.context > 0:
                print(f"  {'─'*40}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
