#!/usr/bin/env python3
"""
T1：浅克隆模块（独立可测）

职责：给定 (repo, commit) → 在本地工作根下准备一份 checkout 到该 commit 的目录，返回 Path。

设计原则：
  1. 24h 内同 (repo, commit) 直接复用本地目录，不重复克隆
  2. 优先尝试"指定 commit 浅克隆"（git protocol v2 + uploadpack.allowReachableSHA1InWant），
     不支持时退化为 `clone --depth=1` + `fetch <commit>` + `checkout`，最后兜底全克隆
  3. 仅做"准备 worktree"这一件事，不做评分；不引入 ai-ready 业务逻辑
  4. 失败抛 CloneError；调用方自行决定是否进入 _status=error

CLI 自检：
  python3 clone_at_commit.py --repo fun/scp-dzbiz-process-server \\
                             --commit a3b416d04811 \\
                             --workdir /tmp/ai-ready-repo-cache
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WORKDIR = Path.home() / ".cache" / "ai-ready-repo"
DEFAULT_FETCH_TIMEOUT = 180  # seconds
CACHE_TTL_SECONDS = 24 * 3600


class CloneError(RuntimeError):
    """浅克隆/checkout 失败的统一异常。"""


@dataclass
class CloneResult:
    """浅克隆产物描述。"""

    repo_dir: Path           # 本地 checkout 后的目录
    repo_url: str            # 实际使用的 SSH/HTTPS 地址
    commit: str              # 实际 checkout 的完整 commit hash
    cached: bool             # True 表示命中已有目录
    elapsed_ms: int          # 准备耗时（毫秒），cached=True 时基本为 0


# ----------------------------------------------------------------------------
# 内部工具
# ----------------------------------------------------------------------------
def _safe_repo_token(repo: str) -> str:
    """把 ssh://git@host/group/name.git 或 group/name 拍平成路径安全的 token。"""
    token = repo.replace("ssh://", "").replace("git@", "")
    token = token.replace("://", "_").replace(":", "_").replace("/", "__")
    if token.endswith(".git"):
        token = token[:-4]
    return token


def _normalize_repo_url(repo: str) -> str:
    """
    支持三种入参形式，统一转换为 SSH URL：
      1) ssh://git@git.dianpingoa.com/group/name.git → 原样返回
      2) git@git.dianpingoa.com:group/name.git → 转成 ssh:// 形式
      3) group/name 简写 → 默认补 ssh://git@git.sankuai.com/group/name.git
    """
    if repo.startswith("ssh://") or repo.startswith("https://") or repo.startswith("http://"):
        return repo
    m = re.match(r"^([^@]+@[^:]+):(.+?)(?:\.git)?$", repo)
    if m:
        host, path = m.group(1), m.group(2)
        if not path.endswith(".git"):
            path += ".git"
        return f"ssh://{host}/{path}"
    if "/" in repo and not repo.startswith("/"):
        path = repo if repo.endswith(".git") else f"{repo}.git"
        # 默认主机：美团内部代码仓
        return f"ssh://git@git.sankuai.com/{path}"
    raise CloneError(f"无法解析 repo 入参为 SSH URL: {repo!r}")


def _short_commit(commit: str) -> str:
    return (commit or "")[:12] or hashlib.sha1((commit or "_unknown_").encode()).hexdigest()[:12]


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_FETCH_TIMEOUT,
    quiet: bool = False,
) -> tuple[int, str, str]:
    """统一的子进程封装，避免 None 流失败的边角问题。"""
    if not quiet:
        print(f"$ {' '.join(cmd)}", file=sys.stderr)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 124, "", f"timeout after {timeout}s ({e})"
    except FileNotFoundError as e:
        return 127, "", f"git not found: {e}"


def _is_repo_at_commit(repo_dir: Path, commit: str) -> bool:
    """检查 repo_dir 是否是合法 git 仓库且 HEAD 为 commit（前缀匹配也算）。"""
    if not (repo_dir / ".git").exists():
        return False
    code, out, _ = _run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, timeout=10, quiet=True
    )
    if code != 0:
        return False
    head = out.strip()
    return bool(head) and (head == commit or head.startswith(commit) or commit.startswith(head))


def _is_fresh_enough(path: Path, ttl: int) -> bool:
    """目录在 ttl 内被 mtime 标记过 → 视为新鲜，可以复用。"""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) < ttl


# ----------------------------------------------------------------------------
# 克隆策略：优先单 commit 浅克隆，失败逐级退化
# ----------------------------------------------------------------------------
def _strategy_shallow_fetch_commit(
    repo_url: str, repo_dir: Path, commit: str, timeout: int
) -> tuple[bool, str]:
    """
    策略 A：先 init 空仓库，再 fetch 指定 commit（最省带宽）。
    需要服务端打开 uploadpack.allowReachableSHA1InWant 或 allowAnySHA1InWant。
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    code, _, err = _run(["git", "init", "-q"], cwd=repo_dir, timeout=10)
    if code != 0:
        return False, f"git init failed: {err}"
    _run(
        ["git", "remote", "add", "origin", repo_url],
        cwd=repo_dir,
        timeout=10,
        quiet=True,
    )
    code, _, err = _run(
        ["git", "fetch", "--depth=1", "origin", commit],
        cwd=repo_dir,
        timeout=timeout,
    )
    if code != 0:
        return False, f"fetch <commit> failed: {err.strip()[-300:]}"
    code, _, err = _run(
        ["git", "checkout", "-q", "FETCH_HEAD"], cwd=repo_dir, timeout=30
    )
    if code != 0:
        return False, f"checkout FETCH_HEAD failed: {err}"
    return True, ""


def _strategy_clone_then_fetch(
    repo_url: str, repo_dir: Path, commit: str, timeout: int
) -> tuple[bool, str]:
    """
    策略 B：先 `clone --depth=1`（默认分支），再 `fetch <commit>` 后 checkout。
    适合：服务端不允许任意 SHA1 fetch，但允许 reachable SHA1 fetch。
    """
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
    code, _, err = _run(
        ["git", "clone", "--depth=1", repo_url, str(repo_dir)],
        timeout=timeout,
    )
    if code != 0:
        return False, f"shallow clone failed: {err.strip()[-300:]}"
    code, _, err = _run(
        ["git", "fetch", "--depth=1", "origin", commit],
        cwd=repo_dir,
        timeout=timeout,
    )
    if code != 0:
        # 允许 fetch 失败（commit 可能在 feature 分支需要全 fetch）
        # 退化到拉所有 refs
        code2, _, err2 = _run(
            ["git", "fetch", "origin"], cwd=repo_dir, timeout=timeout
        )
        if code2 != 0:
            return False, (
                f"both shallow & full fetch failed: {err.strip()[-150:]} | "
                f"{err2.strip()[-150:]}"
            )
    code, _, err = _run(
        ["git", "checkout", "-q", commit], cwd=repo_dir, timeout=30
    )
    if code != 0:
        return False, f"checkout {commit} failed: {err}"
    return True, ""


def _strategy_full_clone(
    repo_url: str, repo_dir: Path, commit: str, timeout: int
) -> tuple[bool, str]:
    """
    策略 C：兜底全克隆 + checkout。慢但最稳。
    """
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
    # 翻倍 timeout，避免大仓库被卡断
    code, _, err = _run(
        ["git", "clone", repo_url, str(repo_dir)], timeout=timeout * 2
    )
    if code != 0:
        return False, f"full clone failed: {err.strip()[-300:]}"
    code, _, err = _run(
        ["git", "checkout", "-q", commit], cwd=repo_dir, timeout=30
    )
    if code != 0:
        return False, f"checkout {commit} after full clone failed: {err}"
    return True, ""


# ----------------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------------
def clone_at_commit(
    repo: str,
    commit: str,
    *,
    workdir: Path | str | None = None,
    timeout: int = DEFAULT_FETCH_TIMEOUT,
    cache_ttl: int = CACHE_TTL_SECONDS,
    force_refresh: bool = False,
) -> CloneResult:
    """
    准备 (repo, commit) 对应的本地 worktree，返回 CloneResult。

    抛 CloneError 表示三个策略均失败。
    """
    if not commit or len(commit) < 7:
        raise CloneError(f"commit 太短，至少 7 位: {commit!r}")
    if not repo:
        raise CloneError("repo 入参为空")

    repo_url = _normalize_repo_url(repo)
    workdir = Path(workdir) if workdir else DEFAULT_WORKDIR
    workdir.mkdir(parents=True, exist_ok=True)
    repo_dir = workdir / f"{_safe_repo_token(repo)}@{_short_commit(commit)}"

    # 缓存命中
    if (
        not force_refresh
        and repo_dir.exists()
        and _is_repo_at_commit(repo_dir, commit)
        and _is_fresh_enough(repo_dir, cache_ttl)
    ):
        return CloneResult(
            repo_dir=repo_dir,
            repo_url=repo_url,
            commit=commit,
            cached=True,
            elapsed_ms=0,
        )

    # 缓存目录存在但 HEAD 不对/已过期 → 删掉重来
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)

    started = time.time()
    errors: list[str] = []

    for label, fn in (
        ("shallow_fetch_commit", _strategy_shallow_fetch_commit),
        ("clone_then_fetch", _strategy_clone_then_fetch),
        ("full_clone", _strategy_full_clone),
    ):
        ok, err = fn(repo_url, repo_dir, commit, timeout)
        if ok:
            # 校验真实 HEAD（避免 checkout 短 commit 后 HEAD 与传入不一致）
            _, head, _ = _run(
                ["git", "rev-parse", "HEAD"], cwd=repo_dir, timeout=10, quiet=True
            )
            head = head.strip() or commit
            elapsed_ms = int((time.time() - started) * 1000)
            return CloneResult(
                repo_dir=repo_dir,
                repo_url=repo_url,
                commit=head,
                cached=False,
                elapsed_ms=elapsed_ms,
            )
        errors.append(f"[{label}] {err}")
        # 下一个策略前清空目录
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)

    raise CloneError(
        "all strategies failed:\n  " + "\n  ".join(errors)
    )


# ----------------------------------------------------------------------------
# CLI 自检
# ----------------------------------------------------------------------------
def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="(repo, commit) → 本地 worktree")
    ap.add_argument("--repo", required=True, help="ssh URL / git@host:path / group/name")
    ap.add_argument("--commit", required=True, help="完整或短 commit hash（≥7 位）")
    ap.add_argument(
        "--workdir",
        default=str(DEFAULT_WORKDIR),
        help=f"工作根目录，默认 {DEFAULT_WORKDIR}",
    )
    ap.add_argument(
        "--timeout", type=int, default=DEFAULT_FETCH_TIMEOUT, help="单次 git 操作超时秒数"
    )
    ap.add_argument(
        "--ttl", type=int, default=CACHE_TTL_SECONDS, help="缓存 TTL（秒），默认 24h"
    )
    ap.add_argument("--force", action="store_true", help="强制重克隆")
    args = ap.parse_args(argv)

    try:
        result = clone_at_commit(
            args.repo,
            args.commit,
            workdir=Path(args.workdir),
            timeout=args.timeout,
            cache_ttl=args.ttl,
            force_refresh=args.force,
        )
    except CloneError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    print(
        f"✅ {'cached' if result.cached else 'fresh'} "
        f"({result.elapsed_ms} ms): {result.repo_dir} @ {result.commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
