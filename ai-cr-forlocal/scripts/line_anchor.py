#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""line_anchor.py — 行号锚定统一封装模块(ai-cr-forlocal 版)

设计原则:
1. 行号准确性为尽力而为的增强项:fail-open,任何异常原样返回,不阻断发布、
   不影响问题检出或导致降级
2. 行号逻辑收敛到本模块,主流程(publish_results_local)零行号知识
3. 不改变现有 issue schema、门禁、发布逻辑(DLC JSON 字段冻结不受影响,
   _anchor 内部标记不进入任何下游输出)
4. 保守校正:仅当 issue.line 缺失/0/非法时才补写权威行号,非 0 不覆盖
   (避免匹配歧义时引入新错误)

本地模式适配说明:
- 输入是本地 git unified diff(非 code 平台 API 行对象),无 format_diff_line
  坐标系修复职责(git diff 输出本身坐标系正确,无需重格式化)
- 锚定索引从 @@ hunk 头推算双坐标:新增/上下文行 → 新文件行号(destination),
  删除行 → 旧文件行号(source);与 issue schema 的 lineType=added/removed 对齐
  (added/context 行锚新文件坐标,removed 行锚旧文件坐标)

ENABLE_ANCHOR 开关(观察期策略):
- False(默认)= 观察模式:仅做 code 片段匹配并打 _anchor=verified/unverified
  标记 + 调用方日志统计,零修改任何 issue 字段(行为与无此模块完全一致)
- True = 校正模式:命中且原 line 缺失/0/非法时补写权威行号
"""

from __future__ import annotations

import re

# 锚定校验器开关(默认关闭:观察期,仅统计 verified/unverified,不校正;
# 错行率数据稳定后再决定是否置 True 开启校正)
ENABLE_ANCHOR = False

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FILE_RE = re.compile(r"^\+\+\+ b/(.+?)\s*$")


def _valid_line(val) -> bool:
    """line 字段是否为有效的正整数(字符串数字也接受)"""
    try:
        return int(str(val).strip()) > 0
    except (TypeError, ValueError):
        return False


def _norm(s: str) -> str:
    """归一化:折叠全部空白(容错缩进/行尾差异)"""
    return " ".join((s or "").split())


def _build_index(diff_text: str) -> tuple[dict, dict]:
    """解析 unified diff,构建双坐标索引。

    返回 (new_lines, old_lines):
      new_lines[file] = [(新文件行号, 归一化内容)]   # added + context 行
      old_lines[file] = [(旧文件行号, 归一化内容)]   # removed + context 行
    """
    new_lines: dict[str, list] = {}
    old_lines: dict[str, list] = {}
    current_file = ""
    src_no = dst_no = 0
    in_hunk = False
    for raw in diff_text.splitlines():
        m = _FILE_RE.match(raw)
        if m:
            current_file = m.group(1)
            in_hunk = False
            new_lines.setdefault(current_file, [])
            old_lines.setdefault(current_file, [])
            continue
        hm = _HUNK_RE.match(raw)
        if hm:
            src_no = int(hm.group(1))
            dst_no = int(hm.group(3))
            in_hunk = True
            continue
        if not in_hunk or not current_file:
            continue
        if raw == "":
            # 空 context 行(行尾空白被部分工具链剥离时 \" \" 变 \"\"):
            # 按空行计入索引并推进双坐标,否则后续行号整体漂移
            new_lines[current_file].append((dst_no, ""))
            old_lines[current_file].append((src_no, ""))
            src_no += 1
            dst_no += 1
            continue
        tag, content = raw[0], raw[1:]
        if tag == "+":
            new_lines[current_file].append((dst_no, _norm(content)))
            dst_no += 1
        elif tag == "-":
            old_lines[current_file].append((src_no, _norm(content)))
            src_no += 1
        elif tag == " ":
            new_lines[current_file].append((dst_no, _norm(content)))
            old_lines[current_file].append((src_no, _norm(content)))
            src_no += 1
            dst_no += 1
        # '\ No newline at end of file' 等元行忽略
    return new_lines, old_lines


def _find_file(index: dict, name: str) -> str | None:
    """文件名归一化匹配(模型可能只写类名或省略路径前缀)"""
    name = (name or "").strip()
    if not name:
        return None
    if name in index:
        return name
    for f in index:
        if f.endswith(name) or name.endswith(f) or f.split("/")[-1] == name.split("/")[-1]:
            return f
    return None


def _match_lines(lines: list, want: list) -> int | None:
    """在索引行序列中找 want(归一化内容列表)的连续命中,返回起始权威行号"""
    if not want or not lines:
        return None
    for i in range(len(lines) - len(want) + 1):
        if all(lines[i + j][1] == want[j] for j in range(len(want))):
            return lines[i][0]
    return None


def anchor_issues(issues: list, diff_text: str | None = None) -> list:
    """发布前锚定校验(fail-open,任何异常返回原列表)。

    拿 issue.code 片段回 diff 双坐标索引做归一化匹配:
      - 命中 → 标记 _anchor="verified";ENABLE_ANCHOR=True 且原 line
        缺失/0/非法时,补写匹配到的权威行号(lineType=removed 锚旧文件坐标,
        其余锚新文件坐标)
      - 未命中 → 原样返回,标记 _anchor="unverified"(仅统计)
    """
    if not issues:
        return issues
    try:
        return _do_anchor(issues, diff_text)
    except Exception:
        return issues


def _do_anchor(issues: list, diff_text: str | None) -> list:
    """anchor_issues 的实际实现(异常由外层统一处理)。"""
    if not diff_text:
        for it in issues:
            it.setdefault("_anchor", "unverified")
        return issues

    new_lines, old_lines = _build_index(diff_text)
    for it in issues:
        it.setdefault("_anchor", "unverified")
        code = (it.get("code") or "").strip()
        if not code:
            continue
        line_type = str(it.get("lineType") or "").strip().lower()
        # removed 行只存在于旧文件 → 锚旧坐标;added/context 锚新坐标
        if line_type == "removed":
            target = _find_file(old_lines, it.get("file") or "")
            lines = old_lines.get(target, []) if target else []
        else:
            target = _find_file(new_lines, it.get("file") or "")
            lines = new_lines.get(target, []) if target else []
        want = [_norm(x) for x in code.splitlines() if x.strip()]
        if not want:
            continue
        hit = _match_lines(lines, want)
        if hit is not None:
            it["_anchor"] = "verified"
            # 保守策略:仅当原行号缺失/0/非法时补写,非 0 不覆盖
            if ENABLE_ANCHOR and not _valid_line(it.get("line")):
                it["line"] = hit
    return issues
