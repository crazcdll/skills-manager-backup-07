#!/usr/bin/env python3
"""在同一仓库版本列举、读取自定义规则，写入规则缓存与回执。

Step 4-C 使用 --branch；交给 FE 的规则使用 --fe-snapshot，从本轮
mode_info.json 取已冻结的源提交。两种结果分开存放，不消费 spec 搜索结果。
退出码：0 完成（含无规则）；2 输入无效；3 获取未完成（回执保留失败与已读文件）。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import repo_search

RULE_PATH_PREFIXES = (".mdp/rules/team/", ".mdp/rules/project/", ".catpaw/rules/")


def _fe_source_commit(snapshot_path, run_dir, repo, pr_id):
    if not snapshot_path or not pr_id:
        raise ValueError("FE 规则需要本轮目录中的范围文件和 PR ID")
    path = Path(snapshot_path).resolve()
    if path.parent != run_dir:
        raise ValueError("FE 规则需要本轮目录中的范围文件和 PR ID")
    info = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(info, dict):
        raise ValueError("本轮范围文件必须是 JSON 对象")
    if (f"{info.get('org')}/{info.get('repo')}".lower() != repo.lower()
            or str(info.get("prId")) != pr_id):
        raise ValueError("范围文件的仓库或 PR ID 与本轮不一致")
    commit = info.get("targetCommit")
    if (info.get("snapshotStatus") != "sampled-consistent"
            or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit)):
        raise ValueError("FE 规则需要通过范围校验的完整源提交 ID")
    return commit.lower()


def _is_index_file(lines):
    """references/rule-reference-resolution.md 的索引文件判定。"""
    nonempty = [l for l in lines if l.strip()]
    if not nonempty or len(lines) > 50:
        return False
    headings = [l for l in nonempty if l.strip().startswith("#")]
    body = [l for l in nonempty if l not in headings]
    if not body:
        return False
    pathish = [l for l in body
               if "/" in l.strip() and l.strip().endswith(".md")]
    return len(pathish) / len(body) >= 0.8


def _extract_ref_paths(lines):
    """从索引文件行提取引用路径(仓库内相对路径,支持 ../ 与子目录)。"""
    paths = []
    for line in lines:
        s = line.strip()
        if s.startswith("- "):
            s = s[2:].strip()
        elif s and s[0].isdigit() and ". " in s[:4]:
            s = s.split(". ", 1)[1].strip()
        if s.startswith("#") or not s:
            continue
        if "/" in s and s.endswith(".md"):
            paths.append(s)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo", required=True, help="ORG/REPO")
    parser.add_argument("--pr-id", default="")
    refs = parser.add_mutually_exclusive_group()
    refs.add_argument("--branch", help="Step 4-C 使用的目标分支（默认 master）")
    refs.add_argument("--fe-snapshot", help="FE 委托使用本轮 mode_info.json 的源提交")
    parser.add_argument("--out", default="")
    parser.add_argument("--receipt", default="")
    parser.add_argument("--max-file-bytes", type=int, default=200 * 1024,
                        help="单文件读取上限(默认 200KB)")
    out_args = parser.parse_args(argv)

    run_dir = Path(out_args.run_dir).resolve()
    repo = out_args.repo
    pr_id = out_args.pr_id

    if not run_dir.is_dir():
        print(f"[collect_custom_rules] run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[^/]+/[^/]+", repo) or out_args.max_file_bytes <= 0:
        parser.error("--repo 必须为 ORG/REPO，--max-file-bytes 必须为正整数")
    project, repo_name = repo.split("/", 1)
    try:
        source_commit = (_fe_source_commit(out_args.fe_snapshot, run_dir, repo, pr_id)
                         if out_args.fe_snapshot is not None else None)
    except (OSError, ValueError) as exc:
        print(f"[collect_custom_rules] FE 范围文件无效: {exc}", file=sys.stderr)
        return 2
    branch = None if source_commit else (out_args.branch or "master")
    ref = source_commit or branch
    if source_commit:
        default_out, default_receipt = run_dir / "fe_custom_rules.md", run_dir / "fe_rule_harvest.json"
    else:
        default_out, default_receipt = run_dir / "custom_rules.md", run_dir / "rule_harvest.json"
    out_path = Path(out_args.out) if out_args.out else default_out
    receipt_path = Path(out_args.receipt) if out_args.receipt else default_receipt

    # 完整文件清单和正文都使用同一 ref；不依赖其他查询恰好留下的结果。
    rule_files = []
    discovery_error = ""
    try:
        cookies = repo_search.get_cookies()
        paths = repo_search.list_repo_files(project, repo_name, ref, cookies, exts=(".md",))
        rule_files = sorted({path for path in paths if path.startswith(RULE_PATH_PREFIXES)})
    except (repo_search.RepoSearchError, OSError) as exc:
        discovery_error = str(exc) or type(exc).__name__
    except SystemExit:
        discovery_error = "无法获取仓库读取凭据"

    failed = [{"stage": "list", "error": discovery_error}] if discovery_error else []

    def read_rule(fpath):
        try:
            text = "\n".join(repo_search.read_repo_file_lines(project, repo_name, ref, fpath, cookies))
            if len(text.encode("utf-8")) > out_args.max_file_bytes:
                raise repo_search.RepoSearchError(f"规则文件超过 {out_args.max_file_bytes} 字节上限")
            return text, ""
        except (repo_search.RepoSearchError, UnicodeError) as exc:
            return "", str(exc) or type(exc).__name__

    merged = []
    resolved_from_index = []
    visited = set(rule_files)
    for fpath in rule_files:
        text, err = read_rule(fpath)
        if err:
            failed.append({"stage": "read", "file": fpath, "error": err})
            continue
        if not text.strip():
            # 全空文本:记录但不注入
            continue
        merged.append((fpath, text))
        # 3) 索引文件判定 → 解析引用
        lines = text.splitlines()
        if _is_index_file(lines) and (fpath.startswith(".mdp/rules/team/")
                                      or fpath.startswith(".mdp/rules/project/")):
            for reference_path in _extract_ref_paths(lines):
                # 越界检查必须在归一化前执行：normpath 会把 "docs/../../x.md"
                # 折叠成 "../x.md"，再去 "./" 前缀会把 ".." 一并剥掉，防线失效
                if reference_path.startswith(("/", "\\")):
                    continue
                ref_norm = os.path.normpath(reference_path)
                if ref_norm.startswith("..") or os.path.isabs(ref_norm):
                    continue
                # 语义正确的去前缀：只剥 "./" 前缀字符串，不按字符集剥离
                # （lstrip("./") 会把 ".knowledge/..." 的前导点也剥掉，导致
                # 仓库相对路径失配、引用规则全部 not found）
                while ref_norm.startswith("./"):
                    ref_norm = ref_norm[2:]
                if ref_norm in visited:
                    continue
                visited.add(ref_norm)
                ref_text, ref_err = read_rule(ref_norm)
                if ref_err:
                    failed.append({"stage": "read", "file": ref_norm, "from": fpath, "error": ref_err})
                    continue
                if ref_text.strip():
                    merged.append((ref_norm, ref_text))
                    resolved_from_index.append({"from": fpath, "to": ref_norm})

    # 4) 写缓存文件
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for fpath, text in merged:
        parts.append(f"## {fpath}\n\n{text}\n")
    header = f"<!-- 本文件由 collect_custom_rules.py 生成;repo={repo};ref={ref} -->\n"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(header + ("\n".join(parts) if parts else ""))

    # 5) 写回执
    receipt = {
        "repo": repo,
        "prId": pr_id,
        "branch": branch,
        "ref": ref,
        "sourceCommit": source_commit,
        "ruleDirs": RULE_PATH_PREFIXES,
        "ruleFilesFound": rule_files,
        "indexResolved": resolved_from_index,
        "ruleFilesLoaded": [f for f, _ in merged],
        "failed": failed,
        "rulesPath": str(out_path),
        "emptyReason": ("" if merged else (
            "rule_discovery_incomplete" if discovery_error else
            "all_found_rule_files_failed" if failed else "all_rule_dirs_searched_empty")),
    }
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)

    print(str(receipt_path))
    return 0 if not failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
