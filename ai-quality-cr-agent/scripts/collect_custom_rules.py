#!/usr/bin/env python3
"""程序化收割仓库自定义规则搜索结果,生成 Step 4-C 规则缓存与回执。

消除 LLM 转述环节(150298 故障根因):主 Agent 只负责执行本脚本并粘贴
回执,不再解读 search_*/result.json、不再转述结论给 4-C 子 Agent。

输入:
  --run-dir        CR_RUN_DIR(必须存在;repo_search_json.py 的 search_*/query 目录在此)
  --repo           ORG/REPO(必须;用于调 repo_search.py 读取规则文件内容)
  --branch         目标分支(默认 master;与搜索时一致)
  --out            规则缓存输出路径(默认 /tmp/cr_custom_rules_{prId}.md;
                   使用默认路径时 prId 从 --pr-id 读取)

行为:
  1. 扫描 run_dir 下所有 search_*/result.json(有效 JSON 数组且结构校验通过)
  2. 从每个 result.json 的 file 字段筛选规则路径:
     .mdp/rules/team/** .mdp/rules/project/** .catpaw/rules/**
  3. 按路径去重,调 repo_search.py -k "任意行" 精确读取全文(见 _fetch_rule_content)
  4. 索引文件判定(≤50 行且 ≥80% 为路径行)→ 解析引用路径,递归读取目标文件
  5. 合并写入 --out(每个文件前加 `## <路径>` 分隔标题),并输出 machine-readable
     回执 rule_harvest.json 到 --receipt(默认 <run_dir>/rule_harvest.json)
  6. stdout 打印回执 JSON 路径(与 repo_search_json.py 风格一致),exit code:
     0 = 成功(含 0 文件:输出空缓存,4-C 跳过)
     2 = run_dir 不存在或无有效 search_*/result.json
     3 = 规则文件内容读取失败(部分失败:failed 列表,成功部分仍写入)

零 LLM 参与,确定性采集;读取失败不产出"伪空缓存"——回执 failed 列表
非空时,主 Agent 必须标注"自定义规则检查未完成",不得按无规则处理。
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

RULE_PATH_PREFIXES = (".mdp/rules/team/", ".mdp/rules/project/", ".catpaw/rules/")
# 3C 搜索目录与规则前缀的映射(来源 A 搜索的 7 个目录中,3 个是规则目录)
SEARCH_DIR_TO_RULE_PREFIX = {
    ".mdp/rules/team": ".mdp/rules/team/",
    ".mdp/rules/project": ".mdp/rules/project/",
    ".catpaw/rules": ".catpaw/rules/",
}


def _is_valid_result(data):
    """与 repo_search_json.py _validate_results 同构的轻量校验。"""
    if not isinstance(data, list):
        return False
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            return False
        if not isinstance(item.get("hits"), list):
            return False
    return True


def _collect_search_dirs(run_dir):
    """收集 run_dir 下带有效 result.json 的查询目录(含名称,用于关联搜索目录)。"""
    found = []
    for query_dir in sorted(Path(run_dir).glob("search_*")):
        if not query_dir.is_dir():
            continue
        result_file = query_dir / "result.json"
        if not result_file.is_file():
            continue
        try:
            with result_file.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if _is_valid_result(data):
            found.append((query_dir.name, data))
    return found


def _rule_files_from_result(data):
    """从单份 result.json 提取规则路径(去重,按路径排序)。"""
    paths = set()
    for item in data:
        fpath = item.get("file", "")
        for prefix in RULE_PATH_PREFIXES:
            if fpath == prefix.rstrip("/") or fpath.startswith(prefix):
                paths.add(fpath)
                break
    return sorted(paths)


def _fetch_file_content(repo, branch, fpath, fetch_fn):
    """读取仓库文件全文,返回 (text, error);error 非空表示读取失败。"""
    return fetch_fn(repo, branch, fpath)


def _make_fetcher():
    """读取单个仓库文件全文。

    生产模式:调用 repo_search.py(-k "." --regex 只返回非空行,按行号重建全文,
    空行仅是 markdown 排版,丢失不影响规则语义)。
    测试模式:环境变量 CCR_FAKE_REPO_ROOT 指向本地目录,直接读本地文件,
    不调网络(单测用)。
    """
    fake_root = os.environ.get("CCR_FAKE_REPO_ROOT")
    script = SKILL_DIR / "scripts" / "repo_search.py"
    cache = {}

    if fake_root:
        def fetch(repo, branch, fpath):
            key = (repo, branch, fpath)
            if key in cache:
                return cache[key]
            local = Path(fake_root) / fpath
            if not local.is_file():
                cache[key] = ("", f"not found in fake repo root: {fpath}")
                return cache[key]
            cache[key] = (local.read_text(encoding="utf-8"), "")
            return cache[key]
        return fetch

    def fetch(repo, branch, fpath):
        key = (repo, branch, fpath)
        if key in cache:
            return cache[key]
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "-r", repo, "-b", branch,
                 "-k", ".", "--regex", "--path", fpath, "--ext", ".md", "--json"],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            cache[key] = ("", f"timeout reading {fpath}")
            return cache[key]
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").strip().splitlines()
            cache[key] = ("", f"exit {proc.returncode}: {stderr_tail[-1] if stderr_tail else 'unknown'}")
            return cache[key]
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            cache[key] = ("", f"invalid JSON from repo_search for {fpath}")
            return cache[key]
        # 重建全文:按最大行号建行数组,hits 填内容,其余补空行(空行仅排版用,
        # 按行号恢复其位置,保真度足够供规则审查)
        entries = data[0]["hits"] if data and isinstance(data[0].get("hits"), list) else []
        if not entries:
            # 搜索非零退出但 JSON 为空数组:文件可能全空行——视为空文件,不算失败
            cache[key] = ("", "")
            return cache[key]
        max_line = max(h.get("line", 0) for h in entries)
        lines = [""] * max_line
        for h in entries:
            ln = h.get("line", 0)
            if 1 <= ln <= max_line:
                lines[ln - 1] = h.get("text", "")
        cache[key] = ("\n".join(lines), "")
        return cache[key]

    return fetch


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
    parser.add_argument("--branch", default="master")
    parser.add_argument("--out", default="")
    parser.add_argument("--receipt", default="")
    parser.add_argument("--max-file-bytes", type=int, default=200 * 1024,
                        help="单文件读取上限,超出截断(默认 200KB)")
    out_args = parser.parse_args(argv)

    run_dir = Path(out_args.run_dir).resolve()
    repo = out_args.repo
    branch = out_args.branch
    pr_id = out_args.pr_id
    out_path = Path(out_args.out) if out_args.out else Path(
        f"/tmp/cr_custom_rules_{pr_id}.md") if pr_id else Path(
        "/tmp/cr_custom_rules.md")
    receipt_path = Path(out_args.receipt) if out_args.receipt else run_dir / "rule_harvest.json"

    if not run_dir.is_dir():
        print(f"[collect_custom_rules] run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2
    searches = _collect_search_dirs(run_dir)
    if not searches:
        print("[collect_custom_rules] run_dir 下无有效 search_*/result.json;"
              " 若 3C 已执行搜索,请检查 --run-dir 是否为本轮 CR_RUN_DIR", file=sys.stderr)
        return 2

    # 1) 从全部搜索结果中收集规则路径
    rule_files = set()
    search_scanned = []
    for name, data in searches:
        files = _rule_files_from_result(data)
        search_scanned.append({"queryDir": name, "ruleFiles": len(files)})
        rule_files.update(files)

    # 2) 读取规则文件内容
    fetcher = _make_fetcher()
    merged = []          # [(fpath, text, sourceNote)]
    failed = []
    resolved_from_index = []
    pending = sorted(rule_files)
    visited = set(pending)
    while pending:
        fpath = pending.pop(0)
        text, err = fetcher(repo, branch, fpath)
        if err:
            failed.append({"file": fpath, "error": err})
            continue
        if len(text.encode("utf-8")) > out_args.max_file_bytes:
            truncated = text.encode("utf-8")[:out_args.max_file_bytes].decode("utf-8", errors="ignore")
            text = truncated + "\n\n(已截断:单文件超 200KB 上限)"
        if not text.strip():
            # 全空文本:记录但不注入
            continue
        merged.append((fpath, text, "direct"))
        # 3) 索引文件判定 → 解析引用
        lines = text.splitlines()
        if _is_index_file(lines) and (fpath.startswith(".mdp/rules/team/")
                                      or fpath.startswith(".mdp/rules/project/")):
            for ref in _extract_ref_paths(lines):
                # 越界检查必须在归一化前执行：normpath 会把 "docs/../../x.md"
                # 折叠成 "../x.md"，再去 "./" 前缀会把 ".." 一并剥掉，防线失效
                if ref.startswith("/") or ref.startswith("\\"):
                    continue
                ref_norm = os.path.normpath(ref)
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
                ref_text, ref_err = fetcher(repo, branch, ref_norm)
                if ref_err:
                    failed.append({"file": ref_norm, "error": f"index-ref: {ref_err}"})
                    continue
                if ref_text.strip():
                    if len(ref_text.encode("utf-8")) > out_args.max_file_bytes:
                        ref_text = ref_text.encode("utf-8")[:out_args.max_file_bytes].decode("utf-8", errors="ignore") + "\n\n(已截断)"
                    merged.append((ref_norm, ref_text, f"index:{fpath}"))
                    resolved_from_index.append({"from": fpath, "to": ref_norm})

    # 4) 写缓存文件
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for fpath, text, note in merged:
        parts.append(f"## {fpath}\n\n{text}\n")
    header = ("<!-- 本文件由 collect_custom_rules.py 生成于 "
              f"{time.strftime('%Y-%m-%d %H:%M:%S')};repo={repo};branch={branch} -->\n")
    with out_path.open("w", encoding="utf-8") as f:
        f.write(header + ("\n".join(parts) if parts else ""))

    # 5) 写回执
    receipt = {
        "repo": repo,
        "branch": branch,
        "searchesScanned": search_scanned,
        "ruleFilesFound": sorted(rule_files),
        "indexResolved": resolved_from_index,
        "ruleFilesLoaded": [f for f, _, _ in merged],
        "failed": failed,
        "rulesPath": str(out_path),
        "emptyReason": ("" if merged else (
            "all_rule_dirs_searched_empty" if not failed else "all_found_rule_files_failed")),
    }
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)

    print(str(receipt_path))
    return 0 if not failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
