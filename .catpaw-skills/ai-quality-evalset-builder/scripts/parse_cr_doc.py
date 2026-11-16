#!/usr/bin/env python3
"""
Step 3: 从学城 CR 文档解析 AI-CR 检出项

输入：candidates.json（Step 2 输出）
输出：parsed_findings.json（每条 PR 的检出项列表）

Usage:
  python3 parse_cr_doc.py --input candidates.json --output parsed_findings.json
"""

import json
import re
import subprocess
import sys
from typing import List, Dict, Any, Optional


MAX_BUGS_PER_PR = 5

# 缺陷分类关键词表（defect_class 自动标注）
DEFECT_KEYWORDS = {
    "C1_npe": ["npe", "nullpointerexception", "空指针", "判空", "null", "optional", "拆箱",
                "map.get", ".get()", "objects.requirenonnull"],
    "C2_resource_leak": ["资源泄漏", "连接未释放", "未关闭", "close", "try-with-resources",
                          "大value", "大 value", "批量", "超限", "oom", "squirrel", "redis.*大"],
    "C3_logic_error": ["逻辑错误", "条件遗漏", "分支遗漏", "switch.*default", "枚举覆盖",
                        "id混用", "状态机", "边界条件", "shopid", "poiid", "spuid"],
    "C4_concurrency": ["并发", "线程安全", "synchronized", "volatile", "concurrentmodification",
                        "单例", "共享变量", "竞态", "simpledateformat", "hashmap.*多线程"],
    "C5_security": ["sql注入", "xss", "ssrf", "硬编码", "密码", "凭证", "token.*硬编码",
                     "secret", "直连.*set", "反序列化漏洞", "日志.*敏感"],
    "C6_performance": ["性能", "n+1", "循环内.*db", "循环内.*rpc", "全量查询", "无分页",
                        "串行", "同步阻塞", "缓存穿透", "无限增长"],
    "C7_cross_repo": ["跨仓库", "dto", "序列化", "反序列化", "fail_on_unknown",
                       "上下游", "接口变更", "版本兼容", "上线顺序", "cx-0"],
}

# 严重等级关键词
SEVERITY_PATTERNS = [
    (r'\bP0\b', "P0"),
    (r'\bP1\b', "P1"),
    (r'\bP2\b', "P2"),
    (r'\bP3\b', "P3"),
    (r'零容忍|必须修复|严重', "P0"),
    (r'稳定性|安全风险', "P1"),
    (r'规范|建议|优化', "P2"),
]


def get_doc_content(doc_id: str) -> Optional[str]:
    """调用 oa-skills citadel 获取文档内容"""
    try:
        result = subprocess.run(
            ["oa-skills", "citadel", "get-content", "--content-id", doc_id],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  ⚠️  citadel get-content 失败: {result.stderr[:200]}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"  ⚠️  调用异常: {e}", file=sys.stderr)
        return None


def classify_defect(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cls, keywords in DEFECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(kw, text_lower))
        if score > 0:
            scores[cls] = score
    if not scores:
        return "C3_logic_error"  # 默认归类
    return max(scores, key=scores.get)


def detect_severity(text: str) -> str:
    for pattern, sev in SEVERITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return sev
    return "P2"  # 默认


def detect_context_layer(text: str) -> str:
    """判断需要哪层上下文"""
    text_lower = text.lower()
    # 跨仓库搜索信号
    if any(kw in text_lower for kw in ["跨仓库", "cx-0", "其他仓库", "调用方仓库"]):
        return "L3_cross_repo_or_business"
    # 仓库内搜索信号
    if any(kw in text_lower for kw in ["code-repo-search", "全仓库", "grep", "调用方", "消费方", "引用"]):
        return "L2_intra_repo_search"
    return "L1_diff_visible"


def extract_file_and_lines(block: str) -> tuple:
    """从代码块或描述文本中提取文件路径和行号"""
    # 文件路径：支持 .java/.ts/.tsx/.vue/.js/.jsx/.py/.go/.kt 等
    file_match = re.search(
        r'[\w/\-\.]+\.(?:java|ts|tsx|vue|js|jsx|py|go|kt|scala|rs|rb|php|cs|swift|xml|yaml|yml|json|properties|sql)',
        block
    )
    file_path = file_match.group(0) if file_match else None

    # 行号：第42行 / 第42-58行 / line 42 / L42 / :42 / @@ -42,16 +42,20 @@
    # diff 格式
    diff_match = re.search(r'@@\s*[-+](\d+)', block)
    line_matches = re.findall(r'(?:第|line\s*|L|:)(\d+)(?:\s*[-~到]\s*(\d+))?(?:行)?', block, re.IGNORECASE)

    lines = []
    if diff_match:
        lines.append(int(diff_match.group(1)))
    for m in line_matches[:2]:
        lines.append(int(m[0]))
        if m[1]:
            lines.append(int(m[1]))

    if len(lines) == 0:
        line_range = None
    elif len(lines) == 1:
        line_range = [lines[0], lines[0] + 5]
    else:
        line_range = [min(lines), max(lines)]

    return file_path, line_range


def parse_findings_from_content(content: str, pr_url: str, doc_id: str) -> List[Dict]:
    """从 CR 文档内容中解析检出项列表"""
    findings = []

    # 按问题段落分割：P0/P1/P2/P3 标题块
    # 常见格式：## P0-1 xxx 或 **P0** xxx 或 > P1: xxx
    blocks = re.split(
        r'(?=(?:#{1,3}\s*(?:P[0-3])|>\s*(?:P[0-3])|\*\*(?:P[0-3])\*\*))',
        content
    )

    if len(blocks) <= 1:
        # 无结构化分块，整体作为一个 finding
        blocks = [content]

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 20:
            continue

        severity = detect_severity(block)
        defect_class = classify_defect(block)
        context_layer = detect_context_layer(block)
        file_path, line_range = extract_file_and_lines(block)

        # 提取描述：第一行非标题的文本
        desc_lines = [l.strip() for l in block.split('\n') if l.strip()
                      and not l.startswith('#') and not l.startswith('```')]
        description = desc_lines[0][:200] if desc_lines else block[:100]

        # 置信度：基础分反映 AI 无信号时的真实准确率（~40%）
        # 有外部信号时（Step 4）会覆盖此值
        # 无信号时上限 0.65，确保全部进 needs_review，等人工仲裁
        confidence = 0.45           # 基础分（AI 检出无确认信号）
        if file_path:
            confidence += 0.05      # 有文件路径
        if line_range:
            confidence += 0.05      # 有行号
        if severity == "P0":
            confidence += 0.10      # P0 规则明确，误报率低
        elif severity == "P1":
            confidence += 0.05      # P1 次之

        findings.append({
            "file": file_path,
            "line_range": line_range,
            "severity": severity,
            "defect_class": defect_class,
            "context_layer_required": context_layer,
            "description": description,
            "ground_truth_source": "ai_detected",  # 默认，Step 4 会更新
            "confidence": round(min(confidence, 1.0), 2),
            "human_verified": False,
            "_raw_block_len": len(block),
        })

    # 去掉置信度 < 0.3 的
    findings = [f for f in findings if f["confidence"] >= 0.3]

    # 按严重等级排序（P0 优先），截断
    sev_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda x: sev_order.get(x["severity"], 4))
    findings = findings[:MAX_BUGS_PER_PR]

    # 添加 bug_id
    pr_id = re.search(r'/pr[s]?/(\d+)', pr_url)
    pr_short = pr_id.group(1) if pr_id else "xxx"
    for i, f in enumerate(findings):
        f["bug_id"] = f"L1-{pr_short}-B{i+1}"

    return findings


def process_candidates(candidates: List[Dict]) -> List[Dict]:
    results = []
    total = len(candidates)

    for i, record in enumerate(candidates):
        doc_id = record.get("cr_doc_id")
        pr_url = record.get("pr_url", "")
        print(f"[{i+1}/{total}] 处理 PR {record.get('pr_id')} doc={doc_id} ...", end=" ")

        if not doc_id:
            print("⏭ 跳过（无 doc_id）")
            continue

        content = get_doc_content(doc_id)
        if not content:
            print("⚠️  文档获取失败")
            continue

        findings = parse_findings_from_content(content, pr_url, doc_id)
        print(f"✅ {len(findings)} 条检出项")

        results.append({
            "pr_url": pr_url,
            "pr_id": record.get("pr_id"),
            "repo_slug": record.get("repo_slug"),
            "merge_date": record.get("date"),
            "submitter": record.get("submitter"),
            "title": record.get("title"),
            "org": record.get("org"),
            "cr_doc_id": doc_id,
            "cr_doc_url": record.get("cr_doc_url"),
            "priority_score": record.get("priority_score", 0),
            "review_conclusion": record.get("review_conclusion"),
            "p0_count": record.get("p0_count"),
            "p1_count": record.get("p1_count"),
            "findings": findings,
            "feedback_marks": [],  # Step 4 填充
        })

    print(f"\n✅ 共处理 {len(results)} / {total} 条 PR，含检出项的: "
          f"{sum(1 for r in results if r['findings'])} 条")
    return results


def main():
    args = sys.argv[1:]
    if "--input" not in args or "--output" not in args:
        print("Usage: python3 parse_cr_doc.py --input candidates.json --output parsed_findings.json")
        sys.exit(1)

    input_file = args[args.index("--input") + 1]
    output_file = args[args.index("--output") + 1]

    with open(input_file, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"📥 候选 PR 数: {len(candidates)}")
    results = process_candidates(candidates)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"💾 输出: {output_file}")


if __name__ == "__main__":
    main()
