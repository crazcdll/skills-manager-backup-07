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
    """返回 code_cli.py 路径（三级回退：同目录 → SKILL_DIR → EFS 原始 skill 目录）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    # 1) 本脚本同目录（scripts/，正常情况）
    primary = os.path.join(here, "code_cli.py")
    if os.path.isfile(primary):
        return primary
    # 2) SKILL_DIR 环境变量指向原始 skill 根目录
    cands = [os.path.join(os.environ.get("SKILL_DIR", ""), "scripts", "code_cli.py")]
    # 3) EFS 原始 skill 目录（平台解包位置，勿在只读 EFS 上打补丁，用原路径执行）
    import glob
    cands += sorted(glob.glob(
        "/efs/data/tenants/*/skills/ai-quality-cr-agent/scripts/code_cli.py"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise CommentError(
        f"code_cli.py 定位失败：本目录({here})无 code_cli.py，且 SKILL_DIR 环境变量与 "
        f"/efs/data/tenants/*/skills/ai-quality-cr-agent/scripts/ 均未找到。"
        "可能原因：脚本被单独复制到其他目录。可操作指引：①设置 SKILL_DIR 环境变量指向 "
        "skill 根目录后重试；②直接用原始 skill 路径执行本脚本（EFS 为只读，勿在其上打补丁；"
        "目录可能随平台解包变化，建议用 glob 或 SKILL_DIR 定位而非写死单一路径）。")


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
        """从 pr-changes 解析 keyword → 完整 path。

        分级匹配（精确优先，消除多候选弃权）：
          1. 精确（path == keyword）
          2. 路径后缀（path.endswith("/" + keyword)）
          3. basename（os.path.basename(path) == keyword）
          4. 子串包含（keyword in path，原逻辑）
        每级唯一命中即返回；子串级 0/多命中抛 CommentError（歧义弃权）。
        """
        ok, out = self._run_with_retry(
            ["pr-changes", "--url", pr_url], label="pr-changes(路径解析)"
        )
        if not ok:
            raise CommentError(f"pr-changes 失败，无法解析路径: {out[:300]}")

        data = parse_json_output(out)
        if not isinstance(data, dict):
            raise CommentError(f"pr-changes 返回非 JSON 对象，无法解析路径: {out[:300]}")

        # 文件列表不完整（翻页安全阀/完整性未证明）时不得做
        # 唯一性判定——缺失页可能包含另一候选，「局部唯一」不等于「全量唯一」，
        # 按歧义失败处理（caller 兜底全局，不盲发到可能错误的文件）
        if data.get("truncated") or data.get("incomplete"):
            raise CommentError(
                "pr-changes 文件列表不完整（"
                + str(data.get("truncatedNote") or data.get("incompleteNote")
                      or "分页完整性未证明")
                + "），无法安全解析路径关键词，本条评论按失败处理")

        changes = data.get("changes", []) or []
        paths = [c.get("path", "") for c in changes]
        kw = (keyword or "").strip()
        if not kw:
            raise CommentError("路径解析关键词为空")

        for label, matcher in (
            ("精确", lambda p: p == kw),
            ("路径后缀", lambda p: p.endswith("/" + kw)),
            ("basename", lambda p: os.path.basename(p) == kw),
            ("子串", lambda p: kw in p),
        ):
            hits = [p for p in paths if p and matcher(p)]
            if len(hits) == 1:
                self.log(f"🔍 路径解析（{label}）：'{kw}' → '{hits[0]}'")
                return hits[0]
            if len(hits) > 1 and label == "子串":
                raise CommentError(
                    f"关键词 '{keyword}' 匹配到多个文件，请使用更精确的关键词：\n"
                    + "\n".join(f"  {h}" for h in hits)
                )
            # 高级别 0 命中或多命中 → 降级到下一级再试

        if not any(kw in (p or "") for p in paths):
            all_paths = "\n".join(f"  {p}" for p in paths)
            raise CommentError(
                f"在 pr-changes 中找不到包含关键词 '{keyword}' 的文件\n📋 所有变更文件：\n{all_paths}"
            )
        # 理论不可达（子串级已处理 0/多命中）；防御性兜底
        hits = [p for p in paths if kw in (p or "")]
        raise CommentError(
            f"关键词 '{keyword}' 匹配到多个文件，请使用更精确的关键词：\n"
            + "\n".join(f"  {h}" for h in hits)
        )

    # ─── 业务操作（库接口）─────────────────────────────────────────────────────
    def send_inline(self, pr_url, file_keyword="", file="", line=0,
                    line_type="ADDED", text="", expected_from_hash=None,
                    expected_to_hash=None, expected_from=None,
                    expected_to=None):
        """发行内评论。成功返回 comment_id，失败抛 CommentError。
        file_keyword 优先；其次用 file 传完整 path。

        expected_from_hash/expected_to_hash（可选，冻结的 diff 基准 hash；
        亦接受 expected_from/expected_to 别名）：
          传入时底层 comment-add 发送前重新读 pr-changes 比对，不一致显式失败
          （不盲发）。仅是发送前比对（compare preflight），不构成原子保证。
        发送超时/网络异常：底层不盲目重发 POST，先回读匹配；未命中则本层
          不再重试（避免重复评论），抛 CommentError 并带 unknown 标记，
          由 caller 兜底（如降级全局评论），不静默丢弃。
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
        ef = str(expected_from_hash or expected_from or "").strip() or None
        et = str(expected_to_hash or expected_to or "").strip() or None
        if ef:
            cli_args += ["--expected-from", ef]
        if et:
            cli_args += ["--expected-to", et]
        # 写操作不重试：POST 非幂等，重发可能产生重复评论；
        # 超时/网络异常由底层回读匹配处理，未命中抛异常交 caller 兜底
        # _run_code_cli 返回 (returncode, output)：returncode==0 才是成功
        rc, out = self._run_code_cli(
            cli_args, label=f"行内评论 {file_path}:{line}"
        )
        if rc != 0:
            raise CommentError(f"行内评论发送失败: {out[:300]}")

        data = parse_json_output(out)
        comment_id = ""
        ok_flag = ""
        unknown = False
        if isinstance(data, dict):
            comment_id = str(data.get("id", "") or "")
            ok_flag = str(data.get("ok", ""))
            unknown = bool(data.get("unknown"))

        if unknown:
            # 发送结果未知且回读未命中：不重发、不静默丢弃，交 caller 兜底
            raise CommentError(
                f"行内评论发送结果未知（超时/网络异常，回读未命中同锚点同正文评论），"
                f"未自动重发以避免重复评论，请人工核验后兜底处理: {out[:300]}")

        if ok_flag.lower() == "true" and comment_id:
            # 如实播报锚点回读核验结果。语义区分（避免过度拒绝）：
            #   - readError 含「命中但锚点不符」→ 双通道都确证评论锚点与请求
            #     不符，评论已写入但锚在错误位置 → 按失败处理，caller 兜底
            #     全局（commentId 随异常携带供人工核验/删除）
            #   - 其余 anchorVerified=false（回读失败/未找到/分页截断）→ 回读
            #     不可用，未证实锚错 → 正常返回，仅日志告警
            _av = data.get("anchorVerified")
            if _av is True:
                self.log(f"✅ 行内评论发送成功（id={comment_id}），锚点回读核验通过: {file_path}:{line}")
                return comment_id
            if _av is False:
                _are = str(data.get("anchorReadError") or "")
                if "锚点不符" in _are:
                    self.log(f"⚠️  行内评论已发送（id={comment_id}），但锚点回读核验未通过"
                             f"（{_are[:200]}），按失败兜底处理")
                    raise CommentError(
                        f"行内评论锚点回读核验未通过（commentId={comment_id}，"
                        f"{_are[:150]}），评论已写入但锚定位置与请求不符，"
                        "请兜底全局并人工核验")
                self.log(f"⚠️  行内评论发送成功（id={comment_id}），已请求锚定到 "
                         f"{file_path}:{line}（回读核验不可用：{_are[:150] or '未找到该评论'}）")
                return comment_id
            self.log(f"✅ 行内评论发送成功（id={comment_id}），已请求锚定到 {file_path}:{line}（回读核验不可用）")
            return comment_id
        raise CommentError(f"行内评论发送失败，返回: {out[:300]}")

    def send_global(self, pr_url, text):
        """发全局评论。成功返回 comment_id（id 非空才算业务成功），失败抛 CommentError。

        发送超时/网络异常：底层不盲目重发 POST，先回读匹配同正文无锚点评论；
        未命中抛 CommentError（unknown），由 caller 兜底，不静默丢弃。
        发送成功后底层按 id 回读 activities 核验存在性；读取不可用时如实
        log 警告，不冒充已验证。
        """
        if not text:
            raise CommentError("global 需要 text 参数")
        self.log("📝 发全局评论")
        # 写操作不重试：POST 非幂等，重发可能产生重复评论
        # _run_code_cli 返回 (returncode, output)：returncode==0 才是成功
        rc, out = self._run_code_cli(
            ["comment-add", "--url", pr_url, "--text", text], label="全局评论"
        )
        if rc != 0:
            raise CommentError(f"全局评论发送失败: {out[:300]}")
        # 退出码为 0 不代表成功：需校验业务返回（id 非空才算业务成功）
        data = parse_json_output(out)
        comment_id = ""
        ok_flag = ""
        unknown = False
        if isinstance(data, dict):
            comment_id = str(data.get("id", "") or "")
            ok_flag = str(data.get("ok", ""))
            unknown = bool(data.get("unknown"))
        if unknown:
            raise CommentError(
                f"全局评论发送结果未知（超时/网络异常，回读未命中同正文评论），"
                f"未自动重发以避免重复评论，请人工核验后兜底处理: {out[:300]}")
        if ok_flag.lower() == "true" and comment_id:
            # 回读核验结果如实报告（code_cli 层已按 id 回读 activities）
            if data.get("globalReadError"):
                self.log(f"⚠️  全局评论回读核验不可用: {str(data.get('globalReadError'))[:200]}")
            elif data.get("globalVerified") is False:
                self.log("⚠️  全局评论回读未确认，不声称已验证")
            self.log(f"✅ 全局评论发送成功（id={comment_id}）")
            return comment_id
        raise CommentError(f"全局评论发送失败，返回: {out[:300]}")

    def delete(self, pr_url, comment_id):
        """删除评论。成功返回 True，失败抛 CommentError。"""
        if not comment_id:
            raise CommentError("delete 需要 comment_id 参数")
        self.log(f"🗑️  删除评论 #{comment_id}")
        ok, out = self._run_with_retry(
            ["comment-delete", "--url", pr_url, "--comment-id", str(comment_id)],
            label=f"删除评论 #{comment_id}",
        )
        if not ok:
            raise CommentError(f"删除失败: {out[:300]}")
        # 退出码为 0 不代表成功：需校验业务返回（与 send_inline 同一模式）
        data = parse_json_output(out)
        ok_flag = ""
        if isinstance(data, dict):
            ok_flag = str(data.get("ok", ""))
        if ok_flag.lower() == "true":
            self.log("✅ 删除成功")
            return True
        raise CommentError(f"删除失败，返回: {out[:300]}")

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
    p.add_argument("--expected-from", default=None, help="冻结的 fromHash（发送前比对，不一致拒绝发送）")
    p.add_argument("--expected-to", default=None, help="冻结的 toHash（发送前比对，不一致拒绝发送）")
    p.add_argument("--expected-from-hash", dest="expected_from", default=None, help="同 --expected-from（别名，供 publish agent 传冻结基准）")
    p.add_argument("--expected-to-hash", dest="expected_to", default=None, help="同 --expected-to（别名，供 publish agent 传冻结基准）")

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
                               line=args.line, line_type=args.line_type, text=args.text,
                               expected_from_hash=args.expected_from,
                               expected_to_hash=args.expected_to)
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
