#!/usr/bin/env python3
"""
Step 4~6: 采纳信号收集 → 代表性采样 → 输出评测集 JSON

采纳信号三个来源（优先级由高到低）：
  1. PR 行评论 reply（精确到 file+line，最可靠）
  2. PR 全局评论四选标记（精确到 PR 级别）
  3. 学城 CR 文档全文评论（整体采纳，最宽泛）

Usage:
  python3 build_evalset.py --input parsed_findings.json --output-dir <eval-dataset/>
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# === 路径配置 ===
CODE_CLI = "/root/.openclaw/skills/code-cli/scripts/code_cli.py"

# === 配置 ===
TARGET_SAMPLES = 100
MIN_SAMPLES = 80
MAX_SAMPLES = 120
NEEDS_REVIEW_THRESHOLD = 0.7   # 低于此值进 needs_review（无信号 finding 最高 0.65，全进）
AUTO_EXCLUDE_THRESHOLD = 0.3   # 低于此值直接排除（解析完全失败的噪声）
COVERAGE_CELL_LIMIT = 3

DEFECT_CLASSES = ["C1_npe", "C2_resource_leak", "C3_logic_error",
                   "C4_concurrency", "C5_security", "C6_performance", "C7_cross_repo"]
CONTEXT_LAYERS = ["L1_diff_visible", "L2_intra_repo_search", "L3_cross_repo_or_business"]

# 多样性约束（宽松模式，数据量充足后可收紧）
MAX_SAME_TEAM_RATIO = 0.60      # 单团队最多占比 60%
MAX_SAME_REPO_COUNT = 10        # 单仓库最多贡献 10 条 PR
MIN_TEAM_COUNT = 3              # 至少覆盖 3 个不同团队

# 行评论 reply 采纳关键词
ACCEPT_REPLY_PATTERNS = re.compile(
    r'(?:已修|已修复|已改|ok|done|fix|fixed|lgtm|采纳|确认|是的|对的|好的|收到|已处理|已优化|👍|✅)',
    re.IGNORECASE
)
REJECT_REPLY_PATTERNS = re.compile(
    r'(?:误报|不是问题|不影响|可以不改|这里没问题|不需要|不用改|逻辑正确|预期行为)',
    re.IGNORECASE
)

# 学城文档评论采纳关键词
DOC_ACCEPT_PATTERNS = re.compile(
    r'(?:已修复|已采纳|已处理|已改|全部修复|都改了|fix完了|处理完了)',
    re.IGNORECASE
)

# 四选标记（PR 全局评论）
FOUR_CHOICE_MARKS = {
    "✅已采纳": ("explicit_accept", 0.95, +50),
    "✅ 已采纳": ("explicit_accept", 0.95, +50),
    "❌误报": ("fp", 0.90, +25),
    "❌ 误报": ("fp", 0.90, +25),
    "⚠️规则太严": ("fp_disputed", 0.40, 0),
    "⚠️ 规则太严": ("fp_disputed", 0.40, 0),
    "⏭暂不修复": ("deferred", 0.60, 0),
    "⏭ 暂不修复": ("deferred", 0.60, 0),
}


# ============================================================
# 工具函数
# ============================================================

def run_code_cli(*args, timeout=30) -> Optional[str]:
    try:
        result = subprocess.run(
            ["python3", CODE_CLI, *args],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None


def run_citadel(*args, timeout=30) -> Optional[str]:
    try:
        result = subprocess.run(
            ["oa-skills", "citadel", *args],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None


def normalize_file(path: str) -> str:
    """统一文件路径格式，去掉仓库根前缀，只保留 src/... 部分"""
    if not path:
        return ""
    # 去掉 a/ b/ 前缀（diff 格式）
    path = re.sub(r'^[ab]/', '', path)
    return path.strip()


def lines_overlap(range1: Optional[list], line2: Optional[int], flex: int = 5) -> bool:
    """判断行号 line2 是否在 range1 ± flex 范围内"""
    if not range1 or not line2:
        return False
    low, high = range1[0] - flex, range1[1] + flex
    return low <= line2 <= high


# ============================================================
# 信号来源 1：PR 行评论 reply（精确到 file+line）
# ============================================================

def _extract_inline_signals(raw: str) -> List[Dict]:
    """
    从已拉取的 PR 评论原始输出中解析行评论 reply 信号。
    """
    if not raw:
        return []

    signals = []
    # code_cli 输出是 JSON 数组 或 文本，尝试 JSON 解析
    try:
        comments = json.loads(raw)
    except json.JSONDecodeError:
        # 文本格式：逐行解析（兜底）
        return _parse_text_comments(raw)

    for comment in comments:
        # 只处理 AI-CR bot 发的行内评论
        author = (comment.get("author", {}) or {}).get("slug", "")
        if "ai" not in author.lower() and "cr" not in author.lower() and "bot" not in author.lower():
            # 也处理无 author 限制（有 file+line 的评论都要看）
            pass

        file_path = normalize_file(
            (comment.get("anchor", {}) or {}).get("path", "") or
            comment.get("path", "") or ""
        )
        line_num = (
            (comment.get("anchor", {}) or {}).get("line") or
            comment.get("line")
        )

        replies = comment.get("comments", []) or comment.get("replies", []) or []
        for reply in replies:
            reply_author = (reply.get("author", {}) or {}).get("slug", "")
            reply_body = reply.get("text", "") or reply.get("body", "") or ""

            if ACCEPT_REPLY_PATTERNS.search(reply_body):
                signals.append({
                    "file": file_path,
                    "line": line_num,
                    "signal": "inline_accept",
                    "confidence": 0.90,
                    "reply_author": reply_author,
                    "reply_text": reply_body[:100],
                })
            elif REJECT_REPLY_PATTERNS.search(reply_body):
                signals.append({
                    "file": file_path,
                    "line": line_num,
                    "signal": "inline_reject",
                    "confidence": 0.85,
                    "reply_author": reply_author,
                    "reply_text": reply_body[:100],
                })

    return signals


def _parse_text_comments(text: str) -> List[Dict]:
    """兜底：从文本格式评论中提取信号（无精确 file/line）"""
    signals = []
    if ACCEPT_REPLY_PATTERNS.search(text):
        signals.append({"file": None, "line": None, "signal": "text_accept", "confidence": 0.70})
    if REJECT_REPLY_PATTERNS.search(text):
        signals.append({"file": None, "line": None, "signal": "text_reject", "confidence": 0.65})
    return signals


# ============================================================
# 信号来源 2：PR 全局评论四选标记
# ============================================================

def _extract_global_marks(raw: str) -> tuple:
    """
    从已拉取的 PR 评论原始输出中解析四选标记。
    返回 (marks列表, 优先级增量)
    """
    if not raw:
        return [], 0

    marks = []
    score_delta = 0
    for mark, (_, _, delta) in FOUR_CHOICE_MARKS.items():
        if mark in raw:
            marks.append(mark)
            score_delta += delta

    return list(set(marks)), score_delta


# ============================================================
# 信号来源 3：学城 CR 文档全文评论
# ============================================================

def fetch_doc_comment_signal(doc_id: str) -> Optional[str]:
    """
    拉取学城 CR 文档评论，判断是否有整体采纳信号。
    返回 "accept" / "reject" / None
    """
    raw = run_citadel("getAllComments", "--contentId", doc_id)
    if not raw:
        return None

    if DOC_ACCEPT_PATTERNS.search(raw):
        return "accept"
    if REJECT_REPLY_PATTERNS.search(raw):
        return "reject"
    return None


# ============================================================
# Step 4：综合三路信号，更新 finding 的 GT 标注
# ============================================================

def enrich_record(record: Dict) -> Tuple[Dict, List[Dict]]:
    """
    对单条 PR 记录综合三路信号，更新所有 finding 的 ground_truth_source + confidence。
    返回 (更新后的 record, fp_findings)
    """
    pr_url = record.get("pr_url", "")
    doc_id = record.get("cr_doc_id", "")
    findings = record.get("findings", [])

    # --- 拉取 PR 评论（只调一次 API，同时提取行评论和四选标记） ---
    raw_comments = run_code_cli("pr-comments", "--url", pr_url) if pr_url else None

    # --- 信号来源 1: PR 行评论 reply ---
    inline_signals = _extract_inline_signals(raw_comments) if raw_comments else []

    # --- 信号来源 2: PR 全局评论四选标记 ---
    global_marks, score_delta = _extract_global_marks(raw_comments) if raw_comments else ([], 0)
    record["priority_score"] = record.get("priority_score", 0) + score_delta
    record["feedback_marks"] = global_marks

    # --- 信号来源 3: 学城文档评论 ---
    doc_signal = fetch_doc_comment_signal(doc_id) if doc_id else None

    # --- 逐条 finding 更新 ---
    fp_findings = []
    for f in findings:
        f_file = normalize_file(f.get("file", "") or "")
        f_lines = f.get("line_range")

        # 优先级 1：行评论精确匹配
        matched_inline = [
            s for s in inline_signals
            if s.get("file") and f_file and
            (normalize_file(s["file"]) == f_file or
             normalize_file(s["file"]).endswith(f_file) or
             f_file.endswith(normalize_file(s["file"]))) and
            lines_overlap(f_lines, s.get("line"))
        ]

        if matched_inline:
            accept_signals = [s for s in matched_inline if "accept" in s["signal"]]
            reject_signals = [s for s in matched_inline if "reject" in s["signal"]]
            if accept_signals:
                f["ground_truth_source"] = "inline_reply_accept"
                f["confidence"] = max(s["confidence"] for s in accept_signals)
                f["evidence"] = {
                    "signal_type": "inline_reply",
                    "reply_author": accept_signals[0].get("reply_author"),
                    "reply_text": accept_signals[0].get("reply_text"),
                }
                continue
            elif reject_signals:
                f["ground_truth_source"] = "inline_reply_reject"
                f["confidence"] = max(s["confidence"] for s in reject_signals)
                f["is_fp"] = True
                fp_findings.append(f)
                continue

        # 优先级 2：四选标记（PR 级别）
        if any(m in ("✅已采纳", "✅ 已采纳") for m in global_marks):
            f["ground_truth_source"] = "explicit_accept"
            f["confidence"] = max(f.get("confidence", 0), 0.90)
            f["evidence"] = {"signal_type": "four_choice_mark", "mark": "✅已采纳"}
            continue

        if any(m in ("❌误报", "❌ 误报") for m in global_marks):
            f["ground_truth_source"] = "fp"
            f["is_fp"] = True
            f["confidence"] = 0.85
            fp_findings.append(f)
            continue

        # 优先级 3：学城文档整体评论
        if doc_signal == "accept":
            f["ground_truth_source"] = "doc_comment_accept"
            f["confidence"] = max(f.get("confidence", 0), 0.75)
            f["evidence"] = {"signal_type": "doc_comment"}
            continue

        # 无信号：保持 ai_detected，confidence 不变
        f.setdefault("ground_truth_source", "ai_detected")

    # 过滤掉 FP findings
    record["findings"] = [f for f in findings if not f.get("is_fp")]
    return record, fp_findings


def enrich_all(records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    enriched = []
    all_fp = []
    total = len(records)

    for i, record in enumerate(records):
        pr_id = record.get("pr_id", "?")
        print(f"[{i+1}/{total}] PR#{pr_id} ...", end=" ", flush=True)

        updated, fp_findings = enrich_record(record)

        # 统计信号命中情况
        sources = [f.get("ground_truth_source", "ai_detected") for f in updated["findings"]]
        high_conf = sum(1 for f in updated["findings"] if f.get("confidence", 0) >= 0.8)
        marks = updated.get("feedback_marks", [])
        print(f"findings={len(updated['findings'])} high_conf={high_conf} marks={marks or '无'} fp={len(fp_findings)}")

        if fp_findings:
            all_fp.append({**record, "findings": fp_findings})

        if updated["findings"]:
            enriched.append(updated)

    print(f"\n✅ 有效 PR: {len(enriched)}, FP 样本: {len(all_fp)}")
    return enriched, all_fp


# ============================================================
# Step 5: 贪心采样
# ============================================================

def greedy_sample(records: List[Dict]) -> List[Dict]:
    sorted_records = sorted(records, key=lambda x: x.get("priority_score", 0), reverse=True)
    coverage: Dict[str, int] = {}
    selected = []

    # 多样性追踪
    team_counts: Dict[str, int] = {}   # org → count
    repo_counts: Dict[str, int] = {}   # repo_slug → count

    for record in sorted_records:
        if len(selected) >= MAX_SAMPLES:
            break

        findings = [f for f in record.get("findings", [])
                    if f.get("confidence", 0) >= AUTO_EXCLUDE_THRESHOLD]
        if not findings:
            continue

        # 多样性检查
        org = record.get("org", "unknown") or "unknown"
        repo = record.get("repo_slug", "unknown") or "unknown"

        # 单仓库上限
        if repo_counts.get(repo, 0) >= MAX_SAME_REPO_COUNT:
            continue

        # 单团队占比上限（已选 > MIN_SAMPLES 时开始约束）
        if len(selected) >= MIN_SAMPLES:
            max_team_allowed = int(MAX_SAMPLES * MAX_SAME_TEAM_RATIO)
            if team_counts.get(org, 0) >= max_team_allowed:
                continue

        # 缺陷覆盖矩阵检查
        cells = set()
        for f in findings:
            dc = f.get("defect_class", "C3_logic_error")
            cl = f.get("context_layer_required", "L1_diff_visible")
            cells.add(f"{dc}/{cl}")

        has_value = any(coverage.get(c, 0) < COVERAGE_CELL_LIMIT for c in cells)
        if has_value or len(selected) < MIN_SAMPLES:
            for c in cells:
                coverage[c] = coverage.get(c, 0) + 1
            for f in findings:
                f["review_status"] = (
                    "needs_review" if f.get("confidence", 0) < NEEDS_REVIEW_THRESHOLD else "auto"
                )
            record["findings"] = findings
            record["selection_tier"] = _tier(record.get("priority_score", 0))
            selected.append(record)

            # 更新多样性计数
            team_counts[org] = team_counts.get(org, 0) + 1
            repo_counts[repo] = repo_counts.get(repo, 0) + 1

    # 多样性报告
    total_cells = len(DEFECT_CLASSES) * len(CONTEXT_LAYERS)
    filled = len(coverage)
    unique_teams = len(team_counts)
    unique_repos = len(repo_counts)
    top_team = max(team_counts.items(), key=lambda x: x[1]) if team_counts else ("none", 0)

    print(f"\n📊 采样结果:")
    print(f"   PR 数: {len(selected)}")
    print(f"   矩阵覆盖: {filled}/{total_cells} 格")
    print(f"   团队数: {unique_teams} {'✅' if unique_teams >= MIN_TEAM_COUNT else '⚠️ 不足'}")
    print(f"   仓库数: {unique_repos}")
    print(f"   最大团队: {top_team[0]} ({top_team[1]}条, {top_team[1]*100//max(len(selected),1)}%)")

    if unique_teams < MIN_TEAM_COUNT:
        print(f"   ⚠️  团队多样性不足（{unique_teams} < {MIN_TEAM_COUNT}），建议扩大数据源")

    return selected


def _tier(score: int) -> str:
    if score >= 80:
        return "gold"
    elif score >= 40:
        return "silver"
    return "bronze"


# ============================================================
# Step 6: 输出
# ============================================================

def build_output(selected: List[Dict]) -> Dict:
    all_findings = [f for r in selected for f in r.get("findings", [])]

    # GT 来源统计
    gt_sources: Dict[str, int] = {}
    sev_dist: Dict[str, int] = {}
    for f in all_findings:
        src = f.get("ground_truth_source", "ai_detected")
        gt_sources[src] = gt_sources.get(src, 0) + 1
        sev = f.get("severity", "P2")
        sev_dist[sev] = sev_dist.get(sev, 0) + 1

    samples = []
    for i, record in enumerate(selected):
        sid = f"L1-{str(i+1).zfill(3)}"
        bugs = []
        for j, f in enumerate(record.get("findings", [])):
            f["bug_id"] = f"{sid}-B{j+1}"
            bugs.append(f)
        samples.append({
            "id": sid,
            "pr_url": record.get("pr_url"),
            "pr_id": record.get("pr_id"),
            "merge_date": record.get("merge_date"),
            "repo": record.get("repo_slug"),
            "submitter": record.get("submitter"),
            "cr_doc_id": record.get("cr_doc_id"),
            "cr_doc_url": record.get("cr_doc_url"),
            "bugs": bugs,
            "clean_zones": [],
            "metadata": {
                "selection_tier": record.get("selection_tier", "bronze"),
                "priority_score": record.get("priority_score", 0),
                "feedback_marks": record.get("feedback_marks", []),
                "review_conclusion": record.get("review_conclusion"),
                "review_status": (
                    "needs_review"
                    if any(f.get("review_status") == "needs_review" for f in bugs)
                    else "auto"
                ),
            }
        })

    return {
        "schema_version": "2.0",
        "generated_at": datetime.now().isoformat(),
        "generator": "ai-quality-evalset-builder v1.1",
        "statistics": {
            "total_samples": len(samples),
            "total_bugs": len(all_findings),
            "severity_distribution": sev_dist,
            "gt_source_distribution": gt_sources,
        },
        "samples": samples,
    }


def main():
    args = sys.argv[1:]
    if "--input" not in args or "--output-dir" not in args:
        print("Usage: python3 build_evalset.py --input parsed_findings.json --output-dir <dir>")
        sys.exit(1)

    input_file = args[args.index("--input") + 1]
    output_dir = args[args.index("--output-dir") + 1]

    import os
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"📥 待处理 PR: {len(records)} 条\n")

    print("=== Step 4: 收集采纳信号（行评论 + 四选标记 + 文档评论）===")
    enriched, fp_pool = enrich_all(records)

    print("\n=== Step 5: 贪心采样 ===")
    selected = greedy_sample(enriched)

    print("\n=== Step 6: 生成输出 ===")
    evalset = build_output(selected)
    needs_review = [
        {
            "pr_url": r.get("pr_url"),
            "cr_doc_url": r.get("cr_doc_url"),
            "findings_to_review": [f for f in r.get("findings", [])
                                    if f.get("review_status") == "needs_review"],
        }
        for r in selected
        if any(f.get("review_status") == "needs_review" for f in r.get("findings", []))
    ]

    def write(filename, data):
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  💾 {path}")

    write("samples.json", evalset)
    write("needs-review.json", needs_review)
    write("fp-pool.json", fp_pool)

    # run-log
    log_path = os.path.join(output_dir, "run-log.md")
    stats = evalset["statistics"]
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# 评测集构建日志\n\n")
        f.write(f"- 执行时间：{datetime.now().isoformat()}\n")
        f.write(f"- 输入候选：{len(records)} 条 PR\n")
        f.write(f"- 最终采样：{len(selected)} 条\n")
        f.write(f"- FP 样本池：{len(fp_pool)} 条\n")
        f.write(f"- 待人工仲裁：{len(needs_review)} 条\n")
        f.write(f"- 总 bug 实例：{stats['total_bugs']}\n\n")
        f.write(f"## GT 来源分布\n\n")
        for src, cnt in sorted(stats.get("gt_source_distribution", {}).items()):
            f.write(f"- {src}: {cnt}\n")
        f.write(f"\n## 严重等级分布\n\n")
        for sev, cnt in sorted(stats.get("severity_distribution", {}).items()):
            f.write(f"- {sev}: {cnt}\n")
    print(f"  💾 {log_path}")

    # === Wiki Markdown 输出（人可读，用于上传学城） ===
    wiki_path = os.path.join(output_dir, "evalset-wiki.md")
    with open(wiki_path, "w", encoding="utf-8") as f:
        f.write("# AI-CR L1 回溯标注评测集\n\n")
        f.write(f"> 自动构建于 {datetime.now().strftime('%Y-%m-%d %H:%M')}，"
                f"共 {len(selected)} 条 PR / {stats['total_bugs']} 个 bug 实例\n\n")
        f.write("---\n\n")

        for idx, rec in enumerate(selected, 1):
            pr_url = rec.get("pr_url", "N/A")
            pr_title = rec.get("title") or rec.get("pr_title") or "未知"
            org = rec.get("org", "未知")
            repo = rec.get("repo_slug", "未知")
            tier = rec.get("selection_tier", "N/A")
            priority_score = rec.get("priority_score", 0)

            f.write(f"## {idx}. {pr_title}\n\n")

            # PR 上下文
            f.write("### PR 上下文\n\n")
            f.write(f"| 字段 | 值 |\n|------|----|\n")
            f.write(f"| PR 链接 | {pr_url} |\n")
            f.write(f"| 团队 | {org} |\n")
            f.write(f"| 仓库 | {repo} |\n")
            f.write(f"| CR 文档 | {rec.get('cr_doc_url', 'N/A')} |\n")
            f.write(f"| 优先级评分 | {priority_score} |\n")
            f.write(f"| 选择层级 | {tier} |\n\n")

            # 选择原因
            f.write("### 圈选原因\n\n")
            reasons = []
            findings = rec.get("findings", [])
            defect_classes = set(f_.get("defect_class", "") for f_ in findings)
            context_layers = set(f_.get("context_layer_required", "") for f_ in findings)
            has_signal = any(f_.get("gt_source") and f_.get("gt_source") != "ai_detected" for f_ in findings)

            if has_signal:
                reasons.append("✅ 有外部采纳信号（高置信 Ground Truth）")
            if "C1_npe" in defect_classes or "C4_concurrency" in defect_classes:
                reasons.append("🎯 覆盖高价值缺陷类型（NPE/并发）")
            if "L2_intra_repo_search" in context_layers or "L3_cross_repo_or_business" in context_layers:
                reasons.append("🔍 需要深层上下文才能检出（L2/L3）")
            if priority_score >= 80:
                reasons.append(f"⭐ 高优先级评分 ({priority_score})")
            if not reasons:
                reasons.append(f"📊 覆盖矩阵补位（{'/'.join(defect_classes)}）")

            for r in reasons:
                f.write(f"- {r}\n")
            f.write("\n")

            # 检出项 + 置信打分 + Ground Truth
            f.write("### 检出项与 Ground Truth\n\n")
            f.write("| # | 文件 | 行 | 严重等级 | 缺陷分类 | 置信度 | GT来源 | GT判定 |\n")
            f.write("|---|------|----|---------|---------|--------|--------|--------|\n")
            for fi, finding in enumerate(findings, 1):
                file_path = finding.get("file") or finding.get("file_path") or "N/A"
                # 截断长路径
                if len(file_path) > 40:
                    file_path = "..." + file_path[-37:]
                line = finding.get("line_range", "N/A")
                severity = finding.get("severity", "P2")
                dc = finding.get("defect_class", "N/A")
                conf = finding.get("confidence", 0)
                gt_src = finding.get("ground_truth_source", "ai_detected")
                # gt_label 推导：有信号=true_positive/false_positive, 无信号=needs_review
                if finding.get("is_fp"):
                    gt_label = "false_positive"
                elif gt_src in ("inline_reply_accept", "explicit_accept", "doc_comment_accept"):
                    gt_label = "true_positive"
                else:
                    gt_label = "needs_review"

                # 置信度颜色标记
                conf_mark = "🟢" if conf >= 0.7 else "🟡" if conf >= 0.45 else "🔴"

                f.write(f"| {fi} | `{file_path}` | {line} | {severity} | {dc} | "
                        f"{conf_mark} {conf:.2f} | {gt_src} | {gt_label} |\n")
            f.write("\n")

            # finding 详情（摘要）
            for fi, finding in enumerate(findings, 1):
                desc = finding.get("description", "")
                if desc:
                    f.write(f"**Finding {fi}**: {desc[:200]}{'...' if len(desc) > 200 else ''}\n\n")

            f.write("---\n\n")

        # 尾部统计
        f.write("## 统计摘要\n\n")
        f.write(f"| 指标 | 值 |\n|------|----|\n")
        f.write(f"| 总 PR 数 | {len(selected)} |\n")
        f.write(f"| 总 Bug 实例 | {stats['total_bugs']} |\n")
        f.write(f"| 待人工仲裁 | {len(needs_review)} |\n")
        f.write(f"| FP 样本池 | {len(fp_pool)} |\n\n")

        f.write("### GT 来源分布\n\n")
        for src, cnt in sorted(stats.get("gt_source_distribution", {}).items()):
            pct = cnt * 100 // max(stats['total_bugs'], 1)
            f.write(f"- **{src}**: {cnt} ({pct}%)\n")

        f.write("\n### 团队分布\n\n")
        team_dist: Dict[str, int] = {}
        for r in selected:
            t = r.get("org", "unknown")
            team_dist[t] = team_dist.get(t, 0) + 1
        for t, cnt in sorted(team_dist.items(), key=lambda x: -x[1]):
            f.write(f"- {t}: {cnt} 条 ({cnt*100//len(selected)}%)\n")

    print(f"  💾 {wiki_path} (学城 wiki 格式)")

    print(f"\n✅ 完成！")
    print(f"   样本: {len(selected)} PR / {stats['total_bugs']} bug 实例")
    print(f"   GT来源: {stats.get('gt_source_distribution', {})}")
    print(f"   待人工仲裁: {len(needs_review)} 条")
    print(f"   Wiki文档: {wiki_path}")


if __name__ == "__main__":
    main()
