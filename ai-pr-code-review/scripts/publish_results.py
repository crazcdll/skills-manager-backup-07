#!/usr/bin/env python3
"""
publish_results.py — AI-CR Agent 发布结果一体化脚本

从统一 Issue JSON 文件 + 章节片段文件拼装全部产物，一次调用完成：
  Step 6（创建学城文档）+ Step 7（评论到 PR）+ Step 8（大象群推送）+ Step 9（回写 CR 结果）

设计原则：报告文档 / PR 评论 / 大象消息的【拼装与发送】全部由本脚本固化完成，
大模型只负责产出结构化 Issue JSON 和少量叙述性章节片段，禁止自由发挥排版。

学城文档的章节结构与文案模板以 references/output/citadel-doc-template.md 为权威规格，
本脚本的 assemble_citadel_doc() 即按该模板拼装（模板仅供脚本内部引用，SKILL.md 不引用）。

用法:
  python3 publish_results.py \
    --pr-url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff" \
    --pr-id 123 --pr-title "PR标题" \
    --org "org" --repo "repo" \
    --submitter-mis "submitter_mis" --author-name "提交人姓名" \
    --trigger-mis "trigger_mis" --trigger-name "触发人姓名" \
    --citadel-parent-id "2763548622" \
    --team-chat-group-id "70528010534" \
    --issues-file /tmp/cr_issues_123_step4.json \
    [--changed-files-file /tmp/cr_changed_files_123.md] \
    [--summary-file /tmp/cr_summary_123.md] \
    [--sdd-file /tmp/cr_sdd_123.md] \
    [--catpaw-file /tmp/cr_catpaw_123.md] \
    [--branch "feature/x"] [--file-count 12] [--line-changes "+120 -30"] \
    [--conclusion "🟠需修复"]   # 不传则按 P0/P1/P2 计数自动推导
    [--km-url "已知的学城URL，跳过Step6"]
    [--conversation-id "1024会话ID"]  # 可选；不传则自动读环境变量 X_AI_SESSIONID → rootConversationId

输出: stdout JSON
  {
    "step6": {"ok": true, "km_url": "..."},
    "step7": {"ok": true, "inline_count": 3, "global_ok": true},
    "step8": {"ok": true, "global_group_ok": true, "team_group_ok": true},
    "step9": {"ok": true, "skipped": false, "status": "ok", "error": ""},
    "counts": {"p0": N, "p1": N, "p2": N, "p3": N},
    "conclusion": "🟠需修复"
  }
"""
import argparse
import json
import os
import subprocess
import sys
import time
import re
from datetime import datetime

# 同目录 import cr_comment（CommentClient）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr_comment import CommentClient, CommentError


# ─── 常量 ────────────────────────────────────────────────────────────────────
RETRY_MAX = 4
RETRY_INTERVAL = 2.5  # 秒

# 大象 API 凭证（与 notify.py / daxiang-notify-api.md 一致）
import base64, hmac, hashlib, uuid, urllib.request, urllib.parse

AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151
TOKEN_URL            = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL             = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"

# Step 9: 写入 DB（submit-task 新建模式 + 多维表格降级）
DB_HOST = "spt.sankuai.com"
DB_PATH = "/api/v1/aicr/submit-task"
DB_TIMEOUT = 20
DB_DEFAULT_SCHEME = "https"
DEFAULT_TABLE_ID = "2751197605"
TABLE_COLUMN_IDS = "1,2,3,4,5,6,7,8,9,11,12"

# 动态从 SKILL.md frontmatter 读取 skillhub.version
import re as _re
# 优先从 __file__ 推导 SKILL.md 路径；如果失败（沙箱解压结构不同），回退到 SKILL_DIR 环境变量
_SKILL_MD_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SKILL.md"),  # scripts/.. / SKILL.md
    os.path.join(os.environ.get("SKILL_DIR", ""), "SKILL.md"),  # $SKILL_DIR/SKILL.md
]
SKILL_VERSION = "V0"
for _path in _SKILL_MD_CANDIDATES:
    try:
        if not _path or not os.path.isfile(_path):
            continue
        with open(_path, "r", encoding="utf-8") as _f:
            _content = _f.read()
        _m = _re.search(r'skillhub\.version:\s*"(V\d+)"', _content)
        if _m:
            SKILL_VERSION = _m.group(1)
            break
    except Exception:
        continue

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "confirm": 4}
SEVERITY_EMOJI = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵", "confirm": "❓"}
SEVERITY_TITLE = {
    "P0": "P0 — 零容忍异常 🔴",
    "P1": "P1 — 稳定性风险 🟠",
    "P2": "P2 — 代码规范 🟡",
    "P3": "P3 — 优化建议 🔵",
}

# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def log(msg):
    """打印日志到 stderr（不污染 stdout JSON 输出）"""
    print(f"[publish] {msg}", file=sys.stderr)


def retry(fn, label="operation"):
    """带重试的执行，返回 (ok, result_or_error)"""
    last_err = ""
    for i in range(1, RETRY_MAX + 1):
        try:
            result = fn()
            return True, result
        except Exception as e:
            last_err = str(e)
            log(f"⚠️  {label} 第 {i}/{RETRY_MAX} 次失败: {last_err}")
            if i < RETRY_MAX:
                time.sleep(RETRY_INTERVAL)
    return False, last_err


def run_cmd(cmd, label="cmd"):
    """执行 shell 命令，返回 stdout+stderr 合并输出。失败抛异常。
    注：oa-skills citadel 等工具把业务输出写到 stderr，所以必须合并。
    """
    log(f"▶ {label}: {cmd[:200]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    if result.returncode != 0:
        raise RuntimeError(f"exit={result.returncode} output={combined[:500]}")
    return combined


def read_text_file(path, default=""):
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        log(f"⚠️  读取文件失败 {path}: {e}")
        return default


def _parse_json_obj(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _extract_content_id(text):
    try:
        data = json.loads(text)
        return str(data.get("contentId") or data.get("id") or data.get("data", {}).get("contentId") or "")
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    m = re.search(r'(?:文档ID|文档 ID|contentId|id)[：:\s]+([0-9]+)', text)
    if m:
        return m.group(1)
    m = re.search(r'collabpage/([0-9]+)', text)
    if m:
        return m.group(1)
    return ""


def _extract_url(text):
    try:
        data = json.loads(text)
        return data.get("url") or data.get("link") or ""
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    m = re.search(r'(https?://km\.sankuai\.com/collabpage/[0-9]+)', text)
    if m:
        return m.group(1)
    return ""


# ─── Issue 加载与拼装 ─────────────────────────────────────────────────────────

def load_issues(issues_files):
    """从多个 JSON 文件加载 issue 列表，合并、去重、排序。
    每个文件内容为 JSON 数组（issue 对象 schema 见 issue-json-schema.md）。
    """
    all_issues = []
    for path in issues_files:
        if not path or not os.path.isfile(path):
            log(f"⚠️  issues 文件不存在，跳过: {path}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log(f"⚠️  解析 issues 文件失败 {path}: {e}")
            continue
        if isinstance(data, list):
            all_issues.extend(data)
        else:
            log(f"⚠️  issues 文件非 JSON 数组，跳过: {path}")

    # 规范化 + 去重（同 file + line + ruleId 视为重复，保留首个）
    seen = set()
    deduped = []
    for it in all_issues:
        if not isinstance(it, dict):
            continue
        sev_raw = (it.get("severity") or "").strip()
        if sev_raw.lower() == "confirm":
            sev = "confirm"
        else:
            sev = sev_raw.upper()
        if sev not in SEVERITY_ORDER:
            log(f"⚠️  issue severity 非法 '{sev_raw}'，丢弃: {it.get('ruleId')}")
            continue
        it["severity"] = sev
        key = (it.get("file", ""), it.get("line"), it.get("ruleId", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    deduped.sort(key=lambda x: SEVERITY_ORDER.get(x["severity"], 99))
    return deduped


def count_issues(issues):
    counts = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}
    for it in issues:
        sev = it["severity"]
        if sev == "P0":
            counts["p0"] += 1
        elif sev == "P1":
            counts["p1"] += 1
        elif sev == "P2":
            counts["p2"] += 1
        elif sev == "P3":
            counts["p3"] += 1
    return counts


def derive_conclusion(counts, override=""):
    """根据 P0/P1/P2 计数自动推导 Review 结论。override 非空时直接用。"""
    if override:
        return override
    if counts["p0"] > 0 or counts["p1"] > 0:
        return "🟠需修复"
    if counts["p2"] > 3:
        return "💚通过有建议"
    return "✅通过"


def split_summary_file(summary_md):
    """将 summary 文件按 ## 标题拆分为三个部分：变更综述、总体评价、人工复审要点。
    返回 dict {"change_summary": str, "overall_eval": str, "manual_review": str}。
    缺失部分返回空字符串。
    """
    result = {"change_summary": "", "overall_eval": "", "manual_review": ""}
    if not summary_md:
        return result

    # 按 ## 标题分段
    sections = {}
    current_title = None
    current_lines = []
    for line in summary_md.split("\n"):
        if line.startswith("## "):
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()

    # 映射到三个部分
    for title, content in sections.items():
        title_lower = title.lower()
        if "变更综述" in title or "change" in title_lower:
            result["change_summary"] = content
        elif "总体评价" in title or "overall" in title_lower:
            result["overall_eval"] = content
        elif "人工复审" in title or "manual" in title_lower or "复审" in title:
            result["manual_review"] = content

    # 如果没有分段标记，整个内容作为总体评价
    if not result["change_summary"] and not result["overall_eval"] and not result["manual_review"]:
        result["overall_eval"] = summary_md.strip()

    return result


def _split_code_blocks(text, lang="java"):
    """将混合内容拆分为代码块和说明文字段落。
    识别策略：
    1. 如果文本已包含 markdown 代码块标记(```),直接透传不二次处理
    2. 以行为单位判断——包含代码语法特征(括号/分号/赋值/方法调用/关键字等)
       的连续行归为代码块,其他行作为说明文字段落
    3. 纯英文说明句(以动词开头+空格+宾语)不误判为代码
    """
    if not text or not text.strip():
        return []

    # 如果已包含 markdown 代码块标记,透传但确保闭合正确且代码块标记前有空行
    if "```" in text:
        tl = text.split("\n")
        fixed = []
        fence_open = False
        for j, ln in enumerate(tl):
            stripped = ln.strip()
            if stripped.startswith("```"):
                if not fence_open:
                    # 代码块开始
                    if fixed and fixed[-1].strip() != "":
                        fixed.append("")  # 代码块标记前加空行
                    fixed.append(ln)
                    fence_open = True
                else:
                    # 代码块结束
                    fixed.append(ln)
                    fence_open = False
                    if j < len(tl) - 1 and tl[j+1].strip() != "":
                        fixed.append("")  # 代码块结束后加空行
            else:
                fixed.append(ln)
        # 如果代码块未闭合,补上闭合标记
        if fence_open:
            fixed.append("```")
        return ["\n".join(fixed)]

    lines = text.strip().split("\n")
    result = []
    code_buf = []

    # 代码关键字列表(用于识别纯英文说明句 vs 代码)
    _JAVA_KEYWORDS = {"if", "else", "for", "while", "switch", "case", "break",
                      "return", "try", "catch", "finally", "throw", "throws",
                      "new", "import", "package", "class", "public", "private",
                      "protected", "static", "final", "void", "int", "long",
                      "boolean", "String", "enum", "interface", "extends",
                      "implements", "this", "super", "null", "true", "false",
                      "abstract", "synchronized", "volatile", "transient"}

    def _is_code(line):
        stripped = line.strip()
        if not stripped:
            return False
        # 中文行 -> 说明文字
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in stripped)
        if has_chinese:
            return False
        # 代码语法特征:括号/分号/赋值/方法调用等
        has_code_syntax = any(c in stripped for c in "=;{}()<>[]@&|!?")
        if has_code_syntax:
            return True
        # 无中文也无代码符号:判断是否为代码行
        # 纯英文句子(含空格+以句号结尾) -> 说明文字
        words = stripped.split()
        if len(words) >= 3 and not words[-1].endswith(";"):
            # 3个以上单词且不以分号结尾,大概率是英文说明句
            # 但如果第一个词是 Java 关键字,仍可能是代码
            if words[0] not in _JAVA_KEYWORDS:
                return False
        # 单词少或以分号结尾 -> 代码
        return True

    for line in lines:
        if _is_code(line):
            code_buf.append(line)
        else:
            if code_buf:
                result.append(("code", "\n".join(code_buf)))
                code_buf = []
            result.append(("text", line))
    if code_buf:
        result.append(("code", "\n".join(code_buf)))

    # 拼装 markdown — 代码块和说明文字之间加空行，避免学城渲染时代码块被粘连
    md_lines = []
    prev_kind = None
    for kind, content in result:
        if kind == "code":
            if prev_kind == "text":
                md_lines.append("")  # 说明文字后加空行再接代码块
            md_lines.append(f"```{lang}")
            md_lines.append(content)
            md_lines.append(f"```")
        else:
            if prev_kind == "code":
                md_lines.append("")  # 代码块后加空行再接说明文字
            md_lines.append(content)
        prev_kind = kind
    return md_lines


def _issue_doc_block(it, idx):
    """拼装单条 issue 的文档文案。P0/P1 用七字段格式，P2/P3 用简洁格式，confirm 用待确认格式。"""
    rule_id = it.get("ruleId", "") or ""
    anomaly = it.get("anomalyType", "") or ""
    summary = it.get("summary", "") or ""
    file_ = it.get("file", "") or ""
    line = it.get("line", "") or ""
    desc = it.get("description", "") or ""
    risk = it.get("risk", "") or ""
    sug = it.get("suggestion", "") or ""
    code = it.get("code", "") or ""
    sev = it["severity"]
    emoji = SEVERITY_EMOJI.get(sev, "")

    if sev in ("P0", "P1"):
        # 七字段格式（标题用 ####，所有字段标签用独立段落而非列表项，避免代码块打断列表）
        title = f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {anomaly} — {summary}" if anomaly else f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {summary}"
        lines = [
            "",
            f"#### {title}",
            "",
            f"**文件**：`{file_}` L{line}",
        ]
        if code:
            lines.append("")
            lines.append(f"**问题代码**：")
            lines.append("")
            lines.append(f"```java")
            lines.append(code)
            lines.append(f"```")
        lines.append("")
        lines.append(f"**检出原因**：{desc}")
        # 触达分析
        reach = it.get("reach_analysis", "") or ""
        if reach:
            lines.append("")
            lines.append(f"**触达分析**：{reach}")
        # 线上场景
        online = it.get("online_scenario", "") or ""
        if online:
            lines.append("")
            lines.append(f"**线上场景**：{online}")
        # 影响范围
        impact = it.get("impact_scope", "") or ""
        if impact:
            lines.append("")
            lines.append(f"**影响范围**：{impact}")
        lines.append("")
        lines.append(f"**修复建议**：")
        lines.append("")
        sug_lines = _split_code_blocks(sug)
        if sug_lines:
            lines.extend(sug_lines)
        else:
            lines.append(sug)
    elif sev in ("P2", "P3"):
        # 简洁格式（标题用 ####，字段用独立段落）
        lines = [
            "",
            f"#### {emoji} [{sev}-{idx:02d}] [{rule_id}] {summary}",
            "",
            f"**文件**：`{file_}` L{line}",
            "",
            f"**问题描述**：{desc}",
            "",
            f"**检出原因**：{risk}",
        ]
        rule_name = it.get("ruleName", "") or ""
        if rule_name:
            lines.append("")
            lines.append(f"**规范要求**：{rule_name}")
        lines.append("")
        lines.append(f"**修复建议**：")
        lines.append("")
        sug_lines = _split_code_blocks(sug)
        if sug_lines:
            lines.extend(sug_lines)
        else:
            lines.append(sug)
    elif sev == "confirm":
        # 待确认问题格式（标题用 ####，字段用独立段落）
        lines = [
            "",
            f"#### ❓ [Q-{idx:02d}] {summary}",
            "",
            f"**文件**：`{file_}` L{line}",
            "",
            f"**问题描述**：{desc}",
        ]
        confirm_reason = it.get("confirm_reason", "") or ""
        if confirm_reason:
            lines.append("")
            lines.append(f"**不确定原因**：{confirm_reason}")
        possible_risk = it.get("possible_risk", "") or ""
        if possible_risk:
            lines.append("")
            lines.append(f"**可能的风险**：{possible_risk}")
        confirm_sug = it.get("confirm_suggestion", "") or ""
        if confirm_sug:
            lines.append("")
            lines.append(f"**建议**：{confirm_sug}")
    else:
        # 回退格式
        lines = [
            "",
            f"##### [{sev}-{idx}] {rule_id} — {anomaly} — {summary}",
            f"",
            f"**命中规则**：`{rule_id}`",
            f"**文件**：{file_} L{line}",
            f"**问题**：{desc}",
            f"**风险**：{risk}",
            f"**修复建议**：{sug}",
        ]
    return "\n".join(lines)


def assemble_review_findings(issues):
    """拼装「四、Review 发现」整章。按 severity 分组、组内编号，不区分来源。
    包含规则命中摘要、P0~P3、待确认问题。"""
    sections = []

    # 规则命中摘要
    rule_summary = assemble_rule_hit_summary(issues)
    if rule_summary:
        sections.append(rule_summary)

    # P0~P3
    for sev in ["P0", "P1", "P2", "P3"]:
        group = [it for it in issues if it["severity"] == sev]
        if not group:
            continue
        lines = [f"### {SEVERITY_TITLE[sev]}", ""]
        for i, it in enumerate(group, 1):
            lines.append(_issue_doc_block(it, i))
            lines.append("")
        sections.append("\n".join(lines))

    # 待确认问题
    confirm_group = [it for it in issues if it["severity"] == "confirm"]
    if confirm_group:
        lines = ["### ❓ 待确认问题", ""]
        for i, it in enumerate(confirm_group, 1):
            lines.append(_issue_doc_block(it, i))
            lines.append("")
        sections.append("\n".join(lines))

    if not sections:
        sections = ["### Review 发现", "", "本次审查未发现问题。", ""]
    return "\n".join(sections)


def _expand_rids(it):
    """将 issue 的 ruleId 拆分为列表（处理合并情况）"""
    merged = it.get("mergedRuleIds", [])
    if merged:
        return merged
    rid = it.get("ruleId", "") or ""
    if "+" in rid:
        return [p.strip() for p in rid.split("+")]
    return [rid] if rid else []


def assemble_rule_hit_summary(issues):
    """从 issues 列表拼装「规则命中摘要」小节。"""
    if not issues:
        return ""

    # 统计各层级命中
    p0_rules = sorted(set(r for it in issues if it["severity"] == "P0" for r in _expand_rids(it)))
    p1_rules = sorted(set(r for it in issues if it["severity"] == "P1" for r in _expand_rids(it)))
    p2_rules = sorted(set(r for it in issues if it["severity"] == "P2" for r in _expand_rids(it)))
    p3_rules = sorted(set(r for it in issues if it["severity"] == "P3" for r in _expand_rids(it)))
    confirm_count = len([it for it in issues if it["severity"] == "confirm"])

    # CR vs MT vs CU 统计（合并的 issue 各计）
    cr_count = 0
    mt_count = 0
    cu_count = 0
    all_rids = []
    for it in issues:
        rids = _expand_rids(it)
        all_rids.extend(rids)
        for r in rids:
            if r.startswith("CR:"):
                cr_count += 1
            elif r.startswith("MT:"):
                mt_count += 1
            elif r.startswith("CU:"):
                cu_count += 1
    # fallback: 如果 CR:/MT:/CU: 都没匹配到，按 source 统计
    if cr_count == 0 and mt_count == 0 and cu_count == 0:
        cr_count = len([it for it in issues if it.get("source") == "step4a"])
        mt_count = len([it for it in issues if it.get("source") == "step4b"])
        cu_count = len([it for it in issues if it.get("source") == "step4c"])

    total_rules = len(set(all_rids))
    total_hits = len(issues)

    lines = [
        "### 规则命中摘要",
        "",
        f"**命中规则综述**：本次审查共激活 {total_rules} 条规则（CR: {cr_count} 条，MT: {mt_count} 条，CU: {cu_count} 条），命中 {total_hits} 条，分布如下：",
        "",
        f"- **P0 零容忍**：命中 {len(p0_rules)} 条{' — ' + ', '.join(p0_rules) if p0_rules else ''}",
        f"- **P1 稳定性**：命中 {len(p1_rules)} 条{' — ' + ', '.join(p1_rules) if p1_rules else ''}",
        f"- **P2 规范**：命中 {len(p2_rules)} 条{' — ' + ', '.join(p2_rules) if p2_rules else ''}",
        f"- **P3 性能**：命中 {len(p3_rules)} 条{' — ' + ', '.join(p3_rules) if p3_rules else ''}",
    ]
    if confirm_count > 0:
        lines.append(f"- **待确认**：{confirm_count} 条")
    lines.append("")
    lines.append("其中 CR: 规则命中 {} 条，MT: 规则命中 {} 条，CU: 自定义规则命中 {} 条。未命中的规则不再逐一列出。".format(
        cr_count, mt_count, cu_count))
    lines.append("")
    return "\n".join(lines)


def assemble_custom_rules_section(issues):
    """拼装「📋 自定义规则检查结果」子节。"""
    cu_issues = [it for it in issues if it.get("source") == "step4c" or
                 any(r.startswith("CU:") for r in _expand_rids(it))]
    if not cu_issues:
        return ""
    lines = [
        "### 📋 自定义规则检查结果",
        "",
        "> 以下问题来自仓库/团队/CatPaw 自定义规则（.mdp/rules/、.catpaw/rules/）。",
        "",
    ]
    # 按 severity 分组展示
    for sev in ("P0", "P1", "P2", "P3"):
        sev_issues = [it for it in cu_issues if it["severity"] == sev]
        if not sev_issues:
            continue
        emoji = SEVERITY_EMOJI.get(sev, "")
        lines.append(f"**{emoji} {sev}**：{len(sev_issues)} 条")
        for it in sev_issues:
            rule_id = it.get("ruleId", "")
            summary = it.get("summary", "")
            file = it.get("file", "")
            line = it.get("line", "")
            lines.append(f"- [{rule_id}] {summary}（`{file}` L{line}）")
        lines.append("")
    return "\n".join(lines)


def _short_hash(h):
    """commit hash 取前 8 位展示，空值返回空串。"""
    return (h or "")[:8]


# get_pr_diff.py 落盘的实际审查模式（含内部降级结果）
CR_MODE_INFO_PATH = "/tmp/cr_mode_info.json"


def _read_target_commit_from_mode_info(path=CR_MODE_INFO_PATH):
    """直接从 cr_mode_info.json 读取 targetCommit，不依赖大模型传参。

    get_pr_diff.py 在流程最早期就落盘了 targetCommit，
    publish_results.py 拼装 PR 评论时直接读文件，
    避免长流程中大模型丢失上下文导致基准行丢失。
    """
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f)
        if not isinstance(info, dict):
            return None
        tc = info.get("targetCommit")
        if tc and isinstance(tc, str) and re.match(r'^[0-9a-fA-F]{40}$', tc):
            return tc
        return None
    except Exception:
        return None


def backfill_cr_mode(args, path=CR_MODE_INFO_PATH):
    """以 cr_mode_info.json 为准回填增量 CR 四参数（兜底机制）。

    为什么需要：`get_pr_diff.py` 可能在内部**静默降级**（基准 commit 非法 /
    不在 commit 链上 / compare API 异常 / 增量无文件）。若 Agent 沿用早先
    Step 2C 的判定结果把 `--cr-mode incremental` 传进来，产出物就会标错
    「增量」，而实际审的是全量——这是静默错误，人看不出来。

    本函数把「靠模型自觉重读文件」变成「结构上不可能错」。

    优先级规则：
      * `crMode`：**文件为真相**。文件说 full 就是 full，直接覆盖命令行。
        （降级只会 incremental→full，不会反向；以文件为准总是安全的）
      * 三个 hash/计数字段：仅在命令行**未传**（None）时才回填，
        避免覆盖调用方显式指定的值。
      * 降为全量时清空 `base_commit` / `commit_count`，防止产出物出现
        「全量 + 却带着基准 commit」的矛盾文案。

    文件不存在 / 解析失败 → 静默跳过，保持命令行参数原样（不阻断主流程）。
    返回实际发生的修正列表，供日志与测试断言。
    """
    fixes = []
    if not os.path.isfile(path):
        return fixes
    try:
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f)
        if not isinstance(info, dict):
            return fixes
    except Exception as e:
        log(f"⚠️  {path} 解析失败，沿用命令行参数：{e}")
        return fixes

    # 1) crMode：文件为真相
    fmode = info.get("crMode")
    if fmode in ("full", "incremental"):
        if getattr(args, "cr_mode", "full") != fmode:
            fixes.append(f"cr_mode: {getattr(args, 'cr_mode', None)} → {fmode}")
            args.cr_mode = fmode

    # 2) hash / 计数：仅回填未传的
    for attr, key in (("base_commit", "baseCommit"),
                      ("target_commit", "targetCommit"),
                      ("commit_count", "commitCount")):
        if not getattr(args, attr, None) and info.get(key) is not None:
            setattr(args, attr, info[key])
            fixes.append(f"{attr}: (未传) → {info[key]}")

    # 3) 全量模式下清掉增量专属字段，避免自相矛盾
    if getattr(args, "cr_mode", "full") == "full":
        for attr in ("base_commit", "commit_count"):
            if getattr(args, attr, None) is not None:
                fixes.append(f"{attr}: {getattr(args, attr)} → None（全量模式清空）")
                setattr(args, attr, None)

    return fixes


def scope_label(args, compact=False):
    """拼装「审查范围」展示文本。

    compact=False → 🟩 增量（从 `7394fa3d` → `4b1e3bd3`，5 个新 commit）
    compact=True  → 🟩增量(5个新commit)   （大象群推送用，尽量短）
    """
    if getattr(args, "cr_mode", "full") != "incremental":
        return "🟦全量" if compact else "🟦 全量"

    base = _short_hash(getattr(args, "base_commit", None))
    target = _short_hash(getattr(args, "target_commit", None))
    cc = getattr(args, "commit_count", None)

    if compact:
        return f"🟩增量({cc}个新commit)" if cc is not None else "🟩增量"

    seg = []
    if base and target:
        seg.append(f"从 `{base}` → `{target}`")
    if cc is not None:
        seg.append(f"{cc} 个新 commit")
    return f"🟩 增量（{'，'.join(seg)}）" if seg else "🟩 增量"


def assemble_citadel_doc(args, issues, counts, conclusion):
    """拼装完整学城文档 Markdown（8 章结构）。"""
    parts = []

    # 标题
    parts.append(f"# PR #{args.pr_id} Code Review：{args.pr_title}")
    parts.append("")

    # 一、PR 概述（脚本拼表格）
    overview_rows = [
        ("仓库", f"{args.org}/{args.repo}"),
        ("PR 编号", f"#{args.pr_id}"),
        ("标题", args.pr_title),
        ("提交人", f"{args.author_name}（{args.submitter_mis}）"),
    ]
    # 触发人
    if args.trigger_name:
        overview_rows.append(("触发人", f"{args.trigger_name}（{args.trigger_mis}）"))
    if args.branch:
        overview_rows.append(("分支", args.branch))
    if args.file_count is not None:
        overview_rows.append(("文件数", str(args.file_count)))
    if args.line_changes:
        overview_rows.append(("行数变化", args.line_changes))
    overview_rows.append(("审查范围", scope_label(args)))
    overview_rows.append(("Skill版本", f"ai-pr-code-review {SKILL_VERSION}"))

    overview_table = "| 项目 | 内容 |\n|------|------|\n"
    for k, v in overview_rows:
        overview_table += f"| {k} | {v} |\n"
    parts.append("## 一、PR 概述")
    parts.append(overview_table.strip())
    parts.append("")

    # 拆分 summary 文件
    summary_md = read_text_file(args.summary_file, "")
    summary_parts = split_summary_file(summary_md)

    # 二、变更综述（从 summary 文件拆分）
    parts.append("## 二、变更综述")
    if summary_parts["change_summary"]:
        parts.append(summary_parts["change_summary"])
    else:
        # 兜底：从变更文件清单自动拼简易综述
        changed_files_md = read_text_file(getattr(args, 'changed_files_file', ''), "")
        if changed_files_md:
            file_lines = [l.strip() for l in changed_files_md.strip().split("\n") if l.strip() and not l.startswith("#")]
            file_count = len(file_lines)
            # 按扩展名分类统计
            ext_counts = {}
            for fl in file_lines:
                name = fl.lstrip("- ").strip()
                ext = os.path.splitext(name)[1] or "(无扩展名)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            ext_summary = "、".join(f"{ext}({cnt}个)" for ext, cnt in sorted(ext_counts.items(), key=lambda x: -x[1])[:5])
            parts.append(f"本次变更涉及 **{file_count}** 个文件，文件类型分布：{ext_summary}。")
            parts.append("")
            parts.append("**变更文件清单：**")
            parts.append("")
            for fl in file_lines[:30]:
                parts.append(f"- {fl.lstrip('- ').strip()}")
            if file_count > 30:
                parts.append(f"- ...（共 {file_count} 个文件，仅展示前 30 个）")
            log("⚠️  变更综述为空，已从变更文件清单自动生成简易综述")
        else:
            parts.append("（主 Agent 未产出变更综述内容，且无变更文件清单可用）")
            log("⚠️  变更综述为空且无变更文件清单，显示占位文本")
    parts.append("")

    # 三、SDD 产物校验（从 sdd 文件透传，无则跳过）
    sdd_md = read_text_file(args.sdd_file, "")
    if sdd_md:
        parts.append("## 三、SDD 产物校验")
        parts.append(sdd_md)
        parts.append("")

    # 四、Review 发现（脚本从 Issue JSON 拼装，含规则命中摘要）
    parts.append("## 四、Review 发现")
    parts.append("")
    parts.append(assemble_review_findings(issues))
    parts.append("")

    # 自定义规则检查结果子节（Step 4-C 检出的问题）
    custom_section = assemble_custom_rules_section(issues)
    if custom_section:
        parts.append(custom_section)

    # 五、总体评价（从 summary 文件拆分）
    parts.append("## 五、总体评价")
    if summary_parts["overall_eval"]:
        parts.append(summary_parts["overall_eval"])
    else:
        parts.append(f"Review 结论：{conclusion}")
    parts.append(f"**发现汇总**：P0: {counts['p0']} | P1: {counts['p1']} | P2: {counts['p2']} | P3: {counts['p3']}")
    parts.append("")

    # 六、人工复审要点（从 summary 文件拆分）
    if summary_parts["manual_review"]:
        parts.append("## 六、人工复审要点")
        parts.append(summary_parts["manual_review"])
        parts.append("")

    # 七、与 CatPaw 对比（从 catpaw 文件透传，无则跳过）
    catpaw_md = read_text_file(args.catpaw_file, "")
    if catpaw_md:
        parts.append("## 七、与 CatPaw 对比")
        parts.append(catpaw_md)
        parts.append("")

    # 八、上轮 CR 采纳情况（从 adopt 文件透传，仅第二轮 CR）
    adopt_file = f"/tmp/cr_adopt_{args.pr_id}.md"
    adopt_md = read_text_file(adopt_file, "")
    if adopt_md:
        parts.append("## 八、上轮 CR 采纳情况（仅第二轮 CR 追加）")
        parts.append(adopt_md)
        parts.append("")

    return "\n".join(parts)


def assemble_inline_comments(issues):
    """从 P0/P1 issue 拼装 PR 行内评论列表。"""
    inline = []
    # 组内编号计数器
    sev_counters = {"P0": 0, "P1": 0}
    for it in issues:
        if it["severity"] not in ("P0", "P1"):
            continue
        sev = it["severity"]
        sev_counters[sev] += 1
        idx = sev_counters[sev]
        emoji = SEVERITY_EMOJI[sev]
        rule_id = it.get("ruleId", "") or ""
        summary = it.get("summary", "") or ""
        desc = it.get("description", "") or ""
        risk = it.get("risk", "") or ""
        sug = it.get("suggestion", "") or ""
        file_ = it.get("file", "") or ""
        line = it.get("line", 0)
        line_type = (it.get("lineType") or "ADDED").upper()

        # 可追溯信息（step4b 来源附在末尾，不暴露 step 编号）
        trace = ""
        rule_name = it.get("ruleName", "") or ""
        rule_file = it.get("ruleFile", "") or ""
        if rule_name or rule_file:
            trace = f"\n（规则：{rule_name}，来源：{rule_file}）"

        anomaly = it.get("anomalyType", "") or ""
        title = f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {anomaly} — {summary}" if anomaly else f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {summary}"
        text = (
            f"{title}\n\n"
            f"**文件**：`{file_}` L{line}\n\n"
            f"**检出原因**：{desc}\n\n"
            f"**风险**：{risk}\n\n"
            f"**修复建议**：\n{sug}"
            f"{trace}\n\n"
            f"---\n"
            f"💬 无回复默认检出正确，计入准确率。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复"
        )

        inline.append({
            "file_keyword": file_,
            "line": int(line) if line else 0,
            "line_type": line_type,
            "text": text,
            "_issue": it,  # 内部字段：来源 issue 引用，发送成功后回写 commentId；归档时剔除
        })
    return inline


def assemble_global_comment(args, issues, counts, conclusion, km_url):
    """从 P0~P3 全量 issue 拼装 PR 全局评论。"""
    lines = [
        "## 🤖 AI Code Review 结果",
        "",
        "> 本 Review 由 AI-CR（AI 代码审查）自动生成，仅供参考，请结合业务实际情况判断。",
        "> P0/P1 问题同时已作为行内评论标注在对应代码行，下方为全量发现。",
        "",
        f"**发现汇总：** P0: {counts['p0']} | P1: {counts['p1']} | P2: {counts['p2']} | P3: {counts['p3']}",
        "",
        f"**Review 结论：** {conclusion}",
        "",
        f"**审查范围：** {scope_label(args)}",
        "",
        "---",
    ]

    for sev in ("P0", "P1", "P2", "P3"):
        group = [it for it in issues if it["severity"] == sev]
        if not group:
            continue
        lines.append("")
        lines.append(f"### {SEVERITY_TITLE[sev]}")
        lines.append("")
        for i, it in enumerate(group, 1):
            rule_id = it.get("ruleId", "") or ""
            summary = it.get("summary", "") or ""
            file_ = it.get("file", "") or ""
            line = it.get("line", "") or ""
            desc = it.get("description", "") or ""
            risk = it.get("risk", "") or ""
            sug = it.get("suggestion", "") or ""
            anomaly = it.get("anomalyType", "") or ""
            emoji = SEVERITY_EMOJI[sev]
            if sev in ("P0", "P1"):
                # 精简七字段（不展示触达分析/线上场景/影响范围，太长了）
                title = f"**{emoji} {sev}-{i:02d}: [{rule_id}] {anomaly} — {summary}**" if anomaly else f"**{emoji} {sev}-{i:02d}: [{rule_id}] {summary}**"
                lines.append(title)
                lines.append(f"文件: `{file_}:{line}`")
                lines.append(f"检出原因：{desc}")
                lines.append(f"风险：{risk}")
                lines.append(f"修复建议：{sug}")
            else:
                # P2/P3 简洁格式（保持不变）
                lines.append(f"**{emoji} {sev}-{i:02d}: [{rule_id}] {summary}**")
                lines.append(f"命中规则：`{rule_id}`")
                lines.append(f"文件: `{file_}:{line}`")
                lines.append(desc)
            lines.append("💬 无回复默认检出正确，计入准确率。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复")
            lines.append("")

    lines.append("---")
    lines.append("")
    if km_url:
        lines.append(f"📄 详细 Review 文档：{km_url}")
    else:
        lines.append("📄 详细 Review 文档：（学城文档创建失败，请查看行内评论）")

    # 【格式固定】末尾基准 commit 行是下次增量 CR 读取起点的依据，勿改勿删
    # 主路径：直接从 cr_mode_info.json 读取（不依赖大模型传参）
    # 兜底：文件不可用时回退到 args.target_commit
    target_commit = _read_target_commit_from_mode_info()
    if not target_commit:
        target_commit = getattr(args, "target_commit", None)
    if target_commit and re.match(r'^[0-9a-fA-F]{40}$', target_commit):
        lines.append("")
        lines.append(f"📦 基准 commit: {target_commit}")
    return "\n".join(lines)


def assemble_daxiang_message(args, issues, counts, conclusion, km_url):
    """拼装大象群推送消息。"""
    header = f"【AI-CR Agent】{args.org}/{args.repo} #{args.pr_id} {args.pr_title}"
    stats = f"{conclusion}  P0={counts['p0']} P1={counts['p1']} P2={counts['p2']} P3={counts['p3']}"
    people = f"提交人：{args.author_name}（{args.submitter_mis}）  触发人：{args.trigger_name}（{args.trigger_mis}）"
    scope = f"范围: {scope_label(args, compact=True)}"

    lines = [header, stats, people, scope, ""]

    top_issues = [it for it in issues if it["severity"] in ("P0", "P1")]
    if top_issues:
        lines.append("⚠️ 关键问题：")
        # 组内编号
        p0_idx = p1_idx = 0
        for it in top_issues:
            if it["severity"] == "P0":
                p0_idx += 1
                tag = f"P0-{p0_idx}"
            else:
                p1_idx += 1
                tag = f"P1-{p1_idx}"
            rule_id = it.get("ruleId", "") or ""
            anomaly = it.get("anomalyType", "") or ""
            summary = it.get("summary", "") or ""
            # 规则缩写展示
            if rule_id:
                lines.append(f"• [{tag}] [{rule_id}] {anomaly} — {summary}" if anomaly else f"• [{tag}] [{rule_id}] {summary}")
            else:
                lines.append(f"• [{tag}] {summary}")
        lines.append("")

    if km_url:
        lines.append(f"📄 详细报告：{km_url}")
    else:
        lines.append("📄 详细报告：学城文档创建失败，请查看 PR 评论")
    lines.append(f"🔗 PR链接：{args.pr_url}")

    msg = "\n".join(lines)
    # 大象群消息统一使用 \r\n 换行（text 类型消息 \n 可能不渲染）
    msg = msg.replace('\n', '\r\n')
    return msg


# ─── Step 9: 回写结构化 CR 结果 ───────────────────────────────────────────────

def _parse_consistency_rate(sdd_md):
    """从 SDD 章节 markdown 解析「一致率：约 X%」，未找到返回空串。"""
    if not sdd_md:
        return ""
    m = re.search(r'一致率[^\d]{0,6}约?\s*(\d+)\s*%', sdd_md)
    return f"{m.group(1)}%" if m else ""


def _build_doc_issues(issues, extra_fields):
    """结构化逐条 issue 列表（覆盖学城文档展示的全部字段，含 confirm 专属字段）。
    与 ai-cr-forlocal cr_record.py 的同名函数保持一致。"""
    result = []
    for idx, it in enumerate(issues, 1):
        entry = {
            "index": idx,
            "severity": it.get("severity", ""),
            "ruleId": it.get("ruleId", "") or "",
            "ruleName": it.get("ruleName", "") or "",
            "ruleFile": it.get("ruleFile", "") or "",
            "anomalyType": it.get("anomalyType", "") or "",
            "summary": it.get("summary", "") or "",
            "file": it.get("file", "") or "",
            "line": it.get("line", 0) or 0,
            "code": it.get("code", "") or "",
            "description": it.get("description", "") or "",
            "risk": it.get("risk", "") or "",
            "suggestion": it.get("suggestion", "") or "",
            "source": it.get("source", "") or "",
            "commentId": it.get("commentId"),
        }
        for k in extra_fields:
            if it.get(k):
                entry[k] = it[k]
        result.append(entry)
    return result


def _build_rule_hit_summary_data(issues):
    """结构化「规则命中摘要」。与 ai-cr-forlocal cr_record.py 的同名函数保持一致。"""
    if not issues:
        return {}
    p0_rules = sorted(set(r for it in issues if it.get("severity") == "P0" for r in _expand_rids(it)))
    p1_rules = sorted(set(r for it in issues if it.get("severity") == "P1" for r in _expand_rids(it)))
    p2_rules = sorted(set(r for it in issues if it.get("severity") == "P2" for r in _expand_rids(it)))
    p3_rules = sorted(set(r for it in issues if it.get("severity") == "P3" for r in _expand_rids(it)))
    confirm_count = len([it for it in issues if it.get("severity") == "confirm"])

    cr_count = mt_count = cu_count = 0
    all_rids = []
    for it in issues:
        rids = _expand_rids(it)
        all_rids.extend(rids)
        for r in rids:
            if r.startswith("CR:"):
                cr_count += 1
            elif r.startswith("MT:"):
                mt_count += 1
            elif r.startswith("CU:"):
                cu_count += 1
    if cr_count == 0 and mt_count == 0 and cu_count == 0:
        cr_count = len([it for it in issues if it.get("source") == "step4a"])
        mt_count = len([it for it in issues if it.get("source") == "step4b"])
        cu_count = len([it for it in issues if it.get("source") == "step4c"])

    return {
        "total_rules": len(set(all_rids)),
        "cr_rule_count": cr_count,
        "mt_rule_count": mt_count,
        "cu_rule_count": cu_count,
        "total_hits": len(issues),
        "p0_rules": p0_rules,
        "p1_rules": p1_rules,
        "p2_rules": p2_rules,
        "p3_rules": p3_rules,
        "confirm_count": confirm_count,
    }


def _build_custom_rules_data(issues):
    """结构化「自定义规则检查结果」子节（CU: 来源 / step4c）。"""
    cu_issues = [it for it in issues if it.get("source") == "step4c" or
                 any(r.startswith("CU:") for r in _expand_rids(it))]
    if not cu_issues:
        return None
    return _build_doc_issues(cu_issues, ("reach_analysis", "online_scenario", "impact_scope",
                                         "confirm_reason", "possible_risk", "confirm_suggestion"))


def _parse_line_changes(line_changes):
    """从 "+120 -30" 格式解析 (added, removed)。解析失败返回 (None, None)。"""
    if not line_changes:
        return None, None
    m_add = re.search(r'\+(\d+)', line_changes)
    m_del = re.search(r'-(\d+)', line_changes)
    added = int(m_add.group(1)) if m_add else None
    removed = int(m_del.group(1)) if m_del else None
    return added, removed


def _build_overview_data(args):
    """结构化「一、PR 概述」表格内容。"""
    added, removed = _parse_line_changes(args.line_changes)
    return {
        "org": args.org,
        "repo": args.repo,
        "pr_id": args.pr_id,
        "pr_title": args.pr_title,
        "submitter_mis": args.submitter_mis,
        "author_name": args.author_name,
        "trigger_mis": args.trigger_mis,
        "trigger_name": args.trigger_name,
        "branch": args.branch or "",
        "file_count": args.file_count,
        "line_changes": args.line_changes or "",
        "added_lines": added,
        "removed_lines": removed,
        "total_changed_lines": (added or 0) + (removed or 0) if (added is not None or removed is not None) else None,
        "cr_mode": getattr(args, "cr_mode", "full"),
        "base_commit": getattr(args, "base_commit", None),
        "target_commit": getattr(args, "target_commit", None),
        "commit_count": getattr(args, "commit_count", None),
        "skill_version": f"ai-pr-code-review {SKILL_VERSION}",
    }


def _build_changed_files_data(args):
    """结构化「二、变更综述」兜底用的变更文件清单。"""
    changed_files_md = read_text_file(getattr(args, "changed_files_file", ""), "")
    if not changed_files_md:
        return []
    file_lines = [l.strip().lstrip("- ").strip() for l in changed_files_md.strip().split("\n")
                  if l.strip() and not l.startswith("#")]
    return file_lines


def build_cr_result(args, issues, counts, conclusion, km_url):
    """拼装结构化 CR 结果 JSON 对象（原样写入 cr_task.cr_result_json）。

    2026-07-28 扩展：新增 issues 字段（逐条明细，仅 P0~P3），供下游
    sku-operation-server 侧 DefenderCallbackConverter 组装 Defender
    notify 回调的 responseMessage（技术方案 6.1/6.3 节，km.sankuai.com/collabpage/2777573642）。

    2026-09-02 对齐 ai-cr-forlocal：学城文档全部章节内容以结构化 JSON 形式铺平到顶层，
    与 assemble_citadel_doc 的 markdown 章节一一对应；issues 字段升级为
    全量明细（P0~P3 + confirm，含文档展示的全部字段）；counts 补充变更规模信息；
    is_sdd / 一致率由主 Agent 显式传参（--is-sdd / --consistency-rate）。
    """
    sdd_md = read_text_file(args.sdd_file, "")
    # is_sdd / 一致率均由主 Agent 按 SDD 校验结论显式传入（--is-sdd / --consistency-rate），
    # 不再从 sdd 文件文本解析（模型写文件时可能漏写「一致率」行，解析静默失败）。
    is_sdd = bool(getattr(args, "is_sdd", False))
    consistency_rate = (getattr(args, "consistency_rate", "") or "").strip()
    summary_parts = split_summary_file(read_text_file(args.summary_file, ""))
    catpaw_md = read_text_file(args.catpaw_file, "")

    # counts 在 P0~P3 计数基础上补充变更规模信息（取自 --file-count / --line-changes 解析）
    added, removed = _parse_line_changes(args.line_changes)
    counts_full = dict(counts)
    counts_full["changedFiles"] = args.file_count if args.file_count is not None else 0
    counts_full["additions"] = added if added is not None else 0
    counts_full["deletions"] = removed if removed is not None else 0

    result = {
        "pr_id": args.pr_id,
        "org": args.org,
        "repo": args.repo,
        "pr_title": args.pr_title,
        "pr_url": args.pr_url,
        "conclusion": conclusion,
        "counts": counts_full,
        "is_sdd": is_sdd,
        "text_code_consistency_rate": consistency_rate if is_sdd else "",
        "skill_version": f"ai-pr-code-review {SKILL_VERSION}",
        "km_url": km_url,
        "review_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "issues": _build_doc_issues(
            issues,
            ("reach_analysis", "online_scenario", "impact_scope",
             "confirm_reason", "possible_risk", "confirm_suggestion"),
        ),
    }

    # ── 学城文档章节内容，铺平到顶层 ──
    result.update({
        # 文档标题
        "doc_title": f"PR #{args.pr_id} Code Review：{args.pr_title}",
        # 一、PR 概述
        "overview": _build_overview_data(args),
        # 二、变更综述
        "change_summary": summary_parts.get("change_summary", ""),
        "changed_files": _build_changed_files_data(args),
        # 三、SDD 产物校验
        "sdd_check": {
            "is_sdd": is_sdd,
            "consistency_rate": consistency_rate if is_sdd else "",
            "content": sdd_md,
        },
        # 四、Review 发现 — 规则命中摘要（明细复用顶层 issues 字段）
        "rule_hit_summary": _build_rule_hit_summary_data(issues),
        # 自定义规则检查结果（无则 None）
        "custom_rules": _build_custom_rules_data(issues),
        # 五、总体评价
        "overall_eval": summary_parts.get("overall_eval", ""),
        # 六、人工复审要点
        "manual_review": summary_parts.get("manual_review", ""),
        # 七、与 CatPaw 对比
        "catpaw_comparison": catpaw_md,
    })
    return result


# ─── Step 6: 创建学城 CR 文档 ─────────────────────────────────────────────────

def step6_create_citadel_doc(args, doc_md):
    """创建学城文档，返回 {"ok": bool, "km_url": str, "error": str}"""
    result = {"ok": False, "km_url": "", "error": ""}

    if args.km_url:
        log("✅ Step 6: 已提供 km_url，跳过创建")
        result["ok"] = True
        result["km_url"] = args.km_url
        return result

    citadel_parent_id = args.citadel_parent_id
    if not citadel_parent_id:
        result["error"] = "缺少 --citadel-parent-id"
        return result

    # 写入临时 markdown 文件供 citadel --file 上传
    findings_file = f"/tmp/cr_review_{args.pr_id}.md"
    try:
        with open(findings_file, "w", encoding="utf-8") as f:
            f.write(doc_md)
    except Exception as e:
        result["error"] = f"写入文档临时文件失败: {e}"
        return result

    date_dir = datetime.now().strftime("%Y-%m-%d")
    date_parent_id = None

    def find_date_dir():
        out = run_cmd(
            f'oa-skills citadel getChildContent --contentId {citadel_parent_id}',
            label="查找日期子目录"
        )
        data = _parse_json_obj(out)
        if data is None:
            return None
        children = data.get("children") if isinstance(data, dict) else None
        if not isinstance(children, list):
            return None
        candidates = [c for c in children if isinstance(c, dict) and c.get("title") == date_dir]
        if not candidates:
            return None

        def sort_key(c):
            is_folder = 1 if (c.get("childCount") or 0) > 0 else 0
            return (is_folder, c.get("createTime") or 0)

        best = max(candidates, key=sort_key)
        return best.get("contentId") or best.get("id")

    ok, val = retry(find_date_dir, label="查找日期子目录")
    if ok and val:
        date_parent_id = str(val)
        log(f"📁 日期目录已存在: {date_dir} (id={date_parent_id})")
    else:
        def create_date_dir():
            out = run_cmd(
                f'oa-skills citadel createDocument --title "{date_dir}" --content "{date_dir}" --parentId {citadel_parent_id}',
                label="创建日期子目录"
            )
            cid = _extract_content_id(out)
            if not cid:
                raise RuntimeError(f"无法提取 contentId: {out[:300]}")
            return str(cid)

        ok, val = retry(create_date_dir, label="创建日期子目录")
        if ok:
            date_parent_id = val
            log(f"📁 日期目录已创建: {date_dir} (id={date_parent_id})")
        else:
            result["error"] = f"创建日期子目录失败: {val}"
            return result

    doc_title = f"PR #{args.pr_id} Code Review：{args.pr_title}"
    doc_title_escaped = doc_title.replace('"', '\\"')

    def create_cr_doc():
        out = run_cmd(
            f'oa-skills citadel createDocument --title "{doc_title_escaped}" --file "{findings_file}" --parentId {date_parent_id}',
            label="创建学城CR文档"
        )
        url = _extract_url(out)
        if not url:
            cid = _extract_content_id(out)
            if cid:
                url = f"https://km.sankuai.com/collabpage/{cid}"
        if not url:
            raise RuntimeError(f"无法提取文档 URL: {out[:300]}")
        return url

    ok, val = retry(create_cr_doc, label="创建学城CR文档")
    if ok:
        result["ok"] = True
        result["km_url"] = val
        log(f"✅ Step 6: 学城文档已创建: {val}")
    else:
        result["error"] = f"创建学城文档失败: {val}"
        log(f"❌ Step 6: {result['error']}")

    return result


# ─── Step 7: 评论到 PR ────────────────────────────────────────────────────────

# 宽松 ruleId 提取：覆盖 [MT:xxx] [CR:xxx] [DEP-01] MT:xxx EH-01 等各种格式
_RULE_PATTERN = re.compile(
    r'\[(?:MT:|CR:|CU:)([A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*)\]'   # [MT:xxx]
    r'|\[([A-Z][A-Z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\]'       # [DEP-01] [HA-F003]
    r'|(?:MT|CR|CU):([A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*)'          # MT:xxx 无方括号
    r'|(?:^|(?<=[\s*]))([A-Z][A-Z]+-[A-Z0-9]+(?:-[A-Z0-9]+)*)(?=[\s\-\]\*,;]|$)'  # EH-01 裸露
)
_P_LEVEL = re.compile(r'^P[0-3](?:-\d+)?$')

def _extract_rule_ids(text):
    """从评论文本中提取所有规则编号，返回列表。"""
    matches = _RULE_PATTERN.findall(text)
    rids = []
    for m in matches:
        rid = next((g for g in m if g), None)
        if rid and not _P_LEVEL.match(rid):
            rids.append(rid)
    return rids


def fetch_existing_inline_comments(pr_url, code_cli_py):
    """拉取 PR 已有行内评论，返回二元组 (exact_set, fuzzy_set)。
    exact_set: set of (file_basename, line, ruleId) — 精确三元组匹配。
    fuzzy_set: set of (file_basename, ruleId) — 模糊二元组匹配（忽略行号，
               用于 PR 新 push 后行号漂移场景的兜底去重）。
    拉取失败返回 None，调用方按 None 处理（不去重，全写）。"""
    try:
        cmd = [sys.executable, code_cli_py, "pr-comments", "--url", pr_url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            log(f"⚠️  拉取已有评论失败(rc={r.returncode}): {r.stderr[:200]}")
            return None
        comments = json.loads(r.stdout)
        exact_set = set()
        fuzzy_set = set()
        for c in comments:
            file_ = c.get("file") or ""
            file_basename = os.path.basename(file_) if file_ else ""
            line = c.get("line") or 0
            text = c.get("text") or ""
            rids = _extract_rule_ids(text)
            if not rids:
                exact_set.add((file_basename, line, ""))
            else:
                for rid in rids:
                    exact_set.add((file_basename, line, rid))
                    fuzzy_set.add((file_basename, rid))
        log(f"📋 已有行内评论: {len(exact_set)} 条精确维度, {len(fuzzy_set)} 条模糊维度")
        return (exact_set, fuzzy_set)
    except Exception as e:
        log(f"⚠️  拉取已有评论异常: {e}")
        return None


def find_code_cli_py():
    """查找 code_cli.py 脚本路径。"""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "code-cli", "scripts", "code_cli.py"),
        os.path.join(os.path.dirname(__file__), "code_cli.py"),
        os.path.expanduser("~/.openclaw/skills/code-cli/scripts/code_cli.py"),
        os.path.expanduser("~/.openclaw/workspace/.claude/skills/code-cli/scripts/code_cli.py"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def filter_duplicate_inline(inline_comments, existing_data):
    """两层去重过滤已存在的行内评论。
    Layer 1 精确匹配: (file_basename, line, ruleId) 完全一致 → 跳过。
    Layer 2 模糊兜底: (file_basename, ruleId) 一致（忽略行号）→ 跳过。
        用于 PR 有新 push 后行号漂移的场景，防止同文件同规则重复评论。
    existing_data 为 None 时不过滤。"""
    if existing_data is None:
        return inline_comments, 0
    exact_set, fuzzy_set = existing_data
    kept = []
    skipped = 0
    skipped_exact = 0
    skipped_fuzzy = 0
    for c in inline_comments:
        file_ = c.get("file_keyword", "")
        file_basename = os.path.basename(file_) if file_ else ""
        line = c.get("line", 0)
        text = c.get("text", "")
        rids = _extract_rule_ids(text)
        if not rids:
            if (file_basename, line, "") in exact_set:
                skipped += 1
                skipped_exact += 1
                continue
        else:
            # Layer 1: 精确匹配 (file, line, ruleId)
            all_exact = all((file_basename, line, rid) in exact_set for rid in rids)
            if all_exact:
                skipped += 1
                skipped_exact += 1
                continue
            # Layer 2: 模糊兜底 (file, ruleId)，忽略行号
            all_fuzzy = all((file_basename, rid) in fuzzy_set for rid in rids)
            if all_fuzzy:
                skipped += 1
                skipped_fuzzy += 1
                continue
        kept.append(c)
    if skipped:
        log(f"⏭️  去重跳过 {skipped} 条（精确={skipped_exact}, 模糊={skipped_fuzzy}）")
    return kept, skipped


def step7_comment_to_pr(args, inline_comments, global_text):
    """发 PR 评论，返回 {"ok": bool, "inline_count": int, "global_ok": bool, "error": str}

    直接 import 调用 cr_comment.CommentClient（无 subprocess），CommentClient 内部自带重试。
    """
    result = {"ok": False, "inline_count": 0, "global_ok": False, "error": ""}

    try:
        client = CommentClient(log_fn=log)
    except CommentError as e:
        result["error"] = f"初始化评论客户端失败: {e}"
        return result

    pr_url = args.pr_url
    pr_id = args.pr_id

    # 写行内评论 JSON 文件（归档用，供调试）— 在去重后写，和实际发送一致
    # 先做去重，再写归档
    inline_count = 0
    inline_errors = []

    # 7A. 行内评论（写入前先拉取已有评论去重）
    if inline_comments:
        # 拉取已有行内评论，失败则不去重（全写）
        code_cli_py = getattr(args, 'code_cli_py', None) or find_code_cli_py()
        existing_data = None
        if code_cli_py:
            existing_data = fetch_existing_inline_comments(pr_url, code_cli_py)
        else:
            log("⚠️  未找到 code_cli.py，跳过去重，全量写入")

        # 去重过滤
        inline_comments, skipped_count = filter_duplicate_inline(inline_comments, existing_data)
        if skipped_count:
            log(f"⏭️  {skipped_count} 条行内评论为历史轮次已写，跳过")

        # 写归档文件（去重后）；剔除内部 _issue 引用字段，保持归档 schema 不变
        inline_file = f"/tmp/cr_inline_comments_{pr_id}.json"
        if inline_comments:
            try:
                with open(inline_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [{k: v for k, v in c.items() if k != "_issue"} for c in inline_comments],
                        f, ensure_ascii=False, indent=2,
                    )
            except Exception as e:
                log(f"⚠️  写行内评论文件失败: {e}")

        if not inline_comments:
            log("⏭️  全部行内评论均为历史已写，跳过 7A")

        for idx, comment in enumerate(inline_comments):
            file_keyword = comment.get("file_keyword", "")
            line = comment.get("line", 0)
            line_type = comment.get("line_type", "ADDED")
            text = comment.get("text", "")

            if not file_keyword or not text:
                inline_errors.append(f"行内评论 #{idx+1} 缺少 file_keyword 或 text，跳过")
                continue

            try:
                comment_id = client.send_inline(
                    pr_url, file_keyword=file_keyword, line=line,
                    line_type=line_type, text=text,
                )
                # 回写 commentId 到来源 issue，供 Step 9 issues 明细使用
                src_issue = comment.get("_issue")
                if isinstance(src_issue, dict):
                    src_issue["commentId"] = comment_id
                inline_count += 1
                log(f"  ✅ 行内评论 #{idx+1}: {file_keyword}:{line} (commentId={comment_id})")
            except CommentError as e:
                inline_errors.append(f"#{idx+1} {file_keyword}:{line} - {e}")
                log(f"  ❌ 行内评论 #{idx+1}: {e}")
    else:
        log("ℹ️  无 P0/P1 行内评论，跳过 7A")

    result["inline_count"] = inline_count

    # 7B. 全局评论
    if global_text:
        global_file = f"/tmp/cr_global_comment_{pr_id}.txt"
        try:
            with open(global_file, "w", encoding="utf-8") as f:
                f.write(global_text)
        except Exception as e:
            inline_errors.append(f"写全局评论文件失败: {e}")

        try:
            client.send_global(pr_url, global_text)
            result["global_ok"] = True
            log("  ✅ 全局评论发送成功")
        except CommentError as e:
            inline_errors.append(f"全局评论失败: {e}")
            log(f"  ❌ 全局评论: {e}")
    else:
        log("ℹ️  无全局评论内容，跳过 7B")
        result["global_ok"] = True

    # 7C. 验证（不阻塞）
    try:
        client.verify(pr_url)
        log(f"  🔍 验证完成")
    except Exception as e:
        log(f"  ⚠️  验证失败（不阻塞）: {e}")

    if inline_errors:
        result["error"] = "; ".join(inline_errors[:3])
    if (inline_count > 0 or not inline_comments) and result["global_ok"]:
        result["ok"] = True
    elif inline_count > 0 or result["global_ok"]:
        result["ok"] = True

    return result


# ─── Step 8: 大象群推送 ───────────────────────────────────────────────────────

def b64url(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def get_dx_token():
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": AICR_BOT_APP_ID, "sub": AICR_BOT_APP_ID,
        "aud": TOKEN_URL,
        "jti": str(uuid.uuid4()), "iat": now, "exp": now + 300
    }
    h = b64url(json.dumps(header, separators=(',', ':')))
    p = b64url(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(AICR_BOT_APP_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    jwt_token = f"{h}.{p}.{b64url(sig)}"

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt_token,
        "client_id": AICR_BOT_APP_ID,
        "scope": "client_id:xm-xai"
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body, method="POST",
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def send_group_msg(token, gid, text):
    payload_data = json.dumps({
        "gid": gid,
        "sendMsgInfo": {
            "type": "text",
            "body": json.dumps({"text": text})
        }
    }).encode()
    req = urllib.request.Request(SEND_URL, data=payload_data, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp_data = json.loads(resp.read())
        if resp_data.get("status", {}).get("code", -1) != 0:
            raise RuntimeError(f"发送失败: {resp_data}")
        return resp_data


def step8_daxiang_push(args, message_text):
    """大象群推送，返回 {"ok": bool, "global_group_ok": bool, "team_group_ok": bool, "error": str}"""
    result = {"ok": False, "global_group_ok": False, "team_group_ok": False, "error": ""}

    if not message_text.startswith("【AI-CR Agent】") and not message_text.startswith("【AI-CR】"):
        result["error"] = "消息未以【AI-CR Agent】开头，拒绝发送"
        return result

    def get_token():
        return get_dx_token()

    ok, token = retry(get_token, label="获取大象 token")
    if not ok:
        result["error"] = f"获取大象 token 失败: {token}"
        return result

    def push_global(t=token):
        return send_group_msg(t, AICR_GLOBAL_GID, message_text)

    ok, val = retry(push_global, label="推送全局群")
    if ok:
        result["global_group_ok"] = True
        log("✅ Step 8: 全局群推送成功")
    else:
        log(f"❌ Step 8: 全局群推送失败: {val}")

    team_gid = args.team_chat_group_id
    if team_gid:
        try:
            team_gid_int = int(team_gid)
        except ValueError:
            log(f"⚠️  团队群 ID 非法: {team_gid}")
            team_gid_int = None

        if team_gid_int:
            def push_team(t=token, gid=team_gid_int):
                return send_group_msg(t, gid, message_text)

            ok, val = retry(push_team, label="推送团队群")
            if ok:
                result["team_group_ok"] = True
                log("✅ Step 8: 团队群推送成功")
            else:
                log(f"❌ Step 8: 团队群推送失败: {val}")
    else:
        result["team_group_ok"] = True
        log("ℹ️  无团队群 ID，跳过团队群推送")

    if result["global_group_ok"]:
        result["ok"] = True
    if not result["global_group_ok"] and not result["team_group_ok"]:
        result["error"] = "所有群推送均失败"

    return result


# ─── Step 9: 写入 DB（submit-task 新建模式 + 多维表格降级）──────────────────

def step9_write_db(args, cr_result, counts, conclusion, km_url):
    """Step 9: 写入 DB（submit-task 新建模式 + 多维表格降级）。

    路径 A（主）：POST 到 spt.sankuai.com/api/v1/aicr/submit-task，写入 cr_task 表
    路径 B（降级）：DB 失败 → 多维表格 addData
    全部失败 → 输出错误信息
    """
    import ssl

    result = {"ok": False, "skipped": False, "status": "", "error": "", "method": ""}

    # 构造 payload
    payload = {
        "pr_url": args.pr_url,
        "author_mis": args.submitter_mis,
        "source_branch": getattr(args, 'source_branch', None) or args.branch or "",
        "target_branch": getattr(args, 'target_branch', None) or "",
        "trigger_source": "skills",
        "trigger_event": "manual",
        "cr_result_json": json.dumps(cr_result, ensure_ascii=False),
    }

    # 路径 A：DB 写入
    # opener 构造与 SSL 策略对齐 ai-cr-forlocal cr_record.py：
    # HTTPSHandler 必须在 build_opener 时传入（事后 add_handler 会被默认 https handler
    # 优先级抢占导致证书配置不生效）；先严格校验，CERTIFICATE_VERIFY_FAILED 时
    # 自动降级跳过校验重试（开发机 Python 普遍缺内网 CA，属环境问题）。
    def _make_opener(skip_verify):
        context = ssl.create_default_context()
        if skip_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({}),  # no proxy
            urllib.request.HTTPSHandler(context=context),
        )

    def _do_post(opener):
        url = f"{DB_DEFAULT_SCHEME}://{DB_HOST}{DB_PATH}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with opener.open(req, timeout=DB_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        if status != 200:
            raise RuntimeError(f"DB HTTP {status}: {body}")
        # 解析响应检查业务错误（与 cr_record.py 一致：error.code != 0 视为失败）
        body_json = None
        try:
            body_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass
        if body_json and isinstance(body_json, dict):
            err_obj = body_json.get("error") or body_json.get("err")
            if isinstance(err_obj, dict) and err_obj.get("code", 0) != 0:
                raise RuntimeError(f"DB business error: {err_obj}")
        return body

    def _db_write():
        return _do_post(_make_opener(skip_verify=False))

    ok, val = retry(_db_write, label="DB 写入")
    # SSL 证书校验失败自动降级：开发机 Python 普遍缺内网 CA，属环境问题而非安全问题
    # （目标为 *.sankuai.com 内网服务）。跳过校验重试一轮，免除用户手动配置。
    if not ok and val and "CERTIFICATE_VERIFY_FAILED" in str(val):
        log("⚠️  SSL 证书校验失败（本机缺内网 CA），自动降级跳过校验重试")

        def _db_write_noverify():
            return _do_post(_make_opener(skip_verify=True))

        ok, val = retry(_db_write_noverify, label="DB 写入（跳过证书校验）")
    if ok:
        result["ok"] = True
        result["method"] = "db"
        result["status"] = "success"
        log("✅ Step 9: DB 写入成功")
        return result

    log(f"❌ Step 9: DB 写入失败: {val}，降级到多维表格...")

    # 路径 B：多维表格降级
    table_result = _write_table(args, counts, conclusion, km_url)
    if table_result.get("status") in ("success", "degraded"):
        result["ok"] = True
        result["method"] = "table"
        result["status"] = table_result["status"]
        log(f"✅ Step 9: 多维表格写入成功（降级）")
        return result

    result["error"] = f"DB: {val}; Table: {table_result.get('error', '')}"
    log(f"❌ Step 9: 全部失败 - {result['error']}")
    return result


def _write_table(args, counts, conclusion, km_url):
    """多维表格降级写入。"""
    import datetime as _dt

    table_id = getattr(args, 'table_id', None) or DEFAULT_TABLE_ID
    operator_mis = getattr(args, 'operator_mis', None) or args.trigger_mis or args.submitter_mis

    # 1. getTableMeta（即使失败也继续）
    def _get_meta():
        cmd = ["oa-skills", "citadel-database", "getTableMeta",
               "--tableId", table_id, "--mis", operator_mis]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=os.environ)
        if r.returncode != 0:
            raise RuntimeError(f"getTableMeta failed: {r.stderr or r.stdout}")
        return r.stdout or r.stderr

    retry(_get_meta, label="getTableMeta")
    # 即使失败也继续

    # 2. addData
    def _add_data():
        now_midnight = _dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_ms = int(now_midnight.timestamp() * 1000)
        assert len(str(date_ms)) == 13 and date_ms > 1735660800000

        remark = f"ai-pr-code-review {SKILL_VERSION}"
        data_value = json.dumps([[
            date_ms,
            args.pr_url,
            args.repo,
            args.pr_title,
            args.submitter_mis,
            "",  # org_id
            conclusion,
            counts["p0"],
            counts["p1"],
            km_url,
            remark,
        ]], ensure_ascii=False)

        cmd = ["oa-skills", "citadel-database", "addData",
               "--tableId", table_id, "--columnIds", TABLE_COLUMN_IDS,
               "--mis", operator_mis, "--data", data_value]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=os.environ)
        if r.returncode != 0:
            raise RuntimeError(f"addData failed: {r.stderr or r.stdout}")
        return r.stdout or r.stderr

    ok, val = retry(_add_data, label="addData")
    if ok:
        return {"status": "degraded", "method": "table", "error": ""}
    return {"status": "failed", "method": "table", "error": val}


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="AI-CR Agent 发布结果脚本")
    parser.add_argument("--pr-url", required=True, help="PR URL")
    parser.add_argument("--pr-id", required=True, help="PR ID")
    parser.add_argument("--pr-title", required=True, help="PR 标题")
    parser.add_argument("--org", required=True, help="仓库组织")
    parser.add_argument("--repo", required=True, help="仓库名")
    parser.add_argument("--submitter-mis", required=True, help="提交人 MIS")
    parser.add_argument("--author-name", required=True, help="提交人姓名")
    parser.add_argument("--trigger-mis", required=True, help="触发人 MIS")
    parser.add_argument("--trigger-name", required=True, help="触发人姓名")
    parser.add_argument("--citadel-parent-id", default="", help="学城父目录 ID")
    parser.add_argument("--team-chat-group-id", default="", help="团队大象群 ID")
    parser.add_argument("--conclusion", default="", help="CR 结论文本（不传则按计数自动推导）")
    parser.add_argument("--issues-file", action="append", default=[], help="统一 Issue JSON 文件路径（可重复传入）")
    parser.add_argument("--changed-files-file", default="", help="变更文件清单章节 markdown")
    parser.add_argument("--summary-file", default="", help="总体评价章节 markdown")
    parser.add_argument("--sdd-file", default="", help="SDD 校验章节 markdown（可选）")
    parser.add_argument("--is-sdd", type=lambda x: x.lower() in ("true", "1", "yes"), default=False,
                        help="本次 CR 是否有 SDD spec 产物（取 SDD 校验结论 has_spec；未传时一律按 false 兜底）")
    parser.add_argument("--consistency-rate", default="",
                        help="文码一致率（取 SDD 校验结论 alignment_rate 原值，如 \"90%\"；无 spec 时传空或不传）")
    parser.add_argument("--catpaw-file", default="", help="与 CatPaw 对比章节 markdown（可选）")
    parser.add_argument("--branch", default="", help="PR 分支（可选）")
    parser.add_argument("--file-count", type=int, default=None, help="变更文件数（可选）")
    parser.add_argument("--line-changes", default="", help="行数变化如 +120 -30（可选）")
    parser.add_argument("--km-url", default="", help="已知学城 URL（跳过 Step 6）")
    parser.add_argument("--conversation-id", default="", help="(已废弃，submit-task 不需要 conversation_id)")
    parser.add_argument("--operator-mis", default="", help="操作人 MIS（多维表格降级用）")
    parser.add_argument("--table-id", default="", help="多维表格 ID（降级用）")
    parser.add_argument("--source-branch", default="", help="源分支（DB 写入用）")
    parser.add_argument("--target-branch", default="", help="目标分支（DB 写入用）")
    # 增量 CR 相关
    parser.add_argument("--cr-mode", choices=["full", "incremental"], default="full",
                        help="CR 模式：全量 or 增量")
    parser.add_argument("--base-commit", default=None, help="增量模式的基准 commit")
    parser.add_argument("--target-commit", default=None, help="本次 CR 的目标 commit")
    parser.add_argument("--commit-count", type=int, default=None, help="增量范围内的 commit 数")
    # 兼容旧用法：直接传入拼好的文档（无 issue JSON 时降级使用）
    parser.add_argument("--findings-file", default="", help="(兼容) 完整文档 markdown，无 --issues-file 时使用")
    return parser.parse_args()


def main():
    args = parse_args()
    output = {}

    log("=" * 60)
    log("AI-CR Agent 发布结果脚本启动")
    log(f"PR: {args.org}/{args.repo} #{args.pr_id}")
    log("=" * 60)

    # 以 get_pr_diff.py 落盘的 cr_mode_info.json 为准回填/校正增量 CR 参数，
    # 防止 Agent 沿用 Step 2C 的旧判定导致产出物标错审查范围（静默错误）。
    _fixes = backfill_cr_mode(args)
    for _f in _fixes:
        log(f"🔧 cr_mode_info.json 校正 → {_f}")
    log(f"📐 审查范围：{scope_label(args)}")

    # ── 加载与拼装 ──
    issues = load_issues(args.issues_file)
    counts = count_issues(issues)
    conclusion = derive_conclusion(counts, args.conclusion)

    log(f"📊 Issues: P0={counts['p0']} P1={counts['p1']} P2={counts['p2']} P3={counts['p3']} → {conclusion}")

    if issues:
        doc_md = assemble_citadel_doc(args, issues, counts, conclusion)
        inline_comments = assemble_inline_comments(issues)
    elif args.findings_file and os.path.isfile(args.findings_file):
        # 兼容旧用法
        doc_md = read_text_file(args.findings_file, "")
        inline_comments = []
    else:
        log("⚠️  未提供 --issues-file，且无 --findings-file，文档将为空")
        doc_md = assemble_citadel_doc(args, issues, counts, conclusion)
        inline_comments = []

    output["counts"] = counts
    output["conclusion"] = conclusion

    # Step 6: 创建学城文档
    log("▶ Step 6: 创建学城 CR 文档...")
    step6_result = step6_create_citadel_doc(args, doc_md)
    output["step6"] = step6_result
    km_url = step6_result.get("km_url", "")

    # 全局评论需 km_url（Step 6 之后拼装）
    global_text = assemble_global_comment(args, issues, counts, conclusion, km_url)

    # Step 7: 评论到 PR
    log("▶ Step 7: 评论到 PR...")
    step7_result = step7_comment_to_pr(args, inline_comments, global_text)
    output["step7"] = step7_result

    # Step 8: 大象群推送
    log("▶ Step 8: 大象群推送...")
    message_text = assemble_daxiang_message(args, issues, counts, conclusion, km_url)
    step8_result = step8_daxiang_push(args, message_text)
    output["step8"] = step8_result

    # Step 9: 写入 DB（submit-task 新建模式 + 多维表格降级）
    log("▶ Step 9: DB 写入...")
    cr_result = build_cr_result(args, issues, counts, conclusion, km_url)
    step9_result = step9_write_db(args, cr_result, counts, conclusion, km_url)
    output["step9"] = step9_result

    log("=" * 60)
    log("发布结果脚本完成")
    log("=" * 60)

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
