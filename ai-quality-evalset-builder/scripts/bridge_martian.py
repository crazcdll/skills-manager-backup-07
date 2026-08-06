#!/usr/bin/env python3
"""
Martian Code Review Benchmark → AI-CR 评测集格式转换器

仅提取 Keycloak (Java) 子集，转换为 EVAL-MRT-001 ~ EVAL-MRT-NNN 标准格式。

用法:
  # 从本地 clone 的 martian benchmark 仓库转换
  python3 bridge_martian.py \
    --input /tmp/martian-bench/offline/data \
    --output-dir eval/cases \
    --language java \
    --fetch-diff

  # 只生成，不拉取 diff（后续手动补）
  python3 bridge_martian.py \
    --input /tmp/martian-bench/offline/data \
    --output-dir eval/cases \
    --language java

  # 指定 GitHub token（避免 rate limit）
  python3 bridge_martian.py \
    --input /tmp/martian-bench/offline/data \
    --output-dir eval/cases \
    --language java \
    --fetch-diff \
    --github-token $GH_TOKEN
"""

import json
import os
import re
import sys
import time
import argparse
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


# ============================================================
# Severity & Defect Class 映射表
# ============================================================

SEVERITY_MAP = {
    # Martian severity_label → AI-CR Severity
    "bug": "P0",
    "critical": "P0",
    "high": "P0",
    "medium": "P1",
    "performance": "P1",
    "low": "P2",
    "maintainability": "P2",
    "style": "P2",
    "suggestion": "P3",
}

DEFECT_CLASS_MAP = {
    # Martian category → AI-CR defect_class
    "concurrency": "C2",
    "resource_leak": "C3",
    "exception_handling": "C4",
    "security": "C5",
    "memory": "C7",
    "performance": "C6",
    "logic": "C1",
    "bug": "C1",
    "readability": "C7",
    "maintainability": "C7",
    "style": "C7",
}

# 项目 → 语言映射
PROJECT_LANGUAGE = {
    "sentry": "python",
    "grafana": "go",
    "cal.com": "typescript",
    "calcom": "typescript",
    "discourse": "ruby",
    "keycloak": "java",
}


def map_severity(label: str) -> str:
    """将 Martian severity label 映射到 AI-CR severity"""
    if not label:
        return "P1"
    return SEVERITY_MAP.get(label.lower().strip(), "P1")


def map_defect_class(category: str) -> str:
    """将 Martian category 映射到 AI-CR defect_class"""
    if not category:
        return "C1"
    return DEFECT_CLASS_MAP.get(category.lower().strip(), "C1")


def infer_verdict(findings: list) -> str:
    """根据 findings 推断 verdict"""
    severities = [f["severity"] for f in findings]
    if "P0" in severities:
        return "🟠需修复"
    if "P1" in severities:
        return "🟠需修复"
    if severities:
        return "💚通过有建议"
    return "✅通过"


def extract_key_concepts(comment: str, file_path: str = "") -> list:
    """
    从 GT comment 和文件路径中提取 key_concepts（语义匹配锚点）
    优先级：反引号标识符 > CamelCase > snake_case > 错误类型关键词
    """
    concepts = []

    # 1. 反引号内的标识符
    backtick_matches = re.findall(r'`([^`]+)`', comment)
    for m in backtick_matches:
        if len(m) > 2 and len(m) < 60:
            concepts.append(m)

    # 2. CamelCase 标识符
    camel_matches = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', comment)
    concepts.extend(camel_matches)

    # 3. snake_case 标识符
    snake_matches = re.findall(r'\b([a-z]+_[a-z_]+)\b', comment)
    concepts.extend([m for m in snake_matches if len(m) > 4])

    # 4. 错误类型关键词
    error_keywords = [
        "race condition", "deadlock", "null", "NPE", "overflow",
        "injection", "leak", "timeout", "infinite loop", "thread safe",
        "concurrent", "synchroniz", "volatile", "atomic",
        "NullPointerException", "ClassCastException", "IndexOutOfBounds",
    ]
    for kw in error_keywords:
        if kw.lower() in comment.lower():
            concepts.append(kw)

    # 5. 从文件路径提取类名
    if file_path:
        basename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(basename)[0]
        if name_no_ext and len(name_no_ext) > 2:
            concepts.append(name_no_ext)

    # 去重 + 截断到 6 个
    seen = set()
    unique = []
    for c in concepts:
        c_lower = c.lower()
        if c_lower not in seen:
            seen.add(c_lower)
            unique.append(c)
    return unique[:6]


def detect_project(repo: str) -> str:
    """从 repo 路径推断项目名"""
    repo_lower = repo.lower()
    for project in PROJECT_LANGUAGE:
        if project in repo_lower:
            return project
    return "unknown"


def fetch_pr_diff(repo: str, pr_number: int, token: str = None) -> Optional[str]:
    """从 GitHub API 拉取 PR diff"""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "AI-CR-Evaluator/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 403:
            print(f"  ⚠️ Rate limited, waiting 60s...")
            time.sleep(60)
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=30) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except Exception:
                pass
        print(f"  ❌ Failed to fetch diff for {repo}#{pr_number}: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Failed to fetch diff for {repo}#{pr_number}: {e}")
        return None


def load_martian_data(input_path: str) -> list:
    """
    加载 Martian benchmark 数据。
    支持两种格式：
    1. 单个 JSON 文件（dashboard.json 或 prs.json）
    2. 目录（包含多个 JSON 文件）
    """
    input_path = Path(input_path)
    all_prs = []

    if input_path.is_file():
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_prs = data
        elif isinstance(data, dict):
            # 可能是 {"prs": [...]} 或 {"results": [...]} 格式
            for key in ["prs", "results", "data", "items"]:
                if key in data and isinstance(data[key], list):
                    all_prs = data[key]
                    break
            if not all_prs:
                all_prs = [data]
    elif input_path.is_dir():
        # 遍历目录下所有 JSON 文件
        for json_file in sorted(input_path.glob("**/*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    all_prs.extend(data)
                elif isinstance(data, dict):
                    # 检查是否有嵌套数组
                    for key in ["prs", "results", "data", "items"]:
                        if key in data and isinstance(data[key], list):
                            all_prs.extend(data[key])
                            break
                    else:
                        all_prs.append(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    else:
        print(f"❌ Input path not found: {input_path}")
        sys.exit(1)

    return all_prs


def transform_one(pr_data: dict, eval_id: str, diff: Optional[str] = None) -> dict:
    """将单条 Martian PR 数据转换为标准 EvalCase（input.json + ground_truth.json）"""

    repo = pr_data.get("repo", "")
    pr_number = pr_data.get("pr_number") or pr_data.get("number")
    pr_id = pr_data.get("id", "")
    title = pr_data.get("title", "") or pr_data.get("description", "") or f"PR#{pr_number}"
    project = detect_project(repo)
    language = PROJECT_LANGUAGE.get(project, "java")

    # 构建 input.json
    input_data = {
        "$schema": "../../schema/input.schema.json",
        "eval_id": eval_id,
        "title": title,
        "repo": repo,
        "pr_number": pr_number,
        "pr_url": f"https://github.com/{repo}/pull/{pr_number}" if repo and pr_number else None,
        "cr_doc_url": None,
        "diff": diff,
        "source": "external",
        "dataset": "martian",
        "dataset_id": pr_id or f"{repo}-{pr_number}",
        "dataset_version": "2026-02",
        "language": language,
        "project": project,
        "repo_url": f"https://github.com/{repo}" if repo else None,
    }

    # 构建 ground_truth.json
    gt_comments = pr_data.get("ground_truth_comments", []) or pr_data.get("golden_comments", []) or []
    findings = []
    for i, gt in enumerate(gt_comments, 1):
        severity_label = gt.get("severity_label", "") or gt.get("severity", "")
        category = gt.get("category", "") or gt.get("type", "")
        comment_text = gt.get("comment", "") or gt.get("text", "") or gt.get("description", "")
        file_path = gt.get("file", "") or gt.get("path", "")

        finding = {
            "id": f"F{i:03d}",
            "severity": map_severity(severity_label),
            "defect_class": map_defect_class(category),
            "context_layer": "L1",
            "file": file_path,
            "line_range": None,
            "description": comment_text[:500],
            "key_concepts": extract_key_concepts(comment_text, file_path),
            "martian_gt_id": gt.get("id", f"gt-{i:03d}"),
        }

        # 尝试提取行号
        line = gt.get("line") or gt.get("line_number")
        if line:
            finding["line_range"] = [int(line), int(line)]

        findings.append(finding)

    ground_truth = {
        "$schema": "../../schema/ground_truth.schema.json",
        "eval_id": eval_id,
        "verdict": infer_verdict(findings),
        "gt_source": "benchmark_verified",
        "annotator": "martian_benchmark",
        "annotated_at": "2026-02-01",
        "confidence": 0.90,
        "findings": findings,
        "expected_absent": [],
    }

    return {
        "input": input_data,
        "ground_truth": ground_truth,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Martian Benchmark → AI-CR 评测集转换器（Java/Keycloak 子集）"
    )
    parser.add_argument("--input", required=True, help="Martian benchmark 数据路径（文件或目录）")
    parser.add_argument("--output-dir", required=True, help="输出目录（eval/cases/）")
    parser.add_argument("--language", default="java", help="筛选语言（默认 java）")
    parser.add_argument("--fetch-diff", action="store_true", help="从 GitHub API 拉取 diff")
    parser.add_argument("--github-token", default=None, help="GitHub Personal Access Token")
    parser.add_argument("--limit", type=int, default=None, help="最多转换 N 条")
    parser.add_argument("--start-index", type=int, default=1, help="EVAL-MRT 起始编号（默认 1）")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写文件")

    args = parser.parse_args()

    # 加载原始数据
    print(f"📦 Loading Martian benchmark data from: {args.input}")
    all_prs = load_martian_data(args.input)
    print(f"   Total PRs loaded: {len(all_prs)}")

    # 筛选目标语言
    target_language = args.language.lower()
    filtered = []
    for pr in all_prs:
        repo = pr.get("repo", "").lower()
        project = detect_project(repo)
        lang = PROJECT_LANGUAGE.get(project, "unknown")
        if lang == target_language:
            filtered.append(pr)

    print(f"   Filtered by language={target_language}: {len(filtered)} PRs")

    if not filtered:
        print("❌ No PRs found for the specified language.")
        print(f"   Available projects: {list(PROJECT_LANGUAGE.items())}")
        sys.exit(1)

    if args.limit:
        filtered = filtered[:args.limit]

    # 转换
    output_dir = Path(args.output_dir)
    results = []
    diff_success = 0
    diff_failed = 0

    for i, pr in enumerate(filtered, args.start_index):
        eval_id = f"EVAL-MRT-{i:03d}"
        repo = pr.get("repo", "")
        pr_number = pr.get("pr_number") or pr.get("number")

        print(f"\n{'─'*60}")
        print(f"  [{eval_id}] {repo}#{pr_number}")

        # 可选拉取 diff
        diff = None
        if args.fetch_diff and repo and pr_number:
            print(f"  🔄 Fetching diff from GitHub...")
            diff = fetch_pr_diff(repo, int(pr_number), args.github_token)
            if diff:
                diff_success += 1
                print(f"  ✅ Diff fetched ({len(diff)} chars)")
            else:
                diff_failed += 1
                print(f"  ⚠️ Diff unavailable, will be null")
            # Rate limit 友好
            time.sleep(1)

        # 转换
        case = transform_one(pr, eval_id, diff)
        results.append(case)

        if not args.dry_run:
            # 写入文件
            eval_dir = output_dir / eval_id
            eval_dir.mkdir(parents=True, exist_ok=True)

            with open(eval_dir / "input.json", "w", encoding="utf-8") as f:
                json.dump(case["input"], f, indent=2, ensure_ascii=False)

            with open(eval_dir / "ground_truth.json", "w", encoding="utf-8") as f:
                json.dump(case["ground_truth"], f, indent=2, ensure_ascii=False)

            print(f"  ✅ Written to {eval_dir}/")
        else:
            gt_count = len(case["ground_truth"]["findings"])
            print(f"  [DRY RUN] Would write {eval_id}/ ({gt_count} findings)")

    # 汇总
    print(f"\n{'═'*60}")
    print(f"✅ Martian Bridge 完成")
    print(f"   总样本数: {len(results)}")
    print(f"   语言: {target_language}")
    print(f"   项目: {detect_project(filtered[0].get('repo', '')) if filtered else 'N/A'}")
    if args.fetch_diff:
        print(f"   Diff 拉取: {diff_success} 成功 / {diff_failed} 失败")
    total_findings = sum(len(r["ground_truth"]["findings"]) for r in results)
    print(f"   GT Findings 总数: {total_findings}")

    severity_dist = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for r in results:
        for f in r["ground_truth"]["findings"]:
            severity_dist[f["severity"]] = severity_dist.get(f["severity"], 0) + 1
    print(f"   Severity 分布: P0={severity_dist['P0']} P1={severity_dist['P1']} P2={severity_dist['P2']} P3={severity_dist['P3']}")

    if not args.dry_run:
        print(f"\n   输出目录: {output_dir}")
        print(f"   文件: EVAL-MRT-{args.start_index:03d} ~ EVAL-MRT-{args.start_index + len(results) - 1:03d}")


if __name__ == "__main__":
    main()
