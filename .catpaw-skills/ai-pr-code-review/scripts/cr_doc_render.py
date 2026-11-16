#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cr_doc_render.py — 学城 CR 文档 Markdown 渲染器

接收结构化 JSON（PR 元数据 + AI 审查结论），按固定骨架渲染成 Markdown。
AI 只需产出 JSON，不需要记住 8 章结构。

用法：
  python3 cr_doc_render.py --input /tmp/cr_result_{prId}.json --output /tmp/cr_review_{prId}.md
  python3 cr_doc_render.py --input /tmp/cr_result_{prId}.json  # 输出到 stdout

JSON Schema 见底部 SCHEMA 注释。
"""

import argparse
import json
import sys
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# 渲染函数
# ═══════════════════════════════════════════════════════════════════════════

def render_chapter1(d):
    """一、PR 概述"""
    pr = d["pr"]
    lines = [
        "## 一、PR 概述\n",
        "| 项目 | 内容 |",
        "|------|------|",
        f'| 仓库 | {pr["org"]}/{pr["repo"]} |',
        f'| PR 编号 | #{pr["id"]} |',
        f'| 标题 | {pr["title"]} |',
        f'| 提交人 | {pr["author_name"]}（{pr["author_mis"]}） |',
        f'| 触发人 | {pr["trigger_name"]}（{pr["trigger_mis"]}） |',
        f'| 分支 | {pr["source_branch"]} → {pr["target_branch"]} |',
        f'| 审查时间 | {pr.get("cr_at", datetime.now().strftime("%Y-%m-%d %H:%M"))} |',
    ]
    return "\n".join(lines)


def render_chapter2(d):
    """二、变更综述"""
    ch = d.get("change_summary", {})
    lines = ["## 二、变更综述\n"]
    lines.append(ch.get("overview", "（变更概述待填充）"))
    lines.append("")

    changes = ch.get("changes", [])
    if changes:
        lines.append("**核心变更内容：**\n")
        for i, c in enumerate(changes, 1):
            cat = c.get("category", f"变更类别 {i}")
            desc = c.get("description", "")
            lines.append(f"{i}. **{cat}**：{desc}")
        lines.append("")
        lines.append("> 变更类别按重要性排列，通常为：新增核心逻辑 → 枚举/配置扩展 → 外部依赖新增 → 已有逻辑修改 → 非代码文件（文档/配置）")

    return "\n".join(lines)


def render_chapter3(d):
    """三、SDD 产物校验"""
    sdd = d.get("sdd", {})
    lines = ["## 三、SDD 产物校验\n"]

    spec_status = sdd.get("spec_status", "— 未采用 SDD")
    lines.append(f"- **Spec 状态**：{spec_status}")

    has_spec = sdd.get("has_spec", False)
    if has_spec:
        alignment = sdd.get("alignment", "N/A")
        lines.append(f"- **对齐率**：{alignment}%")

    # 一致性问题
    issues = sdd.get("issues", [])
    lines.append("- **一致性问题**：")
    if issues:
        for iss in issues:
            lines.append(f"  - {iss}")
    else:
        lines.append("  - ✅ spec 与代码实现一致")

    # 建议
    if has_spec:
        suggestions = sdd.get("suggestions", [])
        if suggestions:
            lines.append("- **建议**：" + "；".join(suggestions))

    # 空模板（has_spec=false 的标准化输出）
    note = sdd.get("note", "")
    if note:
        lines.append("")
        lines.append(f"> {note}")

    return "\n".join(lines)


def _pad_id(raw_id):
    """统一编号为两位补零：1→01, 2→02, 01→01"""
    s = str(raw_id)
    return s.zfill(2) if len(s) < 2 else s


def _render_p0p1_issue(issue, emoji, level):
    """渲染单条 P0/P1"""
    idx = _pad_id(issue.get("id", "01"))
    rule = issue.get("rule", "")
    rule_tag = f" [{rule}]" if rule else ""
    issue_type = issue.get("type", "")
    summary = issue.get("summary", "")
    lines = [f"**{emoji} [{level}-{idx}]{rule_tag} {issue_type} — {summary}**"]
    lines.append(f'- **文件**：`{issue.get("file", "")}` L{issue.get("line", "?")}')

    code = issue.get("code", "")
    if code:
        lines.append("- **问题代码**：")
        lines.append("```java")
        lines.append(code)
        lines.append("```")

    for field, label in [
        ("reason", "检出原因"),
        ("reach_analysis", "触达分析"),
        ("online_scenario", "线上场景"),
        ("impact", "影响范围"),
    ]:
        val = issue.get(field, "")
        if val:
            lines.append(f"- **{label}**：{val}")

    fix = issue.get("fix", "")
    if fix:
        lines.append("- **修复建议**：")
        lines.append("```java")
        lines.append(fix)
        lines.append("```")

    return "\n".join(lines)


def _render_p2_issue(issue):
    """渲染单条 P2"""
    idx = _pad_id(issue.get("id", "01"))
    rule = issue.get("rule", "")
    rule_tag = f" [{rule}]" if rule else ""
    title = issue.get("title", "")
    lines = [f"**🟡 [P2-{idx}]{rule_tag} {title}**"]
    lines.append(f'- **文件**：`{issue.get("file", "")}` L{issue.get("line", "?")}')

    for field, label in [
        ("description", "问题描述"),
        ("reason", "检出原因"),
        ("requirement", "规范要求"),
        ("fix", "修复建议"),
    ]:
        val = issue.get(field, "")
        if val:
            lines.append(f"- **{label}**：{val}")

    return "\n".join(lines)


def _render_p3_issue(issue):
    """渲染单条 P3"""
    idx = _pad_id(issue.get("id", "01"))
    title = issue.get("title", "")
    lines = [f"**🔵 [P3-{idx}] {title}**"]
    lines.append(f'- **文件**：`{issue.get("file", "")}` L{issue.get("line", "?")}')
    suggestion = issue.get("suggestion", "")
    if suggestion:
        lines.append(f"- **建议**：{suggestion}")
    return "\n".join(lines)


def _render_q_issue(issue):
    """渲染单条待确认问题"""
    idx = _pad_id(issue.get("id", "01"))
    title = issue.get("title", "")
    lines = [f"**❓ [Q-{idx}] {title}**"]
    lines.append(f'- **文件**：`{issue.get("file", "")}` L{issue.get("line", "?")}')
    for field, label in [
        ("description", "问题描述"),
        ("uncertainty", "不确定原因"),
        ("risk", "可能的风险"),
        ("suggestion", "建议"),
    ]:
        val = issue.get(field, "")
        if val:
            lines.append(f"- **{label}**：{val}")
    return "\n".join(lines)


def render_chapter4(d):
    """四、Review 发现"""
    findings = d.get("findings", {})
    lines = ["## 四、Review 发现\n"]

    # P0
    p0_list = findings.get("p0", [])
    lines.append("### P0 — 零容忍异常 🔴\n")
    if p0_list:
        for issue in p0_list:
            lines.append(_render_p0p1_issue(issue, "🔴", "P0"))
            lines.append("")
    else:
        lines.append("> ✅ 本次 CR 未发现 P0 问题\n")

    # P1
    p1_list = findings.get("p1", [])
    lines.append("### P1 — 稳定性风险 🟠\n")
    if p1_list:
        for issue in p1_list:
            lines.append(_render_p0p1_issue(issue, "🟠", "P1"))
            lines.append("")
    else:
        lines.append("> ✅ 本次 CR 未发现 P1 问题\n")

    # P2
    p2_list = findings.get("p2", [])
    if p2_list:
        lines.append("### P2 — 代码规范 🟡\n")
        for issue in p2_list:
            lines.append(_render_p2_issue(issue))
            lines.append("")

    # P3
    p3_list = findings.get("p3", [])
    if p3_list:
        lines.append("### P3 — 优化建议 🔵\n")
        for issue in p3_list:
            lines.append(_render_p3_issue(issue))
            lines.append("")

    # 待确认
    q_list = findings.get("questions", [])
    if q_list:
        lines.append("### ❓ 待确认问题\n")
        lines.append("> 以下问题 AI 无法独立判定，需人工确认。\n")
        for issue in q_list:
            lines.append(_render_q_issue(issue))
            lines.append("")

    return "\n".join(lines)


def render_chapter5(d):
    """五、总体评价"""
    eval_ = d.get("evaluation", {})
    lines = ["## 五、总体评价\n"]

    strengths = eval_.get("strengths", [])
    if strengths:
        lines.append("**优点**：")
        for s in strengths:
            lines.append(f"- {s}")
        lines.append("")

    concerns = eval_.get("concerns", [])
    if concerns:
        lines.append("**需关注问题**：")
        for c in concerns:
            lines.append(f"- {c}")
        lines.append("")

    conclusion = eval_.get("conclusion", "✅通过")
    lines.append(f"**Review 结论**：{conclusion}")
    lines.append("")

    counts = eval_.get("counts", {})
    p0 = counts.get("p0", 0)
    p1 = counts.get("p1", 0)
    p2 = counts.get("p2", 0)
    p3 = counts.get("p3", 0)
    lines.append(f"**发现汇总**：P0: {p0} | P1: {p1} | P2: {p2} | P3: {p3}")

    return "\n".join(lines)


def render_chapter6(d):
    """六、人工复审要点（条件输出）"""
    review_points = d.get("review_points", [])
    if not review_points:
        return ""

    lines = ["## 六、人工复审要点\n"]
    lines.append("以下事项 AI 分析难以完全确认，需要人工评审者重点验证：\n")

    for i, pt in enumerate(review_points, 1):
        title = pt.get("title", f"要点 {i}")
        lines.append(f"### ⚠️ {i}. {title}\n")
        lines.append("| 维度 | 内容 |")
        lines.append("|------|------|")
        lines.append("| 变更内容 | " + pt.get("change", "") + " |")
        lines.append("| 需确认 | " + pt.get("confirm", "") + " |")
        lines.append("| 验证方法 | " + pt.get("verify", "") + " |")
        lines.append("")

    lines.append("> 要点来源：行为变更影响面、缓存/状态一致性、新增外部依赖容量、配置来源可靠性、回归测试覆盖度等 AI 难以确认的维度。")

    return "\n".join(lines)


def render_chapter7(d):
    """七、与 CatPaw 对比（条件输出）"""
    catpaw = d.get("catpaw", None)
    if not catpaw:
        return ""

    lines = ["## 七、与 CatPaw 对比\n"]
    lines.append("| 维度 | CatPaw | AI-CR | 差异说明 |")
    lines.append("|------|--------|-------|---------|")

    for level in ["P0", "P1", "P2", "P3"]:
        lk = level.lower()
        cp = catpaw.get(f"catpaw_{lk}", 0)
        ai = catpaw.get(f"aicr_{lk}", 0)
        diff = catpaw.get(f"diff_{lk}", "")
        lines.append(f"| {level} | {cp} | {ai} | {diff} |")

    cp_concl = catpaw.get("catpaw_conclusion", "")
    ai_concl = catpaw.get("aicr_conclusion", "")
    lines.append(f"| 结论 | {cp_concl} | {ai_concl} | |")
    lines.append("")

    aicr_unique = catpaw.get("aicr_unique", [])
    if aicr_unique:
        lines.append("**AI-CR 独有发现**：")
        for item in aicr_unique:
            lines.append(f"- {item}")
        lines.append("")

    cp_unique = catpaw.get("catpaw_unique", [])
    if cp_unique:
        lines.append("**CatPaw 独有发现**：")
        for item in cp_unique:
            lines.append(f"- {item}")

    return "\n".join(lines)


def render_chapter8(d):
    """八、上轮 CR 采纳情况（条件输出）"""
    adoption = d.get("adoption", None)
    if not adoption:
        return ""

    lines = ["## 八、上轮 CR 采纳情况\n"]
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f'| 总发现数 | {adoption.get("total", 0)} |')
    lines.append(f'| ✅ 已采纳 | {adoption.get("adopted", 0)} ({adoption.get("adopted_rate", 0)}%) |')
    lines.append(f'| ⚠️ 规则太严 | {adoption.get("too_strict", 0)} ({adoption.get("strict_rate", 0)}%) |')
    lines.append(f'| ⏭ 暂不修复 | {adoption.get("deferred", 0)} ({adoption.get("defer_rate", 0)}%) |')
    lines.append(f'| ❌ 误报 | {adoption.get("false_positive", 0)} ({adoption.get("fp_rate", 0)}%) |')
    lines.append(f'| 未反馈 | {adoption.get("no_feedback", 0)} |')
    lines.append("")

    by_level = adoption.get("by_level", {})
    if by_level:
        lines.append("**按层级**：\n")
        lines.append("| 层级 | 采纳 | 规则太严 | 暂不修复 | 误报 |")
        lines.append("|------|------|---------|---------|------|")
        for level in ["P0", "P1", "P2", "P3"]:
            lk = level.lower()
            lv = by_level.get(lk, {})
            lines.append(f'| {level} | {lv.get("adopted", 0)} | {lv.get("too_strict", 0)} | {lv.get("deferred", 0)} | {lv.get("false_positive", 0)} |')

    return "\n".join(lines)


def render_document(data):
    """渲染完整文档"""
    pr = data["pr"]
    title = f'# PR #{pr["id"]} Code Review：{pr["title"]}\n'

    chapters = [
        title,
        render_chapter1(data),
        render_chapter2(data),
        render_chapter3(data),
        render_chapter4(data),
        render_chapter5(data),
        render_chapter6(data),   # 条件输出
        render_chapter7(data),   # 条件输出
        render_chapter8(data),   # 条件输出
    ]

    # 过滤空章节，拼接
    return "\n\n".join(ch for ch in chapters if ch.strip())


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="学城 CR 文档 Markdown 渲染器")
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认 stdout）")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    md = render_document(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ 文档已渲染到 {args.output}（{len(md)} 字节）", file=sys.stderr)
    else:
        print(md)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════════
# JSON SCHEMA（AI 产出规范）
# ═══════════════════════════════════════════════════════════════════════════
#
# {
#   "pr": {                                    // 必须 — PR 元数据（Step 1/2）
#     "org": "technician",
#     "repo": "technician-vc-service",
#     "id": 12345,
#     "title": "feat: 新增XX功能",
#     "author_name": "张三",
#     "author_mis": "zhangsan",
#     "trigger_name": "木子",
#     "trigger_mis": "mengmuzi",
#     "source_branch": "feature/xxx",
#     "target_branch": "master",
#     "cr_at": "2026-07-22 00:10"              // 可选，默认当前时间
#   },
#
#   "change_summary": {                        // 必须 — 二、变更综述（AI 生成）
#     "overview": "本次变更新增了XX功能，涉及5个文件，+120/-30行",
#     "changes": [                             // 核心变更分类列表
#       {"category": "新增核心逻辑", "description": "新增 XxxService 类，实现..."},
#       {"category": "配置扩展", "description": "新增枚举值..."}
#     ]
#   },
#
#   "sdd": {                                   // 必须 — 三、SDD 产物校验（Step 3D）
#     "has_spec": true,                        // 是否有 spec 文件
#     "spec_status": "✅ 完备",                // ✅ 完备 / ⚠️ 简略 / ❌ 缺失 / — 未采用 SDD
#     "alignment": 92,                         // 对齐率百分比（仅 has_spec=true）
#     "issues": [                              // 一致性问题列表（空=一致）
#       "[P2] api-spec.md L15：spec 描述「返回列表」，代码实现「返回分页对象」"
#     ],
#     "suggestions": ["建议补充异常场景的 spec"],// 建议（仅 has_spec=true）
#     "note": ""                               // has_spec=false 时的标准化说明
#   },
#
#   "findings": {                              // 必须 — 四、Review 发现（Step 4）
#     "p0": [                                  // P0 列表（空=无 P0）
#       {
#         "id": "01",                          // 编号（两位补零）
#         "rule": "NPE",                       // 规则缩写
#         "type": "空指针异常",                  // 异常类型
#         "summary": "未判空直接调用",           // 一句话概括
#         "file": "XxxService.java",           // 文件路径
#         "line": 42,                          // 行号（dstN）
#         "code": "obj.getName()",             // 问题代码片段
#         "reason": "obj 来自 map.get()...",   // 检出原因
#         "reach_analysis": "被 XxxController.query() 调用...", // 触达分析
#         "online_scenario": "用户搜索时...",   // 线上场景
#         "impact": "单次请求失败...",           // 影响范围
#         "fix": "if (obj != null) {..."       // 修复代码
#       }
#     ],
#     "p1": [],                                // P1 列表，格式同 P0
#     "p2": [                                  // P2 列表
#       {
#         "id": "01",
#         "rule": "NAMING",                    // ruleId
#         "title": "方法命名不规范",
#         "file": "XxxService.java",
#         "line": 15,
#         "description": "方法名 getData 含义模糊",
#         "reason": "违反 Level B 命名规范",
#         "requirement": "方法名应体现业务语义", // 规范要求
#         "fix": "建议改为 querySkuList"
#       }
#     ],
#     "p3": [                                  // P3 列表
#       {
#         "id": "01",
#         "title": "可提取常量",
#         "file": "XxxService.java",
#         "line": 88,
#         "suggestion": "魔法数字 30 建议提取为常量 MAX_RETRY_COUNT"
#       }
#     ],
#     "questions": [                           // 待确认问题列表（可选）
#       {
#         "id": "01",
#         "title": "缓存过期策略是否合理",
#         "file": "CacheConfig.java",
#         "line": 22,
#         "description": "TTL 设置为 5 分钟",
#         "uncertainty": "不清楚业务对数据实时性要求",
#         "risk": "若业务需要实时数据，5分钟缓存可能导致不一致",
#         "suggestion": "确认业务对该数据的实时性要求"
#       }
#     ]
#   },
#
#   "evaluation": {                            // 必须 — 五、总体评价（AI 生成）
#     "strengths": ["代码结构清晰", "异常处理完善"],
#     "concerns": ["部分方法过长，建议拆分"],
#     "conclusion": "💚通过有建议",             // 四选一
#     "counts": {"p0": 0, "p1": 1, "p2": 3, "p3": 2}
#   },
#
#   "review_points": [                         // 可选 — 六、人工复审要点
#     {
#       "title": "新增 RPC 调用容量",
#       "change": "新增对 sku-price-service 的 RPC 调用",
#       "confirm": "下游服务是否已扩容",
#       "verify": "查看 sku-price-service 容量水位"
#     }
#   ],
#
#   "catpaw": null,                            // 可选 — 七、与 CatPaw 对比（null=跳过）
#   // 非 null 时：{catpaw_p0, aicr_p0, diff_p0, ..., catpaw_conclusion, aicr_conclusion, aicr_unique:[], catpaw_unique:[]}
#
#   "adoption": null                           // 可选 — 八、上轮 CR 采纳情况（null=首次 CR 跳过）
#   // 非 null 时：{total, adopted, adopted_rate, too_strict, strict_rate, deferred, defer_rate, false_positive, fp_rate, no_feedback, by_level:{p0:{...},...}}
# }
