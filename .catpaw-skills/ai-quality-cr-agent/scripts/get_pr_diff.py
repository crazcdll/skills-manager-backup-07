#!/usr/bin/env python3
"""
get_pr_diff.py - 逐文件拉取 PR diff 并拼接写入 /tmp/pr_diff.txt

用法:
  全量: python3 get_pr_diff.py --url "{pr_url}" [--output /tmp/pr_diff.txt] [--max-files 30]
  增量: python3 get_pr_diff.py --url "{pr_url}" --since {40位commit hash}

流程（全量）:
  1. 调用 code_cli.py pr-changes 获取变更文件列表
  2. 逐文件调用 code_cli.py pr-diff 拉取 diff
  3. 拼接写入输出文件

流程（增量，--since 有值时）:
  1. 调用 pr-commits 获取 PR 自己的 commit 链，取 index 0 作为 targetCommit
  2. 校验 --since 的 hash 确实存在于该 commit 链中（否则说明已被 force push 冲掉）
  3. 调用 compare-changes 获取 since→target 之间的变更文件列表
  4. 逐文件调用 compare-diff 拉取 diff
  5. 拼接写入输出文件（格式与全量完全一致，下游无感知）
  任一环节异常 → 降级为全量模式

⚠️ targetCommit 必须取自 pr-commits[0]，不能用 pr-changes 的 toHash。
   toHash 是 PR 的合并点/目标分支侧 hash，不在 PR 自己的 commit 链上，
   用它做 compare 会把目标分支上其他人的提交全部算进增量。

参数:
  --url        PR 页面 URL (必需)
  --output     输出文件路径 (默认 /tmp/pr_diff.txt)
  --max-files  最大拉取文件数 (默认 0=不限制, 用于大 PR 截断)
  --since      基准 commit hash（40位），传入则走增量模式，不传则全量模式（默认）
  --mode-info  模式信息 JSON 输出路径 (默认 /tmp/cr_mode_info.json)
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

# code_cli.py 同目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_CLI = os.path.join(SCRIPT_DIR, "code_cli.py")

HASH_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def run_code_cli(args):
    """调用 code_cli.py 并返回 stdout"""
    cmd = ["python3", CODE_CLI] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"⚠️ code_cli 调用失败: {' '.join(args)}", file=sys.stderr)
        print(f"   stderr: {result.stderr[:200]}", file=sys.stderr)
        return None
    return result.stdout


def run_code_cli_json(args):
    """调用 code_cli.py 并解析 JSON；API 报错（{"error": [...]}）时返回 None"""
    out = run_code_cli(args)
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"⚠️ 返回非 JSON: {out[:200]}", file=sys.stderr)
        return None
    # code_cli 对 API 错误是 exit 0 + {"error": [...]}，必须显式判断
    if isinstance(data, dict) and "error" in data:
        msg = data["error"]
        if isinstance(msg, list) and msg:
            msg = msg[0].get("message", msg[0]) if isinstance(msg[0], dict) else msg[0]
        print(f"⚠️ API 返回错误: {str(msg)[:200]}", file=sys.stderr)
        return None
    return data


def short(h):
    """commit hash 取前 8 位"""
    return (h or "")[:8]


def pr_identity(url):
    match = re.fullmatch(r"/code/repo-detail/([^/]+)/([^/]+)/pr/(\d+)(?:/.*)?", urlsplit(url).path)
    if not match:
        raise ValueError("无法从 PR URL 提取 org/repo/prId")
    return dict(zip(("org", "repo", "prId"), (unquote(value) for value in match.groups())))


def write_mode_info(path, cr_mode, base_commit, target_commit, file_count, commit_count, identity=None, failed_files=None,
                      added_lines=None, removed_lines=None, pr_file_num=None, pr_additions=None, pr_deletions=None,
                      snapshot_to_hash=None, snapshot_from_hash=None, diff_path=None, diff_sha256=None,
                      run_id=None, snapshot_status="pending", snapshot_error=None, compare_from_hash=None,
                      compare_to_hash=None, omitted_files=None):
    """写出模式信息 JSON，供下游播报/发布阶段使用。
    failed_files 非空时写入列表，产出物必须如实标注审查覆盖不完整。

    口径字段（双口径，供 publish_results 双字段写入 cr_result_json.overview）:
      * reviewed_added_lines / reviewed_removed_lines: 本轮实际成功拉取 diff 并审查的
        文件中 + 行 / - 行合计（统计 hunk segments，排除 +++/--- 文件头与 CONTEXT 行）。
        与 fileCount（success_count）同源，是「审查覆盖口径」。
      * pr_file_num / pr_additions / pr_deletions: Code 平台 pr-info 的 PR 级权威规模
        （file_num / additions / deletions 原值）。全量/增量模式下均为 PR 终态全量口径。

    快照契约：snapshotFromHash/snapshotToHash 同源于首次 pr-changes，
    不等同于 targetCommit。compareFromHash/compareToHash 是增量 API 的固定参数。
    diffSha256 仅在前后端点采样一致后绑定真实文件字节；这不是原子保护。
    """
    info = {
        "crMode": cr_mode,
        "baseCommit": base_commit,
        "targetCommit": target_commit,
        "snapshotToHash": snapshot_to_hash,
        "snapshotFromHash": snapshot_from_hash,
        "diffPath": diff_path,
        "diffSha256": diff_sha256,
        "runId": run_id,
        "snapshotStatus": snapshot_status,
        "snapshotError": snapshot_error,
        "compareFromHash": compare_from_hash,
        "compareToHash": compare_to_hash,
        "omittedFiles": omitted_files or [],
        "fileCount": file_count,
        "commitCount": commit_count,
        "failedFiles": failed_files or [],
        "reviewedAddedLines": added_lines,
        "reviewedRemovedLines": removed_lines,
        "prFileNum": pr_file_num,
        "prAdditions": pr_additions,
        "prDeletions": pr_deletions,
        **(identity or {}),
    }
    try:
        with open(path, "w") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"⚠️ 模式信息写入失败 {path}: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    return info


def snapshot_endpoints(data):
    """仅接受同一 pr-changes 响应中的两个完整 hash，不推测端点方向。"""
    if not isinstance(data, dict):
        raise ValueError("pr-changes 响应无有效快照")
    pair = tuple(data.get(key) for key in ("fromHash", "toHash"))
    if not all(isinstance(h, str) and HASH_RE.fullmatch(h) for h in pair):
        raise ValueError("pr-changes 缺少有效 fromHash/toHash")
    return tuple(h.lower() for h in pair)


def count_diff_lines(diff_content):
    """统计单个文件 diff 文本的 +行/-行数。

    规则：仅统计行首恰为一个 +/- 的行（跳过 +++/--- 文件头与 @@ hunk 头）。
    get_pr_diff 拼接的是 code_cli pr-diff 的 unified-like 输出。
    """
    added = removed = 0
    for line in diff_content.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def fetch_pr_info_json(url):
    """调 code_cli pr-info 取 Code 平台权威规模（file_num/additions/deletions）。
    失败返回 None（不阻断主流程，原有字段将回退 Agent 传参口径）。"""
    data = run_code_cli_json(["pr-info", "--url", url])
    if not isinstance(data, dict):
        return None
    return data


def fetch_diffs(url, changes, output, since=None, target=None):
    """逐文件拉取 diff 并拼接写入 output。since 有值走 compare-diff，否则 pr-diff。
    返回 (success_count, fail_count, failed_files, added_total, removed_total)，
    失败文件列表供 mode_info 标注；行数合计为审查覆盖口径（仅成功拉取的文件）。"""
    with open(output, "w") as f:
        f.write("")  # 清空旧文件

    success_count = 0
    fail_count = 0
    failed_files = []
    added_total = 0
    removed_total = 0
    for i, change in enumerate(changes):
        filepath = change.get("path", "")
        change_type = change.get("type", "MODIFY")
        if not filepath:
            continue

        if since:
            # 注意参数方向：--from 传新 commit，--to 传旧 commit（已实测验证）
            cli_args = ["compare-diff", "--url", url, "--file", filepath,
                        "--from", target, "--to", since]
        else:
            cli_args = ["pr-diff", "--url", url, "--file", filepath]

        diff_content = run_code_cli(cli_args)
        # code_cli 对 API 错误返回 exit 0 + JSON（含 "error" 键），
        # 空输出同样无有效内容——两者按成功拼入会让错误 JSON 混入
        # diff 快照（覆盖虚高、无缺口标注、垃圾内容进入模型上下文）。
        # 有效 diff 必须非空且不是错误 JSON（真实 diff 文本不是合法 JSON）。
        _err_json = False
        if diff_content and diff_content.lstrip().startswith("{"):
            try:
                _parsed = json.loads(diff_content)
                _err_json = isinstance(_parsed, dict) and "error" in _parsed
            except (ValueError, TypeError):
                _err_json = False
        if diff_content is None or not (diff_content or "").strip() or _err_json:
            print(f"  [{i+1}/{len(changes)}] ❌ {filepath}（返回为空或错误 JSON）", file=sys.stderr)
            fail_count += 1
            failed_files.append(filepath)
            continue

        # 统计本文件 +行/-行（审查覆盖口径，确定性脚本统计）
        a, r = count_diff_lines(diff_content)
        added_total += a
        removed_total += r

        # 拼接写入
        with open(output, "a") as f:
            f.write(diff_content)
            if not diff_content.endswith("\n"):
                f.write("\n")
            f.write("\n")

        success_count += 1
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(changes)}] ✅ {filepath} ({change_type})")

    return success_count, fail_count, failed_files, added_total, removed_total


# pr-commits 查询条数：需覆盖到基准 commit，太小会把“基准在更早的位置”误判为 force push
COMMIT_QUERY_LIMIT = 200


def fetch_pr_commits(url, limit=COMMIT_QUERY_LIMIT):
    """获取 PR 自己的 commit 链（index 0 为最新）；失败返回空列表。

    一次执行中只调用一次，结果在全量/增量两条路径间复用。
    """
    data = run_code_cli_json(["pr-commits", "--url", url, "--limit", str(limit)])
    if not data:
        return []
    # code_cli 返回 {"total": N, "commits": [...]}；兼容裸列表与原始 values 字段
    if isinstance(data, list):
        commits = data
    else:
        commits = data.get("commits") or data.get("values") or []
    if not isinstance(commits, list):
        return []
    return [c for c in commits if isinstance(c, dict)]


def find_commit_index(commits, target_hash):
    """在 commit 链中定位 hash 的下标；不在链上返回 None。

    index 0 为最新 commit，所以基准 commit 的下标即为其之后的新 commit 数量。
    """
    if not target_hash or not commits:
        return None
    needle = target_hash.lower()
    for idx, c in enumerate(commits):
        full = (c.get("id") or "").lower()
        disp = (c.get("displayId") or "").lower()
        if full == needle or (disp and needle.startswith(disp)):
            return idx
    return None


def walk_incremental_window(pr_commits, since, target_hash):
    """从 head 沿 first-parent 回溯到 since，验证增量窗口提交关系。

    返回 (status, detail)：
      - "ok"      : 窗口干净，可以走增量 compare（detail = 窗口内新提交数）
      - "merge"   : 窗口内含合并提交（len(parents)>=2），树 diff 会混入合入分支的改动
                    （detail = 该提交 displayId）
      - "unknown" : 无法确认窗口（parents 缺失 / 截断 / 走不到 since），不能信任任何下标推断
    不依赖列表排序与下标语义：逐 commit 检查其 first-parent 是否指向下一个已知提交。
    """
    def norm(h):
        return (h or "").lower()

    by_id = {}
    for c in pr_commits:
        cid = norm(c.get("id"))
        if cid:
            by_id[cid] = c

    since_id, head_id = norm(since), norm(target_hash)
    cur, steps, seen = head_id, 0, set()
    while cur and cur != since_id:
        c = by_id.get(cur)
        if c is None:
            # 当前 commit 不在已拉取列表里（截断/异常）：无法继续确认，回退全量
            return ("unknown", "commit %s 不在已拉取的提交列表中" % cur[:12])
        parents = c.get("parents")
        if not isinstance(parents, list) or not parents:
            # parents 字段缺失/为空：无法确认提交关系，回退全量
            return ("unknown", "commit %s 的 parents 缺失" % (c.get("displayId") or cur[:12]))
        if len(parents) >= 2:
            # 合并提交：窗口内出现合并，树 diff 语义不可用
            return ("merge", "%s（合并提交，parents=%d）" % ((c.get("displayId") or cur[:12]), len(parents)))
        nxt = parents[0].get("id") if isinstance(parents[0], dict) else None
        nxt = norm(nxt)
        if not nxt:
            return ("unknown", "commit %s 的 first-parent id 缺失" % (c.get("displayId") or cur[:12]))
        if nxt in seen:
            # 环：异常数据防御，回退全量
            return ("unknown", "提交图出现环路（异常数据）")
        seen.add(nxt)
        cur, steps = nxt, steps + 1
        if steps > len(pr_commits) + 1:
            # 回溯步数超过提交总数：异常，回退全量
            return ("unknown", "回溯步数超出提交总数（异常）")
    if cur != since_id:
        return ("unknown", "无法沿 first-parent 到达基准 commit")
    return ("ok", steps)


def main():
    parser = argparse.ArgumentParser(description="逐文件拉取 PR diff 并拼接写入文件")
    parser.add_argument("--url", required=True, help="PR 页面 URL")
    parser.add_argument("--output", default=None, help="输出文件路径 (默认 /tmp/pr_diff_{org}_{repo}_{prId}.txt)")
    parser.add_argument("--max-files", type=int, default=0, help="最大拉取文件数 (0=不限制)")
    parser.add_argument("--since", default=None,
                        help="基准 commit hash（40位），传入则走增量模式，不传则全量模式（默认）")
    parser.add_argument("--mode-info", default="/tmp/cr_mode_info.json",
                        help="模式信息 JSON 输出路径 (默认 /tmp/cr_mode_info_{org}_{repo}_{prId}.json)")
    parser.add_argument("--run-id", default=None, help="本轮 CR_RUN_ID（标准流程必传）")
    args = parser.parse_args()
    try:
        identity = pr_identity(args.url)
    except ValueError as error:
        parser.error(str(error))
    # 多 PR 并行防串轮：未显式指定输出时按 org_repo_prId 命名，避免共享文件名互相覆盖
    if not args.output:
        args.output = "/tmp/pr_diff_{org}_{repo}_{prId}.txt".format(**identity)
    if args.mode_info == "/tmp/cr_mode_info.json":
        args.mode_info = "/tmp/cr_mode_info_{org}_{repo}_{prId}.json".format(**identity)

    args.output = os.path.abspath(args.output)
    if os.path.realpath(args.output) == os.path.realpath(args.mode_info):
        parser.error("--output 与 --mode-info 不能指向同一文件")
    binding = dict(diff_path=args.output, run_id=args.run_id)
    # 先覆盖旧轮次 metadata；中途失败不得遗留可冒充成功的旧快照。
    write_mode_info(args.mode_info, "full", None, None, 0, None, identity, **binding)

    # Step 1: PR 端点与全量文件列表必须取自同一响应。
    changes_data = run_code_cli_json(["pr-changes", "--url", args.url])
    if not isinstance(changes_data, dict):
        write_mode_info(args.mode_info, "full", None, None, 0, None, identity,
                        snapshot_status="failed", snapshot_error="无法获取 PR 变更文件列表", **binding)
        print("❌ 无法获取 PR 变更文件列表", file=sys.stderr)
        sys.exit(1)
    # 分页完整性消费：truncated（安全阀）/ incomplete（游标异常/isLastPage
    # 缺失）都说明列表未证明完整，不得作为完整审查范围继续（SKILL.md 2D
    # 契约：无法证明 isLastPage 时中止，不以部分列表冒充全量）
    if changes_data.get("truncated") or changes_data.get("incomplete"):
        reason = changes_data.get("truncatedNote") or changes_data.get("incompleteNote") or "文件列表分页完整性未证明"
        write_mode_info(args.mode_info, "full", None, None, 0, None, identity,
                        snapshot_status="failed", snapshot_error=f"文件列表不完整: {reason}", **binding)
        print(f"❌ 文件列表不完整（{reason}），禁止以部分列表继续 CR", file=sys.stderr)
        sys.exit(4)
    try:
        before = snapshot_endpoints(changes_data)
    except ValueError as error:
        write_mode_info(args.mode_info, "full", None, None, 0, None, identity,
                        snapshot_status="failed", snapshot_error=str(error), **binding)
        print(f"❌ 快照取证失败: {error}", file=sys.stderr)
        sys.exit(4)
    binding.update(snapshot_from_hash=before[0], snapshot_to_hash=before[1])

    total_files = changes_data.get("totalFiles", 0)
    changes = changes_data.get("changes", [])

    # Step 1.5: 获取 PR 自己的 commit 链，取 index 0 作为 targetCommit
    # ⚠️ 不能用 pr-changes 的 toHash：那是合并点/目标分支侧的 hash，
    #    不在 PR 的 commit 链上，用作 compare 端点会混入目标分支上其他人的提交。
    #    全量模式下这个值会被写进 PR 评论作为下次增量 CR 的基准，同样不能取错。
    pr_commits = fetch_pr_commits(args.url)
    if pr_commits:
        target_hash = pr_commits[0].get("id")
        # 📌 尽早落盘 targetCommit，确保后续步骤即使超时/出错，
        #    publish_results.py 也能读到基准 commit
        write_mode_info(args.mode_info, "full", None, target_hash, 0, None, identity,
                        **binding)
    else:
        target_hash = None
        print("⚠️ 无法获取 PR commit 列表，targetCommit 置空")

    # ── 增量模式判定 ──
    since = args.since
    incremental = False
    commit_count = None

    if since:
        since = since.strip()
        base_idx = find_commit_index(pr_commits, since)
        if not HASH_RE.match(since):
            print(f"⚠️ 降级为全量模式：基准 commit 格式非法（需 40 位十六进制）: {since[:60]}")
            since = None
        elif not target_hash:
            # 没有可靠的 target 就无法算增量，必须降级
            print("⚠️ 降级为全量模式：无法获取当前最新 commit")
            since = None
        elif base_idx is None:
            # 比 compare API 报错更早、更准确的兜底：发出错误请求前就拦住
            print(f"⚠️ 基准 commit 不在最近 {COMMIT_QUERY_LIMIT} 个 commit 中"
                  f"（可能已被 force push 覆盖，或 PR commit 数超出查询范围），降级为全量模式")
            since = None
        elif since.lower() == target_hash.lower():
            print("⚠️ 基准 commit 与当前最新 commit 相同，无新提交")
            # 写空 diff + 模式信息，并以非 0 退出码让调用方感知
            with open(args.output, "w") as f:
                pass
            write_mode_info(args.mode_info, "incremental", since, target_hash, 0, 0, identity,
                            snapshot_status="no-new-commits", **binding)
            print(f"✅ 空 diff 已写入 {args.output} (0 个文件)")
            sys.exit(2)
        else:
            # ── 增量窗口合并提交检测 ──
            # 从 head 沿 first-parent 回溯到 since，验证提交关系。
            # 动机：compare 是两 commit 树 diff，窗口内含合并提交时会把合入分支
            #（如 master）上其他人的改动一并计入，导致 CR 审到别人的代码。
            # 实测案例：web/foodtrade-calc PR217 第4轮（fe1fd68→075dee7）混入
            # master 侧 20 个文件。全量 pr-changes 是 merge-base 净差语义，干净。
            status, detail = walk_incremental_window(pr_commits, since, target_hash)
            if status == "merge":
                print(f"⚠️ 检测到增量窗口包含合并提交（{detail}），已切换 PR 全量净差审查")
                since = None
            elif status == "unknown":
                print(f"⚠️ 增量窗口提交关系无法确认（{detail}），降级为全量模式")
                since = None
            else:
                commit_count = detail

    if since:
        # 注意参数方向：--from 传新 commit，--to 传旧 commit
        cmp_data = run_code_cli_json(["compare-changes", "--url", args.url,
                                      "--from", target_hash, "--to", since])
        if cmp_data is None:
            print("⚠️ compare API 异常（可能是 force push 导致基准 commit 失效），降级为全量模式")
        elif cmp_data.get("truncated") or cmp_data.get("incomplete"):
            # 增量文件列表分页完整性未证明（安全阀/空页非末页/游标
            # 异常/端点漂移）时不得冒充完整增量范围，降级用已校验的全量列表
            _reason = (cmp_data.get("truncatedNote")
                       or cmp_data.get("incompleteNote")
                       or "分页完整性未证明")
            print(f"⚠️ 增量文件列表不完整（{_reason}），降级为全量模式")
        else:
            cmp_changes = cmp_data.get("changes", [])
            if not cmp_changes:
                print("⚠️ 增量范围内无文件变更，降级为全量模式")
            else:
                changes = cmp_changes
                total_files = cmp_data.get("totalFiles", len(cmp_changes))
                incremental = True
                # 新提交数沿用 walk_incremental_window 的回溯步数（已验证父子关系），
                # 不再回退到 find_commit_index 的下标推断，避免依赖列表排序

    if not incremental:
        since = None

    # ── 无变更文件拦截 ──
    # RESCOPED（force push 重算范围）等事件触发的 CR 拿不到有效 diff，
    # 空输入会导致下游误判任务类型（拒绝审查或幻觉审查）。
    # 用专用退出码 3 拦截，调用方必须终止而非降级。
    if not changes:
        print("❌ PR 无变更文件：可能是 RESCOPED/force-push 事件或 diff 获取异常。"
              "拒绝审查，请确认触发事件或手动重新触发 CR", file=sys.stderr)
        with open(args.output, "w") as f:
            pass
        write_mode_info(args.mode_info, "full", None, target_hash, 0, None, identity,
                        snapshot_status="no-changes", **binding)
        sys.exit(3)

    # 截断处理：与 failedFiles 分开标记主动省略的覆盖缺口。
    omitted_files = []
    if args.max_files > 0 and len(changes) > args.max_files:
        print(f"⚠️ 文件数 {len(changes)} 超过上限 {args.max_files}，截断拉取", file=sys.stderr)
        omitted_files = [c.get("path", "") for c in changes[args.max_files:]]
        changes = changes[:args.max_files]

    # ── 播报审查范围 ──
    if incremental:
        cc = commit_count if commit_count is not None else "?"
        print(f"📦 审查范围: 增量（从 {short(since)} → {short(target_hash)}，{cc} 个新 commit，{len(changes)} 个文件）")
    else:
        print(f"📦 审查范围: 全量（{len(changes)} 个文件）")

    # 最终 metadata 仅在成功后盖章；异常退出时保留本轮 pending 而非旧轮成功。
    binding.update(compare_from_hash=target_hash if incremental else None,
                   compare_to_hash=since if incremental else None, omitted_files=omitted_files)
    write_mode_info(args.mode_info, "incremental" if incremental else "full", since,
                    target_hash, 0, commit_count if incremental else None, identity, **binding)

    # Step 2: 逐文件拉取 diff 并拼接（同时确定性统计 +行/-行）
    success_count, fail_count, failed_files, added_total, removed_total = fetch_diffs(
        args.url, changes, args.output, since=since, target=target_hash
    )

    # PR diff 非固定 revision：前后重新读同一端点数据源，漂移不得冒充一致。
    # 固定 compare 也检查 PR 状态，但其 range 单独记录，不能替代 PR snapshot。
    try:
        after = snapshot_endpoints(run_code_cli_json(["pr-changes", "--url", args.url]))
        if before != after:
            raise ValueError(f"PR 端点漂移: {before} -> {after}")
        after_commits = fetch_pr_commits(args.url) if target_hash else []
        if target_hash and (not after_commits or
                            str(after_commits[0].get("id") or "").lower() != target_hash.lower()):
            raise ValueError("PR source head 漂移或复核失败（targetCommit 不再对应本轮 PR）")
        with open(args.output, "rb") as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
            diff_sha256 = digest.hexdigest()
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        write_mode_info(args.mode_info, "incremental" if incremental else "full", since,
                        target_hash, success_count, commit_count if incremental else None, identity,
                        failed_files=failed_files, snapshot_status="failed", snapshot_error=str(error), **binding)
        print(f"❌ 快照校验失败，禁止审查/发布该 diff: {error}", file=sys.stderr)
        sys.exit(4)

    # Step 2.5: 取 Code 平台 PR 级权威规模（平台权威口径三字段数据源；失败不阻断）
    pr_info = fetch_pr_info_json(args.url)
    pr_file_num = None
    pr_additions = None
    pr_deletions = None
    if isinstance(pr_info, dict):
        try:
            pr_file_num = int(pr_info["file_num"])
            pr_additions = int(pr_info["additions"])
            pr_deletions = int(pr_info["deletions"])
        except (KeyError, TypeError, ValueError):
            print("⚠️ pr-info 缺少 file_num/additions/deletions，平台权威口径三字段回退 Agent 传参口径", file=sys.stderr)

    # Step 3: 写模式信息（失败文件列表一并写入，供产出物标注覆盖缺口；
    # 双口径：reviewed*（成功拉取的 diff 行数统计）+ pr*（平台权威值））
    write_mode_info(
        args.mode_info,
        "incremental" if incremental else "full",
        since if incremental else None,
        target_hash,
        success_count,
        commit_count if incremental else None,
        identity,
        failed_files=failed_files,
        added_lines=added_total,
        removed_lines=removed_total,
        pr_file_num=pr_file_num,
        pr_additions=pr_additions,
        pr_deletions=pr_deletions,
        diff_sha256=diff_sha256,
        snapshot_status="sampled-consistent",
        **binding,
    )

    # Step 4: 汇总（失败文件必须在产出物里可见，不能静默丢盖）
    print(f"\n✅ diff 内容已写入 {args.output}")
    print(f"   总文件: {total_files}, 成功: {success_count}, 失败: {fail_count}")
    print(f"   审查覆盖行数: +{added_total} -{removed_total}")
    if pr_file_num is not None:
        print(f"   PR 平台权威规模: {pr_file_num} 文件 +{pr_additions} -{pr_deletions}")
    if fail_count > 0:
        print(f"   ⚠️ 有 {fail_count} 个文件 diff 拉取失败，审查覆盖不完整！"
              "该信息已写入 mode_info 的 failed_files 字段，报告产出物必须如实标注", file=sys.stderr)
    if args.max_files > 0 and total_files > args.max_files:
        print(f"   ⚠️ 已截断: 仅拉取前 {args.max_files} 个文件 (总 {total_files} 个)")
    print(f"   模式信息: {args.mode_info}")


if __name__ == "__main__":
    main()
