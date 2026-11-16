#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""line_anchor.py — 行号逻辑统一封装模块（锚定校验与重定位引擎）

设计原则：
1. 行号准确性为发布前置强制校验项（ENABLE_ANCHOR 默认开启）：
   行号与代码证据（issue.code 片段）对不上时用 code 反查重定位；
   证据不匹配且无法可靠重定位的条目标记 invalid，由发布侧降级全局评论
   （不静默丢弃问题，fail-safe 而非 fail-open）
2. 行号相关逻辑收敛到本模块，其余流程零感知
3. 不改变现有 issue schema、门禁、发布逻辑：
   新增 _anchor / _anchorNote / _anchorOrigLine 内部字段，归档时剔除

坐标系规则（与 format_diff_line 一致，发布端 comment-add 锚定同构）：
- ADDED    → destination（新文件行号），对应评论 lineType=ADDED
- REMOVED  → source（旧文件行号），对应评论 lineType=REMOVED
- CONTEXT  → destination（新文件行号）

锚定校验结果标记（issue["_anchor"]）：
- "verified"   code 片段唯一/多候选命中且与原行号一致（含原行号在候选中）
- "relocated"  code 片段唯一命中但与原行号不一致，已用真实行号覆盖
               （_anchorOrigLine 保留原行号供追溯）
- "kept"       无 code 证据且原行号合法；仅确认坐标，不代表证据已验证
- "invalid"    无法可靠锚定（含文件缺失/歧义、diff 缺失/空索引、异常）
               → 调用方全局兜底，_anchorNote 说明原因
- "skipped"    不参与行内评论的级别

锚定处置为「校验+重定位+非法拦截」三级；parse_diff_index 为公共入口，
供快照漂移重定位复用。
"""

from __future__ import annotations

import re

# 锚定校验器开关（默认开启：行号与代码证据校验为发布前置强制项）
ENABLE_ANCHOR = True

# 参与行内评论的严重级别（其余级别不发行内评论，校验无意义）
_ANCHOR_SEVERITIES = ("P0", "P1", "P2", "P3", "CONFIRM")

# 单行 code 片段参与反查的最小归一化长度（过滤 "}"、");" 类无判别力内容；
# 短内容只允许原行号精确验证，不盲目重定位）
_MIN_SINGLE_LINE_LEN = 4


def normalize_line_no(line_obj: dict, *, prefer: str = "destination") -> object:
    """行号取值 + 空值防御。

    prefer="destination": 优先新文件行号，缺失/None/非法时依次回落
                          source → ''（不返回 None，避免 f"{None:>4}" 输出字面量）
    prefer="source":     优先旧文件行号（REMOVED 行专用）
    """
    fallbacks = {
        "destination": ("destination", "source"),
        "source": ("source", "destination"),
    }[prefer]
    for key in fallbacks:
        val = line_obj.get(key)
        if isinstance(val, int) and val > 0:
            return val
    return ""


def format_diff_line(seg_type: str, line_obj: dict) -> str:
    """统一 diff 行格式化 —— 行号坐标系的唯一权威实现。

    坐标系规则：
      ADDED    → destination（新文件行号），与发布端 comment-add fileType=TO 对齐
      REMOVED  → source（旧文件行号），删除行在新文件中不存在
      CONTEXT  → destination（新文件行号）。
                 与 ADDED 的 destination 混用导致行号序列非单调（倒退/重复）
    输出格式：前缀字符 + 4 宽右对齐行号 + 空格 + 代码内容。
    """
    content = line_obj.get("line", "")
    if seg_type == "ADDED":
        return f"+{normalize_line_no(line_obj, prefer='destination'):>4} {content}"
    if seg_type == "REMOVED":
        return f"-{normalize_line_no(line_obj, prefer='source'):>4} {content}"
    return f" {normalize_line_no(line_obj, prefer='destination'):>4} {content}"


# ─── diff 解析（公共入口）───────────────────────────────────────────────

# 行格式：前缀(+/-/空格) + 右对齐行号(≥4 宽，任意位数) + 空格 + 内容。
# 行号字段显式分组：format_diff_line 在行号缺失时输出 4 个空格占位，
# 若内容以数字开头，内容首数字会被误读为行号（虚构行号）。
# 修复：捕获前导空格并校验宽度（空格 ≤3 且 空格+数字 ≥4），不满足即拒绝该行。
_DIFF_LINE_RE = re.compile(r"^([+\- ])( *)(\d+)(?: (.*))?$")


def parse_diff_index(diff_text):
    """解析 diff 文本 → 文件行索引。

    输入格式（code_cli pr-diff / compare-diff / get_pr_diff 拼接产物）：
      +++ b/path
      @@ -s,sp +d,dp @@
      +{dest:>4} content   (ADDED, destination 坐标)
      -{src:>4} content    (REMOVED, source 坐标)
       {dest:>4} content   (CONTEXT, destination 坐标)

    返回 {file: {"ADDED": [(line, norm)],
                 "REMOVED": [(line, norm)],
                 "CONTEXT": [(line, norm)],
                 "NEWVIEW": [(line, norm)]}}：
      NEWVIEW = ADDED+CONTEXT 按行号升序（新文件坐标系视图，
      lineType=ADDED 的 code 反查主战场；REMOVED 行不在新文件中不参与）。
      行号解析支持任意位数。
    """
    index = {}
    current_file = ""
    source_file = ""
    for raw in (diff_text or "").splitlines():
        if raw.startswith("--- "):
            # 新文件边界清空旧状态；删除文件 destination 可能为空。
            source_file = raw[4:].strip()
            if source_file.startswith("a/"):
                source_file = source_file[2:]
            if source_file == "/dev/null":
                source_file = ""
            current_file = ""
            continue
        if raw.startswith("+++ "):
            destination_file = raw[4:].strip()
            if destination_file.startswith("b/"):
                destination_file = destination_file[2:]
            current_file = (source_file if destination_file in ("", "/dev/null")
                            else destination_file)
            if current_file and current_file not in index:
                index[current_file] = {"ADDED": [], "REMOVED": [], "CONTEXT": []}
            source_file = ""
            continue
        if not current_file or current_file not in index:
            continue
        m = _DIFF_LINE_RE.match(raw)
        if not m:
            continue
        prefix, pad, num, content = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        # 宽度校验：行号缺失的占位行（4 空格 + 1 空格 = ≥5 前导空格）与
        # 窄于 4 宽的畸形行号一律不解析（fail-closed，不参与锚定索引）
        if len(pad) > 3 or len(pad) + len(num) < 4:
            continue
        bucket = {"+": "ADDED", "-": "REMOVED", " ": "CONTEXT"}[prefix]
        index[current_file][bucket].append((int(num), _norm(content)))
    for buckets in index.values():
        buckets["NEWVIEW"] = sorted(
            buckets["ADDED"] + buckets["CONTEXT"], key=lambda x: x[0])
    return index


# ─── 锚定校验与重定位（主入口）─────────────────────────────────────────

def anchor_issues(issues: list, diff_text: str | None = None) -> list:
    """锚定校验与重定位主入口（原地修改并返回 issues）。

    校验链（对每条参与行内评论的 issue）：
      1. code 片段反查（归一化空白匹配，保留内部空行）：
         仅实际 ADDED/REMOVED 起始行可成为对应 lineType 的候选；
         原行号命中 verified / 唯一其他候选 relocated / 否则 invalid。
         过短单行证据只允许验证原行号，不用于重定位。
      2. 无 code 片段 → 仅行号合法性校验，合法 kept / 否则 invalid。
    无 diff 快照 / 内部异常 → invalid + 原因，由调用方全局兜底；
    不删 issue、不修改失败条目的行号、不抛出校验异常。
    幂等：已带 _anchor 标记的条目不重算（支持快照漂移后二次校验，
    二次校验前调用方需先 pop 掉旧标记）。
    """
    if not issues:
        return issues
    if not ENABLE_ANCHOR:
        for it in issues:
            it.setdefault("_anchor", "disabled")
        return issues
    try:
        if not diff_text or not diff_text.strip():
            return _mark_unresolved(issues, "missing_diff: diff 快照缺失或为空，需全局兜底")
        return _do_anchor(issues, diff_text)
    except Exception as exc:
        return _mark_unresolved(
            issues, f"error: 锚定校验异常 {type(exc).__name__}，需全局兜底")


def _mark_unresolved(issues: list, note: str) -> list:
    """保留列表及既有标记；待校验条目显式交给调用方兜底。"""
    for it in issues:
        if not isinstance(it, dict) or "_anchor" in it:
            continue
        if str(it.get("severity") or "").upper() not in _ANCHOR_SEVERITIES:
            it["_anchor"] = "skipped"
        else:
            it["_anchor"] = "invalid"
            it["_anchorNote"] = note
    return issues


def _do_anchor(issues: list, diff_text: str) -> list:
    """anchor_issues 的实际实现（异常由外层兜底）。"""
    index = parse_diff_index(diff_text)
    if not any(b["ADDED"] or b["REMOVED"] or b["CONTEXT"] for b in index.values()):
        return _mark_unresolved(issues, "empty_diff: diff 无可解析行，需全局兜底")
    for it in issues:
        if not isinstance(it, dict) or "_anchor" in it:
            continue  # 幂等：已标记的不重算
        try:
            _anchor_one(it, index)
        except Exception as exc:
            _mark_unresolved([it], f"error: 锚定校验异常 {type(exc).__name__}，需全局兜底")
    return issues


def _anchor_one(it: dict, index: dict) -> None:
    """单条校验；隔离坏字段异常，不阻止其余 issue 重定位。

    片段语义（与 schema 对齐）：issue.code 是「问题代码片段（含上下文
    ≥3-5 行）」，issue.line 指向其中的问题行——问题行可位于片段任意位置
    （含首行），片段起始行≠问题行。判定：
      - verified: 原行号落在某个匹配 span 内且属于该 lineType 合法行
      - relocated: 原 line 缺失/非法/不在任何 span 内，且全部 span 中恰有
        一个合法「问题行」候选 → 用该行覆盖；多 span 或 span 内多合法行
        （歧义）不重定位，交全局兜底
      - 其余 → invalid（调用方全局兜底，不静默丢弃）
    """
    sev = (it.get("severity") or "").upper()
    if sev not in _ANCHOR_SEVERITIES:
        it["_anchor"] = "skipped"
        return
    file_ = (it.get("file") or "").strip()
    line = it.get("line")
    line_type = (it.get("lineType") or "ADDED").upper()
    target = _find_file(index, file_)
    if not target or line_type not in ("ADDED", "REMOVED"):
        it["_anchor"] = "invalid"
        it["_anchorNote"] = ("nofile: 文件缺失或路径匹配有歧义，需全局兜底"
                             if not target else f"非法 lineType={line_type}，需全局兜底")
        return
    buckets = index[target]
    legal = _legal_lines(buckets, line_type)
    line_valid = isinstance(line, int) and not isinstance(line, bool) and line > 0
    code = (it.get("code") or "").strip()
    want = [_norm(x) for x in code.splitlines()] if code else []
    search_seq = buckets["REMOVED"] if line_type == "REMOVED" else buckets["NEWVIEW"]
    # NEWVIEW 可用 CONTEXT 验证后续序列；REMOVED 序列同构。
    # span = 匹配起始行号；问题行候选 = span 覆盖范围内属于该 lineType
    # 合法行的行号（span..span+len(want)-1，含首行）。
    spans = _find_sequence(search_seq, want) if want else []
    m = len(want)
    legal_in_span = sorted({ln for ln in spans
                            for ln in range(ln, ln + m)
                            if ln in legal}) if want else []
    short = len(want) == 1 and len(want[0]) < _MIN_SINGLE_LINE_LEN

    if line_valid and line in legal_in_span:
        it["_anchor"] = "verified"
    elif not want and line_valid and line in legal:
        it["_anchor"] = "kept"
        it["_anchorNote"] = "无 code 证据，仅确认行号合法（未验证代码）"
    elif len(spans) == 1 and not short:
        # 唯一 span：优先取 span 覆盖范围内合法问题行——
        #   恰一个 → 重定位到该行
        #   多个（如 span 覆盖多个连续 ADDED 行）→ 歧义不猜：无论原 line
        #     是否存在均不取首个合法行，标 invalid 交全局兜底（契约①不猜行号）
        if len(legal_in_span) == 1:
            cand = legal_in_span[0]
            it["_anchorOrigLine"] = line
            it["line"] = cand
            it["_anchor"] = "relocated"
            it["_anchorNote"] = f"行号 {line} → {cand}（按 code 片段重定位）"
            return
        it["_anchor"] = "invalid"
        it["_anchorNote"] = (f"code 片段唯一命中但 span 内 {line_type} 合法行 "
                             f"{len(legal_in_span)} 个（歧义），需全局兜底")
        return
    else:
        it["_anchor"] = "invalid"
        reason = ("单行 code 过短，不能可靠重定位" if short else
                  f"code 片段 {len(spans)} 处命中（合法候选 {len(legal_in_span)}），"
                  f"原行号 {line} 未命中" if want else
                  f"无 code 证据且行号 {line} 不在 {line_type} 行集合")
        it["_anchorNote"] = reason + "，需全局兜底"


def _legal_lines(buckets: dict, line_type: str) -> set:
    """该 lineType 的合法行号集合（评论锚定坐标系）。"""
    if line_type == "REMOVED":
        return {ln for ln, _ in buckets["REMOVED"]}
    if line_type == "ADDED":
        return {ln for ln, _ in buckets["ADDED"]}
    return set()


def _find_sequence(seq: list, want: list) -> list:
    """在 [(line, norm)] 有序序列中查找 want（归一化行列表）的所有命中起始行号。

    行号连续性约束：命中序列的行号必须逐行 +1 递增（NEWVIEW 排序后
    跨 hunk 的行号跳跃不算连续，防止把断裂处的相邻行误判为代码序列）。
    """
    if not want or not seq:
        return []
    n, m = len(seq), len(want)
    hits = []
    for i in range(n - m + 1):
        base = seq[i][0]
        if all(seq[i + j][1] == want[j] and seq[i + j][0] == base + j
               for j in range(m)):
            hits.append(base)
    return hits


def _norm(s: str) -> str:
    """归一化：引号外折叠连续空白并去首尾；引号内内容原样保留。

    仅对引号字面量外的空白做归一，字面量内部空白保留原样。
    局限（保守降级，不产生错锚）：非词法级实现——注释内撇号（don't/can't）、
    跨行字符串截断行会进入"引号内"状态导致空白不折叠，此时与基线一致
    按整行折叠处理（对称归一，两侧同文本仍判等，仅降低空白漂移容忍度，
    误判走 invalid → 全局兜底，符合「定位可靠性与问题有效性分开」原则）。
    """
    s = s or ""
    # 引号配对不平衡（" 与 ' 各自为奇数个）→ 非合法字面量行（注释/截断行），
    # 回退基线整行折叠，避免撇号把后续空白锁进"引号内"造成假不等
    if s.count('"') % 2 == 1 or s.count("'") % 2 == 1:
        return " ".join(s.split())
    out = []
    i, n = 0, len(s)
    in_str = False
    quote = ""
    pending_ws = False
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch in ("'", '"'):
            if pending_ws and out:
                out.append(" ")
            pending_ws = False
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch.isspace():
            pending_ws = True
            i += 1
            continue
        if pending_ws and out:
            out.append(" ")
        pending_ws = False
        out.append(ch)
        i += 1
    return "".join(out)


def _find_file(file_lines: dict, name: str) -> str | None:
    name = (name or "").strip()
    if not name:
        return None
    if name in file_lines:
        return name
    # 分级匹配，后缀要求目录边界；任一级多命中立即弃权。
    for matcher in (
        lambda f: f.endswith("/" + name) or name.endswith("/" + f),
        lambda f: f.split("/")[-1] == name.split("/")[-1],
    ):
        hits = [f for f in file_lines if matcher(f)]
        if hits:
            return hits[0] if len(hits) == 1 else None
    return None
