#!/usr/bin/env python3
"""
publish_results_local.py — AI-CR forLocal 一体化发布脚本
Skill: ai-cr-forlocal

功能：
  1. 加载 Issue JSON（支持多文件合并去重）
  2. 统计 P0/P1/P2/P3 数量
  3. 推导 Review 结论
  4. 拼装学城文档 Markdown
  5. 创建学城文档（查找/创建日期目录 + 创建文档）
  6. DB 写入（HTTP POST，失败不阻塞）
  7. SDLC JSON 输出
  8. CatPaw IDE Markdown 报告

不包含：PR 评论、大象群播、多维表格写入
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime

# 行号锚定统一封装模块(同目录导入;导入失败降级为直通函数,
# 不影响发布主流程 —— fail-open 原则)
try:
    from line_anchor import anchor_issues
except Exception:  # noqa: BLE001
    def anchor_issues(issues, diff_text=None):
        """降级直通:模块缺失时零行为变化"""
        return issues

from rule_id import normalize_fe_rule_id

def _skill_version():
    """从 SKILL.md frontmatter 读 skillhub.version（单一真源），读不到回落 latest"""
    try:
        import re as _re
        m = _re.search(r'skillhub\.version:\s*"([^"]+)"', (Path(__file__).resolve().parent.parent / "SKILL.md").read_text(encoding="utf-8"))
        return m.group(1) if m else "latest"
    except Exception:
        return "latest"

SKILL_VERSION = _skill_version()


def _cr_config():
    """读 cr-config.yaml；yaml 模块缺失时降级正则解析；失败返回空 dict"""
    try:
        text = (Path(__file__).resolve().parent.parent / "cr-config.yaml").read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        import yaml as _yaml
        return _yaml.safe_load(text) or {}
    except ImportError:
        # 无 yaml 模块时简单解析顶层 key: value（本文件无嵌套需求键）
        import re as _re
        cfg = {}
        for m in _re.finditer(r'^([a-z_]+):\s*"?([^"\n#]*)', text, _re.M):
            cfg[m.group(1)] = m.group(2).strip()
        return cfg


def _cr_config_str(key):
    return str(_cr_config().get(key, "") or "")

# DB 写入：由 scripts/cr_record.py 承载（复用 ai-pr-code-review-testn 生产脚本，
# 路径 A=spt.sankuai.com/api/aicr/submit-task（原版 forlocal 同源），路径 B=多维表格 2751197605 降级）
DB_WRITE_URL = os.environ.get("AI_CR_DB_WRITE_URL", "https://spt.sankuai.com/api/aicr/submit-task")  # 兼容保留


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def log(msg):
    """日志输出到 stderr"""
    print(f"[publish_local] {msg}", file=sys.stderr, flush=True)


def retry(fn, label, max_retries=3, delay=2):
    """重试包装"""
    for i in range(max_retries):
        try:
            return fn()
        except Exception as e:
            log(f"{label} 第 {i+1}/{max_retries} 次失败: {e}")
            if i < max_retries - 1:
                time.sleep(delay)
    log(f"{label} 全部 {max_retries} 次重试失败")
    return None


def run_cmd(cmd, label, timeout=30):
    """执行 shell 命令"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            log(f"{label} 命令失败 (exit={result.returncode}): {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        log(f"{label} 命令超时 ({timeout}s)")
        return None
    except Exception as e:
        log(f"{label} 命令异常: {e}")
        return None


def read_text_file(path, default=""):
    """安全读文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log(f"读取文件失败 {path}: {e}")
        return default


def _parse_json_obj(text):
    """从文本中提取 JSON 对象"""
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 ```json ... ``` 块
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试提取第一个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _extract_url(text):
    """从文本中提取 URL"""
    m = re.search("https?://[^\\s<>\"'`)]+", text)
    return m.group(0) if m else ""


def _extract_content_id(text):
    """从文本中提取学城 contentId"""
    m = re.search(r"contentId[\"']?\s*[:=]\s*[\"']?(\d+)", text)
    if m:
        return m.group(1)
    m = re.search(r"cid[\"']?\s*[:=]\s*[\"']?(\d+)", text)
    if m:
        return m.group(1)
    # 尝试从 URL 提取
    m = re.search(r"/(\d{6,})(?:\?|$|/)", text)
    if m:
        return m.group(1)
    return None


# ──────────────────────────────────────────────
# Issue 处理
# ──────────────────────────────────────────────

def load_issues(issues_files):
    """
    从一个或多个 JSON 文件加载 issue，合并去重。
    去重规则：按 ruleId + file + line 去重
    """
    all_issues = []
    seen = set()

    for filepath in issues_files:
        if not os.path.exists(filepath):
            log(f"Issue 文件不存在: {filepath}")
            continue
        text = read_text_file(filepath)
        if not text:
            continue
        data = _parse_json_obj(text)
        if data is None:
            # 尝试作为 JSON 数组直接解析
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                log(f"无法解析 Issue 文件: {filepath}")
                continue
        if isinstance(data, list):
            issues = data
        elif isinstance(data, dict):
            issues = data.get("issues", data.get("data", []))
        else:
            issues = []

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            try:
                normalize_fe_rule_id(issue)
            except ValueError as exc:
                log(f"⚠️ FE 规则字段校验失败，保留问题及原始字段: {exc}")
            key = (
                issue.get("ruleId", ""),
                issue.get("file", ""),
                str(issue.get("line", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            all_issues.append(issue)

    log(f"加载完成: {len(all_issues)} 条 issue（去重后）")
    return all_issues


def count_issues(issues):
    """统计各级别数量（confirm 类不计入 P0~P3，单独统计）"""
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "confirm": 0, "dismissed": 0}
    for it in issues:
        sev = it.get("severity", "P2")
        sl = sev.lower()
        sev = "confirm" if sl == "confirm" else ("dismissed" if sl == "dismissed" else sev.upper())
        if sev in counts:
            counts[sev] += 1
    return counts


def derive_conclusion(counts, override=None):
    """
    推导 Review 结论（四选一）
    - P0>0 或 P1>0 → 🟠需修复
    - P2≤3 → ✅通过
    - P2>3 → 💚通过有建议
    - 架构级问题 → 🔴需重新设计（暂不在此推导，由主 Agent 判断）
    """
    if override:
        return override
    if counts["P0"] > 0 or counts["P1"] > 0:
        return "🟠需修复"
    if counts["P2"] > 3:
        return "💚通过有建议"
    return "✅通过"


# ──────────────────────────────────────────────
# 文档拼装
# ──────────────────────────────────────────────

def _issue_doc_block(it, idx):
    """单条 issue 文档块"""
    severity = it.get("severity", "P2")
    sl = severity.lower()
    severity = "confirm" if sl == "confirm" else ("dismissed" if sl == "dismissed" else severity.upper())
    rule_id = it.get("ruleId") or "无规则标注"
    rule_name = it.get("ruleName", "")
    anomaly = it.get("anomalyType", "")
    summary = it.get("summary", "")
    file = it.get("file", "")
    line = it.get("line", "")
    code = it.get("code", "")
    description = it.get("description", "")
    risk = it.get("risk", "")
    suggestion = it.get("suggestion", "")
    reach = it.get("reach_analysis", "")
    online = it.get("online_scenario", "")
    impact = it.get("impact_scope", "")

    emoji = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵", "confirm": "❓", "dismissed": "⛔"}.get(severity, "🟡")

    if severity in ("P0", "P1"):
        block = f"**{emoji} [{severity}-{idx:02d}] [{rule_id}] {anomaly} — {summary}**\n"
        block += f"- **文件**：`{file}` L{line}\n"
        if code:
            block += f"- **问题代码**：\n```java\n{code}\n```\n"
        block += f"- **检出原因**：{description}\n"
        if reach:
            block += f"- **触达分析**：{reach}\n"
        if online:
            block += f"- **线上场景**：{online}\n"
        if impact:
            block += f"- **影响范围**：{impact}\n"
        block += f"- **修复建议**：\n{suggestion}\n"
    elif severity == "P2":
        block = f"**{emoji} [{severity}-{idx:02d}] [{rule_id}] {summary}**\n"
        block += f"- **文件**：`{file}` L{line}\n"
        block += f"- **问题描述**：{description}\n"
        block += f"- **检出原因**：{risk}\n"
        if rule_name:
            block += f"- **规范要求**：{rule_name}\n"
        block += f"- **修复建议**：{suggestion}\n"
    elif severity == "dismissed":  # 复审误报移除（可追溯附录）
        block = f"**{emoji} [dismissed-{idx:02d}] [{rule_id}] {summary}**\n"
        block += f"- **文件**：`{file}` L{line}\n"
        block += f"- **复审移除理由**：{description}\n"
    elif severity == "confirm":  # 待人工确认（复审疑似误报/疑似漏报）
        block = f"**{emoji} [confirm-{idx:02d}] [{rule_id}] {summary}**\n"
        block += f"- **文件**：`{file}` L{line}\n"
        if code:
            block += f"- **问题代码**：\n```java\n{code}\n```\n"
        block += f"- **说明**：{description}\n"
        block += f"- **修复建议（如确认）**：{suggestion}\n"
    else:  # P3
        block = f"**{emoji} [{severity}-{idx:02d}] [{rule_id}] {summary}**\n"
        block += f"- **文件**：`{file}` L{line}\n"
        block += f"- **建议**：{suggestion}\n"

    return block


def assemble_review_findings(issues):
    """拼装 Review 发现章节"""
    groups = {"P0": [], "P1": [], "P2": [], "P3": [], "confirm": [], "dismissed": []}
    for it in issues:
        sev = it.get("severity", "P2")
        sl = sev.lower()
        sev = "confirm" if sl == "confirm" else ("dismissed" if sl == "dismissed" else sev.upper())
        if sev in groups:
            groups[sev].append(it)

    sections = []
    for level in ["P0", "P1", "P2", "P3", "confirm", "dismissed"]:
        items = groups[level]
        if not items:
            continue
        titles = {
            "P0": "### P0 — 零容忍异常 🔴",
            "P1": "### P1 — 稳定性风险 🟠",
            "P2": "### P2 — 代码规范 🟡",
            "P3": "### P3 — 优化建议 🔵",
            "confirm": "### confirm — 待人工确认 ❓（复审疑似误报/疑似漏报，不删不升级，人工定夺）",
            "dismissed": "### dismissed — 复审误报移除附录 ⛔（高置信误报已剔除，附代码证据，人工可翻案）",
        }
        blocks = [titles[level]]
        for i, it in enumerate(items, 1):
            blocks.append(_issue_doc_block(it, i))
        sections.append("\n".join(blocks))

    if not sections:
        return "本次审查未发现问题。"

    return "\n\n".join(sections)


def assemble_citadel_doc(args, issues, counts, conclusion):
    """拼装学城文档 Markdown（六章节）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    repo = args.repo
    branch = args.branch
    operator = args.operator_mis

    # 统计文件数和行数变化（简化版）
    file_count = len(set(it.get("file", "") for it in issues))

    # 变更综述：优先使用主 Agent 通过 --overview 传入的内容，否则用默认
    overview = args.overview if args.overview else f"本次对 {repo} 分支 {branch} 进行了本地代码审查。"

    # Review 发现
    findings = assemble_review_findings(issues)

    # 规则命中摘要
    rule_ids = sorted(set(it.get("ruleId", "") for it in issues if it.get("ruleId")))

    doc = f"""# {repo}/{branch} 本地 CR — {now}

## 一、CR 概述

| 项目 | 内容 |
|------|------|
| 仓库 | {repo} |
| 操作者 | {operator} |
| 分支 | {branch} |
| 审查时间 | {now} |
| 审查范围 | 🟦 全量 |
| Skill 版本 | ai-cr-forlocal {SKILL_VERSION} |

## 二、变更综述

{overview}

## 三、Review 发现

**规则命中摘要**：共命中 {len(rule_ids)} 条规则

- **P0 零容忍**：{counts['P0']} 条
- **P1 稳定性**：{counts['P1']} 条
- **P2 规范**：{counts['P2']} 条
- **P3 性能**：{counts['P3']} 条

{findings}

## 四、总体评价

**Review 结论**：{conclusion}

**发现汇总**：P0: {counts['P0']} | P1: {counts['P1']} | P2: {counts['P2']} | P3: {counts['P3']}

## 五、人工复审要点

以下事项建议人工评审者重点验证：

> AI 分析难以完全确认的领域需人工补充审查。

## 六、附录

- Skill: ai-cr-forlocal {SKILL_VERSION}
- 审查模式: 本地分支模式（forLocal）
- 数据写入: 学城文档 + SDLC JSON
"""
    return doc


def assemble_local_report(args, issues, counts, conclusion, km_url):
    """CatPaw IDE Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    repo = args.repo
    branch = args.branch

    findings = assemble_review_findings(issues)

    report = f"""# AI-CR 本地审查报告

| 项目 | 内容 |
|------|------|
| 仓库 | {repo} |
| 分支 | {branch} |
| 审查时间 | {now} |
| Skill | ai-cr-forlocal {SKILL_VERSION} |
| 结论 | {conclusion} |
| 汇总 | P0={counts['P0']} P1={counts['P1']} P2={counts['P2']} P3={counts['P3']} |

{f'📄 学城文档：{km_url}' if km_url else ''}

---

{findings}

---

> 本报告由 ai-cr-forlocal {SKILL_VERSION} 自动生成
"""
    return report


# ──────────────────────────────────────────────
# 学城文档创建
# ──────────────────────────────────────────────

def step_create_citadel_doc(args, doc_md):
    """创建学城文档（查找/创建日期目录 + 创建文档，4 次重试）"""
    parent_id = args.citadel_parent_id
    if not parent_id:
        log("未提供 citadel-parent-id，跳过学城文档创建")
        return ""

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    date_dir_name = f"AI-CR-{date_str}"

    # 尝试查找日期目录
    list_result = retry(
        lambda: run_cmd(
            f'oa-skills citadel getChildContent --parentId "{parent_id}"',
            "citadel-list-child",
        ),
        "citadel-list-child",
    )

    date_dir_id = None
    if list_result:
        try:
            children = json.loads(list_result)
            if isinstance(children, list):
                for child in children:
                    if child.get("name") == date_dir_name or child.get("title") == date_dir_name:
                        date_dir_id = child.get("id") or child.get("contentId")
                        break
        except json.JSONDecodeError:
            pass

    # 创建日期目录（如果不存在）
    if not date_dir_id:
        create_dir_result = retry(
            lambda: run_cmd(
                f'oa-skills citadel createDocument --parentId "{parent_id}" --title "{date_dir_name}"',
                "citadel-create-dir",
            ),
            "citadel-create-dir",
        )
        if create_dir_result:
            date_dir_id = _extract_content_id(create_dir_result)

    if not date_dir_id:
        log("无法创建/找到日期目录，尝试直接在父目录创建文档")
        date_dir_id = parent_id

    # 创建文档（用 --file 方式，禁止用 --content，\n 不会转换为换行）
    doc_title = f"{args.repo}_{args.branch}_{now.strftime('%H%M%S')}"

    # 写入临时文件，用 --file 方式创建文档
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
        tmp.write(doc_md)
        tmp_path = tmp.name

    for attempt in range(4):
        result = retry(
            lambda: run_cmd(
                f'oa-skills citadel createDocument --parentId "{date_dir_id}" --title "{doc_title}" --file "{tmp_path}"',
                f"citadel-create-doc-attempt-{attempt+1}",
            ),
            f"citadel-create-doc-attempt-{attempt+1}",
        )

        if result:
            url = _extract_url(result)
            if url:
                log(f"学城文档创建成功: {url}")
                os.unlink(tmp_path)
                return url
            content_id = _extract_content_id(result)
            if content_id:
                url = f"https://km.sankuai.com/c/{content_id}"
                log(f"学城文档创建成功 (contentId={content_id}): {url}")
                os.unlink(tmp_path)
                return url

        if attempt < 3:
            time.sleep(2)

    # 清理临时文件
    os.unlink(tmp_path)
    log("学城文档创建失败（4 次重试均失败）")
    return ""


# ──────────────────────────────────────────────
# DB 写入
# ──────────────────────────────────────────────

def step_db_write(args, issues, counts, conclusion, km_url):
    """DB 写入：调用 cr_record.py（复用 ai-pr-code-review-testn 生产脚本）。

    本地模式无 PR：pr_url 用 dev.sankuai.com 伪 PR 格式（服务端校验路径模式，
    pr/0 + ?branch= 查询串承载真实分支信息），写入 cr_task 表。
    失败不阻塞：cr_record.py 内部自带「多维表格降级」，此处只透传结果。
    """
    import subprocess
    import shlex

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cr_record.py")
    pr_url = (
        km_url
        or f"https://dev.sankuai.com/code/repo-detail/{args.repo}/pr/0/overview?branch={args.branch}"
    )

    # issues 明细写临时文件（写入 DB cr_result_json.issues，对齐 ai-cr-forlocal）
    issues_file = ""
    if issues:
        branch_safe = re.sub(r"[^A-Za-z0-9._-]", "_", args.branch)[:60]
        issues_file = f"/tmp/cr_issues_{args.repo.split('/')[-1]}_{branch_safe}.json"
        with open(issues_file, "w", encoding="utf-8") as f:
            json.dump(issues, f, ensure_ascii=False)

    cmd = [
        sys.executable, script,
        "--pr-url", pr_url,
        "--repo", args.repo,
        "--pr-title", f"[本地CR] {args.repo}:{args.branch}",
        "--author-mis", args.operator_mis or "unknown",
        "--conclusion", conclusion,
        "--p0", str(counts.get("P0", 0)),
        "--p1", str(counts.get("P1", 0)),
        "--p2", str(counts.get("P2", 0)),
        "--p3", str(counts.get("P3", 0)),
        "--doc-url", km_url or "N/A",
        "--operator-mis", args.operator_mis or "unknown",
        "--source-branch", args.branch,
        "--target-branch", args.base_branch or "",
        *( [] if getattr(args, "is_sdd", False) else ["--no-sdd"] ),
        "--alignment", getattr(args, "alignment_rate", None) or "N/A",
        "--skill-version", f"ai-cr-forlocal {SKILL_VERSION}",
        "--org-id", _cr_config_str("org_id"),
        "--table-id", _cr_config_str("table_id") or "2751197605",
        "--no-proxy",
    ]
    # cr_result_json 对齐字段（agent 版 build_cr_result 同构）
    if getattr(args, "file_count", None) is not None:
        cmd += ["--file-count", str(args.file_count)]
    if getattr(args, "line_changes", ""):
        cmd += ["--line-changes", args.line_changes]
    if getattr(args, "tech_stack", ""):
        cmd += ["--tech-stack", args.tech_stack]
    if getattr(args, "overview", ""):
        cmd += ["--overview-text", args.overview]
    if issues_file:
        cmd += ["--issues-file", issues_file]
    # ONES 工作项关联 + 触发源覆盖（仅显式传参才透传，存量行为不变）
    if getattr(args, "ones_id", ""):
        cmd += ["--ones-id", args.ones_id]
    if getattr(args, "ones_url", ""):
        cmd += ["--ones-url", args.ones_url]
    if getattr(args, "trigger_source", ""):
        cmd += ["--trigger-source", args.trigger_source]
    # DB 写入异步化：不阻塞 publish 主流程（学城文档已产出，DB 只是运营统计）
    # 后台跑，日志落 /tmp/cr_db_write_async.log，publish 结束后可查
    import subprocess as _sp
    logline = f"DB 写入（异步）: repo={args.repo} branch={args.branch} p0={counts.get('P0',0)} p1={counts.get('P1',0)}"
    try:
        with open("/tmp/cr_db_write_async.log", "a", encoding="utf-8") as lf:
            lf.write(logline + "\n")
            _sp.Popen(
                cmd, stdout=lf, stderr=_sp.STDOUT,
                start_new_session=True,  # 脱离会话组，publish 退出不杀子进程
            )
        log(f"✅ DB 写入已转后台（结果见 /tmp/cr_db_write_async.log）")
        return True
    except Exception as e:
        log(f"DB 写入转后台失败（不阻塞）: {e}")
        return False


# ──────────────────────────────────────────────
# SDLC JSON 输出（schema 与 AI-SDLC 平台约定，禁止增删改字段）
# ──────────────────────────────────────────────

def dlc_conclusion(conclusion):
    """中文结论 → DLC 英文枚举（AI-SDLC 平台约定，冻结）"""
    if "需重新设计" in conclusion:
        return "NEED_REDESIGN"
    if "需修复" in conclusion:
        return "NEED_FIX"
    if "有建议" in conclusion:
        return "PASS_WITH_SUGGESTION"
    return "PASS"


def write_dlc_json(args, issues, counts, conclusion, km_url):
    """SDLC JSON 输出到 /tmp/ai_cr_result_{repoName}_{branch}.json"""
    branch_safe = args.branch.replace("/", "-")
    repo_name = args.repo.split("/")[-1]  # 与 forlocal 对齐：org/repo 取 repoName
    output_path = f"/tmp/ai_cr_result_{repo_name}_{branch_safe}.json"

    # ⚠️ AI-SDLC 平台约定的 JSON schema，禁止增删改任何字段（字段冻结）
    # 完全对齐 ai-cr-forlocal 原始 DLC JSON schema
    dlc_data = {
        "cr_result": dlc_conclusion(conclusion),
        "p0_count": counts["P0"],
        "p1_count": counts["P1"],
        "p2_count": counts["P2"],
        "p3_count": counts["P3"],
        "km_doc_url": km_url,
        "pr_url": None,
        "repo": args.repo,
        "branch": args.branch,
        "changed_files": len(set(it.get("file", "") for it in issues)),
        "cr_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "issues": [
            {
                "level": it.get("severity", "P2"),
                "file": it.get("file", ""),
                "line": it.get("line", 0),
                "title": it.get("summary", ""),
                "suggestion": it.get("suggestion", ""),
                "fix_type": it.get("fix_type", ""),
                "fix_range": it.get("fix_range", {}),
                "fix_code": it.get("fix_code", ""),
                "fix_description": it.get("fix_description", ""),
            }
            for it in issues if it.get("severity") in ("P0", "P1")
        ],
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dlc_data, f, ensure_ascii=False, indent=2)
        log(f"SDLC JSON 写入成功: {output_path}")
        return output_path
    except Exception as e:
        log(f"SDLC JSON 写入失败: {e}")
        return None


# ──────────────────────────────────────────────
# 参数解析 + 主流程
# ──────────────────────────────────────────────

def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="AI-CR forLocal 一体化发布脚本 (ai-cr-forlocal)"
    )
    parser.add_argument("--repo", required=True, help="仓库名")
    parser.add_argument("--base-branch", default="", help="基准分支（DB 上报 target_branch）")
    parser.add_argument("--branch", required=True, help="分支名")
    # ONES 工作项关联（可选）+ 触发源覆盖（ADC 触发传 adc）
    parser.add_argument("--ones-id", default="", help="ONES 工作项全局 ID（纯数字，透传 cr_record.py）")
    parser.add_argument("--ones-url", default="", help="ONES 工作项链接（透传 cr_record.py）")
    parser.add_argument("--trigger-source", default="", help="触发来源覆盖，默认 forlocal；ADC 触发传 adc（透传 cr_record.py）")
    parser.add_argument("--operator-mis", default="", help="操作者 MIS")
    parser.add_argument("--citadel-parent-id", default="", help="学城父目录 ID")
    parser.add_argument(
        "--issues-file",
        action="append",
        required=True,
        help="Issue JSON 文件路径（可多次指定）",
    )
    parser.add_argument("--overview", default="", help="变更综述（主 Agent 补充的上下文）")
    parser.add_argument("--file-count", type=int, default=None, help="变更文件数（透传 cr_record.py → cr_result_json）")
    parser.add_argument("--line-changes", default="", help="行数变化如 +120 -30（透传 cr_record.py → cr_result_json）")
    parser.add_argument("--tech-stack", default="",
                       help="技术栈（java/nodejs/mrn/max/miniprogram/duo/react/android/ios/harmony/native/flutter/unknown；缺失或非法值登记 unknown）")
    parser.add_argument("--conclusion-override", default=None, help="结论覆盖")
    parser.add_argument(
        "--no-citadel", action="store_true", help="跳过学城文档创建"
    )
    parser.add_argument("--no-db", action="store_true", help="跳过 DB 写入")
    parser.add_argument("--is-sdd", action="store_true", default=False, help="本次变更采用 SDD 流程（4-D SDD_CHECK_RESULT.has_spec）")
    parser.add_argument("--alignment-rate", default="N/A", help="文码一致率（SDD_CHECK_RESULT.alignment_rate，如 92%%）")
    parser.add_argument(
        "--empty-result",
        action="store_true",
        help="空 diff 提前退出模式：仅写零问题 SDLC JSON，跳过学城/DB",
    )
    parser.add_argument("--reason", default="", help="空结果原因（配合 --empty-result）")

    return parser.parse_args()


def main():
    args = parse_args()

    # 空结果模式（Step 1A 空校验提前退出）：只写 SDLC JSON，不建学城/不写 DB
    if args.empty_result:
        zero_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        reason = args.reason or "diff 为空"
        write_dlc_json(
            args,
            issues=[],
            counts=zero_counts,
            conclusion=f"✅通过（{reason}）",
            km_url="",
        )
        log(f"空结果模式完成：{reason}，SDLC JSON 已写入，跳过学城/DB")
        return

    log(f"=== AI-CR forLocal 发布流程启动 ({SKILL_VERSION}) ===")
    log(f"仓库: {args.repo}, 分支: {args.branch}")
    log(f"Issue 文件: {args.issues_file}")

    # 1. 加载 Issue
    issues = load_issues(args.issues_file)
    if not issues:
        log("⚠️ 无 issue 数据，继续生成空报告")

    # 1.5 行号锚定校验（fail-open 增强，不改变任何发布逻辑）
    #     拿 issue.code 回 /tmp/local_cr_diff.txt 做归一化匹配打标；
    #     ENABLE_ANCHOR=False 观察期仅统计，True 后才校正缺失/0 行号。
    #     任何异常 → 原样放行（anchor_issues 内部已兜底）
    diff_text = ""
    try:
        # cr-cli.sh prep 阶段写入的全量 diff(唯一权威来源,见 tools/cr-cli.sh:182)
        _diff_path = "/tmp/local_cr_diff.txt"
        if os.path.isfile(_diff_path):
            diff_text = read_text_file(_diff_path, "")
    except Exception:
        diff_text = ""
    anchored = anchor_issues(issues, diff_text or None)
    try:
        _verified = sum(1 for it in anchored if it.get("_anchor") == "verified")
        _total = len(anchored)
        if _total:
            log(f"行号锚定: {_verified}/{_total} 条 issue 命中 diff 坐标"
                f"（verified/unverified，观察期不校正；ENABLE_ANCHOR 状态见 line_anchor.py）")
    except Exception:
        pass
    issues = anchored
    # _anchor 为内部标记，发布前剥离，不进入学城/DB/SDLC JSON
    for it in issues:
        it.pop("_anchor", None)

    # 2. 统计
    counts = count_issues(issues)
    log(f"统计: P0={counts['P0']} P1={counts['P1']} P2={counts['P2']} P3={counts['P3']}")

    # 3. 推导结论
    conclusion = derive_conclusion(counts, args.conclusion_override)
    log(f"结论: {conclusion}")

    # 4. 拼装学城文档
    doc_md = assemble_citadel_doc(args, issues, counts, conclusion)

    # 5. 创建学城文档
    km_url = ""
    if not args.no_citadel and args.citadel_parent_id:
        km_url = step_create_citadel_doc(args, doc_md)
    else:
        log("跳过学城文档创建")

    # 6. DB 写入
    if not args.no_db:
        step_db_write(args, issues, counts, conclusion, km_url)
    else:
        log("跳过 DB 写入")

    # 7. SDLC JSON 输出
    write_dlc_json(args, issues, counts, conclusion, km_url)

    # 8. CatPaw IDE 报告
    local_report = assemble_local_report(args, issues, counts, conclusion, km_url)
    print(local_report)

    log(f"=== 发布流程完成 ===")
    log(f"结论: {conclusion}")
    log(f"学城文档: {km_url or '（未创建）'}")


if __name__ == "__main__":
    main()
