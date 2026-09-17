#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言引擎核心：数据模型 + 引擎编排。

三层渐进式判定（verdict，与结果 result 正交）：
  T1 exact    — 程序化精确匹配（引擎自动），直接 result=pass，无 hook
  T2 semantic — T1 未命中，构建元素索引供 AI 语义确认，生成 verify_text_assertion hook
  T3 visual   — 截图视觉确认（AI 读图），生成 verify_visual_assertion hook

断言类型（kind）：text | visual。两者结构完全同构，只是判定方式不同：
  text   —— 有 match（present/gone），目标是一个文案
  visual —— 无 match，目标是「预期」+ 可选的多条 targets（逐项验收点）
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Any

from assertions.constants import (
    KIND_TEXT,
    KIND_VISUAL,
    MATCH_PRESENT,
    MATCH_GONE,
    RESULT_PASS,
    RESULT_FAIL,
    RESULT_PENDING,
    VERDICT_EXACT,
    VERDICT_SEMANTIC,
    VERDICT_VISUAL,
    DECIDED_BY_ENGINE,
    DECIDED_BY_AI,
)


# ═══════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AssertionSpec:
    """断言定义（来自 Flow 的 steps[].asserts[]）。

    文本与视觉同构，仅 kind 不同：

      {"id": "A1", "kind": "text", "match": "present", "expect": "立即支付"}

      {"id": "A3", "kind": "visual",
       "expect": "券码模块展示二维码与待使用券码信息",
       "targets": ["二维码可见", "券码为 11 位数字"],
       "criteria": "二维码可见且券码为 11 位数字",
       "on_fail": "券码模块缺失或券码位数不符"}

    字段语义：
      id       — 断言编号（缺省时由 parse_asserts 自动编号 A1/A2…），AI 判定按 id 引用
      kind     — text | visual
      match    — present | gone（仅 kind=text）
      expect   — 目标/预期（卡片主文案，短句）
      targets  — 额外验收点（可选，视觉/语义断言用于把多个验收点拆开逐项判定）
      criteria — 判断标准（可选，展开查看）
      on_fail  — 失败提示（可选）
    """
    kind: str = KIND_TEXT
    match: str = MATCH_PRESENT
    expect: str = ""
    id: str = ""
    targets: List[str] = field(default_factory=list)
    criteria: str = ""
    on_fail: str = ""

    @classmethod
    def from_dict(cls, d: dict, index: int = 0) -> "AssertionSpec":
        if not isinstance(d, dict):
            raise ValueError(
                f"asserts[{index}] 必须是对象，收到 {type(d).__name__}；"
                f'正确写法：{{"kind":"text","match":"present","expect":"目标文案"}}'
            )
        kind = str(d.get("kind") or KIND_TEXT).strip().lower()
        if kind not in (KIND_TEXT, KIND_VISUAL):
            kind = KIND_TEXT
        match = str(d.get("match") or MATCH_PRESENT).strip().lower()
        if match not in (MATCH_PRESENT, MATCH_GONE):
            match = MATCH_PRESENT
        raw_targets = d.get("targets") or []
        if isinstance(raw_targets, str):
            raw_targets = [raw_targets]
        targets = [str(t).strip() for t in raw_targets if str(t).strip()]
        return cls(
            kind=kind,
            match=match,
            expect=str(d.get("expect") or "").strip(),
            id=str(d.get("id") or "").strip() or f"A{index + 1}",
            targets=targets,
            criteria=str(d.get("criteria") or "").strip(),
            on_fail=str(d.get("on_fail") or "").strip(),
        )

    @property
    def strategy_key(self) -> str:
        """策略注册表的键：visual 走视觉策略，text 按 match 走 present/gone。"""
        return KIND_VISUAL if self.kind == KIND_VISUAL else self.match

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "expect": self.expect}
        if self.kind == KIND_TEXT:
            d["match"] = self.match
        if self.targets:
            d["targets"] = list(self.targets)
        if self.criteria:
            d["criteria"] = self.criteria
        if self.on_fail:
            d["on_fail"] = self.on_fail
        return d


@dataclass
class AssertionResult:
    """断言结果（引擎输出 + AI 判定回填），结构与 AssertionSpec 同构并追加结果字段。

    与 spec 的差异：
      result        — pass | fail | pending
      verdict       — exact | semantic | visual（判定方式；待判定时为空）
      actual        — 实测值/现象（AI 判定回填，供报告直接展示）
      reason        — 差异/失败原因（AI 判定回填）
      targets       — 逐目标结果 [{"expect","result","actual","reason"}]
      evidence      — 证据 {"screenshot","sidecar","match_level","matched_text","matched_node"}
    """
    spec: AssertionSpec
    result: str = RESULT_PENDING
    verdict: str = ""
    actual: str = ""
    reason: str = ""
    targets: List[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    available: bool = False

    # ── 构造器 ──────────────────────────────────────────────────

    @classmethod
    def pass_exact(cls, spec: AssertionSpec, matched_text: str = "",
                   match_level: int = -1, matched_node: dict = None) -> "AssertionResult":
        """T1 程序化匹配通过（result=pass / verdict=exact）"""
        evidence = {}
        if match_level >= 0:
            evidence["match_level"] = match_level
        if matched_text:
            evidence["matched_text"] = matched_text
        if matched_node:
            evidence["matched_node"] = matched_node
        evidence["decided_by"] = DECIDED_BY_ENGINE
        return cls(
            spec=spec,
            result=RESULT_PASS,
            verdict=VERDICT_EXACT,
            actual=matched_text or spec.expect,
            evidence=evidence,
            available=True,
        )

    @classmethod
    def pass_semantic(cls, spec: AssertionSpec, matched_text: str = "",
                      match_level: int = -1, matched_node: dict = None) -> "AssertionResult":
        """T1.5 程序化子串命中（result=pass / verdict=semantic）。

        判定口径与 AI 完全一致：expect 是页面复合文案的子串（或反之）即语义等价，
        如 expect=「没有更多了」/ 页面节点=「- 没有更多了 -」。
        仅在候选文案形态唯一时使用 —— 多形态候选语义不确定，仍交 AI 判定。
        """
        evidence = {}
        if match_level >= 0:
            evidence["match_level"] = match_level
        if matched_text:
            evidence["matched_text"] = matched_text
        if matched_node:
            evidence["matched_node"] = matched_node
        evidence["decided_by"] = DECIDED_BY_ENGINE
        return cls(
            spec=spec,
            result=RESULT_PASS,
            verdict=VERDICT_SEMANTIC,
            actual=matched_text or spec.expect,
            evidence=evidence,
            available=True,
        )

    @classmethod
    def pending_semantic(cls, spec: AssertionSpec, sidecar: str,
                         screenshot: str = "") -> "AssertionResult":
        """T1 未命中，待 AI 语义判定（result=pending / verdict 待定）"""
        evidence = {}
        if sidecar:
            evidence["sidecar"] = sidecar
        if screenshot:
            evidence["screenshot"] = screenshot
        return cls(
            spec=spec,
            result=RESULT_PENDING,
            verdict="",
            evidence=evidence,
            available=bool(sidecar),
        )

    @classmethod
    def pending_visual(cls, spec: AssertionSpec, screenshot: str,
                       sidecar: str = "") -> "AssertionResult":
        """视觉断言（T3），始终待 AI 读图确认（result=pending / verdict=visual）"""
        evidence = {}
        if screenshot:
            evidence["screenshot"] = screenshot
        if sidecar:
            evidence["sidecar"] = sidecar
        return cls(
            spec=spec,
            result=RESULT_PENDING,
            verdict=VERDICT_VISUAL,
            evidence=evidence,
            available=bool(screenshot),
        )

    @classmethod
    def fail_unavailable(cls, spec: AssertionSpec) -> "AssertionResult":
        """数据不可用（引擎未能收集到判定所需证据，result=fail）"""
        return cls(
            spec=spec,
            result=RESULT_FAIL,
            verdict="",
            reason="数据不可用：引擎未收集到判定所需证据",
            available=False,
        )

    # ── 序列化 ──────────────────────────────────────────────────

    def hydrate_targets(self) -> List[dict]:
        """把 spec.targets（声明）与 AI 回填的逐目标结果合并成统一结构。"""
        merged = merge_targets(self.spec.targets if self.spec else [], self.targets)
        for item in merged:
            item.setdefault("result", self.result)
            item.setdefault("actual", "")
            item.setdefault("reason", "")
        return merged

    def to_dict(self) -> dict:
        d = dict(self.spec.to_dict()) if self.spec else {"id": "", "kind": KIND_TEXT, "expect": ""}
        d["result"] = self.result
        if self.verdict:
            d["verdict"] = self.verdict
        if self.actual:
            d["actual"] = self.actual
        if self.reason:
            d["reason"] = self.reason
        targets = self.hydrate_targets()
        if targets:
            d["targets"] = targets
        d["evidence"] = dict(self.evidence or {})
        d["available"] = self.available
        # 是否需人工复核：AI 主观判定（语义/视觉）通过 → True。
        # 由「判定者」派生，与 result / verdict 正交；报告层据此特殊标识。
        d["needs_review"] = compute_needs_review(
            self.result, self.verdict, self.evidence.get("decided_by")
        )
        return d

    # ── 兼容字段（供策略层读取目标文案，避免策略到处判断 kind） ──

    @property
    def expect(self) -> str:
        return self.spec.expect if self.spec else ""

    @property
    def kind(self) -> str:
        return self.spec.kind if self.spec else KIND_TEXT

    @property
    def match(self) -> str:
        return self.spec.match if self.spec else MATCH_PRESENT


# ═══════════════════════════════════════════════════════════════════
# 执行上下文
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExecutionContext:
    """断言执行上下文"""
    ops: Any = None              # 平台操作对象（PlatformOps）
    case_ws: str = ""            # case 工作目录
    sid: str = ""                # 步骤 ID
    screenshot_path: str = ""    # 截图文件路径
    view_tree: Any = None        # 缓存视图树
    device_alive: bool = True


# ═══════════════════════════════════════════════════════════════════
# 策略基类
# ═══════════════════════════════════════════════════════════════════

class BaseAssertionStrategy:
    """断言策略基类"""
    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════
# 断言引擎
# ═══════════════════════════════════════════════════════════════════

class AssertionEngine:
    """断言引擎总入口"""

    def __init__(self):
        from assertions.registry import REGISTRY
        self._registry = REGISTRY

    def execute(self, specs: List[AssertionSpec], context: ExecutionContext) -> List[AssertionResult]:
        """执行一组断言，返回结果列表"""
        results = []
        for spec in specs:
            strategy = self._registry.get(spec.strategy_key)
            if strategy is None:
                print(f"  ⚠️ 断言策略缺失: strategy_key={spec.strategy_key!r}"
                      f"（断言 id={spec.id}），已按数据不可用处理", file=sys.stderr)
                results.append(AssertionResult.fail_unavailable(spec))
                continue
            try:
                result = strategy.execute(spec, context)
            except Exception as exc:  # noqa: BLE001 — 策略异常不得中断整条断言链
                # 策略内部异常必须可见：历史上它被静默吞掉（只降级为 fail），
                # 导致策略实现 bug（如签名不匹配的 TypeError）长期无人发现。
                print(f"  ⚠️ 断言策略执行异常 [{spec.strategy_key}] 断言 id={spec.id}: "
                      f"{type(exc).__name__}: {exc}", file=sys.stderr)
                result = AssertionResult.fail_unavailable(spec)
            results.append(result)
        return results


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def parse_asserts(raw: List[dict]) -> List[AssertionSpec]:
    """将原始 JSON 数组解析为 AssertionSpec 列表（缺省 id 时按序编号 A1/A2…）"""
    return [AssertionSpec.from_dict(d, index) for index, d in enumerate(raw or [])]


def build_assertions_dict(results: List[AssertionResult]) -> dict:
    """把断言结果按 kind 分组，供 hook 生成与 flow-context 消费。

    返回: {"text": [<结构化断言结果>...], "visual": [...]}
    条目结构 = AssertionResult.to_dict()：
      {id, kind, match, expect, targets, criteria, on_fail,
       result, verdict, actual, reason, evidence, available}
    """
    grouped: dict = {}
    for r in results:
        key = r.kind if r.kind in (KIND_TEXT, KIND_VISUAL) else KIND_TEXT
        grouped.setdefault(key, []).append(r.to_dict())
    return grouped


def merge_targets(declared, ai_targets):
    """合并「声明的 targets」与「AI 逐目标结果」，按 expect 对齐，AI 结果优先。

    declared    : list[str] | list[dict] | None —— spec.targets 的声明形态
    ai_targets  : list[dict] | None —— AI 回填 [{"expect","result","actual","reason"}]

    返回 list[dict]：声明顺序在前，AI 额外补充的目标追加在后。
    本函数是 targets 合并的唯一实现（报告层、flow-context 回写层共用）。
    """
    declared_expects = []
    for item in declared or []:
        expect = item if isinstance(item, str) else str((item or {}).get("expect") or "")
        expect = expect.strip()
        if expect:
            declared_expects.append(expect)

    by_expect = {}
    for item in ai_targets or []:
        if isinstance(item, dict):
            key = str(item.get("expect") or "").strip()
            if key:
                by_expect[key] = dict(item)

    merged = []
    for expect in declared_expects:
        entry = dict(by_expect.get(expect) or {})
        entry["expect"] = expect
        merged.append(entry)
    for key, entry in by_expect.items():
        if key not in declared_expects:
            merged.append(entry)
    return merged


def apply_verdicts(entries, verdicts):
    """把 AI 的逐断言判定（键=断言 id）合并进断言条目列表。

    entries  : list[dict] —— 断言条目（含 id；缺 id 时按 A1/A2… 顺序补齐）
    verdicts : dict       —— {"A1": {"result","verdict","actual","reason","targets"}}
              （值也允许是 "pass"/"fail"/"pending" 简写）

    返回新列表；AI 未给出的字段保持原值，未命中的 id 被忽略。
    本函数是「AI 判定 → 断言条目」回写的唯一实现：
      - step_scheduler.apply_followup_result → 回写 flow-context（flow-status 实时可见）
      - report.steps._build_assertions      → 回写报告
    """
    if not isinstance(verdicts, dict):
        return list(entries or [])

    merged = []
    for index, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            merged.append(entry)
            continue
        item = dict(entry)
        aid = str(item.get("id") or f"A{index + 1}")
        item["id"] = aid
        ai = verdicts.get(aid)
        if isinstance(ai, str):
            ai = {"result": ai}
        if isinstance(ai, dict):
            for key in ("result", "verdict", "actual", "reason"):
                if ai.get(key):
                    item[key] = ai[key]
            targets = merge_targets(item.get("targets"), ai.get("targets"))
            if targets:
                item["targets"] = targets
            # AI 判定回写 → 记录判定者并派生 needs_review。
            # AI 主观判定（语义/视觉）通过时必须标记待人工复核，避免被静默当作确定通过。
            evidence = dict(item.get("evidence") or {})
            evidence["decided_by"] = DECIDED_BY_AI
            item["evidence"] = evidence
            item["needs_review"] = compute_needs_review(
                item.get("result"), item.get("verdict"), DECIDED_BY_AI
            )
        merged.append(item)
    return merged


def apply_verdicts_grouped(grouped, verdicts):
    """apply_verdicts 的按 kind 分组版本：{"text": [...], "visual": [...]} → 同结构。"""
    if not isinstance(grouped, dict):
        return grouped
    return {kind: apply_verdicts(items, verdicts) for kind, items in grouped.items()}


def compute_needs_review(result, verdict, decided_by):
    """该断言结论是否需要人工复核。

    规则（唯一实现）：AI 主观判定通过 → 需要人工确认。
      - T1 精确 / T1.5 唯一子串（decided_by=engine）是程序化确定性结论 → 不需要；
      - T2 语义 / T3 视觉（decided_by=ai）是 AI 主观判定 → 通过时需人工兜底。

    verdict 不参与判定：只要「判定者是 AI 且结果为 pass」即需复核，
    这样语义与视觉（及未来新增的 AI 判定方式）自动纳入，无需逐类型维护。

    返回 bool；未通过（fail/pending）不算「待确认」——它们本就需要 AI/人工处理。
    """
    if result != RESULT_PASS:
        return False
    return decided_by == DECIDED_BY_AI


def compute_result_from_entries(entries):
    """从断言条目（list 或按 kind 分组 dict）计算步骤 ok。

    0    = 任一断言 result=fail
    None = 有断言 result=pending（待 AI 判定）
    1    = 全部断言 result=pass（或无断言）

    与 compute_step_ok 语义一致，区别是输入为序列化后的条目。
    本函数是「断言 → 步骤结论」这条护栏的唯一实现，供回写层（flow-context）与
    报告层共用，避免出现「断言失败但步骤通过」的自相矛盾结论。
    """
    if isinstance(entries, dict):
        flat = [item for items in entries.values() for item in (items or [])]
    else:
        flat = list(entries or [])
    if not flat:
        return 1
    has_pending = False
    for item in flat:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if result == RESULT_FAIL:
            return 0
        if result == RESULT_PENDING or result is None:
            has_pending = True
    return None if has_pending else 1


def compute_step_ok(results: List[AssertionResult]) -> Optional[int]:
    """根据断言结果计算步骤 ok_val。

    1    = PASS  — 断言全部 pass
    None = PENDING — 有断言待 AI 判定（result=pending）
    0    = FAIL  — 任一断言 fail
    """
    if not results:
        return 1
    has_pending = False
    for r in results:
        if r.result == RESULT_FAIL:
            return 0
        if r.result == RESULT_PENDING:
            has_pending = True
    return None if has_pending else 1
