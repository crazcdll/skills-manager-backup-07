#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言常量：类型(kind) / 判定方式(verdict) / 判定结果(result) 三个维度彻底解耦。

设计原则（单一权威，所有消费方引用此处）：
  kind    —— 断言是什么：text | visual
  match   —— 文本断言的匹配方式：present | gone（visual 不适用）
  verdict —— 怎么判出来的：exact(T1 程序化) | semantic(T2 AI 语义) | visual(T3 AI 视觉)
  result  —— 判成什么：pass | fail | pending

历史实现把三者塞进同一个 verdict 枚举（exact_pass / semantic_pending / visual_pass / fail），
导致「失败」时丢失类型与判定方式信息，现已废除。
"""

# ─── 断言类型 ──────────────────────────────────────────────────────

KIND_TEXT = "text"
KIND_VISUAL = "visual"

MATCH_PRESENT = "present"
MATCH_GONE = "gone"

# ─── 判定结果（唯一表示"通过/失败/待定"） ──────────────────────────

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_PENDING = "pending"

# ─── 判定方式（与结果正交） ────────────────────────────────────────

VERDICT_EXACT = "exact"        # T1 程序化精确匹配
VERDICT_SEMANTIC = "semantic"  # T2 AI 语义确认
VERDICT_VISUAL = "visual"      # T3 AI 视觉确认

# ─── 判定者（谁判的，与 verdict 正交） ──────────────────────────────
# decided_by 记录该断言的结论由谁给出：
#   engine — 引擎程序化判定（T1 精确 / T1.5 唯一子串语义），确定性结论，无需人工复核；
#   ai     — AI 主观判定（T2 语义 / T3 视觉），需人工复核兜底。
# 由此派生 needs_review（见 assertions.engine.compute_needs_review）：
# 「AI 判定通过」必须标记，避免主观判定被静默当作确定通过。
DECIDED_BY_ENGINE = "engine"
DECIDED_BY_AI = "ai"

# ─── 展示标签 ──────────────────────────────────────────────────────

RESULT_LABELS = {
    RESULT_PASS: "✅",
    RESULT_FAIL: "❌",
    RESULT_PENDING: "📍",
}

# 判定方式展示标签。注意 verdict=semantic 有两个来源：
#   引擎唯一子串自动判定（T1.5，见 AssertionResult.pass_semantic，evidence.decided_by=engine）
#   AI 语义确认（T2，override-step-result 写回）
# 所以标签只描述「判定方式」，不再用 T1/T2/T3 混淆「谁来判定」。
VERDICT_LABELS = {
    VERDICT_EXACT: "精确匹配",
    VERDICT_SEMANTIC: "语义等价",
    VERDICT_VISUAL: "视觉判定",
}

KIND_LABELS = {
    KIND_TEXT: "文本",
    KIND_VISUAL: "视觉",
}

MATCH_LABELS = {
    MATCH_PRESENT: "出现",
    MATCH_GONE: "消失",
}

STEP_OK_STATUS = {0: "❌ FAIL", 1: "✅ PASS", 2: "⚠️ WARN"}
# 无判定备注（ok=None）：只作展示，不进通过/失败统计
NOTE_STATUS = "📝 NOTE"
