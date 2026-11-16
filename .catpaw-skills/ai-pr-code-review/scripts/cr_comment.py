#!/usr/bin/env python3
"""
cr_comment.py — AI CR 评论发送工具

封装 code_cli.py 的 comment-add / comment-delete / pr-comments / pr-changes 操作，
提供路径解析 + 重试。既可作为库被 import 调用（send_inline / send_global / ...），
也可作为 CLI 使用。

库调用（publish_results.py 采用）:
  from cr_comment import CommentClient
  client = CommentClient()
  client.send_inline(pr_url, file_keyword="Foo.java", line=42, text="...")
  client.send_global(pr_url, text="...")

CLI 调用:
  python3 cr_comment.py inline --url "..." --file-keyword "Foo.java" --line 42 --text "..."
  python3 cr_comment.py global --url "..." --text "..."
  python3 cr_comment.py delete --url "..." --comment-id 50318595
  python3 cr_comment.py verify --url "..."
  python3 cr_comment.py list-paths --url "..."
"""
import argparse
import json
import os
import subprocess
import sys
import time

RETRY_MAX = 4
RETRY_INTERVAL = 2  # 秒


class CommentError(Exception):
    """评论操作失败异常"""


def _log(msg):
    print(msg, file=sys.stderr)


def resolve_code_cli():
    """返回 code_cli.py 路径（写死：本脚本同目录，沙箱统一环境）。"""
    # code_cli.py 与本脚本同在 scripts/ 目录
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "code_cli.py")


def parse_json_output(text):
    """从可能混有日志的输出中解析 JSON 对象/数组。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                pass
    return None


class CommentClient:
    """评论操作客户端。封装 code_cli.py 调用 + 重试 + 路径解析。"""

    def __init__(self, code_cli=None, log_fn=None, retry_max=RETRY_MAX,
                 retry_interval=RETRY_INTERVAL):
        self.code_cli = code_cli or resolve_code_cli()
        if not self.code_cli or not os.path.isfile(self.code_cli):
            raise CommentError(f"内置 code_cli.py 不存在({self.code_cli}),沙箱异常")
        self.log = log_fn or _log
        self.retry_max = retry_max
        self.retry_interval = retry_interval

    # ─── 底层 ─────────────────────────────────────────────────────────────────
    def _run_code_cli(self, args_list, label="code_cli"):
        """执行 code_cli.py，返回 (returncode, combined_output)。合并 stdout+stderr。"""
        cmd = [sys.executable, self.code_cli] + args_list
        self.log(f"▶ {label}: {' '.join(cmd[:6])}...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return 1, "timeout after 120s"
        combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return result.returncode, combined

    def _run_with_retry(self, args_list, label="operation"):
        """带重试执行 code_cli，成功返回 (True, output)，全失败返回 (False, last_err)。"""
        last_err = ""
        for i in range(1, self.retry_max + 1):
            rc, out = self._run_code_cli(args_list, label=label)
            if rc == 0:
                return True, out
            last_err = out
            self.log(f"⚠️  {label} 第 {i}/{self.retry_max} 次失败: {last_err[:300]}")
            if i < self.retry_max:
                time.sleep(self.retry_interval)
        return False, last_err

    def resolve_file_path(self, pr_url, keyword):
        """从 pr-changes 模糊匹配 keyword，返回完整 path。匹配 0 或 >1 抛 CommentError。"""
        ok, out = self._run_with_retry(
            ["pr-changes", "--url", pr_url], label="pr-changes(路径解析)"
        )
        if not ok:
            raise CommentError(f"pr-changes 失败，无法解析路径: {out[:300]}")

        data = parse_json_output(out)
        if not isinstance(data, dict):
            raise CommentError(f"pr-changes 返回非 JSON 对象，无法解析路径: {out[:300]}")

        changes = data.get("changes", []) or []
        hits = [c.get("path", "") for c in changes if keyword in (c.get("path") or "")]

        if not hits:
            all_paths = "\n".join(f"  {c.get('path', '')}" for c in changes)
            raise CommentError(
                f"在 pr-changes 中找不到包含关键词 '{keyword}' 的文件\n📋 所有变更文件：\n{all_paths}"
            )

        if len(hits) > 1:
            raise CommentError(
                f"关键词 '{keyword}' 匹配到多个文件，请使用更精确的关键词：\n"
                + "\n".join(f"  {h}" for h in hits)
            )

        path = hits[0]
        self.log(f"🔍 路径解析：'{keyword}' → '{path}'")
        return path

    # ─── 业务操作（库接口）─────────────────────────────────────────────────────
    def send_inline(self, pr_url, file_keyword="", file="", line=0,
                    line_type="ADDED", text=""):
        """发行内评论。成功返回 comment_id，失败抛 CommentError。
        file_keyword 优先；其次用 file 传完整 path。
        """
        if not line:
            raise CommentError("inline 需要 line 参数")
        if not text:
            raise CommentError("inline 需要 text 参数")

        if file_keyword:
            file_path = self.resolve_file_path(pr_url, file_keyword)
        elif file:
            file_path = file
            self.log(f"📝 使用传入路径: {file_path}（建议改用 file_keyword 更安全）")
        else:
            raise CommentError("inline 需要 file_keyword 或 file 参数")

        self.log(f"📝 发行内评论 → {file_path}:{line} ({line_type})")
        cli_args = [
            "comment-add", "--url", pr_url,
            "--file", file_path, "--line", str(line),
            "--line-type", line_type, "--text", text,
        ]
        ok, out = self._run_with_retry(
            cli_args, label=f"行内评论 {file_path}:{line}"
        )
        if not ok:
            raise CommentError(f"行内评论发送失败: {out[:300]}")

        data = parse_json_output(out)
        comment_id = ""
        ok_flag = ""
        if isinstance(data, dict):
            comment_id = str(data.get("id", "") or "")
            ok_flag = str(data.get("ok", ""))

        if ok_flag.lower() == "true" and comment_id:
            self.log(f"✅ 行内评论发送成功（id={comment_id}），已带 anchor 锚定到 {file_path}:{line}")
            return comment_id
        raise CommentError(f"行内评论发送失败，返回: {out[:300]}")

    def send_global(self, pr_url, text):
        """发全局评论。成功返回 True，失败抛 CommentError。"""
        if not text:
            raise CommentError("global 需要 text 参数")
        self.log("📝 发全局评论")
        ok, out = self._run_with_retry(
            ["comment-add", "--url", pr_url, "--text", text], label="全局评论"
        )
        if ok:
            self.log("✅ 全局评论发送成功")
            return True
        raise CommentError(f"全局评论发送失败: {out[:300]}")

    def delete(self, pr_url, comment_id):
        """删除评论。成功返回 True，失败抛 CommentError。"""
        if not comment_id:
            raise CommentError("delete 需要 comment_id 参数")
        self.log(f"🗑️  删除评论 #{comment_id}")
        ok, out = self._run_with_retry(
            ["comment-delete", "--url", pr_url, "--comment-id", str(comment_id)],
            label=f"删除评论 #{comment_id}",
        )
        if ok:
            self.log("✅ 删除成功")
            return True
        raise CommentError(f"删除失败: {out[:300]}")

    def verify(self, pr_url):
        """验证评论（列出 PR 所有评论）。失败不抛异常（仅 log）。"""
        self.log("🔍 验证 PR 评论列表")
        ok, out = self._run_with_retry(
            ["pr-comments", "--url", pr_url], label="验证评论"
        )
        if not ok:
            self.log(f"⚠️  验证失败（不阻塞）: {out[:300]}")
        return out

    def list_paths(self, pr_url):
        """列出 PR 所有变更文件 path。失败抛 CommentError。"""
        self.log("📋 PR 变更文件列表：")
        ok, out = self._run_with_retry(
            ["pr-changes", "--url", pr_url], label="list-paths"
        )
        if not ok:
            raise CommentError(f"list-paths 失败: {out[:300]}")
        data = parse_json_output(out)
        if isinstance(data, dict):
            for c in data.get("changes", []):
                t = (c.get("type") or "").strip()[:6]
                print(f"  [{t:6}] {c.get('path', '')}")
        else:
            print(out)
        return out


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="AI CR 评论发送工具")
    sub = parser.add_subparsers(dest="subcmd")

    def add_url(p):
        p.add_argument("--url", required=True, help="PR URL")

    p = sub.add_parser("inline", help="发行内评论")
    add_url(p)
    p.add_argument("--file", default="", help="完整文件 path（兼容旧用法）")
    p.add_argument("--file-keyword", default="", help="文件名关键词，自动从 pr-changes 解析 path")
    p.add_argument("--line", type=int, default=0)
    p.add_argument("--line-type", default="ADDED")
    p.add_argument("--text", default="")

    p = sub.add_parser("global", help="发全局评论")
    add_url(p)
    p.add_argument("--text", default="")

    p = sub.add_parser("delete", help="删除评论")
    add_url(p)
    p.add_argument("--comment-id", type=int, default=0)

    p = sub.add_parser("verify", help="验证评论")
    add_url(p)

    p = sub.add_parser("list-paths", help="列出变更文件 path")
    add_url(p)

    return parser.parse_args()


def main():
    args = parse_args()
    if not args.subcmd:
        _log("用法: python3 cr_comment.py <inline|global|delete|verify|list-paths> [参数...]")
        sys.exit(1)

    try:
        client = CommentClient()
        if args.subcmd == "inline":
            client.send_inline(args.url, file_keyword=args.file_keyword, file=args.file,
                               line=args.line, line_type=args.line_type, text=args.text)
        elif args.subcmd == "global":
            client.send_global(args.url, args.text)
        elif args.subcmd == "delete":
            client.delete(args.url, args.comment_id)
        elif args.subcmd == "verify":
            client.verify(args.url)
        elif args.subcmd == "list-paths":
            client.list_paths(args.url)
    except CommentError as e:
        _log(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
