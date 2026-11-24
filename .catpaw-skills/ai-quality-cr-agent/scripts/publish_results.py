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
    [--session-id "会话ID"] [--agent-name "AICR_Agent"]  # 可选；Step 9 落库用；不传则自动嗅探（session_id 同 conversation_id 链路；agent_name 读 X_AI_PAAS → 1024_PAAS，白名单校验 AICR_Agent 前缀，不规范值丢弃）

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
import inspect
import json
import os
import subprocess
import sys
import time
import re
import shlex
import tempfile
from datetime import datetime

# 同目录 import cr_comment（CommentClient）；EFS 只读连锁自愈：
# 1024 平台可能把 scripts/ 复制到其他目录（如 /tmp）后仅单独携带本文件，
# 同目录找不到 cr_comment.py 时依次从 SKILL_DIR 环境变量、EFS 原始 skill 目录回退定位。
try:
    from cr_comment import CommentClient, CommentError
except ImportError:
    _here = os.path.dirname(os.path.abspath(__file__))
    _cand = [
        os.path.join(os.environ.get("SKILL_DIR", ""), "scripts"),
    ]
    import glob as _glob
    _cand += sorted(_glob.glob(
        "/efs/data/tenants/*/skills/ai-quality-cr-agent/scripts"))
    for _d in _cand:
        _mod = os.path.join(_d, "cr_comment.py")
        if _d and os.path.isfile(_mod):
            sys.path.insert(0, _d)
            break
    from cr_comment import CommentClient, CommentError

from rule_id import normalize_fe_rule_id

# 锚定校验引擎（同目录优先；回退链与 cr_comment 一致）
try:
    from line_anchor import anchor_issues as _la_anchor_issues
    from line_anchor import resolve_publish_anchors as _la_resolve
except ImportError:
    _la_dir = os.path.dirname(os.path.abspath(__file__))
    if _la_dir not in sys.path:
        sys.path.insert(0, _la_dir)
    try:
        from line_anchor import anchor_issues as _la_anchor_issues
        from line_anchor import resolve_publish_anchors as _la_resolve
    except ImportError:
        _la_anchor_issues = None
        _la_resolve = None



# ─── 常量 ────────────────────────────────────────────────────────────────────
RETRY_MAX = 4
RETRY_INTERVAL = 2.5  # 秒
CITADEL_DIR_CAPACITY_FULL = 490  # 接近上限自动续编阈值（≥此值滚动到《日期-N》续编目录）

# 大象 API 凭证（与 notify.py / daxiang-notify-api.md 一致）
import base64, hmac, hashlib, uuid, urllib.request, urllib.parse

AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151
TOKEN_URL            = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL             = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"
MIS2UID_URL          = "https://xopen.sankuai.com/open-apis/dx/queryEmpIdentityByMisList"

# Step 9: 回写 CR 结果到 cr_task.cr_result_json（接口文档见 km.sankuai.com/collabpage/2773928547）
SUBMIT_CR_RESULT_URL = "https://spt.sankuai.com/api/v1/aicr/submit-result"

# 动态从 SKILL.md frontmatter 读取 skillhub.version
import re as _re
# 优先从 __file__ 推导 SKILL.md 路径；如果失败（沙箱解压结构不同），回退到 SKILL_DIR 环境变量
_SKILL_MD_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SKILL.md"),  # scripts/.. / SKILL.md
    os.path.join(os.environ.get("SKILL_DIR", ""), "SKILL.md"),  # $SKILL_DIR/SKILL.md
]
SKILL_VERSION = "V0"

# ── 触发溯源取值抽离至 runner_identity.py ──
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from runner_identity import (  # noqa: E402
    agent_and_session,
    agent_overview_url,
    get_agent_name,
    get_session_id,
    session_analysis_url,
    sniffed_conversation_id,
)
from trigger_identity import clean_trigger_identity  # noqa: E402

for _path in _SKILL_MD_CANDIDATES:
    try:
        if not _path or not os.path.isfile(_path):
            continue
        with open(_path, "r", encoding="utf-8") as _f:
            _content = _f.read()
        _m = _re.search(r"skillhub\.version:\s*\"(V[\w.\-]+)\"", _content)
        if _m:
            SKILL_VERSION = _m.group(1)
            break
    except Exception:
        continue

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "confirm": 4}
SEVERITY_EMOJI = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵", "confirm": "🔎"}
SEVERITY_TITLE = {
    "P0": "P0 — 零容忍异常 🔴",
    "P1": "P1 — 稳定性风险 🟠",
    "P2": "P2 — 代码规范 🟡",
    "P3": "P3 — 优化建议 🔵",
}

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


def run_cmd(cmd, label="cmd", timeout=120):
    """执行参数数组，返回 stdout+stderr 合并输出。失败抛异常。
    注：oa-skills citadel 等工具把业务输出写到 stderr，所以必须合并。
    """
    if not isinstance(cmd, (list, tuple)):
        raise TypeError("命令必须使用参数数组")
    log(f"▶ {label}: {shlex.join(cmd)[:200]}...")
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout)
    combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    if result.returncode != 0:
        raise RuntimeError(f"exit={result.returncode} output={combined[:500]}")
    return combined


def run_cmd_raw(cmd, label="cmd", timeout=120):
    """执行 shell 命令，只返回 stdout（--raw 模式下 oa-skills 输出纯 JSON 到 stdout，
    人类可读日志走 stderr 不返回）。
    与 run_cmd 的区别：子文档标题含 {hotfix} 等花括号时，合并输出的 find/rfind
    提取会被干扰导致 JSON 解析失败；--raw + 独立解析 stdout 彻底隔离日志噪声。
    """
    if not isinstance(cmd, (list, tuple)):
        raise TypeError("命令必须使用参数数组")
    log(f"▶ {label}: {shlex.join(cmd)[:200]}...")
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"exit={result.returncode} stderr={result.stderr.strip()[:300]}")
    return result.stdout.strip()


def read_text_file(path, default=""):
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        log(f"⚠️  读取文件失败 {path}: {e}")
        return default


# 技术栈由审查 Agent 根据本轮模块证据判定；发布阶段不按路径重新分类。
VALID_TECH_STACKS = ["java", "nodejs", "mrn", "max", "miniprogram", "duo", "react",
                     "android", "ios", "harmony", "native", "flutter", "unknown"]


def resolve_tech_stack(args):
    """规范化显式判定；缺失或非法值登记 unknown，避免伪造确定分类。"""
    explicit = (getattr(args, "tech_stack", "") or "").strip().lower()
    if explicit in VALID_TECH_STACKS:
        return explicit
    log("⚠️ 技术栈缺失或不在支持值域内，登记 unknown；需核对本轮模块证据")
    return "unknown"


def _strip_dup_section_title(md, titles):
    """去掉透传章节文件自带的一级/二级标题行，避免与脚本拼装的章节标题重复。

    Agent 按 adoption-rate-template 等模板写 /tmp/cr_adopt_xxx.md 时，
    模板自带的「## 七、上轮 CR 采纳情况」标题会被一并写入，
    脚本外面又套一层章节标题 → 文档出现双重标题（且章号可能不一致）。
    这里删除开头连续的标题行（# 开头，允许中间空行）。
    """
    if not md:
        return md
    lines = md.split("\n")
    i = 0
    # 跳过开头的空行
    while i < len(lines) and not lines[i].strip():
        i += 1
    # 删除开头连续的 # 标题行（含紧随的空行）
    while i < len(lines) and lines[i].lstrip().startswith("#"):
        heading = lines[i].strip()
        # 只删除与目标章节相关的标题，避免误删正文里的无关标题
        if not any(t in heading for t in titles):
            break
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    return "\n".join(lines[i:]).strip()


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
    m = re.search(r'(?:^|\n)文档ID[：:]\s*([0-9]+)(?:\n|$)', text)
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
        elif isinstance(data, dict) and data.get("schema") == "step4e-envelope/v1":
            # step4e 封装体 —— findings 从封装体内提取;
            # checks 状态由 --extan-status-file 门禁路径单独判定,此处只取 findings
            all_issues.extend(data.get("findings") or [])
        else:
            log(f"⚠️  issues 文件非 JSON 数组，跳过: {path}")

    # 规范化 + 去重（同 file + line + ruleId 视为重复，保留首个）
    seen = set()
    deduped = []
    for it in all_issues:
        if not isinstance(it, dict):
            continue
        try:
            normalize_fe_rule_id(it)
        except ValueError as exc:
            log(f"⚠️ FE 规则字段校验失败，保留问题及原始字段: {exc}")
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

def soft_gate_issues(args, issues):
    """软门禁：对每条 issue 运行 issue_io 的 schema 校验（同款规则，不 import CLI）。

    设计原则（与强卡门禁的区别）：
    - 不阻塞发布：评审必须保证有结果，任何情况下不因格式问题整体失败
    - 不静默修正：不替模型补字段；不合规条目降级而非丢弃
    - 落盘追溯：逐条判定写入 /tmp/cr_gate_{prId}.json，Agent 是否修正有据可查

    降级规则：
    - severity/lineType 非法且无法锚定 → 强制降为 P2，lineType 补 ADDED，记录降级原因
    - 无法解析（非 dict）→ 丢弃并计入 dropped（保留摘要供追溯）
    - confirm 校验失败，或锚点/severity 合法但缺其它字段 → 保留，计入 warned
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from issue_io import validate_issue, IssueValidationError
    except Exception as e:
        log(f"⚠️ 软门禁模块加载失败（跳过校验，不阻塞）: {e}")
        return issues

    gate_report = {"pr_id": args.pr_id, "total": len(issues), "passed": 0,
                   "downgraded": [], "dropped": [], "warned": []}
    kept = []
    for idx, it in enumerate(issues):
        loc = f"issues[{idx}]"
        try:
            validated = validate_issue(dict(it), loc)
            gate_report["passed"] += 1
            kept.append(validated)
            continue
        except IssueValidationError as exc:
            reason = str(exc)
            if not isinstance(it, dict):
                gate_report["dropped"].append({"location": loc, "reason": reason,
                                                "summary": str(it)[:200]})
                log(f"⚠️ 软门禁丢弃 {loc}: 无法解析")
                continue
            sev = (it.get("severity") or "").strip().upper()
            line_type = (it.get("lineType") or "").strip().upper()
            anchor_ok = line_type in ("ADDED", "REMOVED")
            if sev == "CONFIRM" or (anchor_ok and sev in ("P0", "P1", "P2", "P3")):
                # confirm 允许无锚点保留；行内发布另行筛选有效锚点；其它问题要求合法定级和 lineType
                gate_report["warned"].append({"location": loc, "reason": reason,
                                              "ruleId": it.get("ruleId", "")})
                log(f"⚠️ 软门禁警告 {loc}: {reason}（保留发布）")
                kept.append(it)
            else:
                # 锚点非法或 severity 非法：降级 P2 + 补 ADDED，不丢弃信号
                it["lineType"] = "ADDED"
                it["severity"] = "P2"
                gate_report["downgraded"].append({"location": loc, "reason": reason,
                                                  "ruleId": it.get("ruleId", ""),
                                                  "summary": (it.get("summary") or "")[:120]})
                log(f"⚠️ 软门禁降级 {loc} → P2/ADDED: {reason}")
                kept.append(it)
    try:
        with open(f"/tmp/cr_gate_{args.pr_id}.json", "w", encoding="utf-8") as f:
            json.dump(gate_report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠️ 门禁报告落盘失败（不影响发布）: {e}")
    if gate_report["downgraded"] or gate_report["dropped"] or gate_report["warned"]:
        log(f"📊 软门禁: {gate_report['passed']}/{gate_report['total']} 通过，"
            f"{len(gate_report['downgraded'])} 降级，{len(gate_report['dropped'])} 丢弃，"
            f"{len(gate_report['warned'])} 警告 → /tmp/cr_gate_{args.pr_id}.json")
    return kept


def count_issues(issues):
    counts = {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "confirm": 0, "ext": 0}
    # 灰度边界: EXT(step4e) 不作为问题定级,归入 confirm 统计——
    # 「先呈现信息不计入问题统计」的完整语义:confirm 不是定级而是待人工确认,
    # EXT findings 本就未经主流程复审,进 confirm 既可见又不污染 P0-P3。
    # 转正名单: arch-pr-verifier 按原级直接计入
    # P0-P3 统计并参与 Review 结论推导(仍不进 4-Review 二次复审);
    # 其余 analyzer 维持灰度 confirm 统计。
    for it in issues:
        sev = it["severity"]
        if it.get("source") == "step4e":
            if _extan_is_promoted(it):
                # 转正: 原级计入 P0-P3(EXTAN_PROMOTED 与 loader 同名单;不在名单回落 confirm)
                if sev == "P0":
                    counts["p0"] += 1
                elif sev == "P1":
                    counts["p1"] += 1
                elif sev == "P2":
                    counts["p2"] += 1
                elif sev == "P3":
                    counts["p3"] += 1
                else:
                    counts["confirm"] += 1
                counts["ext"] += 1
                continue
            # 外部专项审查（灰度）：计入待确认(含保留 confirm 原级的),ext 仅作展示计数
            counts["confirm"] += 1
            counts["ext"] += 1
            continue
        if sev == "P0":
            counts["p0"] += 1
        elif sev == "P1":
            counts["p1"] += 1
        elif sev == "P2":
            counts["p2"] += 1
        elif sev == "P3":
            counts["p3"] += 1
        elif sev == "confirm":
            counts["confirm"] += 1
    return counts


# ---------------- 外部专项审查发布门禁(2026-11-02, PR#293 事故修复) ----------------
# 原则: 计入结论(required/promoted)的 analyzer,失败必须拦结论。
# findings=[] 不再等价于零发现;step4e 封装体的 checks 数组携带逐 analyzer 状态。
EXTAN_STATUS_STATUSES = ("READY", "FAILED", "UNKNOWN", "TIMEOUT")


def load_extan_checks(path):
    """读取 step4e 封装体或兼容旧裸数组格式。
    返回 (checks, findings, degraded_note, envelope_meta):
    degraded_note 描述兼容降级情况;envelope_meta 含顶层 runId/targetCommit/runIdMatch(身份校验)。"""
    note = ""
    checks, findings = [], []
    if not path:
        # 未传 --extan-status-file = 未启用 4-E/门禁(0F 无匹配 analyzer),合法不拦
        return checks, findings, "未启用外部专项审查(--extan-status-file 未传)", {}
    if not os.path.isfile(path):
        # 传了门禁路径但文件不存在 = collect 未执行/产物丢失,按 UNKNOWN 拦截(清单: 文件缺失→UNKNOWN)
        return ([{"analyzer": "missing-step4e", "status": "UNKNOWN",
                   "error": "step4e-envelope-missing: 门禁已启用但封装体不存在(collect 未执行?)",
                   "required": True, "mode": "auto", "dropReasons": ["envelope-missing"]}],
                 [], "step4e 封装体缺失(已启用门禁但文件不存在),按 UNKNOWN 拦截", {})
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return ([{"analyzer": "unknown", "status": "UNKNOWN",
                   "error": "step4e-envelope-unreadable:%s" % type(e).__name__,
                   "required": True, "mode": "auto", "dropReasons": []}], [],
                 "step4e 封装体损坏", {})
    env_meta = {}
    if isinstance(data, dict):
        checks = list(data.get("checks") or [])
        findings = list(data.get("findings") or [])
        env_meta = {"runId": data.get("runId") or "", "targetCommit": data.get("targetCommit") or ""}
        if not checks and data.get("status") and data.get("status") != "READY":
            # 有顶层状态无 checks(如 collect 早退写整体状态): 合成一条 unknown check
            checks = [{"analyzer": "unknown", "status": data.get("status"),
                       "error": str(data.get("error") or ""), "required": True,
                       "mode": "auto", "dropReasons": []}]
    elif isinstance(data, list):
        # 旧裸数组格式(及更早 loader 产出): 无状态可判,按 UNKNOWN 提示升级
        findings = data
        note = "step4e 为旧裸数组格式(无 checks 状态,loader 才产出封装体);本次按无门禁数据处理"
    else:
        return ([{"analyzer": "unknown", "status": "UNKNOWN",
                   "error": "step4e-envelope-shape:%s" % type(data).__name__,
                   "required": True, "mode": "auto", "dropReasons": []}], [],
                 "step4e 封装体形状非法", {})
    return checks, findings, note, env_meta


def evaluate_extan_gate(checks, note):
    """判定外部专项审查门禁。返回 (gate_ok, gate_reason, required_failed)。
    required=true 且 status != READY → 拦结论(gate_ok=False);
    required=false 失败 → 不拦,但 gate_reason 记录可见降级。"""
    required_failed = []
    optional_failed = []
    for c in checks:
        if not isinstance(c, dict):
            continue
        analyzer = str(c.get("analyzer") or "unknown")
        status = str(c.get("status") or "UNKNOWN")
        if status not in EXTAN_STATUS_STATUSES:
            status = "UNKNOWN"
        if status == "READY":
            continue
        entry = (analyzer, status, str(c.get("error") or "")[:300])
        if c.get("required"):
            required_failed.append(entry)
        else:
            optional_failed.append(entry)
    gate_ok = not required_failed
    if required_failed:
        names = ", ".join("%s(%s)" % (a, s) for a, s, _ in required_failed)
        gate_reason = "必选专项审查未完成: %s" % names
    elif optional_failed:
        gate_reason = "可选专项审查降级(不拦结论): %s" % ", ".join(
            "%s(%s)" % (a, s) for a, s, _ in optional_failed)
    else:
        gate_reason = "外部专项审查全部完成"
    if note:
        gate_reason = (gate_reason + "; " + note) if gate_reason else note
    return gate_ok, gate_reason, required_failed


def derive_conclusion(counts, override="", extan_gate_ok=True, extan_gate_reason=""):
    """根据 P0/P1/P2 计数自动推导 Review 结论。
    override 非空且门禁未通过时,override 被否决(门禁优先级最高);
    门禁通过时 override 直接生效。"""
    if not extan_gate_ok:
        return "⚠️ 核验未完成（%s）" % extan_gate_reason
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


def _clean_suggestion_code(text):
    """清理 suggestion 文本里的模板噪声：代码块内首行的 `// 代码块` 注释残留。"""
    if not text or "// 代码块" not in text:
        return text
    out = []
    fence_open = False
    for ln in text.split("\n"):
        if ln.strip().startswith("```"):
            fence_open = not fence_open
            out.append(ln)
            continue
        if fence_open and ln.strip() == "// 代码块":
            continue  # 丢弃模板噪声行
        out.append(ln)
    return "\n".join(out)


def _fence_lang_for(content, default="java"):
    """按代码内容嗅探语言标记：XML 结构(<tag> 且无典型 java 特征)用 xml，否则 default。"""
    if not content:
        return default
    stripped = content.strip()
    has_xml_tag = bool(re.match(r"^\s*<(\?xml|!--|[a-zA-Z][\w.:-]*(?:\s|/?>))", stripped))
    has_java_sig = any(k in stripped for k in ("public ", "private ", "protected ", "static ", "void ", "new ", "import "))
    if has_xml_tag and not has_java_sig:
        return "xml"
    return default


def _split_code_blocks(text, lang="java"):
    """将混合内容拆分为代码块和说明文字段落。
    识别策略：
    1. 如果文本已包含 markdown 代码块标记(```),直接透传不二次处理(仅清理 `// 代码块` 噪声行)
    2. 以行为单位判断——包含代码语法特征(括号/分号/赋值/方法调用/关键字等)
       的连续行归为代码块,其他行作为说明文字段落
    3. 纯英文说明句(以动词开头+空格+宾语)不误判为代码
    """
    if not text or not text.strip():
        return []

    # 如果已包含 markdown 代码块标记,透传但确保闭合正确且代码块标记前有空行
    if "```" in text:
        text = _clean_suggestion_code(text)
        tl = text.split("\n")
        fixed = []
        fence_open = False
        fence_lang = lang
        for j, ln in enumerate(tl):
            stripped = ln.strip()
            if stripped.startswith("```"):
                if not fence_open:
                    # 代码块开始：无语言标记或标注为 java 但内容是 XML 时,嗅探修正
                    fence_lang = stripped[3:].strip() or ""
                    if j + 1 < len(tl):
                        next_lines = "\n".join(tl[j+1:j+8])
                        if not fence_lang or (fence_lang.lower() in ("java", "")):
                            sniffed = _fence_lang_for(next_lines, default=fence_lang or lang)
                            ln = "```" + sniffed if fence_lang else f"```{sniffed}"
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
    rule_id = it.get("ruleId", "") or "无规则标注"
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
        # 历史证据标注：降级条目的行号是审查时快照口径，未在当前代码上
        # 验证锚定（不将历史证据伪装成当前已证实），指向 PR 全局评论兜底说明
        _pub_note = it.get("_publishNote")
        if _pub_note:
            lines.append("")
            lines.append(f"> ⚠️ 行号为审查时快照口径，未能在当前代码上验证锚定"
                         f"（{_pub_note}）；该问题将附于 PR 全局评论（发送前口径，"
                         f"实际发布结果以 PR 评论为准）")
        if code:
            lines.append("")
            lines.append(f"**问题代码**：")
            lines.append("")
            # 按文件后缀选语法高亮：前端文件不用 java 标记
            _ext = (file_ or "").rsplit(".", 1)[-1].lower() if ("." in (file_ or "")) else ""
            _lang = {
                "js": "javascript", "jsx": "jsx", "ts": "typescript", "tsx": "tsx",
                "vue": "vue", "css": "css", "scss": "scss", "less": "less",
                "html": "html", "xml": "xml", "json": "json", "groovy": "groovy",
            }.get(_ext, "java")
            lines.append(f"```{_lang}")
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
        ]
        _pub_note = it.get("_publishNote") or it.get("_anchorNote")
        if _pub_note and _position_status_of(it) == "unconfirmed":
            lines.append("")
            lines.append(f"> ⚠️ 行号为审查时快照口径，未在当前代码上验证锚定（{_pub_note}）")
        # P2/P3 保留「问题描述/检出原因」字段——
        # 锚定改造时误删，导致 P2/P3 在学城文档只剩修复建议（内容完整性回归）
        lines.append("")
        lines.append(f"**问题描述**：{desc}")
        lines.append("")
        lines.append(f"**检出原因**：{risk}")
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
        # 待确认问题格式（标题用 ####，字段结构化分块，不堆坨）
        lines = [
            "",
            f"#### 🔎 待人工确认 [Q-{idx:02d}] {summary}",
            "",
            f"**文件**：`{file_}` L{line}",
        ]
        _pub_note = it.get("_publishNote")
        if _pub_note:
            lines.append("")
            lines.append(f"> ⚠️ 行号为审查时快照口径，未能在当前代码上验证锚定"
                         f"（{_pub_note}）；该问题将附于 PR 全局评论（发送前口径，"
                         f"实际发布结果以 PR 评论为准）")
        lines.append("")
        lines.append("**现象与差异**：")
        lines.append("")
        lines.append(desc)
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
    """拼装「四、Review 发现」整章。按 severity 分组、组内编号。
    EXT（source=step4e）不进主列表，由 assemble_extanalyzer_section 单独成节展示，
    避免同一条目在主列表+EXT 子节重复出现、且与发现汇总行计数不一致
    （count_issues 对 step4e 单独计 ext 不计 P0-P3）。"""
    sections = []
    issues = [it for it in issues if it.get("source") != "step4e"]

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
        lines = ["### 🔎 待人工确认", ""]
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
    """从 issues 列表拼装「规则命中摘要」小节。EXT（source=step4e）不参与统计，
    其来源为外部 skill 能力而非内置规则库，混入会污染 CR/MT/CU 规则口径。"""
    issues = [it for it in issues if it.get("source") != "step4e"]
    if not issues:
        return ""

    # 统计各层级命中
    p0_rules = sorted(set(r for it in issues if it["severity"] == "P0" for r in _expand_rids(it)))
    p1_rules = sorted(set(r for it in issues if it["severity"] == "P1" for r in _expand_rids(it)))
    p2_rules = sorted(set(r for it in issues if it["severity"] == "P2" for r in _expand_rids(it)))
    p3_rules = sorted(set(r for it in issues if it["severity"] == "P3" for r in _expand_rids(it)))
    confirm_count = len([it for it in issues if it["severity"] == "confirm"])

    # CR vs MT vs CU vs FE 统计（合并的 issue 各计）
    cr_count = 0
    mt_count = 0
    cu_count = 0
    l2_count = 0
    fe_count = 0
    bl_count = 0
    unlabeled_count = sum(not _expand_rids(it) for it in issues)
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
            elif r.startswith("L2:"):
                l2_count += 1
            elif r.startswith("FE:"):
                fe_count += 1
            elif r.startswith("BL:"):
                bl_count += 1

    total_rules = len(set(all_rids))
    total_hits = len(issues)

    # 分层问题数（与正文条目一一对应；与规则标签数分开统计）
    p0_items = [it for it in issues if it["severity"] == "P0"]
    p1_items = [it for it in issues if it["severity"] == "P1"]
    p2_items = [it for it in issues if it["severity"] == "P2"]
    p3_items = [it for it in issues if it["severity"] == "P3"]
    confirm_items = [it for it in issues if it["severity"] == "confirm"]

    # 自检告警：分层问题数之和与总数不一致时归入其他桶并告警，不阻断发布（软门禁导向）
    check_sum = len(p0_items) + len(p1_items) + len(p2_items) + len(p3_items) + len(confirm_items)
    other_items = [it for it in issues if it["severity"] not in ("P0", "P1", "P2", "P3", "confirm")]
    if check_sum != total_hits:
        print(f"⚠️ 规则命中摘要自检告警: P0({len(p0_items)})+P1({len(p1_items)})+P2({len(p2_items)})"
              f"+P3({len(p3_items)})+待确认({len(confirm_items)})={check_sum} != 问题总数({total_hits})，"
              f"存在未知 severity（{len(other_items)} 条），已归入其他桶继续发布", file=sys.stderr)

    # 账面口径：问题数与规则数分开，表格化分布
    lines = [
        "### 规则命中摘要",
        "",
        f"本次审查共发现 **{total_hits} 个问题**，涉及 **{total_rules} 条去重规则**（CR: {cr_count} / MT: {mt_count} / CU: {cu_count} / L2: {l2_count} / BL: {bl_count} / FE: {fe_count} 次命中；无规则标注: {unlabeled_count} 个问题；一个问题可带多条规则标签）。分布如下：",
        "",
        "| 层级 | 问题数 | 规则标签（去重） |",
        "| --- | --- | --- |",
        f"| 🚨 P0 零容忍 | {len(p0_items)} | {', '.join(p0_rules) or '—'} |",
        f"| 🔴 P1 稳定性 | {len(p1_items)} | {', '.join(p1_rules) or '—'} |",
        f"| 🟡 P2 规范 | {len(p2_items)} | {', '.join(p2_rules) or '—'} |",
        f"| 🔵 P3 性能 | {len(p3_items)} | {', '.join(p3_rules) or '—'} |",
    ]
    if confirm_items:
        lines.append(f"| 🔎 待人工确认 | {len(confirm_items)} | 待人工确认后定级 |")
    if other_items:
        lines.append(f"| ⚠️ 其他(未知 severity) | {len(other_items)} | 已告警，见 stderr 日志 |")
    lines.append("")
    return "\n".join(lines)


def assemble_custom_rules_section(issues):
    """拼装「📋 自定义规则检查结果」子节（仓库自定义规则）与「🧩 L2 团队规范检查结果」子节（平台订阅 L2）。"""
    cu_issues = [it for it in issues if any(r.startswith("CU:") for r in _expand_rids(it))
                 or (it.get("source") == "step4c" and not any(r.startswith("L2:") for r in _expand_rids(it)))]
    l2_issues = [it for it in issues if any(r.startswith("L2:") for r in _expand_rids(it))]
    if not cu_issues and not l2_issues:
        return ""
    lines = []
    if cu_issues:
        lines += [
            "### 📋 自定义规则检查结果",
            "",
            "> 以下问题来自仓库/团队/CatPaw 自定义规则（.mdp/rules/、.catpaw/rules/）。",
            "",
        ]
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
    if l2_issues:
        lines += [
            "### 🧩 L2 团队规范检查结果",
            "",
            "> 以下问题来自平台订阅的 L2 团队规范（规则分发平台，Step 2I 预取）。",
            "",
        ]
        for sev in ("P0", "P1", "P2", "P3"):
            sev_issues = [it for it in l2_issues if it["severity"] == sev]
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


EXTAN_SECTION_TITLES = {
    # analyzer 名 → 展示标题（专项语义化命名）
    "arch-pr-verifier": "🏗️ 架构漂移",
}

# 转正名单: 与 loader 的 EXTAN_PROMOTED 同名单。
# 名单内 analyzer 的 EXT findings 按原级计入 P0-P3 统计与 Review 结论(不降 confirm);
# 仍不进 Step 4-Review 二次复审。名单外 analyzer 维持灰度降级 confirm。
EXTAN_PROMOTED = {"arch-pr-verifier"}


def _extan_is_promoted(it):
    """判断一条 step4e issue 是否来自转正名单 analyzer。

    ruleId 形如 EXT:{analyzer名}:{规则号};兼容 mergedRuleIds。鲁棒判空,
    任何解析失败都回落 False(灰度),安全优先。
    """
    if it.get("source") != "step4e":
        return False
    rids = _expand_rids(it)
    for r in rids:
        parts = str(r).split(":")
        if len(parts) > 2 and parts[1] in EXTAN_PROMOTED:
            return True
    return False


def _extan_card(it, idx):
    """EXT finding 单条卡片（SOP finding 字段语义 → 六字段文档格式）。

    字段映射（对接 SOP 2787539320 finding 契约）：
    - 标题：原级（_origSeverity）+ 组内编号 + ruleId + summary
    - 文件：file + line + lineType
    - 问题描述：description（判定依据）
    - 检出原因：risk（风险/后果）
    - 规范要求：ruleName（analyzer 填），缺省回落 anomalyType
    - 修复建议：suggestion（_split_code_blocks 处理代码块）
    """
    rule_id = it.get("ruleId", "") or "无规则标注"
    summary = it.get("summary", "") or ""
    file_ = it.get("file", "") or ""
    line = it.get("line", "") or ""
    line_type = (it.get("lineType") or "ADDED").upper()
    desc = it.get("description", "") or ""
    risk = it.get("risk", "") or ""
    sug = it.get("suggestion", "") or ""
    # 原级展示：灰度降级后 severity=confirm，原级取 _origSeverity；
    # analyzer 未被降级（灰度关闭）时 severity 即原级
    orig_sev = it.get("_origSeverity") or it["severity"]
    if orig_sev not in SEVERITY_EMOJI:
        orig_sev = "confirm"
    emoji = SEVERITY_EMOJI.get(orig_sev, "")

    lines = [
        "",
        f"#### {emoji} [{orig_sev}-{idx:02d}] **{summary}**（`{rule_id}`）",
        "",
        f"**文件**：`{file_}` L{line}（{line_type}）",
        "",
        f"**问题描述**：{desc}",
        "",
        f"**检出原因**：{risk}",
    ]
    rule_name = it.get("ruleName", "") or ""
    if not rule_name:
        rule_name = it.get("anomalyType", "") or ""
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
    return "\n".join(lines)


def assemble_extanalyzer_section(issues):
    """拼装「四、Review 发现」内 ext-analyzer 外部专项审查子节。

    单独成节展示，不与内置四路混排。
    - analyzer 有专属标题时按 analyzer 分组，每组独立子节
      （如 arch-pr-verifier →「🏗️ 架构漂移」），组内每条用六字段卡片格式
    - 其余 analyzer 保持简洁概览（一行式）
    来源标注：ruleId 前缀 EXT:{analyzer名}: 即来源 skill；
    _analyzerSkillVersion 字段（loader collect 注入）含版本时一并展示。
    灰度边界不变：不计入 P0-P3 与 Review 结论，仅原级展示。
    """
    ext_issues = [it for it in issues if it.get("source") == "step4e"
                  or any(r.startswith("EXT:") for r in _expand_rids(it))]
    if not ext_issues:
        return ""

    def _analyzer_of(it):
        for r in _expand_rids(it):
            if r.startswith("EXT:"):
                parts = r.split(":")
                if len(parts) > 1:
                    return parts[1]
        rid = it.get("ruleId", "") or ""
        parts = rid.split(":")
        return parts[1] if len(parts) > 1 and parts[0] == "EXT" else "unknown"

    lines = []
    # 分节 banner: 架构漂移按检出级别计入统计;其他 analyzer 仅展示待人工判定。
    banner = "> 以下问题来自外部专项审查（ext-analyzer），产出结果未经主流程二次复审。架构漂移已按检出级别计入统计与 Review 结论，其余待人工判定。"

    card_groups, plain_groups = {}, {}
    for it in ext_issues:
        name = _analyzer_of(it)
        ver = it.get("_analyzerSkillVersion", "")
        if name in EXTAN_SECTION_TITLES:
            card_groups.setdefault(name, []).append(it)
        else:
            plain_groups.setdefault((name, ver), []).append(it)

    # 卡片子节（如 🏗️ 架构漂移）：六字段格式，按原级分组编号
    for name, group in sorted(card_groups.items()):
        title = EXTAN_SECTION_TITLES[name]
        ver = group[0].get("_analyzerSkillVersion", "")
        # 架构漂移标记: 名单内 analyzer 标题带标识,注明按检出级别计入统计
        if name in EXTAN_PROMOTED:
            title = title + "（按检出级别计入统计）"
        lines.append(f"### {title}")
        lines.append("")
        lines.append(banner)
        lines.append("")
        # 检测标准概览已撤: 来源不可靠(本机无 arch-pr-verifier skill 落盘,
        # 无法验证其真实检出规则),无清晰证据不写入文档
        # 按原级分组、组内连续编号（P1-01、P1-02 …）
        for sev in ("P0", "P1", "P2", "P3", "confirm"):
            sev_issues = [it for it in group
                          if (it.get("_origSeverity") or it["severity"]) == sev]
            if not sev_issues:
                continue
            for i, it in enumerate(sev_issues, 1):
                lines.append(_extan_card(it, i))
                lines.append("")
        if ver:
            lines.append(f"**检查工具**：`ext-analyzer-{name}` v{ver}，检出 {len(group)} 条")
            lines.append("")
        else:
            lines.append(f"**检查工具**：`ext-analyzer-{name}`，检出 {len(group)} 条")
            lines.append("")

    # 其余 analyzer：简洁概览（一行式，保持原样式）
    if plain_groups:
        lines.append("### 🧩 自定义检查能力")
        lines.append("")
        lines.append(banner)
        lines.append("")
        for sev in ("P0", "P1", "P2", "P3", "confirm"):
            sev_issues = [it for its in plain_groups.values() for it in its
                          if (it.get("_origSeverity") or it["severity"]) == sev]
            if not sev_issues:
                continue
            emoji = SEVERITY_EMOJI.get(sev, "")
            lines.append(f"**{emoji} {sev}**：{len(sev_issues)} 条")
            for it in sev_issues:
                rule_id = it.get("ruleId", "")
                summary = it.get("summary", "")
                file = it.get("file", "")
                line = it.get("line", "")
                ver = it.get("_analyzerSkillVersion", "")
                lines.append(f"- [{rule_id}] **{summary}**（`{file}` L{line}）" + (f"（版本 {ver}）" if ver else ""))
            lines.append("")
        src = {}
        for (name, ver), its in plain_groups.items():
            src[(name, ver)] = len(its)
        if src:
            lines.append("**检查工具**：" + "；".join(
                f"`ext-analyzer-{n}`" + (f" v{v}" if v else "") + f"，检出 {c} 条"
                for (n, v), c in sorted(src.items())))
            lines.append("")
    return "\n".join(lines) if lines else ""


def _short_hash(h):
    """commit hash 取前 8 位展示，空值返回空串。"""
    return (h or "")[:8]


CR_MODE_INFO_PATH = "/tmp/cr_mode_info.json"


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
    # 禁用共享默认路径 /tmp/cr_mode_info.json（跨轮串读风险）；
    # 仅接受显式 --mode-info-file 或 PR 专属路径，且须通过身份+runId 校验
    # （_load_mode_info_dict 统一判定，身份不匹配/跨轮旧文件整份拒绝）
    path = getattr(args, "mode_info_file", None) or         "/tmp/cr_mode_info_{org}_{repo}_{prId}.json".format(
            org=getattr(args, "org", ""), repo=getattr(args, "repo", ""),
            prId=getattr(args, "pr_id", ""))
    if not path or not os.path.isfile(path):
        return fixes
    info, _mi_path, reject = _load_mode_info_dict(args)
    if not info:
        # 身份不匹配/runId 不匹配/不可读 → 拒绝回填（防串轮），沿用命令行参数
        log(f"⚠️  mode_info 拒绝读取（{reject}），沿用命令行参数")
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
            fixes.append(f"{attr}: 从 cr_mode_info 补齐")

    # 3) 降为全量时清空增量参数
    if args.cr_mode == "full":
        for attr in ("base_commit", "commit_count"):
            if getattr(args, attr, None) is not None:
                setattr(args, attr, None)
                fixes.append(f"{attr}: 已清空（全量模式）")

    # 4) 失败文件列表（get_pr_diff 写入 failedFiles）→ 供产出物标注覆盖缺口
    ff = info.get("failedFiles")
    if isinstance(ff, list) and ff:
        args._mode_failed_files = ff
        fixes.append(f"failed_files: {len(ff)} 个文件拉取失败（需标注覆盖缺口）")

    # 5) 双口径统计量回填（未显式传参时）
    #    平台权威口径三字段：PR 平台权威规模（pr-info），fileCount 成功数仅作回退
    #    审查覆盖口径三字段：审查覆盖口径（成功拉取 diff 的脚本统计）
    if not getattr(args, "file_count", None) and isinstance(info.get("prFileNum"), int):
        args.file_count = info["prFileNum"]
        args._scale_backfilled = True
        fixes.append(f"file_count: 从 mode_info prFileNum 回填（平台权威 {info['prFileNum']}）")
    if not getattr(args, "line_changes", "") and isinstance(info.get("prAdditions"), int) \
            and isinstance(info.get("prDeletions"), int):
        args.line_changes = f"+{info['prAdditions']} -{info['prDeletions']}"
        args._scale_backfilled = True
        fixes.append(f"line_changes: 从 mode_info prAdditions/prDeletions 回填（平台权威）")
    if getattr(args, "reviewed_file_count", None) is None and isinstance(info.get("fileCount"), int):
        args.reviewed_file_count = info["fileCount"]
        fixes.append(f"reviewed_file_count: 从 mode_info fileCount 回填（覆盖口径 {info['fileCount']}）")
    if not getattr(args, "reviewed_line_changes", "") and isinstance(info.get("reviewedAddedLines"), int) \
            and isinstance(info.get("reviewedRemovedLines"), int):
        args.reviewed_line_changes = f"+{info['reviewedAddedLines']} -{info['reviewedRemovedLines']}"
        fixes.append(f"reviewed_line_changes: 从 mode_info reviewedAddedLines/removed 回填（覆盖口径）")
    args._pr_scale = {k: info.get(k) for k in ("prFileNum", "prAdditions", "prDeletions")}

    return fixes

def document_title(args):
    return f"{args.org}/{args.repo} PR #{args.pr_id} Code Review {args.run_id}：{args.pr_title}"


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
        if getattr(args, "_trigger_auto", False):
            # 数字账号触发 → 标注 AI 自动触发,不显示账号括号
            overview_rows.append(("触发人", f"{args.trigger_name}（{getattr(args, '_trigger_mis_raw', '')}，非人类触发者）"))
        else:
            overview_rows.append(("触发人", f"{args.trigger_name}（{args.trigger_mis}）"))
    # 触发溯源（不依赖 branch;两信息均空则不展示）
    _an, _sid = agent_and_session(args)
    if _an:
        overview_rows.append(("触发Agent", f"{_an}（[主页]({agent_overview_url(_an)})）"))
    if _sid and _an:
        overview_rows.append(("执行会话", f"[会话细则]({session_analysis_url(_an, _sid)})"))
    if args.branch:
        overview_rows.append(("分支", args.branch))
    if args.file_count is not None:
        overview_rows.append(("文件数", str(args.file_count)))
    if args.line_changes:
        overview_rows.append(("行数变化", args.line_changes))
    # 审查覆盖口径（与老口径分开呈现，标注语义防误读）
    _rfc = getattr(args, "reviewed_file_count", None)
    _rlc = getattr(args, "reviewed_line_changes", "")
    if _rfc is not None or _rlc:
        overview_rows.append(("审查覆盖", f"{_rfc if _rfc is not None else '-'} 个文件" + (f"，{_rlc}" if _rlc else "")))
    overview_rows.append(("审查范围", scope_label(args)))
    ff = getattr(args, "_mode_failed_files", None) or []
    if ff:
        overview_rows.append(("覆盖缺口", f"⚠️ {len(ff)} 个文件 diff 拉取失败，本次审查未覆盖，请人工补充检查（清单见 PR 评论末尾）"))
    overview_rows.append(("Skill版本", f"ai-quality-cr-agent {SKILL_VERSION}"))

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

    # 三、SDD 产物校验（从 sdd 文件透传，无则跳过；先去宏自带的重复标题避免双标题）
    sdd_md = read_text_file(args.sdd_file, "")
    if sdd_md:
        sdd_md = _strip_dup_section_title(sdd_md, ["SDD 产物校验"])
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

    # 自定义检查能力子节（Step 4-E ext-analyzer 检出的问题，独立成节不与内置混排）
    extan_section = assemble_extanalyzer_section(issues)
    if extan_section:
        parts.append(extan_section)

    # 五、总体评价（从 summary 文件拆分）
    parts.append("## 五、总体评价")
    if summary_parts["overall_eval"]:
        parts.append(summary_parts["overall_eval"])
    else:
        parts.append(f"Review 结论：{conclusion}")
    confirm_total = counts.get("confirm", 0)
    parts.append(f"**发现汇总**：P0={counts['p0']} | P1={counts['p1']} | P2={counts['p2']} | P3={counts['p3']}" + (f" | 待确认={confirm_total}" if confirm_total else "") + (f" | 外部专项={counts['ext']}（架构漂移）" if counts.get("ext") else ""))
    parts.append("")

    # 六、人工复审要点（从 summary 文件拆分）
    if summary_parts["manual_review"]:
        parts.append("## 六、人工复审要点")
        parts.append(summary_parts["manual_review"])
        parts.append("")

    # 七、与 CatPaw 对比（从 catpaw 文件透传，无则跳过）
    catpaw_md = read_text_file(args.catpaw_file, "")
    catpaw_md = _strip_dup_section_title(catpaw_md, ["与 CatPaw 对比", "上轮 CR 采纳情况"])
    if catpaw_md:
        parts.append("## 七、与 CatPaw 对比")
        parts.append(catpaw_md)
        parts.append("")

    # 末章：上轮 CR 采纳情况（从 adopt 文件透传，仅第二轮 CR）
    # 章号动态计算：七（CatPaw 对比）存在则为八，不存在则为七——避免跳号
    adopt_file = f"/tmp/cr_adopt_{args.pr_id}.md"
    adopt_md = read_text_file(adopt_file, "")
    adopt_md = _strip_dup_section_title(adopt_md, ["上轮 CR 采纳情况", "与 CatPaw 对比"])
    if adopt_md:
        parts.append(f"## {'八' if catpaw_md else '七'}、上轮 CR 采纳情况（仅第二轮 CR 追加）")
        parts.append(adopt_md)
        parts.append("")

    return "\n".join(parts)


# ─── 锚定校验 / 快照贯穿 / 兜底锚定 ────────────────────────────────────

_FULL_HASH_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _is_full_hash(v):
    """完整 40 位十六进制 hash 校验（短 hash 或非 hex 值
    不得参与「双端一致」判定——字符串相等不等于端点可信）。"""
    return bool(_FULL_HASH_RE.match(str(v or "").strip()))


def _append_global_fallback(global_text, title, entries):
    """兜底锚定：无法行内发送的问题降级追加到全局评论（不丢弃）。

    entries: [(meta, text), ...]，meta 为降级原因说明（含文件/行号）。
    插入位置：最后一个「---」分隔线之前——保证「📦 基准 commit 行始终是
    评论最后一行」的既定格式契约（下次增量 CR 的解析锚点，SKILL.md 固定格式）。
    """
    if not entries:
        return global_text
    section = ["", "---", "", f"## ⚠️ {title}", ""]
    for meta, text in entries:
        section.append(f"**（{meta}）**")
        section.append("")
        section.append((text or "").strip())
        section.append("")
    body = "\n".join(section)
    base = (global_text or "").rstrip()
    pos = base.rfind("\n---\n")
    if pos == -1:
        return base + "\n" + body
    return base[:pos] + body + base[pos:]


def _load_mode_info_dict(args):
    """读取本轮 mode_info（仅显式 --mode-info-file 或 PR 专属路径）。

    绑定要求：
    - 禁用共享默认路径 /tmp/cr_mode_info.json（多 PR 并行时跨轮串读旧文件）
    - 身份校验：mode_info 的 org/repo/prId 任一存在且与本轮不一致 → 整份拒绝，
      拒绝后不得回退任何其他路径（含共享路径与 PR 专属默认路径）
    - runId 校验：mode_info.runId 与本轮 --run-id 均存在且不一致 → 跨轮旧文件，
      整份拒绝（同 PR 不同轮次的 targetCommit/snapshot 均不可信）
    返回 (info, path, reject_reason)；info 为 {} 时 reject_reason 说明原因。
    """
    path = getattr(args, "mode_info_file", None) or \
        f"/tmp/cr_mode_info_{args.org}_{args.repo}_{args.pr_id}.json"
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
        if isinstance(info, dict):
            # 身份字段缺失同样拒绝（
            # org/repo/prId 全缺失时仍可能被接受为可信快照 → fail-open）
            for k, v in (("org", getattr(args, "org", "")),
                         ("repo", getattr(args, "repo", "")),
                         ("prId", getattr(args, "pr_id", None))):
                if info.get(k) is None:
                    log(f"⛔ mode_info 缺少身份字段 {k}，无绑定证据，拒绝该文件: {path}")
                    return {}, path, f"identity-missing({k})"
                if str(info[k]) != str(v):
                    log(f"⛔ mode_info 身份不匹配（{k}={info[k]!r} vs 本轮 {v!r}），"
                        f"拒绝该文件: {path}")
                    return {}, path, f"identity-mismatch({k})"
            mi_run = info.get("runId")
            cur_run = getattr(args, "run_id", None)
            if mi_run and cur_run and str(mi_run) != str(cur_run):
                log(f"⛔ mode_info.runId 不匹配（{mi_run!r} vs 本轮 {cur_run!r}），"
                    f"判定为跨轮旧文件，拒绝该文件: {path}")
                return {}, path, "runId-mismatch"
            # runId 必填且实际一致才可作为 trusted 快照依据；
            # 任一缺失即无绑定证据，按 unverified 处理（不冒充 trusted）。
            if not mi_run or not cur_run:
                log("⚠️ mode_info.runId 或本轮 --run-id 缺失，快照无 runId 绑定，"
                    "按不可信处理（走重拉/全局兜底）")
                return {}, path, "runId-missing"
            return info, path, ""
        return {}, path, "not-a-dict"
    except Exception as e:
        return {}, path, f"unreadable({type(e).__name__})"


def _resolve_diff_snapshot(args):
    """定位本轮审查 diff 快照（信任分级，移除不安全回退）。

    信任分级（绑定要求：缺元数据/身份/SHA 一律不可靠，告警后走重拉/全局兜底）：
      trusted    mode_info 身份+runId 匹配 + diffSha256 校验通过（diffPath 或
                 --diff-file 显式恢复路径，两者都必须过同一把 SHA 锁）
      rejected   SHA 不匹配（跨轮旧文件/被覆盖）→ 显式告警拒绝，
                 不回退任何旧默认路径
      unverified mode_info 缺失/不可读/身份或 runId 不匹配/无 diffPath/
                 无 diffSha256 → 无绑定证据，不作为可信快照使用
                 （行号校验转「重拉当前 diff」通道）

    返回 (diff_text, note, trust)；diff_text 为空 = 无可信快照。
    身份/SHA 拒绝后禁止回退 PR 专属默认路径 /tmp/pr_diff_*.txt：
    该路径无身份/SHA 绑定，跨轮旧文件无法识别（拒绝后回退 = 违背绑定要求），
    已移除——拒绝即无快照，走重拉/全局兜底。
    """
    info, mi_path, reject = _load_mode_info_dict(args)
    if not info:
        log(f"⚠️ 锚定校验: mode_info 不可用（{reject}）: {mi_path}，无绑定快照")
        return "", f"mode_info 不可用（{reject}）", "unverified"
    want_sha = str(info.get("diffSha256") or "").strip()
    if not want_sha:
        log("⚠️ 锚定校验: mode_info 无 diffSha256（无法证明 diff 文件属于本轮），"
            "快照不可信，跳过快照校验（走重拉/全局兜底）")
        return "", "mode_info 无 diffSha256", "unverified"
    candidates = []
    if info.get("diffPath"):
        candidates.append(("mode_info.diffPath", str(info["diffPath"])))
    explicit = getattr(args, "diff_file", None)
    if explicit and str(explicit) not in [c[1] for c in candidates]:
        candidates.append(("--diff-file", str(explicit)))
    if not candidates:
        log("⚠️ 锚定校验: mode_info 无 diffPath 且未传 --diff-file，无快照可校验")
        return "", "无 diffPath/--diff-file", "unverified"
    sha_mismatch = False
    for cand_src, cand_path in candidates:
        try:
            if not os.path.isfile(cand_path):
                log(f"⚠️ 锚定校验: diff 快照文件不存在（{cand_src} {cand_path}）")
                continue
            with open(cand_path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            log(f"⚠️ 锚定校验: diff 快照读取失败（{cand_src} {cand_path}）: {e}")
            continue
        if not text:
            log(f"⚠️ 锚定校验: diff 快照为空（{cand_src} {cand_path}，增量空 diff 或损坏）")
            continue
        got = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if got.lower() != want_sha.lower():
            sha_mismatch = True
            log(f"⛔ 锚定校验: diff 快照 sha256 不匹配（{cand_src} {cand_path}），拒绝旧文件"
                f"（期望 {want_sha[:12]}… 实际 {got[:12]}…），不回退其他路径")
            continue
        return text, f"{cand_src} {cand_path}（sha256 已验证）", "trusted"
    trust = "rejected" if sha_mismatch else "unverified"
    return "", f"diff 快照校验未通过（{trust}）", trust


def apply_anchor_validation(args, issues):
    """行内评论锚定校验与重定位（发布前置强制项）。

    数据源（信任分级）：mode_info.diffPath / --diff-file 显式恢复路径，
    均须通过 mode_info 身份+runId+diffSha256 绑定校验；不可信快照不参与锚定
    （行号校验转由 plan_publish_anchors 的「重拉当前 diff」通道完成）。
    坐标系与发布端 comment-add 锚定同构。
    校验链：code 片段反查 → 行号一致 verified / 不一致 relocated（覆盖行号）
    / 无法定位且行号非法 invalid（发布侧降级全局评论，不静默丢弃）。
    内部异常 fail-open 不阻断发布（锚定校验故障 ≠ CR 失败）。
    """
    if _la_anchor_issues is None:
        log("⚠️ 锚定校验: line_anchor 模块不可用，明确降级（不 fail-open）")
        args._diff_snapshot = {"trust": "unverified", "note": "line_anchor 不可用"}
        # 模块缺失时所有行内候选显式标 global（不盲发行内，
        # 全部走全局兜底，内容不丢）；非候选保持无标记（不参与行内）。
        for it in issues:
            if not isinstance(it, dict):
                continue
            if _inline_severity(it) in ("P0", "P1") or (
                    it.get("severity") == "confirm"
                    and it.get("source") == "fe-ai-review"):
                it["_publishPlan"] = "global"
                it["_publishNote"] = "line_anchor 模块不可用，锚定校验未执行，降级全局"
        return issues
    diff_text, diff_note, diff_trust = _resolve_diff_snapshot(args)
    args._diff_snapshot = {"trust": diff_trust, "note": diff_note,
                           "text_len": len(diff_text)}
    if not diff_text:
        log(f"⚠️ 锚定校验: {diff_note}，无可信快照，一级锚定跳过（转重拉/全局兜底通道）")
    else:
        log(f"🧭 锚定校验: diff 快照 = {diff_note}（trust={diff_trust}）")
    try:
        issues = _la_anchor_issues(issues, diff_text)
    except Exception as exc:
        # 锚定引擎异常 → 显式降级全部行内候选（不 fail-open 泄漏行内）
        log(f"⛔ 锚定校验异常（{type(exc).__name__}），全部行内候选降级全局（内容不丢）")
        for it in issues:
            if not isinstance(it, dict):
                continue
            if _inline_severity(it) in ("P0", "P1") or (
                    it.get("severity") == "confirm"
                    and it.get("source") == "fe-ai-review"):
                it["_publishPlan"] = "global"
                it["_publishNote"] = f"锚定校验异常（{type(exc).__name__}），降级全局"
        return issues
    # 统计播报（不阻断）
    try:
        from collections import Counter
        stats = Counter((it.get("_anchor") or "unknown") for it in issues)
        log(f"🧭 锚定校验: {dict(stats) if stats else '无 issue'}")
        for it in issues:
            mark = it.get("_anchor")
            if mark == "relocated":
                log(f"  🔧 重定位 {it.get('file')} L{it.get('_anchorOrigLine')}→L{it.get('line')}"
                    f"（{it.get('_anchorNote', '')}）")
            elif mark == "invalid":
                log(f"  ⛔ 无法锚定 {it.get('file')} L{it.get('line')} → 降级全局评论"
                    f"（{it.get('_anchorNote', '')}）")
            elif mark == "nofile":
                log(f"  ⚠️ 文件不在 diff 快照 {it.get('file')}（{it.get('_anchorNote', '')}）")
    except Exception:
        pass
    return issues


# ─── 发布前锚定/快照统一计划（文档与全局正文生成前完成）────────────────

_LIVE_REFETCH_FILE_CAP = 30   # 重拉文件数安全阀（行内候选文件数上限，超出告警降级）
_LIVE_REFETCH_CONTEXT = 30    # 重拉 context：大于审查快照默认 3，救援 code 证据
                              # 落在 CONTEXT 区外导致的 kept（重拉定位救援）


def _query_current_range(pr_url, code_cli_py, timeout=60):
    """查询当前 pr-changes from/to 双端 hash。返回 (ok, from_hash, to_hash)。

    绑定要求：查询失败 ok=False，调用方不得按「一致」处理（无法确认 ≠ 一致）。
    注意：fromHash/toHash 是 pr-changes 的 diff 双端语义（merge-preview 基准），
    与 targetCommit/baseCommit（PR commit 链端点，CR 审查范围）是不同概念，
    禁止互相比较或互相回填（目标 hash 与快照 hash 不能混淆）。
    """
    try:
        r = subprocess.run(
            [sys.executable, code_cli_py, "pr-changes", "--url", pr_url],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return False, "", ""
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        if isinstance(data, dict) and data.get("error"):
            return False, "", ""
        f_, t_ = str(data.get("fromHash") or ""), str(data.get("toHash") or "")
        if not t_:
            return False, "", ""
        return True, f_, t_
    except Exception:
        return False, "", ""


def _fetch_file_diff(pr_url, code_cli_py, file_path,
                     context=_LIVE_REFETCH_CONTEXT, timeout=60):
    """重拉 PR 当前某文件 diff（大 context）。失败返回空串。

    code_cli 出错时 returncode=0 且 stdout 是 {"error":...} JSON，必须校验
    含 diff 头才算有效 diff，否则错误 JSON 会被当 diff 解析。
    """
    try:
        r = subprocess.run(
            [sys.executable, code_cli_py, "pr-diff", "--url", pr_url,
             "--file", file_path, "--context", str(context)],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and "+++ b/" in (r.stdout or ""):
            return r.stdout
    except Exception:
        pass
    return ""


def _fetch_drift_diff(args, pr_url, code_cli_py, file_path, plan, timeout=60):
    """拉取漂移 diff（snap_to → cur_to，某文件）供 L1 坐标迁移。

    方向与 get_pr_diff 增量口径一致：--from 新(cur_to) --to 旧(snap_to)，
    输出 hunk 的 source(旧坐标) → destination(新坐标) 即迁移方向。
    双端 hash 不完整（上游契约违规/短 hash）时返回空串（L1 跳过，
    仅重锚定 + 降档链，不产生假迁移）。失败安全：任何异常返回空串。
    """
    try:
        import subprocess as _sp
        exp = [str(plan.get("cur_to") or ""), str(plan.get("snap_to") or "")]
        if not all(h and len(h) == 40 for h in exp):
            return ""
        r = _sp.run(
            [sys.executable, code_cli_py, "compare-diff", "--url", pr_url,
             "--file", file_path, "--from", exp[0], "--to", exp[1],
             "--context", "0"],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and "@@" in (r.stdout or ""):
            return r.stdout
    except Exception:
        pass
    return ""


def _inline_severity(it):
    """行内候选级别（与 assemble_inline_comments 同口径）：
    转正 EXT 用原级；灰度 EXT 用 _origSeverity；其余用 severity。"""
    if it.get("source") == "step4e" and not _extan_is_promoted(it):
        return (it.get("_origSeverity") or "").upper()
    return (it.get("severity") or "").upper()


def _inline_candidates(issues):
    """行内评论候选：P0/P1（含 EXT 转正/灰度口径）+ confirm-FE（全量口径）。"""
    out = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        if _inline_severity(it) in ("P0", "P1"):
            out.append(it)
        elif it.get("severity") == "confirm" and it.get("source") == "fe-ai-review":
            out.append(it)
    return out


def _line_shape_ok(it):
    """行号形状合法性（assemble_inline_comments 同口径的最终闸）。"""
    line = it.get("line")
    lt = (it.get("lineType") or "ADDED").upper()
    return (isinstance(line, int) and not isinstance(line, bool) and line > 0
            and lt in ("ADDED", "REMOVED"))


def _publish_note_of(it, mark, plan, diff_trust):
    """拼装降级全局的可追踪原因（不将历史证据伪装成当前已证实）。"""
    bits = []
    anchor_note = it.get("_anchorNote") or ""
    if mark in ("invalid", "nofile"):
        bits.append(f"锚定校验未通过（{anchor_note or mark}）")
    elif mark == "kept":
        bits.append(f"行号合法但代码证据未确认（{anchor_note or '重拉后仍无法唯一锚定'}）")
    elif mark in ("skipped", "error", "disabled"):
        bits.append(f"锚定校验未执行/异常（{anchor_note or it.get('_liveNote') or mark}）")
    elif mark in ("verified", "relocated") and not it.get("_liveVerified"):
        # verified/relocated 但锚定依据不可信（快照未过绑定校验且重拉未成功）
        bits.append("锚定依据不可信（快照未通过绑定校验且重拉未成功）")
    if it.get("_liveNote"):
        bits.append(it["_liveNote"])
    if plan.get("consistent") is False:
        bits.append(f"PR 审查期间有更新（{plan.get('note', '')}）")
    elif not plan.get("hash_query_ok") and mark not in ("verified", "relocated"):
        bits.append("当前 hash 查询失败，无法确认快照仍有效")
    if not bits:
        bits.append(f"锚定标记 {mark}（trust={diff_trust}）")
    return "；".join(bits)


def plan_publish_anchors(args, issues):
    """发布前锚定与快照统一计划（学城文档/全局正文生成前完成）。

    绑定要求落地：
    1. 定位/快照计划先于文档与全局正文：同一视图（学城文档 / PR 行内评论 /
       全局评论 / cr_result）使用同一套最终行号；发送前的过晚漂移由 step7
       二次复核 + comment-add --expected-from/to 冻结比对兜底（两道闸门只能
       降低竞态窗口，不构成原子保证，不声称消除）
    2. 快照 from+to 双端校验（全量/增量同口径：均为审查时冻结的 pr-changes
       diff 基准双端）；查询失败 ≠ 一致
    3. 只有「可信快照 + 双端一致」或「当前实时 diff 重锚定」verified/relocated
       的条目才发行内；nofile/kept/skipped/error/disabled/invalid 一律不盲发
       行内，降级全局兜底并保留全部问题内容（_publishNote 可追踪）
    4. 目标 hash 与快照 hash 语义严格区分（不能混淆）：
       targetCommit/baseCommit = CR 审查范围（PR commit 链端点）
       snapshotFrom/ToHash = pr-changes diff 基准双端（merge-preview）
       两者来自不同 API，禁止互相比较或互相回填

    流程：
      P1 一级锚定：apply_anchor_validation 已跑（可信快照；不可信则全 skipped）
      P2 双端比对：pr-changes 当前 from/to vs mode_info snapshotFrom/To
         双端一致 → 快照仍有效，仅未 verified/relocated 条目重拉救援；
         任一端不一致 / 查询失败 / 无冻结值 → 全部候选重拉当前 diff 重锚定
      P3 重拉重锚定：pr-diff --context 30（大于审查快照 context 3），
         pop 旧标记后二次锚定，成功打 _liveVerified
      P4 终态标记：_publishPlan = "inline" / "global"（_publishNote 记录原因）

    结果挂 args._snapshot_plan（step7 发送前复核与 expected 冻结取值）。
    """
    snap = getattr(args, "_diff_snapshot", None) or {}
    diff_trust = snap.get("trust", "unverified")
    plan = {
        "diff_trust": diff_trust,
        "snap_from": "", "snap_to": "",   # mode_info 冻结的审查时双端 hash
        "cur_from": "", "cur_to": "",     # 计划时点读到的当前双端（查询失败为空）
        "hash_query_ok": False,
        "consistent": None,               # True/False/None(无法判定)
        "note": "", "inline_ok": 0, "global_fallback": 0,
    }
    args._snapshot_plan = plan

    candidates = _inline_candidates(issues)
    if not candidates:
        plan["note"] = "无行内候选，跳过快照/锚定计划"
        return plan

    info, _mi_path, _reject = _load_mode_info_dict(args)
    plan["snap_from"] = str(info.get("snapshotFromHash") or "")
    plan["snap_to"] = str(info.get("snapshotToHash") or "")

    pr_url = getattr(args, "pr_url", "")
    code_cli_py = getattr(args, "code_cli_py", None) or find_code_cli_py()

    # ── P2 双端比对（查询失败 ≠ 一致）──
    if code_cli_py:
        ok, cur_from, cur_to = _query_current_range(pr_url, code_cli_py)
        plan["hash_query_ok"] = ok
        plan["cur_from"], plan["cur_to"] = cur_from, cur_to
    else:
        plan["note"] = "code_cli 不可用，无法查询当前 hash"

    if plan["hash_query_ok"] and plan["snap_to"]:
        # 快照/当前 hash 必须为完整 40 位十六进制才可比对；
        # 短 hash、缺 from 端（本轮文件应为 get_pr_diff 全量产物，缺即畸形）
        # 一律按「无法判定」处理（全部候选重拉校验），不以字符串相等冒充一致
        hashes_ok = (_is_full_hash(plan["snap_to"]) and _is_full_hash(plan["cur_to"])
                     and _is_full_hash(plan["snap_from"])
                     and _is_full_hash(plan["cur_from"]))
        if not hashes_ok:
            plan["consistent"] = None
            plan["note"] = ("快照/当前 hash 非完整 40 位或 from 端缺失，"
                            "无法比对（全部候选重拉校验）")
        else:
            to_ok = plan["cur_to"].lower() == plan["snap_to"].lower()
            from_ok = plan["cur_from"].lower() == plan["snap_from"].lower()
            plan["consistent"] = to_ok and from_ok
            if plan["consistent"]:
                plan["note"] = "快照双端一致（to=%s, from=%s）" % (
                    plan["cur_to"][:8], plan["cur_from"][:8])
            else:
                drift = []
                if not to_ok:
                    drift.append("to %s→%s" % (plan["snap_to"][:8], plan["cur_to"][:8]))
                if not from_ok:
                    drift.append("from %s→%s" % (plan["snap_from"][:8], plan["cur_from"][:8]))
                plan["note"] = "快照双端不一致（%s），全部候选重拉当前 diff 重锚定" % "; ".join(drift)
    elif plan["hash_query_ok"]:
        plan["consistent"] = None
        if _reject:
            plan["note"] = ("mode_info 已拒绝（%s），无冻结 hash，无法比对"
                            "（全部候选重拉校验）" % _reject)
        else:
            plan["note"] = "mode_info 无 snapshotToHash，无法比对，按不可判定处理（全部候选重拉校验）"
    else:
        plan["consistent"] = None
        plan["note"] = (plan["note"] + "; " if plan["note"] else "") + \
            "当前 hash 查询失败（≠一致），全部候选重拉当前 diff 重锚定"

    # ── P3 重拉重锚定 ──
    if plan["consistent"] is True and diff_trust == "trusted":
        need_live = [it for it in candidates
                     if (it.get("_anchor") or "skipped") not in ("verified", "relocated")]
        why = "快照一致且可信，仅重拉未锚定条目（大 context 救援 kept/nofile）"
    else:
        # 不一致 / 查询失败 / 无法判定 / 一级快照不可信 → 全部候选重拉：
        # consistent 只说明 hash 未漂移，不说明一级锚定用过可信数据
        need_live = candidates
        why = plan["note"] if diff_trust == "trusted" else \
            "一级锚定快照不可信（%s），全部候选重拉当前 diff 重锚定" % diff_trust

    live_verified = 0
    if need_live:
        log("🧭 发布计划: %s；重拉 %d 条候选" % (why, len(need_live)))
        if code_cli_py and _la_anchor_issues is not None:
            files = sorted({(it.get("file") or "").strip() for it in need_live} - {""})
            capped = files[:_LIVE_REFETCH_FILE_CAP]
            if len(capped) < len(files):
                log("⚠️ 重拉文件数超安全阀（%d>%d），超出部分无法重拉校验，"
                    "按不可锚定降级全局" % (len(files), _LIVE_REFETCH_FILE_CAP))
            fresh = {}
            for fp in capped:
                fresh[fp] = _fetch_file_diff(pr_url, code_cli_py, fp)
            fetched = sum(1 for v in fresh.values() if v)
            log("🧭 重拉 %d 个文件 diff（成功 %d，context=%d）"
                % (len(capped), fetched, _LIVE_REFETCH_CONTEXT))
            if _la_resolve is not None:
                # 收拢入口: 漂移坐标迁移(L1) + T0 重锚定 + P0/P1 降档链(T2-T4)
                # 全部在 line_anchor.resolve_publish_anchors 内完成（行号漂移
                # 处理唯一实现点;漂移 diff 逐文件 compare-diff 拉取）
                for it in need_live:
                    for k in ("_anchor", "_anchorNote", "_anchorOrigLine"):
                        it.pop(k, None)
                for fp in capped:
                    group = [it for it in need_live
                             if (it.get("file") or "").strip() == fp]
                    if not group or not fresh.get(fp):
                        continue
                    drift_diff = _fetch_drift_diff(args, pr_url, code_cli_py, fp, plan) \
                        if (plan.get("consistent") is not True
                            and plan.get("snap_to") and plan.get("cur_to")) else None
                    try:
                        _la_resolve(group, fresh[fp], drift_diff)
                    except Exception:
                        _la_anchor_issues(group, fresh[fp])
                    live_verified += sum(
                        1 for it in group
                        if (it.get("_anchor") or "") in ("verified", "relocated"))
                for it in need_live:
                    fp = (it.get("file") or "").strip()
                    if not fresh.get(fp):
                        it["_anchor"] = "skipped"
                        it["_anchorNote"] = "当前文件 diff 重拉失败，无法校验行号"
                    elif (it.get("_anchor") or "") in ("verified", "relocated"):
                        it["_liveVerified"] = True
            else:
                for it in need_live:
                    fp = (it.get("file") or "").strip()
                    diff_text = fresh.get(fp, "")
                    # 清除首轮标记（幂等要求：二次校验前 pop 旧标记，防陈旧 note 混入）
                    for k in ("_anchor", "_anchorNote", "_anchorOrigLine"):
                        it.pop(k, None)
                    if diff_text:
                        _la_anchor_issues([it], diff_text)
                        if (it.get("_anchor") or "") in ("verified", "relocated"):
                            it["_liveVerified"] = True
                            live_verified += 1
                    else:
                        it["_anchor"] = "skipped"
                        it["_anchorNote"] = "当前文件 diff 重拉失败，无法校验行号"  
        else:
            reason = "line_anchor 不可用" if _la_anchor_issues is None else "code_cli 不可用"
            for it in need_live:
                it["_liveNote"] = "重拉通道不可用（%s），无法校验行号" % reason
            log("⚠️ 发布计划: 重拉通道不可用（%s），未锚定条目全部降级全局" % reason)
    # 重拉通道异常/不可用时，未锚定条目不得以旧 verified/relocated
    # 标记盲发行内——P4 终态判定已要求 basis_ok（_liveVerified 或
    # consistent+trusted），此处无需额外改动，保持门禁语义。

    # ── P4 终态标记 ──
    for it in candidates:
        mark = it.get("_anchor") or "skipped"
        _sev = _inline_severity(it)
        if mark in ("verified", "relocated"):
            basis_ok = bool(it.get("_liveVerified")) or \
                (plan["consistent"] is True and diff_trust == "trusted")
            if basis_ok or (_sev in ("P0", "P1")
                            and it.get("_anchorPrecision")):
                # P0/P1: 经降档链(near/approximate/file-level/mapped)产出的
                # relocated 同样发行内（行号漂移处理统一收拢于 line_anchor，
                # 此处不再弃权；精度档记录在 _anchorPrecision 供追溯与播报）
                it["_publishPlan"] = "inline"
                plan["inline_ok"] += 1
                continue
        if _sev in ("P0", "P1") and _line_shape_ok(it):
            # 极端兜底: P0/P1 不落 global——重拉通道整体不可用/锚定 invalid
            # 时，只要行号形状合法（int>0 + lineType 合法）就以现有最优行号
            # 发行内；invalid 且行号形状非法（如 None/0）的极端情况由
            # line_anchor 降档链保证不出现，此处仅为防御性最终闸。
            it["_publishPlan"] = "inline"
            it.setdefault("_publishNote",
                          "P0/P1 强制行内（锚定降级，采用最优可用锚点：%s）" % (mark or "unknown"))
            plan["inline_ok"] += 1
            continue
        it["_publishPlan"] = "global"
        plan["global_fallback"] += 1
        it["_publishNote"] = _publish_note_of(it, mark, plan, diff_trust)

    log("🧭 发布计划终态: 行内 %d 条 / 全局兜底 %d 条（重拉锚定成功 %d）"
        % (plan["inline_ok"], plan["global_fallback"], live_verified))
    return plan


def _verify_late_drift(args, pr_url, code_cli_py, inline_comments):
    """发送前轻量复核（降低竞态窗口，不声称消除）。

    比对计划时冻结的 from/to（plan.cur_*，查询失败回退 mode_info snapshot*）
    与当前 pr-changes 双端：
    - 一致 → (True, note, []) 按计划行号发送
    - 不一致 / 查询失败（≠一致）→ 逐文件重拉当前 diff 重锚定：
        重锚定 verified/relocated 且行号与计划一致 → 保留行内（位置当前有效）
        行号漂移 / 无法锚定 / 拉取失败 → degraded（降级全局，明确标识过晚
        漂移；不静默改行号——正文与学城文档已按计划行号生成，改锚点会造成
        视图错位，且 issue.line 恢复计划值防 cr_result 与文档不一致）
    同时把最终冻结值挂 args._send_expected，供 comment-add
    --expected-from/--expected-to 发送前比对（第三道闸门）。
    """
    plan = getattr(args, "_snapshot_plan", None) or {}
    exp_from = plan.get("cur_from") or plan.get("snap_from") or ""
    exp_to = plan.get("cur_to") or plan.get("snap_to") or ""
    ok, cur_from, cur_to = _query_current_range(pr_url, code_cli_py)
    if ok:
        args._send_expected = (cur_from, cur_to)
    else:
        args._send_expected = (exp_from or None, exp_to or None)
    # hash 必须为完整 40 位才可判「一致」；短 hash/缺 from 端
    # 一律按不可判定进入逐文件复核（不以字符串相等冒充一致）。
    # from 端缺失同样不可判一致（SKILL.md 契约「fromHash 和 toHash 对照，
    # 无法确认不可视为一致」——缺 from 即无法确认）
    if ok and _is_full_hash(exp_to) and _is_full_hash(cur_to) \
            and cur_to.lower() == exp_to.lower() \
            and _is_full_hash(exp_from) and _is_full_hash(cur_from) \
            and cur_from.lower() == exp_from.lower():
        return True, "发送前复核双端一致（to=%s）" % cur_to[:8], []

    if not ok:
        base_note = "发送前 hash 查询失败（≠一致）"
    elif not exp_to:
        base_note = "无冻结 hash 可比对（按不可判定处理）"
    else:
        drift = ["to %s→%s" % (exp_to[:8], cur_to[:8])]
        if exp_from and cur_from.lower() != exp_from.lower():
            drift.append("from %s→%s" % (exp_from[:8], cur_from[:8]))
        base_note = "发送前检测到过晚漂移（%s）" % "; ".join(drift)
    note = base_note + "，逐文件重拉当前 diff 复核"
    log("📸 %s" % note)

    degraded = []
    if _la_anchor_issues is None:
        # 模块缺失分支同样标记 _snapshot=degrade（
        # degraded 列表不标记，step7 过滤不生效 → 同一问题既全局兜底又发行内）
        for c in inline_comments:
            _iss_m = c.get("_issue")
            if (isinstance(_iss_m, dict)
                    and _inline_severity(_iss_m) in ("P0", "P1")
                    and _line_shape_ok(_iss_m)):
                # P0/P1 强制行内：无法复核但锚点形状合法，按现有锚点行内
                c["_snapshot"] = "degraded-inline"
                c["_snapshotNote"] = ("%s且 line_anchor 不可用，按现有锚点发行内（未复核）"
                                      % base_note)
                _iss_m.setdefault("_publishNote", c["_snapshotNote"])
                _iss_m["positionStatus"] = "unconfirmed"
                continue
            c["_snapshot"] = "degrade"
            c["_snapshotNote"] = ("%s且 line_anchor 不可用，无法复核 `%s` L%s"
                                  % (base_note, c.get("file_keyword", ""),
                                     c.get("line", "?")))
            degraded.append((c["_snapshotNote"], c.get("text", "")))
        return False, note, degraded
    fresh = {}
    for c in inline_comments:
        issue = c.get("_issue")
        text = c.get("text", "") or ""
        fp = (c.get("file_keyword")
              or (issue.get("file") if isinstance(issue, dict) else "") or "").strip()
        planned_line = c.get("line")
        if not isinstance(issue, dict):
            # 缺 _issue 引用分支同样标记 degrade（理由同上）
            c["_snapshot"] = "degrade"
            c["_snapshotNote"] = ("%s，评论缺少 issue 引用无法复核 `%s` L%s"
                                  % (base_note, fp, planned_line))
            degraded.append((c["_snapshotNote"], text))
            continue
        if fp not in fresh:
            fresh[fp] = _fetch_file_diff(pr_url, code_cli_py, fp)
        diff_text = fresh[fp]
        for k in ("_anchor", "_anchorNote", "_anchorOrigLine"):
            issue.pop(k, None)
        if not diff_text:
            if _inline_severity(issue) in ("P0", "P1") and _line_shape_ok(issue):
                # P0/P1 强制行内：diff 拉取失败按现有最优锚点发行内，
                # 标注未确认（不盲信快照也不降级丢可见性）
                c["_snapshot"] = "degraded-inline"
                c["_snapshotNote"] = "%s且当前 diff 拉取失败，按现有锚点发行内（未复核）" % base_note
                issue.setdefault("_publishNote", c["_snapshotNote"])
                issue["positionStatus"] = "unconfirmed"
                continue
            c["_snapshot"] = "degrade"
            c["_snapshotNote"] = "%s且当前 diff 拉取失败，无法校验行号" % base_note
            # 拉取失败降级同样同步结构化最终状态（同下方漂移分支口径）
            issue["_publishPlan"] = "global"
            issue["_publishNote"] = c["_snapshotNote"]
            degraded.append(("%s：`%s` L%s" % (c["_snapshotNote"], fp, planned_line), text))
            continue
        _la_anchor_issues([issue], diff_text)
        mark = issue.get("_anchor") or "skipped"
        new_line = issue.get("line", planned_line)
        if mark in ("verified", "relocated") and new_line == planned_line:
            c["_snapshot"] = "kept"   # 计划行号当前仍有效（复核通过）
            continue
        _sev_late = _inline_severity(issue)
        if _sev_late in ("P0", "P1"):
            # P0/P1 强制行内（红线 20）：发送前漂移不降级全局——
            # verified/relocated 迁移到新坐标继续行内；invalid 等极端
            # 场景行号形状合法即按现有最优锚点发行内（与 P4 兜底同口径）。
            # 全文只在主列表出现一次（_is_inline_publishable 去重）。
            if mark in ("verified", "relocated"):
                c["line"] = new_line
                issue["line"] = new_line
                issue["_liveVerified"] = True
                c["_snapshot"] = "drift-migrated"
                c["_snapshotNote"] = ("%s，已迁移至新坐标 L%s（重锚定 %s）"
                                      % (base_note, new_line, mark))
                # 正文中的原行号引用同步更新（审计 11-24：
                # 发送锚点 L700 而正文仍写 L691——视图错位）。
                # 仅替换明确的 L{n} / 行 {n} 形态；找不到引用不改（保守）。
                # 前置条件：本分支 mark 已是 verified/relocated（T0 内容
                # 验证通过）——SKILL 红线 20-③ 唯一允许的行号替换路径，
                # 引擎受控修正，非人工改号。
                if isinstance(planned_line, int) and planned_line != new_line:
                    # 三种形态边界感知替换（数字后不能再跟数字，
                    # 防 L691 误伤 L6912→L7002 的子串碰撞）：
                    # L691→L700、行 691→行 700、第691行→第700行
                    _body = c.get("text") or ""
                    _p = str(planned_line)
                    _n = str(new_line)
                    _body = re.sub(r"(?<!\d)L%d(?!\d)" % planned_line,
                                   "L" + _n, _body)
                    _body = re.sub(r"(?<!\d)行 %d(?!\d)" % planned_line,
                                   "行 " + _n, _body)
                    _body = re.sub(r"(?<!\d)第%d行" % planned_line,
                                   "第" + _n + "行", _body)
                    c["text"] = _body
                if "📍 行号锚定" not in (c.get("text") or ""):
                    c["text"] = (c.get("text") or "") + \
                        "\n📍 行号锚定：发送前代码更新，已迁移至新位置（精度：迁移）"
                issue.setdefault("_publishNote", "发送前漂移已迁移 L%s" % new_line)
                if issue.get("positionStatus") != "confirmed":
                    issue["positionStatus"] = "unconfirmed"
                log("📍 P0/P1 %s:%s 晚漂移迁移 → L%s（保持行内）"
                    % (fp, planned_line, new_line))
                continue
            if _line_shape_ok(issue):
                c["_snapshot"] = "degraded-inline"
                c["_snapshotNote"] = ("%s，%s——按最优可用锚点发行内（P0/P1 不降级全局）"
                                      % (base_note, issue.get("_anchorNote") or mark))
                issue.setdefault("_publishNote", c["_snapshotNote"])
                issue["positionStatus"] = "unconfirmed"
                continue
            # 行号形状非法（理论不可达，防御）：落入通用降级
        if mark in ("verified", "relocated") and new_line != planned_line:
            # 走到这里 new_line 必 != planned_line（一致情形已 kept 返回）
            why = ("代码证据定位至 L%s，与计划行号 L%s 不一致，"
                   "为保持与报告正文一致不改动锚点" % (new_line, planned_line))
        else:
            why = "无法锚定（%s）" % (issue.get("_anchorNote") or mark)
        c["_snapshot"] = "degrade"
        c["_snapshotNote"] = "%s，%s" % (base_note, why)
        issue["_publishPlan"] = "global"
        issue["_publishNote"] = c["_snapshotNote"]
        if issue.get("line") != planned_line:
            issue["line"] = planned_line
        degraded.append(("%s：`%s` L%s" % (c["_snapshotNote"], fp, planned_line), text))
    return False, note, degraded


def _send_inline_with_expected(client, pr_url, file_keyword, line, line_type, text,
                               exp_from, exp_to):
    """expected 固定 commitRange 集成（防御式，不硬依赖新接口）。

    cr_comment.send_inline 新签名支持 expected_from/expected_to（透传
    comment-add --expected-from/--expected-to，发送前与当前值比对，不一致
    显式拒绝发送）。
    不用 try/except TypeError 兜底重发——若 TypeError 来自
    send_inline 函数体内部（而非参数不匹配），会触发第二次 POST，可能产生
    重复评论且丢失冻结比对。改为调用前用 inspect.signature 预检签名，
    不做异常驱动的重试。
    expected 比对失败抛 CommentError → 由调用方既有兜底降级全局（不丢弃）。
    """
    if exp_from or exp_to:
        try:
            sig_params = inspect.signature(client.send_inline).parameters
            has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD
                             for p in sig_params.values())
            supports_from = has_var_kw or "expected_from" in sig_params
            supports_to = has_var_kw or "expected_to" in sig_params
        except (TypeError, ValueError):
            supports_from = supports_to = False
        # 仅透传对端支持的参数：单侧签名（如仅 expected_to）传双侧会
        # TypeError 中断 step7（已发行内评论保留、全局评论不发、无兜底）
        kwargs = {}
        if exp_from and supports_from:
            kwargs["expected_from"] = exp_from
        if exp_to and supports_to:
            kwargs["expected_to"] = exp_to
        if kwargs:
            return client.send_inline(
                pr_url, file_keyword=file_keyword, line=line,
                line_type=line_type, text=text, **kwargs)
        log("⚠️ cr_comment.send_inline 不支持 expected_from/to，"
            "无冻结发送（竞态防护退化为发送前预检）")
    return client.send_inline(
        pr_url, file_keyword=file_keyword, line=line,
        line_type=line_type, text=text)


def _fallback_issue_text(it, sev, idx, emoji, rule_id, reason):
    """全局兜底条目：完整问题内容 + 可追踪降级原因（不丢内容）。

    与行内评论同字段口径（检出原因/风险/修复建议/规则溯源全保留），
    保证降级条目脱离行内上下文后仍自含全部问题信息。
    """
    anomaly = it.get("anomalyType", "") or ""
    summary = it.get("summary", "") or ""
    title = (f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {anomaly} — {summary}"
             if anomaly else f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {summary}")
    rule_name = it.get("ruleName", "") or ""
    rule_file = it.get("ruleFile", "") or ""
    trace = f"\n（规则：{rule_name}，来源：{rule_file}）" if (rule_name or rule_file) else ""
    return (
        f"{title}\n\n"
        f"**文件**：`{it.get('file', '')}` L{it.get('line', '')}\n\n"
        f"**降级原因**：{reason}\n\n"
        f"**检出原因**：{it.get('description', '') or ''}\n\n"
        f"**风险**：{it.get('risk', '') or ''}\n\n"
        f"**修复建议**：\n{it.get('suggestion', '') or ''}"
        f"{trace}"
    )


def _is_inline_publishable(it):
    """行内发布判定的单一事实源。

    assemble_inline_comments 的收口三条件（lineType 枚举 / 行号形状 /
    发布计划 inline）收敛为一个函数；assemble_global_comment 据此决定
    主列表是否展开详情——两处共用同一口径，物理上不会再分叉。
    """
    line = it.get("line")
    line_shape_ok = isinstance(line, int) and not isinstance(line, bool) and line > 0
    line_type = (it.get("lineType") or "ADDED").upper()
    return (line_type in ("ADDED", "REMOVED")
            and line_shape_ok
            and it.get("_publishPlan") == "inline")


def _rewrite_inline_claim(global_text, annotated, total):
    """发送后按实际结果改写全局评论头部的行内标注声明。

    头部声明发送前按 _publishPlan 生成，
    行内发送失败或晚漂移降级后头部声明与事实不符。step7 在行内发送完成后
    调用本函数，按「实际已标注（本轮发送 + 历史去重跳过）/ 应标注总数」改写。
    annotated/total 均为 0 或缺失信息时保持原文不改写。
    """
    if not global_text or not total:
        return global_text
    if annotated >= total:
        claim = "> P0/P1 问题均已作为行内评论标注（本轮发送或历史轮次已存在），下方为全量发现。"
    elif annotated > 0:
        claim = (f"> P0/P1 问题中 {annotated}/{total} 条已作为行内评论标注（本轮发送或历史轮次已存在）；"
                 "其余条目行号未能在当前代码上确认或发送失败，已兜底至本评论展示。")
    else:
        claim = "> P0/P1 问题行号均未能在当前代码上确认锚定，未发行内评论，完整内容在本评论展示。"
    lines = global_text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("> P0/P1") or ln.startswith("> 本轮无 P0/P1"):
            lines[i] = claim
            return "\n".join(lines)
    return global_text


def assemble_inline_comments(issues, cr_mode="full"):
    """拼装 P0/P1 行内评论；全量最多追加一条普通待确认问题，增量不追加。

    发布计划门禁：只有 _publishPlan=inline（plan_publish_anchors 判定
    锚定依据可信：可信快照+双端一致，或当前实时 diff 重锚定）才发行内；
    nofile/kept/skipped/error/disabled/invalid 及行号形状非法一律不盲发行内，
    降级文本（完整问题内容）进 fallbacks 附到全局评论，保证问题不在 PR 上
    静默消失。返回 (inline, fallbacks)。"""
    inline = []
    inline_fallbacks = []  # 无法行内锚定的 P0/P1 降级文本
    # 组内编号计数器
    sev_counters = {"P0": 0, "P1": 0}
    for it in issues:
        # 转正: 转正名单 analyzer(如 arch-pr-verifier)的 EXT findings 按
        # 原级(severity 即原级,loader 不再降 confirm)走正常 P0/P1 行内评论;
        # 灰度 analyzer 维持「待人工判定」展示逻辑(原级行内+待人工判定尾注)。
        is_ext_promoted = _extan_is_promoted(it)
        is_ext_grey = it.get("source") == "step4e" and not is_ext_promoted
        if is_ext_grey:
            # 灰度 EXT: 沿用原级(_origSeverity)生成行内评论(仅限架构漂移等已注册标题的 analyzer)
            is_ext = it.get("source") == "step4e" and "架构漂移" in (
                EXTAN_SECTION_TITLES.get((it.get("ruleId", "") or "").split(":")[1] if len((it.get("ruleId", "") or "").split(":")) > 2 else "", ""))
            sev = (it.get("_origSeverity") or "").upper()
        else:
            is_ext = False
            sev = it["severity"]
        if sev not in ("P0", "P1"):
            continue
        sev_counters[sev] += 1
        idx = sev_counters[sev]
        emoji = SEVERITY_EMOJI[sev]
        rule_id = it.get("ruleId", "") or "无规则标注"
        summary = it.get("summary", "") or ""
        desc = it.get("description", "") or ""
        risk = it.get("risk", "") or ""
        sug = it.get("suggestion", "") or ""
        file_ = it.get("file", "") or ""
        line = it.get("line", 0)
        line_type = (it.get("lineType") or "ADDED").upper()
        # 发布计划门禁（前置，合并 invalid/lineType 两处检查）：
        # 只有 plan=inline（锚定依据可信）且行号形状合法才发行内；
        # nofile/kept/skipped/error/disabled/invalid、行号形状非法、
        # lineType 非法（Bitbucket segment 枚举仅支持 ADDED/REMOVED，MODIFIED
        # 等非法值会被服务端拒绝）一律不盲发行内 → 全局兜底（保留全部内容）
        plan_ok = it.get("_publishPlan") == "inline"
        line_shape_ok = isinstance(line, int) and not isinstance(line, bool) and line > 0
        publishable = _is_inline_publishable(it)
        if not publishable:
            reasons = []
            if not plan_ok:
                reasons.append(it.get("_publishNote")
                               or "未经锚定计划校验（_publishPlan 缺失，不盲发行内）")
            if not line_shape_ok:
                reasons.append(f"行号形状非法（line={line!r}）")
            if line_type not in ("ADDED", "REMOVED"):
                reasons.append(f"lineType={line_type} 非法（仅支持 ADDED/REMOVED）")
            log(f"⚠️ 降级全局 {file_}:{line}：{'；'.join(reasons)}")
            inline_fallbacks.append(
                _fallback_issue_text(it, sev, idx, emoji, rule_id, "；".join(reasons)))
            continue

        # 可追溯信息（step4b 来源附在末尾，不暴露 step 编号）
        trace = ""
        rule_name = it.get("ruleName", "") or ""
        rule_file = it.get("ruleFile", "") or ""
        if rule_name or rule_file:
            trace = f"\n（规则：{rule_name}，来源：{rule_file}）"

        anomaly = it.get("anomalyType", "") or ""
        title = f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {anomaly} — {summary}" if anomaly else f"{emoji} [{sev}-{idx:02d}] [{rule_id}] {summary}"
        # 尾注三分支: 转正 EXT(计入统计+参与结论)、灰度 EXT(原级展示不计入)、内置(计入准确率)。
        # 灰度分支: EXTAN_SECTION_TITLES 注册标题且未转正的 analyzer(当前为空集,
        # 转正名单全覆盖了已注册标题;未来新增注册标题未转正时自动命中此分支)
        if is_ext_promoted:
            footer = f"🔍 外部专项审查（架构漂移）：该检出未经主流程二次复审，请结合业务实际判断。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复"
        elif is_ext_grey and is_ext:
            footer = f"🔍 外部专项审查（待人工判定）：检出原级别为 {sev}，未计入问题统计与 Review 结论，请人工确认。"
        elif is_ext_grey:
            # 无注册标题的灰度 analyzer: 文档展示为主,行内不计准确率(EXT 未纳入准确率统计)
            footer = f"🔍 外部专项审查（待人工判定）：检出原级别为 {sev}，未计入问题统计与 Review 结论，请人工确认。"
        else:
            footer = f"💬 无回复默认检出正确，计入准确率。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复"
        text = (
            f"{title}\n\n"
            f"**文件**：`{file_}` L{line}\n\n"
            f"**检出原因**：{desc}\n\n"
            f"**风险**：{risk}\n\n"
            f"**修复建议**：\n{sug}"
            f"{trace}\n\n"
            f"---\n"
            f"{footer}"
        )
        # 锚定精度标注（行号漂移处理收拢后，P0/P1 降档链产出的近似锚点
        # 需在评论中透明标注，不伪装成精确锚点）
        _prec = it.get("_anchorPrecision") or ""
        if _prec and _prec != "exact":
            _prec_label = {"mapped": "坐标迁移已验证", "near": "就近（片段命中区间首行）",
                           "approximate": "近似（片段首行唯一命中）",
                           "file-level": "文件级（问题行在更新后不可定位）"}.get(_prec, _prec)
            text += f"\n📍 行号锚定：{_prec_label}"

        inline.append({
            "file_keyword": file_,
            "line": int(line) if line else 0,
            "line_type": line_type,
            "text": text,
            "_issue": it,  # 内部字段：来源 issue 引用，发送成功后回写 commentId；归档时剔除
        })
    if cr_mode != "full":
        return inline, inline_fallbacks

    # 优先复审前风险级别；同级/无原级沿用主审按业务影响与核实价值排好的顺序。
    # 保留原 Q 编号，与报告和全局摘要对应；外部专项仍沿用灰度策略。
    # 【2026-11-03】confirm 行内评论限额只发给 FE 来源（fe-ai-review），
    # 后端/复审存疑等来源的 confirm 项不占行内限额，仍完整保留在文档与全局摘要。
    questions = [it for it in issues if it["severity"] == "confirm" and it.get("source") == "fe-ai-review"]
    ranked_questions = sorted(enumerate(questions, 1), key=lambda pair: SEVERITY_ORDER.get(
        pair[1].get("preReviewSeverity"), SEVERITY_ORDER["confirm"]))
    for idx, it in ranked_questions:
        file_ = (it.get("file") or "").strip()
        line = it.get("line")
        line_type = (it.get("lineType") or "").upper()
        if not file_ or not isinstance(line, int) or isinstance(line, bool) or line <= 0 or line_type not in ("ADDED", "REMOVED"):
            continue
        # 发布计划门禁：confirm 仅 plan=inline（锚定依据可信）才占行内名额
        if it.get("_publishPlan") != "inline":
            log(f"⚠️ confirm 未通过锚定计划 {file_}:{line}（{it.get('_publishNote', '')}），不占行内名额")
            continue
        if not all((it.get(key) or "").strip() for key in ("confirm_reason", "possible_risk", "confirm_suggestion")):
            continue
        inline.append({
            "file_keyword": file_, "line": line, "line_type": line_type,
            "text": _issue_doc_block(it, idx),
            "_issue": it,
        })
        break
    return inline, inline_fallbacks


def assemble_global_comment(args, issues, counts, conclusion, km_url, inline_fallbacks=None):
    """从 P0~P3 全量 issue 拼装 PR 全局评论。"""
    # 去除固定「P0/P1 均已行内」声明，按实际发布计划动态表述；
    # 行号未确认的问题如实标注（不将降级条目伪装成已行内标注）。
    _p0p1 = [it for it in issues if isinstance(it, dict)
             and _inline_severity(it) in ("P0", "P1")]
    _p0p1_inline = [it for it in _p0p1 if it.get("_publishPlan") == "inline"]
    if _p0p1 and len(_p0p1_inline) == len(_p0p1):
        _inline_claim = "> P0/P1 问题同时已作为行内评论标注在对应代码行，下方为全量发现。"
    elif _p0p1_inline:
        _inline_claim = (f"> P0/P1 问题中 {len(_p0p1_inline)}/{len(_p0p1)} 条已作为行内评论"
                         "标注在对应代码行；其余条目行号未能在当前代码上确认，已兜底至本评论展示。")
    elif _p0p1:
        _inline_claim = "> P0/P1 问题行号均未能在当前代码上确认锚定，未发行内评论，完整内容在本评论展示。"
    else:
        _inline_claim = "> 本轮无 P0/P1 问题，下方为全量发现。"
    # 该提示行仅在确实存在 unconfirmed 条目时输出（
    # 输出，全部锚定确认时与事实不符）
    _has_unconfirmed = any(
        isinstance(it, dict) and _position_status_of(it) == "unconfirmed"
        for it in issues)
    lines = [
        "## 🤖 AI Code Review 结果",
        "",
        "> 本 Review 由 AI-CR（AI 代码审查）自动生成，仅供参考，请结合业务实际情况判断。",
        _inline_claim,
    ]
    if _has_unconfirmed:
        lines.append("> ⚠️ 行号未确认的问题已如实标注（未在当前代码上验证锚定），内容完整保留。")
    lines += [
        "",
        f"**发现汇总：** P0={counts['p0']} | P1={counts['p1']} | P2={counts['p2']} | P3={counts['p3']}" + (f" | 待确认={counts['confirm']}" if counts.get('confirm') else "") + (f" | 外部专项={counts['ext']}（架构漂移）" if counts.get('ext') else ""),
        "",
        f"**Review 结论：** {conclusion}",
        "",
        f"**审查范围：** {scope_label(args)}",
        "",
        "---",
    ]

    # 触发Agent + 执行会话（1024 宿主 env 嗅探；空串不展示不阻断）
    _an_g, _sid_g = agent_and_session(args)
    if _an_g:
        info = [f"**🤖 触发Agent：** [{_an_g}]({agent_overview_url(_an_g)})"]
        if _sid_g:
            info.append(f"**💬 执行会话：** [会话细则]({session_analysis_url(_an_g, _sid_g)})")
        _sep = lines.index("---")
        lines[_sep:_sep] = info + [""]

    for sev in ("P0", "P1", "P2", "P3"):
        group = [it for it in issues if it["severity"] == sev]
        if not group:
            continue
        lines.append("")
        lines.append(f"### {SEVERITY_TITLE[sev]}")
        lines.append("")
        for i, it in enumerate(group, 1):
            rule_id = it.get("ruleId", "") or "无规则标注"
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
                if not _is_inline_publishable(it):
                    # 未发行内（锚定失败/行号形状非法/计划未过）：详情全文
                    # 统一由末尾「无法行内锚定的问题」章节展示一次，此处
                    # 只留索引行——修复同一条 P0/P1 主列表+fallback 重复
                    # 展示两遍的渲染 bug（单一事实源:_is_inline_publishable）
                    lines.append("↩ 详情见下方「无法行内锚定的问题」章节（行内锚定未通过，内容完整保留）")
                    lines.append("💬 无回复默认检出正确，计入准确率。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复")
                    lines.append("")
                    continue
                _pos_note = it.get("_publishNote") or it.get("_anchorNote")
                if _pos_note and _position_status_of(it) == "unconfirmed":
                    lines.append(f"⚠️ 行号未确认（{_pos_note}）")
                lines.append(f"检出原因：{desc}")
                lines.append(f"风险：{risk}")
                lines.append(f"修复建议：{sug}")
            else:
                # P2/P3 简洁格式（保持不变）
                lines.append(f"**{emoji} {sev}-{i:02d}: [{rule_id}] {summary}**")
                lines.append(f"命中规则：`{rule_id}`")
                lines.append(f"文件: `{file_}:{line}`")
                _pos_note = it.get("_publishNote") or it.get("_anchorNote")
                if _pos_note and _position_status_of(it) == "unconfirmed":
                    lines.append(f"⚠️ 行号未确认（{_pos_note}）")
                lines.append(desc)
            lines.append("💬 无回复默认检出正确，计入准确率。有异议请回复：❌误报 / ⚠️规则太严 / ⏭暂不修复")
            lines.append("")

    questions = [it for it in issues if it["severity"] == "confirm" and it.get("source") != "step4e"]
    if questions:
        inline_policy = (
            "全量审查仅允许风险最高且可定位的条目发送最多 1 条行内评论"
            if getattr(args, "cr_mode", "full") == "full"
            else "本轮不发送待确认行内评论"
        )
        lines.extend(["", "### 🔎 待人工确认", "", f"以下事项需人工核实，不计入 P0–P3；{inline_policy}，完整信息见报告。", ""])
        for idx, it in enumerate(questions, 1):
            lines.append(f"- **[Q-{idx:02d}] {it.get('summary', '')}**（`{it.get('file', '')}:{it.get('line', '')}`）：{it.get('confirm_suggestion', '')}")
        lines.append("")

    # 无法行内锚定的降级文本（锚定计划未通过：nofile/kept/skipped/
    # error/disabled/invalid、行号形状/lineType 非法），不静默丢弃；
    # 条目含完整问题内容与可追踪降级原因（_publishNote）。
    # 覆盖缺口清单同理——两者都放在「---」分隔线之前，
    # 保证末尾基准 commit 行始终是评论最后一行（下次增量 CR 的解析锚点）
    if inline_fallbacks:
        lines.append("")
        lines.append("### ⚠️ 无法行内锚定的问题（已兜底全局，内容完整保留）")
        lines.append("")
        lines.append("以下问题未通过发布前锚定校验（行号无法在当前代码上确认），"
                     "为避免误导未发行内评论，完整内容在此展示：")
        lines.append("")
        lines.extend(inline_fallbacks)

    failed_files = getattr(args, "_mode_failed_files", None) or []
    if failed_files:
        lines.append("")
        lines.append(f"### ⚠️ 审查覆盖缺口：{len(failed_files)} 个文件 diff 拉取失败")
        lines.append("")
        lines.append("以下文件未能获取 diff，本次审查未覆盖，请人工补充检查：")
        for fp in failed_files[:20]:
            lines.append(f"- `{fp}`")
        if len(failed_files) > 20:
            lines.append(f"- ...等共 {len(failed_files)} 个")

    lines.append("---")
    lines.append("")
    if km_url:
        lines.append(f"📄 详细 Review 文档：{km_url}")
    else:
        lines.append("📄 详细 Review 文档：（学城文档创建失败，请查看行内评论）")

    # 【格式固定】末尾基准 commit 行是下次增量 CR 读取起点的依据，勿改勿删
    target_commit = getattr(args, "target_commit", None)
    if target_commit and re.match(r'^[0-9a-fA-F]{40}$', target_commit):
        lines.append("")
        lines.append(f"📦 基准 commit: {target_commit}")
    return "\n".join(lines)


def assemble_daxiang_message(args, issues, counts, conclusion, km_url):
    """拼装大象群推送消息。"""
    header = f"【AI-CR Agent】{args.org}/{args.repo} #{args.pr_id} {args.pr_title}"
    stats = f"{conclusion}  P0={counts['p0']} P1={counts['p1']} P2={counts['p2']} P3={counts['p3']}" + (f" 外部专项={counts['ext']}" if counts.get("ext") else "")
    _t_auto = getattr(args, "_trigger_auto", False)
    _t_raw = getattr(args, "_trigger_mis_raw", "")
    if _t_auto:
        people = f"提交人：{args.author_name}（{args.submitter_mis}）  触发人：AI 自动触发（{_t_raw}，非人类触发者）"
    else:
        people = f"提交人：{args.author_name}（{args.submitter_mis}）  触发人：{args.trigger_name}（{args.trigger_mis}）"
    scope = f"范围: {scope_label(args, compact=True)}"

    lines = [header, stats, people, scope, ""]

    # 转正 EXT severity 即原级,自动进关键问题列表;灰度 EXT 不进(severity=confirm)
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

    # diff 拉取失败文件（覆盖缺口）标注，与全局评论同步
    ff = getattr(args, "_mode_failed_files", None) or []
    if ff:
        lines.append("")
        lines.append(f"⚠️ 审查覆盖缺口：{len(ff)} 个文件 diff 拉取失败，本次审查未覆盖，请人工补充检查（详见 PR 评论末尾清单）")

    # 触发Agent + 执行会话链接（1024 宿主 env 嗅探；空串整块不展示）
    # 紧跟 PR 链接，不插空行
    _an_d, _sid_d = agent_and_session(args)
    if _an_d:
        lines.append(f"🤖 触发Agent：{_an_d}")
        lines.append(f"🔍 Agent主页：{agent_overview_url(_an_d)}")
        if _sid_d:
            lines.append(f"💬 会话细则：{session_analysis_url(_an_d, _sid_d)}")

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


def _build_rule_hit_summary_data(issues):
    """结构化「规则命中摘要」（与 assemble_rule_hit_summary 的 markdown 版本同源）。"""
    if not issues:
        return {}
    p0_rules = sorted(set(r for it in issues if it["severity"] == "P0" for r in _expand_rids(it)))
    p1_rules = sorted(set(r for it in issues if it["severity"] == "P1" for r in _expand_rids(it)))
    p2_rules = sorted(set(r for it in issues if it["severity"] == "P2" for r in _expand_rids(it)))
    p3_rules = sorted(set(r for it in issues if it["severity"] == "P3" for r in _expand_rids(it)))
    confirm_count = len([it for it in issues if it["severity"] == "confirm"])

    cr_count = mt_count = cu_count = l2_count = bl_count = fe_count = 0
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
            elif r.startswith("L2:"):
                l2_count += 1
            elif r.startswith("FE:"):
                fe_count += 1
            elif r.startswith("BL:"):
                bl_count += 1

    return {
        "total_rules": len(set(all_rids)),
        "cr_rule_count": cr_count,
        "mt_rule_count": mt_count,
        "cu_rule_count": cu_count,
        "l2_rule_count": l2_count,
        "fe_rule_count": fe_count,
        "bl_rule_count": bl_count,
        "unlabeled_count": sum(not _expand_rids(it) for it in issues),
        "total_hits": len(issues),
        "p0_rules": p0_rules,
        "p1_rules": p1_rules,
        "p2_rules": p2_rules,
        "p3_rules": p3_rules,
        "confirm_count": confirm_count,
    }


def _position_status_of(it):
    """统一位置状态：行号是否已在当前代码上确认锚定。

    状态枚举（与发布链路 _anchor/_publishPlan 同源）：
      confirmed   verified/relocated 且未被显式降级（_publishPlan != "global"）；
                  P0/P1/confirm-FE 行内候选以发布计划为准（inline=确认），
                  P2/P3 不参与行内发布，锚定校验通过即视为确认（仅展示口径）
      unconfirmed 其余一切情形（invalid/kept/skipped/nofile/未参与/降级全局）
    只描述定位可靠性，不改变严重级别、计数门禁与行内策略。
    """
    if (it.get("_anchor") in ("verified", "relocated")
            and it.get("_publishPlan") != "global"):
        # 精度档语义：exact（内容验证）/ mapped（L1 显式配对迁移）= 已确认；
        # near / approximate / file-level（降档链择优，代码内容未逐行验证）= 未确认。
        # 强制行内红线只解决「可见性」，不等于「定位可靠」——两维度分开表达。
        prec = str(it.get("_anchorPrecision") or "")
        if prec in ("", "exact", "mapped") and not it.get("_pendingReanchor"):
            return "confirmed"
    return "unconfirmed"


def _build_doc_issues(issues, extra_fields):
    """结构化逐条 issue 列表（覆盖学城文档展示的全部字段，含 confirm 专属字段）。"""
    result = []
    for idx, it in enumerate(issues, 1):
        entry = {
            "index": idx,
            "severity": it.get("severity", ""),
            "positionStatus": _position_status_of(it),
            # 优先 _publishNote（终态降级原因，含晚漂移），
            # _anchorNote（如「L9 → L10」）仅作兜底——以 _publishNote 为准，
            # 会用重定位说明覆盖晚漂移终态原因
            "positionNote": (it.get("_publishNote") or it.get("_anchorNote") or "").strip(),
            "ruleId": it.get("ruleId", "") or "",
            "ruleName": it.get("ruleName", "") or "",
            "ruleFile": it.get("ruleFile", "") or "",
            "anomalyType": it.get("anomalyType", "") or "",
            "summary": it.get("summary", "") or "",
            "file": it.get("file", "") or "",
            "line": it.get("line", 0) or 0,
            "lineType": it.get("lineType", "") or "",
            "code": it.get("code", "") or "",
            "description": it.get("description", "") or "",
            "risk": it.get("risk", "") or "",
            "suggestion": it.get("suggestion", "") or "",
            "source": it.get("source", "") or "",
            "commentId": it.get("commentId"),
        }
        if "rule_sources" in it:
            entry["rule_sources"] = it["rule_sources"]
        # 文档展示的扩展字段（触达分析/线上场景/影响范围 + confirm 专属）
        for k in extra_fields:
            if it.get(k):
                entry[k] = it[k]
        result.append(entry)
    return result


def _build_custom_rules_data(issues):
    """结构化「自定义规则检查结果」子节（CU: 来源 / step4c）。"""
    cu_issues = [it for it in issues if it.get("source") == "step4c" or
                 any(r.startswith("CU:") for r in _expand_rids(it))]
    if not cu_issues:
        return None
    return _build_doc_issues(cu_issues, ("reach_analysis", "online_scenario", "impact_scope",
                                         "confirm_reason", "possible_risk", "confirm_suggestion"))


def _build_layer2_stats(args):
    """汇总本轮反查埋点（layer2_stats.jsonl，repo_search_json 每次搜索追加）。

    返回 {hit_files, hit_lines, queries}；无埋点文件时返回 None（不落字段）。
    多仓 PR：埋点文件在各自 CR_RUN_DIR；本函数仅读 mode_info 同仓 run 目录，
    以 --layer2-stats-file 显式传入为准。
    """
    path = getattr(args, "layer2_stats_file", None) or ""
    if not path or not os.path.isfile(path):
        return None
    queries = hit_files = hit_lines = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                queries += 1
                hit_files += int(rec.get("hitFiles", 0))
                hit_lines += int(rec.get("hitLines", 0))
    except OSError:
        return None
    return {"queries": queries, "hit_files": hit_files, "hit_lines": hit_lines}


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
    """结构化「一、PR 概述」表格内容。

    双口径（与 cr_task 表列对齐，下游 CrResultParser 直接解析）：
      * 平台权威口径三字段（file_count/added_lines/removed_lines）= PR 平台权威规模
        （Code 平台 pr-info：file_num/additions/deletions）。老版本 Agent
        传参口径作为回退保留。
      * 审查覆盖口径三字段（reviewed_*）= 审查覆盖口径：本轮实际成功拉取 diff 并审查
        的文件数与 +行/-行合计（get_pr_diff 脚本确定性统计，排除 +++/---
        文件头与 CONTEXT 行；不含反查命中文件）。反查覆盖另行以
        layer2_hit_files/layer2_hit_lines 落字段。
      * NULL 语义：reviewed_* 为 null 表示未采集（之前的存量），
        0 = 真实零行，与后端 DB 列 DEFAULT NULL 约定一致。
    """
    added, removed = _parse_line_changes(args.line_changes)
    r_added, r_removed = _parse_line_changes(getattr(args, "reviewed_line_changes", ""))
    reviewed_file_count = getattr(args, "reviewed_file_count", None)
    overview = {
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
        "reviewed_file_count": reviewed_file_count,
        "reviewed_additions": r_added,
        "reviewed_deletions": r_removed,
        "reviewed_total_changed_lines": (r_added or 0) + (r_removed or 0) if (r_added is not None or r_removed is not None) else None,
        "cr_mode": getattr(args, "cr_mode", "full"),
        "base_commit": getattr(args, "base_commit", None),
        "target_commit": getattr(args, "target_commit", None),
        "commit_count": getattr(args, "commit_count", None),
        "skill_version": f"ai-quality-cr-agent {SKILL_VERSION}",
    }
    return overview


def _build_changed_files_data(args):
    """结构化「二、变更综述」兜底用的变更文件清单。"""
    changed_files_md = read_text_file(getattr(args, "changed_files_file", ""), "")
    if not changed_files_md:
        return []
    file_lines = [l.strip().lstrip("- ").strip() for l in changed_files_md.strip().split("\n")
                  if l.strip() and not l.startswith("#")]
    return file_lines


def build_cr_result(args, issues, counts, conclusion, km_url, summary_parts=None):
    """拼装结构化 CR 结果 JSON 对象（原样写入 cr_task.cr_result_json）。

    2026-07-28 扩展：新增 issues 字段（逐条明细，仅 P0~P3），供下游
    sku-operation-server 侧 DefenderCallbackConverter 组装 Defender
    notify 回调的 responseMessage（技术方案 6.1/6.3 节，km.sankuai.com/collabpage/2777573642）。

    2026-08-24 扩展：学城文档全部章节内容以结构化 JSON 形式铺平到顶层，
    与 assemble_citadel_doc 的 markdown 章节一一对应；issues 字段升级为
    全量明细（P0~P3 + confirm，含文档展示的全部字段），下游可直接复用。
    """
    sdd_md = read_text_file(args.sdd_file, "")
    # is_sdd / 一致率均由主 Agent 按 Step 3D 结论显式传入（--is-sdd / --consistency-rate），
    # 不从 sdd 文件文本解析（模型写文件时可能漏写「一致率」行，解析静默失败）。
    # is_sdd 未显式传入时一律按 false 兜底（sdd 文件非空不能说明有 spec——无 spec 时模板要求写占位文案）
    is_sdd = bool(args.is_sdd)
    consistency_rate = (getattr(args, "consistency_rate", "") or "").strip()
    if summary_parts is None:
        summary_parts = split_summary_file(read_text_file(args.summary_file, ""))
    catpaw_md = read_text_file(args.catpaw_file, "")
    adopt_md = read_text_file(f"/tmp/cr_adopt_{args.pr_id}.md", "")

    # issues：全量明细（含 confirm），覆盖文档展示的全部字段，复用同一字段名
    issues_data = _build_doc_issues(
        issues,
        ("reach_analysis", "online_scenario", "impact_scope",
         "confirm_reason", "possible_risk", "confirm_suggestion"),
    )

    result = {
        "pr_id": args.pr_id,
        "org": args.org,
        "repo": args.repo,
        "pr_title": args.pr_title,
        "pr_url": args.pr_url,
        "conclusion": conclusion,
        "counts": counts,
        "is_sdd": is_sdd,
        "text_code_consistency_rate": consistency_rate if is_sdd else "",
        "skill_version": f"ai-quality-cr-agent {SKILL_VERSION}",
        "tech_stack": resolve_tech_stack(args),
        "km_url": km_url,
        "review_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "issues": issues_data,
    }

    # ── 学城文档章节内容，铺平到顶层 ──
    result.update({
        # 文档标题
        "doc_title": document_title(args),
        # 一、PR 概述
        "overview": _build_overview_data(args),
        # 反查覆盖（Layer 2 / Cross-Repo 命中统计，repo_search_json 埋点汇总；
        # 供成本分析，不计入 reviewed_* 三字段）
        "layer2_stats": _build_layer2_stats(args),
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
        # 八、上轮 CR 采纳情况（仅第二轮 CR）
        "previous_round_adoption": adopt_md,
    })
    return result


# ─── Step 6: 创建学城 CR 文档 ─────────────────────────────────────────────────

def step6_create_citadel_doc(args, doc_md):
    with tempfile.TemporaryDirectory(prefix="cr_publish_") as work_dir:
        return _step6_create_citadel_doc(args, doc_md, os.path.join(work_dir, "review.md"))


def _step6_create_citadel_doc(args, doc_md, findings_file):
    """创建学城文档，返回 {"ok": bool, "km_url": str, "error": str, "capacity_warn": str}"""
    result = {"ok": False, "km_url": "", "error": "", "capacity_warn": ""}
    # 容量滚动提示：目录满员自动续编时附在大象推送里（非告警）
    capacity_warn = ""

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
    try:
        with open(findings_file, "w", encoding="utf-8") as f:
            f.write(doc_md)
    except Exception as e:
        result["error"] = f"写入文档临时文件失败: {e}"
        return result

    # 按标题查重：verify-then-create 的查询步。
    # 查询失败不阻断创建（只是多一层复用机会），返回 None 走正常创建。
    def find_existing_cr_doc():
        out = run_cmd_raw(
            ["oa-skills", "citadel", "getChildContent", "--contentId", str(date_parent_id), "--raw"],
            label="按标题查重CR文档"
        )
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"查重 getChildContent 解析失败: {e}; stdout[:200]={out[:200]}")
        if not isinstance(data, dict):
            raise RuntimeError(f"查重 getChildContent 输出非对象: {type(data).__name__}")
        children = data.get("children")
        if not isinstance(children, list):
            raise RuntimeError("查重 children 字段非列表")
        # 同标题取最新创建的（重复场景下复用最新一份）
        cands = [c for c in children if isinstance(c, dict) and c.get("title") == doc_title]
        if not cands:
            return None
        best = max(cands, key=lambda c: c.get("createTime") or 0)
        cid = str(best.get("contentId") or best.get("id") or "")
        return f"https://km.sankuai.com/collabpage/{cid}" if cid else None

    date_dir = datetime.now().strftime("%Y-%m-%d")
    date_parent_id = None
    doc_title = document_title(args)

    def _is_708(err):
        """识别学城 code=708（协作文档服务/配额异常，含目录子节点写满）"""
        return "708" in str(err)

    def _switch_to_overflow_dir(err):
        """708 兜底：扫描《日期-N》续编序列找未满目录，没有就新建下一个编号
        （verify-then-create 防并发重建）。只切 date_dir/date_parent_id 和
        capacity_warn，抛错交给外层 retry 在新目录重建。"""
        nonlocal date_dir, date_parent_id, capacity_warn
        log(f"⚠️ 创建命中 708（疑似目录写满/服务异常）: {str(err)[:200]}")
        seq = 2
        while True:
            ext_title = f"{date_dir}-{seq}"
            found = None
            for c in _list_children_of(citadel_parent_id):
                if isinstance(c, dict) and c.get("title") == ext_title:
                    found = c
                    break
            if found is None:
                def create_ext_once():
                    out = run_cmd_raw(
                        ["oa-skills", "citadel", "createDocument", "--title", ext_title, "--content", ext_title, "--parentId", str(citadel_parent_id), "--raw"],
                        label=f"708兜底创建续编目录 {ext_title}", timeout=30
                    )
                    data = json.loads(out)
                    cid = str((data or {}).get("contentId") or (data or {}).get("id") or "")
                    if not cid:
                        raise RuntimeError(f"无法提取续编目录 contentId: stdout[:300]={out[:300]}")
                    return cid
                def verify_create_ext():
                    for c in _list_children_of(citadel_parent_id):
                        if isinstance(c, dict) and c.get("title") == ext_title:
                            return str(c.get("contentId") or c.get("id") or "")
                    return create_ext_once()
                ok_x, val_x = retry(verify_create_ext, label=f"708兜底创建续编目录 {ext_title}")
                if not ok_x:
                    raise RuntimeError(f"708兜底续编目录创建失败: {val_x}")
                date_dir, date_parent_id = ext_title, str(val_x)
                capacity_warn = (f"📁 容量滚动：创建时命中 708，已自动切续编目录《{ext_title}》。")
                log(f"📁 已切换续编目录: {ext_title} (id={val_x})")
                return
            # 续编目录已存在，看它满没满
            ext_id = str(found.get("contentId") or found.get("id") or "")
            n_ext = len(_list_children_of(ext_id))
            if n_ext < CITADEL_DIR_CAPACITY_FULL:
                date_dir, date_parent_id = ext_title, ext_id
                capacity_warn = (f"📁 容量滚动：命中 708 后已切续编目录《{ext_title}》（{n_ext}/500）。")
                log(f"📁 已切换续编目录: {ext_title} (id={ext_id})")
                return
            seq += 1

    def _list_children_of(cid):
        """拉某节点的子列表（--raw 纯 JSON），异常时抛错。"""
        out = run_cmd_raw(
            ["oa-skills", "citadel", "getChildContent", "--contentId", str(cid), "--raw"],
            label="拉取子节点"
        )
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"getChildContent 解析失败: {e}; stdout[:200]={out[:200]}")
        if not isinstance(data, dict):
            raise RuntimeError(f"getChildContent 输出非对象: {type(data).__name__}")
        children = data.get("children")
        if not isinstance(children, list):
            raise RuntimeError("children 字段非列表")
        return children

    def find_date_dir():
        # --raw 模式：stdout 只有纯 JSON，stderr 日志不参与解析，
        # 子文档标题含 {hotfix} 等花括号也不会干扰。
        out = run_cmd_raw(
            ["oa-skills", "citadel", "getChildContent", "--contentId", str(citadel_parent_id), "--raw"],
            label="查找日期子目录"
        )
        # 解析/结构异常 → 抛错进重试（重试的是查询），
        # 绝不能返回 None 被“目录不存在”分支误建目录。
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"getChildContent 输出解析失败: {e}; stdout[:200]={out[:200]}")
        if not isinstance(data, dict):
            raise RuntimeError(f"getChildContent 输出非对象: {type(data).__name__}")
        if data.get("warning"):
            # safeRoom 返回不完整 → 禁止据此判断“目录不存在”去创建
            raise RuntimeError(f"getChildContent 返回不完整: {data['warning']}")
        children = data.get("children")
        if not isinstance(children, list):
            raise RuntimeError("children 字段非列表")
        candidates = [c for c in children if isinstance(c, dict) and c.get("title") == date_dir]
        if not candidates:
            return None

        # API 返回中不存在 childCount 字段（恒为0，等于没排序），
        # 真实字段是 isChildExist（布尔）。活跃目录优先，活跃中取最新，
        # 避免重复目录场景下选中空壳目录。
        def sort_key(c):
            is_active = 1 if c.get("isChildExist") else 0
            return (is_active, c.get("createTime") or 0)

        best = max(candidates, key=sort_key)
        return best.get("contentId") or best.get("id")

    # 查不到 → 延迟3s复查一次（覆盖读延迟/并发窗口），仍查不到才创建。
    # 查询彻底失败（重试耗尽）→ 直接 Step 6 失败，不静默降级成"目录不存在"去盲建目录。
    ok, val = retry(find_date_dir, label="查找日期子目录")
    if ok and not val:
        time.sleep(3)
        ok, val = retry(find_date_dir, label="二次查找日期子目录")
    if not ok:
        result["error"] = f"查询日期目录失败: {val}"
        return result

    # 容量巡检：≥ 阈值则预警（不阻断）；≥ 续编阈值自动滚动到《日期-N》目录
    # （500 是学城硬上限，查重只能避免重复；续编 = 每个新目录重置 500 容量）
    def pick_dir_with_capacity():
        """从当前日期目录起，找到第一个没满的目录。
        当前目录 < FULL → 直接用；≥ FULL → 依次探《日期-2》《日期-3》…，
        找到未满的续编目录用之，都没有则新建下一个编号。返回 (dir_name, dir_id)。"""
        n = len(_list_children_of(date_parent_id))
        if n < CITADEL_DIR_CAPACITY_FULL:
            return date_dir, date_parent_id, ""
        # ≥ FULL：找续编目录
        seq = 2
        while True:
            ext_title = f"{date_dir}-{seq}"
            found = None
            for c in _list_children_of(citadel_parent_id):
                if isinstance(c, dict) and c.get("title") == ext_title:
                    found = c
                    break
            if found is None:
                # 新建续编目录（含 verify：并发时另一进程已建 → 重查复用）
                def create_ext_once():
                    out = run_cmd_raw(
                        ["oa-skills", "citadel", "createDocument", "--title", ext_title, "--content", ext_title, "--parentId", str(citadel_parent_id), "--raw"],
                        label=f"创建续编目录 {ext_title}", timeout=30
                    )
                    data = json.loads(out)
                    cid = str((data or {}).get("contentId") or (data or {}).get("id") or "")
                    if not cid:
                        raise RuntimeError(f"无法提取续编目录 contentId: stdout[:300]={out[:300]}")
                    return cid
                def verify_create_ext():
                    # 先查根目录下是否已有同名续编（并发/前次超时已建），有则复用绝不重建
                    for c in _list_children_of(citadel_parent_id):
                        if isinstance(c, dict) and c.get("title") == ext_title:
                            return str(c.get("contentId") or c.get("id") or "")
                    return create_ext_once()
                ok_x, val_x = retry(verify_create_ext, label=f"创建续编目录 {ext_title}")
                if not ok_x:
                    raise RuntimeError(f"续编目录创建失败: {val_x}")
                _warn = (f"📁 容量滚动：当日目录《{date_dir}》已满({n}/500)，"
                         f"自动启用续编目录《{ext_title}》。")
                return ext_title, str(val_x), _warn
            # 续编目录已存在，看它满没满
            ext_id = str(found.get("contentId") or found.get("id") or "")
            n_ext = len(_list_children_of(ext_id))
            if n_ext < CITADEL_DIR_CAPACITY_FULL:
                _warn = f"📁 容量滚动：已启用续编目录《{ext_title}》（{n_ext}/500）。"
                return ext_title, ext_id, _warn
            seq += 1

    if val:
        date_parent_id = str(val)
        log(f"📁 日期目录已存在: {date_dir} (id={date_parent_id})")
        # 容量巡检 + 自动续编
        ok_c, val_c = retry(pick_dir_with_capacity, label="目录容量巡检")
        if not ok_c:
            # 巡检失败不阻断，留在原目录（目录满时创建会失败并进入重试，错误可见）
            log(f"⚠️ 容量巡检失败（不阻断）: {val_c}")
        else:
            _dir, _id, _warn = val_c
            if _dir != date_dir:
                date_dir, date_parent_id = _dir, _id
                log(f"📁 使用目录: {date_dir} (id={date_parent_id})")
            if _warn:
                capacity_warn = _warn
    else:
        def create_date_dir_once():
            # --raw：stdout 纯 JSON，直接取 contentId，不碰 stderr 日志。
            # 换用较短 timeout（30s）：createDocument 正常秒级返回，超时说明
            # “服务端可能已成功但响应丢失”，此时必须先查询核实而不是盲目重发。
            out = run_cmd_raw(
                ["oa-skills", "citadel", "createDocument", "--title", date_dir, "--content", date_dir, "--parentId", str(citadel_parent_id), "--raw"],
                label="创建日期子目录", timeout=30
            )
            try:
                data = json.loads(out)
            except (json.JSONDecodeError, ValueError):
                raise RuntimeError(f"createDocument 输出解析失败: stdout[:300]={out[:300]}")
            cid = str((data or {}).get("contentId") or (data or {}).get("id") or "")
            if not cid:
                raise RuntimeError(f"无法提取 contentId: stdout[:300]={out[:300]}")
            return cid

        def verify_then_create():
            # 验证式创建：每次尝试前先查一遍目录是否已存在（含其他进程/前次
            # 超时创建的），存在则直接复用，绝不重复建。
            ok_q, val_q = retry(find_date_dir, label="创建前核实日期目录")
            if ok_q and val_q:
                return str(val_q)
            # 创建失败/超时（结果不明）时，下一轮 retry 会重新走这里先查询核实，
            # 服务端已建成功的场景在此转为复用。
            return create_date_dir_once()

        ok, val = retry(verify_then_create, label="创建日期子目录")
        if ok:
            date_parent_id = val
            log(f"📁 日期目录已创建: {date_dir} (id={date_parent_id})")
        else:
            result["error"] = f"创建日期子目录失败: {val}"
            return result


    def create_cr_doc():
        # 验证式创建（与日期目录创建逻辑一致）：
        # 1) 先查日期目录下是否已有同标题文档（前次超时重试已建成功/并发创建），
        #    存在 → 直接复用 URL，避免重复建（重复建会浪费目录子节点配额）。
        # 2) 不存在 → 创建。超时/失败（结果不明）时 retry 重新进入这里先查再建，
        #    服务端已建成功的场景在此转为复用。
        # 3) 708 兜底：容量巡检依赖 getChildContent 计数，500 上限+并发窗口下会漏判
        #    （目录显示 489 却在创建时命中 708）。捕获 code=708 时不再原地重试
        #    （对目录写满无效），而是切到未满的《日期-N》续编目录，交外层 retry 重建。
        ok_q, val_q = retry(find_existing_cr_doc, label="创建前核实CR文档")
        if ok_q and val_q:
            log(f"✅ 检测到同标题文档已存在，复用: {val_q}")
            return val_q
        try:
            out = run_cmd(
                ["oa-skills", "citadel", "createDocument", "--title", doc_title, "--file", findings_file, "--parentId", str(date_parent_id)],
                label="创建学城CR文档", timeout=30
            )
        except RuntimeError as e:
            if _is_708(e):
                # 换目录后立即直建一次(同轮内),避免外层 retry 的间隔;
                # 失败则抛错交给外层 retry 在新目录重建
                try:
                    _switch_to_overflow_dir(e)
                    out = run_cmd(
                        ["oa-skills", "citadel", "createDocument", "--title", doc_title, "--file", findings_file, "--parentId", str(date_parent_id)],
                        label="创建学城CR文档(续编目录)", timeout=30
                    )
                    url = _extract_url(out)
                    if not url:
                        cid = _extract_content_id(out)
                        if cid:
                            url = f"https://km.sankuai.com/collabpage/{cid}"
                    if url:
                        return url
                except Exception as e2:
                    if _is_708(e2):
                        _switch_to_overflow_dir(e2)  # 再满再切, 直到成功或重试耗尽
                    else:
                        raise
                raise RuntimeError(f"708切换续编目录后重建仍失败: {str(e)[:200]}")
            raise
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
        result["capacity_warn"] = capacity_warn
        log(f"✅ Step 6: 学城文档已创建: {val}")
        if capacity_warn:
            log(f"⚠️ {capacity_warn}")
    else:
        result["error"] = f"创建学城文档失败: {val}"
        log(f"❌ Step 6: {result['error']}")

    return result


# ─── Step 7: 评论到 PR ────────────────────────────────────────────────────────

# 仅从本脚本同目录加载纯计算模块，不走 sys.path 或新增扫描回退。
import importlib.util as _dedup_importlib
try:
    _dedup_spec = _dedup_importlib.spec_from_file_location(
        "_aicr_comment_dedup", os.path.join(_HERE, "comment_dedup.py"))
    _comment_dedup = _dedup_importlib.module_from_spec(_dedup_spec)
    _dedup_spec.loader.exec_module(_comment_dedup)
except BaseException:
    _comment_dedup = None
_dedup_fallback_warned = False

# 原 V131 基线内联实现：同目录模块加载失败时保持计算行为不变。
_RULE_PATTERN = re.compile(
    r'\[((?:CR|MT|CU|L2|BL|FE|EXT):[A-Za-z0-9][A-Za-z0-9._:/-]*)\]'
    r'|(?:^|(?<=[\s*`\[(]))((?:CR|MT|CU|L2|BL|FE|EXT):[A-Za-z0-9][A-Za-z0-9._:/-]*)(?=[\s`\-\]\*,;)]|$)'
    r'|\[([A-Z][A-Z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\]'
    r'|(?:^|(?<=[\s*`\[(]))([A-Z][A-Z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?=[\s`\-\]\*,;)]|$)'
    r'|(?:^|(?<=[\s*`\[(]))(java-l1:[A-Z]{2,4}-[0-9]{2,3}\.[A-Za-z0-9-]+)(?=[\s`\-\]\*,;)]|$)'
)

_P_LEVEL = re.compile(r"^P[0-3](?:-\d+)?$")


def _warn_comment_dedup_fallback():
    """兼容入口首次使用内联回退时告警一次。"""
    global _dedup_fallback_warned
    if not _dedup_fallback_warned:
        _dedup_fallback_warned = True
        log("⚠️ comment_dedup 同目录模块加载失败，降级为 V131 基线内联去重实现")


def _extract_rule_ids(text):
    """从评论文本中提取已经规范化的规则编号。"""
    if _comment_dedup is not None:
        return _comment_dedup._extract_rule_ids(text)
    _warn_comment_dedup_fallback()
    matches = _RULE_PATTERN.findall(text or "")
    ids = [next((group for group in match if group), "") for match in matches]
    return [rid for rid in ids if rid and not _P_LEVEL.fullmatch(rid)]


def _comment_fp(text):
    """正文 SHA-256 指纹：只规范换行、首尾空白和首行问题序号。
    保留正文内空白、证据行号、严重级别及正文中的编号引用。"""
    if _comment_dedup is not None:
        return _comment_dedup._comment_fp(text)
    _warn_comment_dedup_fallback()
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return ""
    title, separator, body = t.partition("\n")
    title = re.sub(
        r"^((?:#{1,6}[ \t]+)?(?:\*\*)?(?:[🚨🔴🟠🟡🔵][ \t]*)?)\[P([0-3])-\d+\]",
        r"\1[P\2]", title, count=1,
    )
    # 旧问号标题与新标签归一，避免仅展示文案/Q 编号变化导致重复评论。
    title = re.sub(
        r"^((?:#{1,6}[ \t]+)?)(?:❓[ \t]*|(?:🟡|🔎)[ \t]*待人工确认[ \t]*)\[Q-\d+\]",
        r"\1[Q]", title, count=1,
    )
    return hashlib.sha256((title + separator + body).encode("utf-8")).hexdigest()


def fetch_existing_inline_comments(pr_url, code_cli_py, max_pages=10):
    """拉取 PR 已有行内评论，返回三元组 (exact_set, fuzzy_set, raw_list)。
    exact_set/fuzzy_set: 既有规则编号与正文指纹去重键。
    普通 confirm 另用 (confirm, 完整路径, line, lineType, 正文指纹) 精确键，
    不因同位置已有其它问题而跳过；缺少有效锚点的旧评论不构建此键。
    raw_list: 完整评论原文（含正文），供全局评论去重使用。
    翻页: pr-comments 底层 activities 单页限 100 条，多轮 CR 的 PR 评论
    超过 100 条会被截断 → 去重集合不完整 → 重复评论。多次调用并按
    评论 id 去重累积，单页 < 90 条视为取完。
    拉取失败返回 None，调用方按 None 处理（不去重，全写）。"""
    try:
        all_comments = []
        seen_ids = set()
        for page in range(max_pages):
            cmd = [sys.executable, code_cli_py, "pr-comments", "--url", pr_url]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                log(f"⚠️  拉取已有评论失败(rc={r.returncode}): {r.stderr[:200]}")
                return None
            page_comments = json.loads(r.stdout)
            new = [c for c in page_comments if c.get("id") not in seen_ids]
            if not new:
                break
            for c in new:
                seen_ids.add(c.get("id"))
            all_comments.extend(new)
            if len(page_comments) < 90:
                break
        comments = all_comments
        exact_set = set()
        fuzzy_set = set()
        for c in comments:
            file_ = c.get("file") or ""
            # 去重键用完整路径归一（小写化处理大小写差异），避免同 repo 跨目录同名文件误判；
            # 旧评论若无路径信息则回退 basename
            file_key = (file_ or "").strip().lower() or (os.path.basename(file_) if file_ else "")
            line = c.get("line") or 0
            text = c.get("text") or ""
            line_type = (c.get("lineType") or "").upper()
            if file_ and isinstance(line, int) and not isinstance(line, bool) and line > 0 and line_type in ("ADDED", "REMOVED"):
                exact_set.add(("confirm", file_, line, line_type, _comment_fp(text)))
            rids = _extract_rule_ids(text)
            if not rids:
                exact_set.add((file_key, line, ""))
                fuzzy_set.add((file_key, _comment_fp(text)))
            else:
                for rid in rids:
                    exact_set.add((file_key, line, rid))
                    fuzzy_set.add((file_key, rid))
                fuzzy_set.add((file_key, _comment_fp(text)))
        log(f"📋 已有评论: {len(exact_set)} 精确维度, {len(fuzzy_set)} 模糊维度, 原文 {len(comments)} 条")
        return (exact_set, fuzzy_set, comments)
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


def _global_comment_exists(raw_comments, global_text, min_len=80):
    """判断同内容全局评论是否已存在。
    只匹配无 file 锚点、无 replies 的长文本评论（bot 全局报告特征），
    只规范换行和首尾空白，保留正文中代码及证据的语义空白。"""
    norm_new = (global_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(norm_new) < min_len:
        return False
    for c in raw_comments or []:
        if c.get("file") or c.get("replies"):
            continue
        text = c.get("text") or ""
        if text.replace("\r\n", "\n").replace("\r", "\n").strip() == norm_new:
            return True
    return False


def filter_duplicate_inline(inline_comments, existing_data):
    """三层去重过滤已存在的行内评论。
    Layer 1 精确匹配: (file_key, line, ruleId) 完全一致 → 跳过。
    Layer 2 模糊兜底: (file_key, ruleId) 一致（忽略行号）→ 跳过。
        用于 PR 有新 push 后行号漂移的场景，防止同文件同规则重复评论。
    Layer 2.5 指纹层: 无规则编号时，正文去首行序号后相同 → 已评论过 → 跳过。
    file_key 为完整路径小写归一；两侧路径粒度不一致时（一侧完整路径一侧 basename），
    回退用 basename 匹配，保证兼容旧数据不漏判。
    existing_data 为 None 时不过滤。"""
    if _comment_dedup is not None:
        kept, skipped, skipped_exact, skipped_fuzzy = _comment_dedup.filter_duplicate_inline(
            inline_comments, existing_data, return_details=True)
        if skipped:
            log(f"⏭️ 去重跳过 {skipped} 条（精确={skipped_exact}, 模糊={skipped_fuzzy}）")
        return kept, skipped
    _warn_comment_dedup_fallback()
    if existing_data is None:
        return inline_comments, 0
    exact_set, fuzzy_set = existing_data
    kept = []
    skipped = 0
    skipped_exact = 0
    skipped_fuzzy = 0
    for c in inline_comments:
        file_ = c.get("file_keyword", "")
        file_key = (file_ or "").strip().lower()
        file_basename = os.path.basename(file_) if file_ else ""
        line = c.get("line", 0)
        text = c.get("text", "")
        issue = c.get("_issue") or {}
        if issue.get("severity") == "confirm" and issue.get("source") != "step4e":
            key = ("confirm", file_, line, c.get("line_type"), _comment_fp(text))
            if key in exact_set:
                skipped += 1
                skipped_exact += 1
            else:
                kept.append(c)
            continue
        rids = _extract_rule_ids(text)
        if not rids:
            # 无规则编号时仅凭位置无法区分独立风险，必须匹配评论正文指纹。
            fp = _comment_fp(text)
            if fp and _dedup_hit(fuzzy_set, file_key, file_basename, (fp,)):
                skipped += 1
                skipped_fuzzy += 1
                continue
        else:
            # Layer 1: 精确匹配 (file, line, ruleId)
            all_exact = all(_dedup_hit(exact_set, file_key, file_basename, (line, rid)) for rid in rids)
            if all_exact:
                skipped += 1
                skipped_exact += 1
                continue
            # Layer 2: 模糊兜底 (file, ruleId)，忽略行号
            all_fuzzy = all(_dedup_hit(fuzzy_set, file_key, file_basename, (rid,)) for rid in rids)
            if all_fuzzy:
                skipped += 1
                skipped_fuzzy += 1
                continue
        kept.append(c)
    if skipped:
        log(f"⏭️ 去重跳过 {skipped} 条（精确={skipped_exact}, 模糊={skipped_fuzzy}）")
    return kept, skipped


def _dedup_hit(key_set, file_key, file_basename, tail):
    """去重键匹配：优先完整路径，路径粒度不一致时回退 basename。
    key_set 元素结构为 (file, *tail)。两侧同为完整路径或同为 basename 时用原键；
    一侧完整路径一侧 basename 时追加 basename 键兼容旧数据，两侧都试不误判
    （不同目录同名文件仅在同粒度键下才会命中，精确层仍区分路径）。"""
    if _comment_dedup is not None:
        return _comment_dedup._dedup_hit(key_set, file_key, file_basename, tail)
    _warn_comment_dedup_fallback()
    if (file_key, *tail) in key_set:
        return True
    if file_basename and file_basename != file_key:
        return (file_basename, *tail) in key_set
    return False


def step7_comment_to_pr(args, inline_comments, global_text):
    """发 PR 评论，返回 {"ok": bool, "inline_count": int, "global_ok": bool, "error": str}

    直接 import 调用 cr_comment.CommentClient（无 subprocess），CommentClient 内部自带重试。
    """
    result = {"ok": False, "inline_count": 0, "global_ok": False, "error": ""}

    # 进入即固化「应标注总数」口径（P0/P1 计划行内条数），
    # 供发送后改写全局评论头部「已作为行内评论标注」声明使用
    def _is_p0p1_comment(c):
        _iss = c.get("_issue")
        return isinstance(_iss, dict) and _inline_severity(_iss) in ("P0", "P1")

    planned_inline_total = len(inline_comments)
    planned_p0p1_total = sum(1 for c in inline_comments if _is_p0p1_comment(c))
    p0p1_total = getattr(args, "_p0p1_total", None) or planned_p0p1_total

    try:
        client = CommentClient(log_fn=log)
    except CommentError as e:
        result["error"] = f"初始化评论客户端失败: {e}"
        return result

    pr_url = args.pr_url
    pr_id = args.pr_id

    # 发送前复核（快照双端 + 过晚漂移）：定位/快照计划已在学城文档与
    # 全局正文生成前完成（plan_publish_anchors），此处只做轻量复核；
    # 不一致/查询失败（≠一致）→ 逐文件重拉复核，漂移条目明确标识降级全局
    # （不丢内容、不改锚点，保持与已生成文档同一行号视图）。
    # 该闸门与 comment-add --expected-from/to 冻结比对共同降低发送前后竞态，
    # 不构成原子保证（不声称消除）。
    snapshot_degraded = []  # [(meta, text)] 过晚漂移降级条目
    if inline_comments:
        code_cli_py = getattr(args, 'code_cli_py', None) or find_code_cli_py()
        if code_cli_py:
            try:
                _consistent, snap_note, late_degraded = _verify_late_drift(
                    args, pr_url, code_cli_py, inline_comments)
                log(f"📸 发送前复核: {snap_note}")
                if late_degraded:
                    # V135: P0/P1 漂移迁移(drift-migrated)与降级行内
                    # (degraded-inline)条目保留发送；仅真降级(degrade)过滤
                    inline_comments = [c for c in inline_comments
                                       if c.get("_snapshot") != "degrade"]
                    snapshot_degraded = late_degraded
                    log(f"📸 {len(late_degraded)} 条行内评论因过晚漂移降级全局（内容不丢）")
            except Exception as e:
                # 复核异常同样全部降级全局（
                # 发送」与版本声明「异常显式降级」矛盾——异常时无法确认快照有效，
                # 盲发行内可能锚错行；expected 冻结仅覆盖能查到 hash 的场景）
                log(f"⚠️ 发送前复核异常（{type(e).__name__}）: {e}")
                for c in inline_comments:
                    _iss = c.get("_issue")
                    _lp = (_inline_severity(_iss) in ("P0", "P1")
                           and _line_shape_ok(_iss)) if isinstance(_iss, dict) else False
                    if _lp:
                        # P0/P1 强制行内：复核异常不盲降级（expected 第三道
                        # 闸门仍在，hash 冻结比对失败会拒绝单条发送→该条兜底）
                        c["_snapshot"] = "degraded-inline"
                        c["_snapshotNote"] = f"发送前复核异常（{type(e).__name__}），按现有锚点发行内"
                        if isinstance(_iss, dict):
                            _iss.setdefault("_publishNote", c["_snapshotNote"])
                            _iss["positionStatus"] = "unconfirmed"
                    else:
                        c["_snapshot"] = "degrade"
                        c["_snapshotNote"] = f"发送前复核异常（{type(e).__name__}），降级全局"
                        if isinstance(_iss, dict):
                            _iss["_publishPlan"] = "global"
                            _iss["_publishNote"] = c["_snapshotNote"]
                        snapshot_degraded.append((
                            f"{c['_snapshotNote']}：`{c.get('file_keyword', '')}` L{c.get('line', '?')}",
                            c.get("text", "")))
                inline_comments = [c for c in inline_comments
                                   if c.get("_snapshot") != "degrade"]
        else:
            log("⚠️  未找到 code_cli.py，跳过发送前复核")

    # 写行内评论 JSON 文件（归档用，供调试）— 在去重后写，和实际发送一致
    # 先做去重，再写归档
    inline_count = 0
    p0p1_sent = 0
    inline_errors = []
    uncovered_errors = []  # 未被全局兜底覆盖的失败（纯跳过等），不因存在其他兜底而被掩盖
    inline_send_failures = []  # 发送失败的行内评论 [(meta, text)]，兜底进全局
    existing_data = None
    raw_existing = None
    if inline_comments or global_text:
        code_cli_py = getattr(args, 'code_cli_py', None) or find_code_cli_py()
        if code_cli_py:
            fetched = fetch_existing_inline_comments(pr_url, code_cli_py)
            if fetched is not None:
                existing_data = (fetched[0], fetched[1])
                raw_existing = fetched[2]
        else:
            log("⚠️  未找到 code_cli.py，跳过去重，全量写入")

    # 7A. 行内评论（写入前先拉取已有评论去重）
    p0p1_skipped = 0
    if inline_comments:
        # 去重过滤
        pre_dedup_snapshot = [(id(c), dict(c)) for c in inline_comments]
        inline_comments, skipped_count = filter_duplicate_inline(inline_comments, existing_data)
        # 仅精确层跳过（file+line+ruleId 完全一致）才视为「已在
        # 代码行标注」；模糊层（忽略行号）跳过只防重复，不代表本轮行号已标注
        # ——被跳过条目的 issue 同步 unconfirmed 终态（行号漂移，历史评论在
        # 旧行），声明口径不冒充
        _kept_ids = {id(c) for c in inline_comments}
        _skipped_comments = [orig for _cid, orig in pre_dedup_snapshot
                             if _cid not in _kept_ids]
        for _sc in _skipped_comments:
            _siss = _sc.get("_issue")
            if isinstance(_siss, dict) and _is_p0p1_comment(_sc):
                _siss["_publishPlan"] = "global"
                _siss["_publishNote"] = (f"历史评论已存在（去重跳过重发，行号可能"
                                         f"漂移：计划 L{_sc.get('line', '?')}），"
                                         "完整内容保留于本评论")
        p0p1_skipped = 0  # 模糊/精确跳过均不计入「已标注」声明口径
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
                # 有正文但缺文件锚定的条目兜底进全局（不丢弃）；两者皆缺才纯跳过
                if text:
                    inline_send_failures.append(
                        (f"行内评论缺少文件锚定（file 为空）", text))
                    inline_errors.append(f"行内评论 #{idx+1} 缺少 file_keyword，已兜底全局")
                else:
                    inline_errors.append(f"行内评论 #{idx+1} 缺少 file_keyword 或 text，跳过")
                    uncovered_errors.append(f"行内评论 #{idx+1} 缺少 file_keyword 或 text，无内容可兜底")
                continue

            try:
                # expected 固定 commitRange 集成：发送前与当前 pr-changes
                # 双端比对（comment-add --expected-from/to），不一致显式拒绝；
                # 拒绝抛 CommentError → 下方既有兜底降级全局（不丢弃）
                _exp = getattr(args, "_send_expected", None) or (None, None)
                comment_id = _send_inline_with_expected(
                    client, pr_url, file_keyword, line, line_type, text,
                    _exp[0], _exp[1])
                # 回写 commentId 到来源 issue，供 Step 9 issues 明细使用
                src_issue = comment.get("_issue")
                if isinstance(src_issue, dict):
                    src_issue["commentId"] = comment_id
                inline_count += 1
                if _is_p0p1_comment(comment):
                    p0p1_sent += 1
                log(f"  ✅ 行内评论 #{idx+1}: {file_keyword}:{line} (commentId={comment_id})")
            except CommentError as e:
                inline_errors.append(f"#{idx+1} {file_keyword}:{line} - {e}")
                log(f"  ❌ 行内评论 #{idx+1}: {e}")
                # 发送失败不丢弃——分两种兜底口径（防重复展示）：
                # ① 主列表已展开详情的（原 plan=inline 的 P0/P1）：
                #    全文已在全局评论区主列表，只追加单行标注防重复；
                # ② 未在主列表展开的：全文进兜底章节（内容不丢）
                _fiss = comment.get("_issue")
                _shown_in_main = (isinstance(_fiss, dict)
                                  and _inline_severity(_fiss) in ("P0", "P1"))
                if text and not _shown_in_main:
                    inline_send_failures.append(
                        (f"行内评论发送失败：`{file_keyword}` L{line}", text))
                elif _shown_in_main:
                    inline_send_failures.append(
                        (f"行内评论发送失败：`{file_keyword}` L{line}",
                         "详情见上方主列表（已完整展示，此处不重复）"))
                # 失败分支同步 issue 结构化终态（与漂移降级分支
                # 同口径）——否则 issue 仍按计划口径标 confirmed 行内，
                # cr_result/学城文档与 PR 实际（全局兜底）不一致
                if isinstance(_fiss, dict):
                    _fiss["_publishPlan"] = "global"
                    _fiss["_publishNote"] = f"行内评论发送失败（{str(e)[:120]}），兜底全局"
    else:
        log("ℹ️  无可发送的行内评论，跳过 7A")

    result["inline_count"] = inline_count

    # 7B. 全局评论
    # global_text 为空但存在兜底条目（发送失败/过晚漂移降级）时，
    # 拼最小全局正文承载兜底内容——兜底链不能因正文为空而丢内容
    if not global_text and (inline_send_failures or snapshot_degraded):
        global_text = (
            "## 🤖 AI Code Review 结果\n\n"
            "> 本 Review 由 AI-CR（AI 代码审查）自动生成，仅供参考，"
            "请结合业务实际情况判断。\n\n"
            f"**PR**：{getattr(args, 'org', '')}/{getattr(args, 'repo', '')} "
            f"#{getattr(args, 'pr_id', '')}\n\n---\n"
        )
        log("🛟 全局正文为空但存在兜底条目，已生成最小全局正文承载（不丢内容）")
    if global_text:
        # 行内发送完成后按实际结果改写头部「已作为行内评论标注」声明
        # （原文案发送前生成，发送失败/漂移降级后与事实不符）
        # annotated 仅计本轮实际发送成功数（p0p1_sent）——
        # 去重跳过（行号可能漂移）与 anchorVerified=false 均不冒充已标注
        if planned_p0p1_total or p0p1_sent:
            global_text = _rewrite_inline_claim(
                global_text, p0p1_sent, p0p1_total)
        # 兜底锚定（用户原则：不能随便丢评论，实在不行兜底全局）
        if inline_send_failures:
            global_text = _append_global_fallback(
                global_text, "以下问题行内评论发送失败（兜底全局展示）",
                inline_send_failures)
            log(f"🛟 {len(inline_send_failures)} 条行内评论发送失败，已追加全局评论兜底")
        if snapshot_degraded:
            global_text = _append_global_fallback(
                global_text, "以下问题因发送前检测到 PR 更新无法可靠锚定（兜底全局展示）",
                snapshot_degraded)
            log(f"📸 {len(snapshot_degraded)} 条过晚漂移降级条目已追加全局评论兜底")
        global_file = f"/tmp/cr_global_comment_{pr_id}.txt"
        try:
            with open(global_file, "w", encoding="utf-8") as f:
                f.write(global_text)
        except Exception as e:
            inline_errors.append(f"写全局评论文件失败: {e}")

        try:
            # 全局评论去重：同一 PR 上已有内容相同的 bot 全局评论则跳过。
            # 增量 CR 重跑场景下，报告内容未变时不再重复刷屏。
            if raw_existing and _global_comment_exists(raw_existing, global_text):
                log("  ⏭️  全局评论已存在（内容相同），跳过")
                result["global_ok"] = True
            else:
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
    # 行内失败/降级均已兜底进全局评论且全局发送成功 → 视为有效触达
    # 未被兜底覆盖的失败（缺 file_keyword 且无 text 的纯跳过等）
    # 不得因存在其他兜底条目而被掩盖——ok 需同时要求无 uncovered 错误
    fallbacked = bool(inline_send_failures or snapshot_degraded)
    result["ok"] = (result["global_ok"] and not uncovered_errors
                    and (not inline_errors or fallbacked))
    # 兜底计数不再依赖 inline_errors（纯降级场景无行内错误，
    # 但降级条目数对可观测性同样重要）
    if result["ok"] and fallbacked:
        result["fallbacked"] = len(inline_send_failures) + len(snapshot_degraded)

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


def get_uid_by_mis(token, mis_list):
    """mis → 大象 uid 批量转换，返回 {mis: str(uid)}；未命中/查不到的 mis 不出现在返回值里"""
    payload = json.dumps({"misList": [m for m in mis_list if m]}).encode()
    req = urllib.request.Request(MIS2UID_URL, data=payload, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    if result.get("status", {}).get("code", -1) != 0:
        raise RuntimeError(f"mis→uid 查询失败: {result.get('status')}")
    data = (result.get("data") or {}).get("data") or {}
    return {mis: str(item["uid"]) for mis, item in data.items() if item.get("uid")}


def format_at_text(name, uid):
    """大象 @ 高亮协议文本；必须配合 extension.at（send_group_msg 的 at_uids）才出现真实 @ 效果"""
    return f"[@{name}|mtdaxiang://www.meituan.com/profile?uid={uid}&isAt=true]"


def apply_at_to_person(message_text, label, name, mis, uid):
    """把消息中「{label}：{name}（{mis}）」替换为带 @ 协议的版本；返回 (新文本, 是否替换成功)"""
    plain = f"{label}：{name}（{mis}）"
    if plain not in message_text:
        return message_text, False
    at_line = f"{label}：{format_at_text(name, uid)}（{mis}）"
    return message_text.replace(plain, at_line, 1), True


def send_group_msg(token, gid, text, at_uids=None):
    """发送群文本消息；at_uids 传大象 uid 列表时携带 extension.at 实现真实 @
    （要求 text 内已含 [@姓名|mtdaxiang://...] 高亮协议，两者缺一不可；模板消息不支持 @）"""
    send_info = {"type": "text", "body": json.dumps({"text": text})}
    if at_uids:
        send_info["extension"] = json.dumps({"at": [str(u) for u in at_uids]})
    payload_data = json.dumps({"gid": gid, "sendMsgInfo": send_info}).encode()
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
            # 团队群：真实 @ 模板 people 行人员（提交人 + 触发人；同一人去重）
            # mis→uid 批量转换，转换成功的人才替换为 @ 版并进 extension.at；查不到的保持纯文本，推送不中断
            persons = []
            if args.submitter_mis and args.author_name:
                persons.append(("提交人", args.author_name, args.submitter_mis))
            if args.trigger_mis and args.trigger_name and not getattr(args, "_trigger_auto", False):
                # 数字员工账号触发已降级「AI 自动触发」,trigger_mis 为空串
                # 自然不进 @ 名单;此处 _trigger_auto 双保险(防误传)
                persons.append(("触发人", args.trigger_name, args.trigger_mis))

            at_uids = []
            team_message_text = message_text
            if persons:
                mis_list = sorted({m for _, _, m in persons})

                def query_uids(t=token, mlist=mis_list):
                    return get_uid_by_mis(t, mlist)

                ok_uid, uid_map = retry(query_uids, label="mis→uid 转换(团队群@周知对象)")
                if ok_uid:
                    for label, name, mis in persons:
                        uid = uid_map.get(mis)
                        if not uid:
                            log(f"⚠️  Step 8: {label} {mis} 未查到 uid, 保持纯文本")
                            continue
                        team_message_text, applied = apply_at_to_person(team_message_text, label, name, mis, uid)
                        if applied:
                            if uid not in at_uids:
                                at_uids.append(uid)
                            log(f"✅ Step 8: 团队群将 @ {label} {name}（{mis} → uid {uid}）")
                        else:
                            log(f"⚠️  Step 8: 未匹配到{label}行, {name}（{mis}）保持纯文本")
                else:
                    log(f"⚠️  Step 8: mis→uid 转换失败, 团队群降级纯文本: {uid_map}")
            else:
                log("ℹ️  无提交人/触发人信息, 团队群降级纯文本")

            def push_team(t=token, gid=team_gid_int, txt=team_message_text, uids=at_uids):
                return send_group_msg(t, gid, txt, at_uids=uids)

            ok, val = retry(push_team, label="推送团队群")
            if ok:
                result["team_group_ok"] = True
                log("✅ Step 8: 团队群推送成功")
            else:
                log(f"❌ Step 8: 团队群推送失败: {val}")
    else:
        result["team_group_ok"] = True
        log("ℹ️  无团队群 ID，跳过团队群推送")

    result["ok"] = result["global_group_ok"] and result["team_group_ok"]
    if not result["ok"]:
        result["error"] = "群推送未全部成功，请按 global_group_ok/team_group_ok 核对后重试"

    return result


# ─── Step 9: 回写结构化 CR 结果 ───────────────────────────────────────────────

def step9_submit_cr_result(args, cr_result):
    """把结构化 CR 结果回写到 cr_task.cr_result_json。

    接口：POST {SUBMIT_CR_RESULT_URL}，body={"conversation_id":..., "cr_result":<JSON字符串>,
          "session_id":...（可选）, "agent_name":...（可选）}。
    会话 ID 获取顺序：--conversation-id（显式传参）→ 环境变量 X_AI_SESSIONID → 环境变量 rootConversationId。
    agent_name 获取顺序：--agent-name（显式传参）→ 环境变量 X_AI_PAAS → 环境变量 1024_PAAS；各来源均经 AICR_Agent 前缀白名单校验，非该前缀的值(数字员工账号等非 Agent 实例名)丢弃后继续下一来源，无合法值时留空不上送。
    session_id/agent_name 为可选宽松字段：缺失/空串不上送（服务端按 null 透传，不覆盖既有值）。
    conversation_id 均未提供时跳过（不报错，向后兼容）。
    返回 {"ok": bool, "skipped": bool, "status": str, "error": str}。
    """
    result = {"ok": False, "skipped": False, "status": "", "error": ""}
    conversation_id = (args.conversation_id or "").strip()
    if not conversation_id:
        conversation_id = sniffed_conversation_id()
    if not conversation_id:
        result["skipped"] = True
        result["ok"] = True
        log("ℹ️  Step 9: 未提供 conversation_id（--conversation-id / X_AI_SESSIONID / rootConversationId 均为空），跳过 CR 结果回写")
        return result

    # cr_result 整体作为一个 JSON 字符串传入，json.dumps 会自动转义内部双引号
    cr_result_str = json.dumps(cr_result, ensure_ascii=False)

    # session_id / agent_name：可选宽松字段（服务端缺失/空串按 null 透传，不覆盖既有值）
    # 取值统一走 get_agent_name / get_session_id（与学城/大象展示同源, 不漂移）
    agent_name, session_id = agent_and_session(args)
    if session_id:
        log(f"📝 Step 9: session_id={session_id}")
    if agent_name:
        log(f"📝 Step 9: agent_name={agent_name}")

    def do_post():
        body_obj = {
            "conversation_id": conversation_id,
            "cr_result": cr_result_str,
        }
        # 只在有值时上送，空串不占位（服务端宽松解析）
        if session_id:
            body_obj["session_id"] = session_id
        if agent_name:
            body_obj["agent_name"] = agent_name
        body = json.dumps(body_obj).encode()
        req = urllib.request.Request(
            SUBMIT_CR_RESULT_URL, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode().strip()

    ok, val = retry(do_post, label="回写 CR 结果")
    if not ok:
        result["error"] = f"请求失败: {val}"
        log(f"❌ Step 9: {result['error']}")
        return result

    status, body = val
    result["status"] = body
    if body == "ok":
        result["ok"] = True
        log("✅ Step 9: CR 结果已回写 cr_task")
    elif body == "not found":
        result["error"] = f"not found (conversation_id={conversation_id} 未匹配 cr_task)"
        log(f"⚠️  Step 9: {result['error']}")
    else:
        result["error"] = f"http {status} body={body}"
        log(f"❌ Step 9: {result['error']}")
    return result


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def parse_bool(value):
    value = value.lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError("必须为 true/false、1/0 或 yes/no")


def parse_run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise argparse.ArgumentTypeError("run-id 必须为 1~80 位字母、数字、下划线或连字符")
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="AI-CR Agent 发布结果脚本")
    parser.add_argument("--pr-url", default="", help="PR URL（缺失时可由 org/repo/pr-id 反拼）")
    parser.add_argument("--pr-id", type=int, default=None, help="PR ID（缺失时从 --pr-url 反解）")
    parser.add_argument("--pr-title", default="", help="PR 标题（空串时兜底不阻断）")
    parser.add_argument("--org", default="", help="仓库组织（缺失时从 --pr-url 反解）")
    parser.add_argument("--repo", default="", help="仓库名（缺失时从 --pr-url 反解）")
    parser.add_argument("--submitter-mis", default="", help="提交人 MIS（空串时兜底不阻断）")
    parser.add_argument("--author-name", default="", help="提交人姓名（空串时兜底不阻断）")
    parser.add_argument("--trigger-mis", default="", help="触发人 MIS（空串时兜底不阻断）")
    parser.add_argument("--trigger-name", default="", help="触发人姓名（空串时兜底不阻断）")
    parser.add_argument("--citadel-parent-id", default="", help="学城父目录 ID")
    parser.add_argument("--team-chat-group-id", default="", help="团队大象群 ID")
    parser.add_argument("--conclusion", default="", help="CR 结论文本（不传则按计数自动推导）")
    parser.add_argument("--issues-file", action="append", default=[], help="统一 Issue JSON 文件路径（可重复传入）")
    parser.add_argument("--extan-status-file", default="",
                         help="外部专项审查门禁: step4e 封装体文件路径(含逐 analyzer 状态 checks);"
                              " 必选(required/promoted)专项非 READY 时结论强制为核验未完成")
    parser.add_argument("--changed-files-file", default="", help="变更文件清单章节 markdown")
    parser.add_argument("--summary-file", default="", help="总体评价章节 markdown")
    parser.add_argument("--sdd-file", default="", help="SDD 校验章节 markdown（可选）")
    parser.add_argument("--is-sdd", type=parse_bool, default=False,
                        help="本次 CR 是否有 SDD spec 产物（取 Step 3D 结论 has_spec；未传时一律按 false 兜底）")
    parser.add_argument("--consistency-rate", default="",
                        help="文码一致率（取 Step 3D 或 FE 等价结果 alignment_rate 原值，如 \"90%%\"；无 spec 时传空或不传）")
    parser.add_argument("--catpaw-file", default="", help="与 CatPaw 对比章节 markdown（可选）")
    parser.add_argument("--tech-stack", default="",
                        help="技术栈（Step 2H 判定值：java/nodejs/mrn/max/miniprogram/duo/react/android/ios/harmony/native/flutter/unknown；缺失或非法值登记 unknown）")
    parser.add_argument("--branch", default="", help="PR 分支（可选）")
    parser.add_argument("--file-count", type=int, default=None, help="变更文件数（可选）")
    parser.add_argument("--line-changes", default="", help="行数变化如 +120 -30（可选）")
    # 审查覆盖口径（DB 新增三列 reviewed_*）：优先从 mode_info 自动回填，
    # 显式传参仅作兼容口子
    parser.add_argument("--reviewed-file-count", type=int, default=None, help="实际审查覆盖文件数（可选，默认从 mode_info 回填）")
    parser.add_argument("--reviewed-line-changes", default="", help="实际审查覆盖行数如 +110 -25（可选，默认从 mode_info 回填）")
    parser.add_argument("--layer2-stats-file", default="", help="反查埋点汇总文件路径（可选，CR_RUN_DIR/layer2_stats.jsonl；提供则落 layer2_stats 字段）")
    parser.add_argument("--km-url", default="", help="已知学城 URL（跳过 Step 6）")
    parser.add_argument("--conversation-id", default="", help="1024 会话 ID（Step 9 回写 cr_task 用；未传则自动读环境变量 X_AI_SESSIONID → rootConversationId）")
    parser.add_argument("--session-id", default="", help="执行会话 ID（学城「执行会话」行+大象+全局评论+Step 9 落库共用；未传则复用 conversation_id 嗅探链路 X_AI_SESSIONID → rootConversationId）")
    parser.add_argument("--agent-name", default="", help="执行 agent 名称（大象「触发Agent」+学城+Step 9 落库共用；未传则自动读环境变量 X_AI_PAAS → 1024_PAAS，白名单校验 AICR_Agent 前缀，不规范值丢弃）")
    # 增量 CR 相关
    # run-id 软门禁化：缺失不再报错退出，自动生成并告警；同轮重试应显式传同一值以保幂等
    parser.add_argument("--run-id", type=parse_run_id, default=None,
                        help="本轮唯一标识：同轮重试必须复用同一值，标题查重依赖它防重复建文；缺失时自动生成并告警（不阻断发布）")
    parser.add_argument("--mode-info-file", default="", help="可选的 PR 专属范围文件，必须含 org/repo/prId，不读取共享缓存")
    parser.add_argument("--diff-file", default="",
                        help="本轮审查 diff 快照路径（$CR_DIFF_FILE；须能通过 mode_info 身份+runId+diffSha256 绑定校验才可信，"
                             "无 diffSha256 绑定时不可信、不参与锚定（走重拉/全局兜底））")
    parser.add_argument("--cr-mode", choices=["full", "incremental"], default=None,
                        help="CR 模式：全量 or 增量")
    parser.add_argument("--base-commit", default=None, help="增量模式的基准 commit")
    parser.add_argument("--target-commit", default=None, help="本次 CR 的目标 commit")
    parser.add_argument("--commit-count", type=int, default=None, help="增量范围内的 commit 数")
    # 兼容旧用法：直接传入拼好的文档（无 issue JSON 时降级使用）
    parser.add_argument("--findings-file", default="", help="(兼容) 完整文档 markdown，仍须提供经校验的 --issues-file")
    parser.add_argument("--dry-run", type=parse_bool, default=False,
                        help="演练模式：只拼装产物不真实上报（Step 6 可选真建，Step 7/8/9 一律跳过，产物落盘 /tmp/cr_dryrun/）")
    parser.add_argument("--dry-run-doc", type=parse_bool, default=False,
                        help="演练模式下是否真建学城文档（默认不建，用假 URL 占位）")
    args = parser.parse_args(argv)
    if args.dry_run_doc and not args.dry_run:
        parser.error("--dry-run-doc true 必须配合 --dry-run true")
    return normalize_args(args)


def _url_parts(url):
    """从 PR URL 反解 (org, repo, pr_id)。识别 /org/repo/pr/ID 或 repo-detail/org/repo/pr/ID。"""
    m = re.search(r"(?:repo-detail/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pr/([0-9]+)", url or "")
    if not m:
        return None, None, None
    return m.group(1), m.group(2), int(m.group(3))


def normalize_args(args, _parser=None):
    """参数缺失兜底：
    - org/repo/pr-id 缺失时从 --pr-url 反解；反向（有 org/repo/pr-id 无 url）则反拼 URL
    - 人名/标题类字段空串兜底不阻断
    - 核心四项（pr-url/pr-id/org/repo）仍缺才退出，输出结构化 JSON 错误
      （含 missing 清单和修复提示）替代裸 usage 文本
    """
    def _set(name, value):
        if value:
            setattr(args, name, value)

    # URL ↔ 三元组互拼
    u_org, u_repo, u_pr = _url_parts(args.pr_url)
    if u_org and not args.org:
        args.org = u_org
    if u_repo and not args.repo:
        args.repo = u_repo
    if u_pr and args.pr_id is None:
        args.pr_id = u_pr
    if not args.pr_url and args.org and args.repo and args.pr_id is not None:
        args.pr_url = (
            f"https://dev.sankuai.com/code/repo-detail/{args.org}/{args.repo}"
            f"/pr/{args.pr_id}/overview"
        )
    # pr-id 还原成 int（从 URL 反解后仍是 int；显式传可能是 int）
    if args.pr_id is not None and not isinstance(args.pr_id, int):
        try:
            args.pr_id = int(args.pr_id)
        except (TypeError, ValueError):
            args.pr_id = None

    # 人名/标题类空串兜底
    _set("pr_title", args.pr_title or "(untitled PR)")
    _set("submitter_mis", args.submitter_mis or "unknown")
    _set("author_name", args.author_name or args.submitter_mis or "unknown")
    # 触发人身份语义校验：数字员工账号(1024_ 前缀,如 1024_aicragent)
    # 不是人类触发者——展示降级为「AI 自动触发」、落库置空、@ 名单剔除；
    # 不自动替换成 PR 提交人（提交人≠触发人,替换=编造）。原始值留追溯。
    _t_mis, _t_name, _t_auto = clean_trigger_identity(
        getattr(args, "trigger_mis", ""), getattr(args, "trigger_name", ""))
    if _t_auto:
        print(f"⚠️ trigger_mis '{args.trigger_mis}' 为数字员工账号,"
              f"触发人按「AI 自动触发」处理(原始值保留于 _trigger_mis_raw)",
              file=sys.stderr)
        args._trigger_mis_raw = args.trigger_mis
        args._trigger_auto = True
        # _set 只写非空值;此处需显式清空(数字账号不得进落库/@名单)
        args.trigger_mis = ""
        args.trigger_name = "AI 自动触发"
    else:
        _set("trigger_mis", _t_mis or "unknown")
        _set("trigger_name", _t_name or _t_mis or "unknown")

    # 核心四项校验：结构化 JSON 错误（含 missing 清单与修复提示）
    missing = [
        name for name, val in (
            ("--pr-url", args.pr_url), ("--pr-id", args.pr_id),
            ("--org", args.org), ("--repo", args.repo),
        ) if not val
    ]
    if missing:
        print(json.dumps({
            "error": "missing_required_args",
            "missing": missing,
            "hint": "四项可互推：传了 --pr-url 即可反解 org/repo/pr-id；"
                    "或传 --org --repo --pr-id 反拼 URL",
        }, ensure_ascii=False, indent=2))
        sys.exit(2)
    return args


def main(argv=None):
    args = parse_args(argv)
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

    # ── 双口径自检 ──
    # 全量且无失败文件时，审查覆盖应等于 PR 平台权威规模，不等则告警（不阻断，
    # 可能是截断/字段缺失；告警留痕供排查）。增量模式下两者口径不同，不比对。
    _ff = getattr(args, "_mode_failed_files", None) or []
    # 显式传参（存量流程兼容）优先于 mode_info 回填；回填值不参与自检比对
    _explicit_scale = not getattr(args, "_scale_backfilled", False)
    if args.cr_mode == "full" and not _ff and not _explicit_scale:
        _ps = getattr(args, "_pr_scale", None) or {}
        try:
            _pf, _pa, _pd = _ps.get("prFileNum"), _ps.get("prAdditions"), _ps.get("prDeletions")
            _ra, _rr = _parse_line_changes(getattr(args, "reviewed_line_changes", ""))
            if isinstance(_pf, int) and getattr(args, "reviewed_file_count", None) is not None \
                    and args.reviewed_file_count != _pf:
                log(f"⚠️ 双口径自检：reviewed_file_count={args.reviewed_file_count} ≠ 平台 file_num={_pf}（可能存在截断）")
            if isinstance(_pa, int) and isinstance(_pd, int) and _ra is not None and _rr is not None \
                    and (_ra, _rr) != (_pa, _pd):
                log(f"⚠️ 双口径自检：reviewed(+{_ra} -{_rr}) ≠ 平台(+{_pa} -{_pd})（可能存在截断或统计差异）")
        except Exception:
            pass

    # ── 加载与拼装 ──
    # run-id 软门禁化：缺失时自动生成并告警，不阻断发布；同轮重试应显式传同一值
    if not args.run_id:
        import uuid as _uuid
        args.run_id = "auto-" + _uuid.uuid4().hex[:16]
        log(f"⚠️ 软门禁: --run-id 未传, 已自动生成 {args.run_id} 继续发布; 同轮重试请显式传同一值以保幂等")

    issues = load_issues(args.issues_file)
    # 软门禁：issue_io 逐条校验，不阻塞发布；结果落盘供追溯，不合规条目降级处理
    issues = soft_gate_issues(args, issues)
    # ── 外部专项审查门禁: FAILED 不再等价零发现,必选失败拦结论 ──
    extan_checks, _extan_findings, extan_note, extan_meta = load_extan_checks(args.extan_status_file)
    # runId 匹配校验: 封装体是上一轮 PR 的陈旧残留时,checks 不得被本轮门禁误读
    if extan_checks:
        env_run = extan_meta.get("runId") or ""
        env_tc = extan_meta.get("targetCommit") or ""
        stale = None
        # ① prId 比对(runId 可解析时);不可解析(自定义 --query-id)则跳过,不整体失效
        if env_run and args.pr_id is not None:
            try:
                env_pr = int(str(env_run).split("#")[1].split("@")[0]) if "#" in str(env_run) else None
            except Exception:
                env_pr = None
            if env_pr is not None and env_pr != args.pr_id:
                stale = "runId-mismatch: 封装体 runId=%s 属于其他 PR(本轮 prId=%s)" % (env_run, args.pr_id)
        # ② targetCommit 比对(与①独立,同 PR 新 commit 的陈旧残留也拦;queryId 不可解析时同样生效)
        if not stale and env_tc and args.target_commit and env_tc != args.target_commit:
            stale = "targetCommit-mismatch: 封装体=%s 本轮=%s(同 PR 新 commit 或上一轮残留)" % (env_tc[:12], args.target_commit[:12])
        if stale:
            extan_checks = [{"analyzer": "stale-step4e", "status": "UNKNOWN",
                             "error": stale,
                             "required": True, "mode": "auto", "dropReasons": ["runid-mismatch"]}]
            extan_note = "step4e 封装体身份不匹配(疑似陈旧残留),按 UNKNOWN 拦截"
    extan_gate_ok, extan_gate_reason, extan_required_failed = evaluate_extan_gate(extan_checks, extan_note)
    counts = count_issues(issues)
    conclusion = derive_conclusion(counts, args.conclusion, extan_gate_ok, extan_gate_reason)

    log(f"📊 Issues: P0={counts['p0']} P1={counts['p1']} P2={counts['p2']} P3={counts['p3']} → {conclusion}")
    if not extan_gate_ok:
        log(f"⛔ 外部专项审查门禁拦截: {extan_gate_reason} → 结论强制: 核验未完成(不发布 ✅ 通过口径)")
    elif extan_note or extan_gate_reason != "外部专项审查全部完成":
        log(f"⚠️ 外部专项审查: {extan_gate_reason}")

    if args.dry_run:
        log("🧪 DRY-RUN 模式：Step 7/8/9 一律不执行，产物落盘 /tmp/cr_dryrun/")
    else:
        # 3 秒缓冲：给上游 code-cli 的登录态/连接池一点预热时间即可，
        # 无任何限流依据需要 20s（Step 内部已有各自的 retry 与退避）
        time.sleep(3)

    if issues:
        # 锚定校验与重定位：行号与代码证据校验，对不上时重定位。
        # 发布前锚定/快照统一计划：必须先于 assemble_citadel_doc /
        # assemble_inline_comments / assemble_global_comment 执行——
        # 快照双端校验（查询失败≠一致）、重拉重定位与降级决定完成后的最终行号
        # 同步进学城文档、PR 行内评论、全局评论与 cr_result，保证同一视图
        # 有一致位置；过晚漂移由 step7 发送前复核 + expected 冻结兜底
        # （只降低竞态窗口，不声称消除）
        issues = apply_anchor_validation(args, issues)
        _plan = plan_publish_anchors(args, issues)
        log(f"🧭 快照计划: {_plan.get('note', '')}（行内 {_plan['inline_ok']}"
            f" / 全局兜底 {_plan['global_fallback']}）")
        doc_md = assemble_citadel_doc(args, issues, counts, conclusion)
        inline_comments, inline_fallbacks = assemble_inline_comments(issues, cr_mode=args.cr_mode)
    elif args.findings_file and os.path.isfile(args.findings_file):
        # 兼容旧用法
        doc_md = read_text_file(args.findings_file, "")
        inline_comments = []
        inline_fallbacks = []
    else:
        doc_md = assemble_citadel_doc(args, issues, counts, conclusion)
        inline_comments = []
        inline_fallbacks = []

    output["counts"] = counts
    output["conclusion"] = conclusion

    # Step 6: 创建学城文档
    log("▶ Step 6: 创建学城 CR 文档...")
    if args.dry_run and not args.dry_run_doc:
        step6_result = {"ok": True, "km_url": f"https://km.sankuai.com/collabpage/DRYRUN_{args.pr_id}", "error": "", "dry_run": True}
        log(f"🧪 Step 6 DRY-RUN：跳过真实创建，km_url={step6_result['km_url']}")
        os.makedirs("/tmp/cr_dryrun", exist_ok=True)
        with open(f"/tmp/cr_dryrun/cr_review_{args.pr_id}.md", "w", encoding="utf-8") as f:
            f.write(doc_md)
    else:
        step6_result = step6_create_citadel_doc(args, doc_md)
    output["step6"] = step6_result
    km_url = step6_result.get("km_url", "")
    _capacity_warn = step6_result.get("capacity_warn", "") if isinstance(step6_result, dict) else ""

    # 全局评论需 km_url（Step 6 之后拼装）；无法行内锚定的 P0/P1 降级文本附到全局评论末尾
    global_text = assemble_global_comment(args, issues, counts, conclusion, km_url, inline_fallbacks=inline_fallbacks)

    # DRY-RUN：全局评论落盘
    if args.dry_run:
        os.makedirs("/tmp/cr_dryrun", exist_ok=True)
        with open(f"/tmp/cr_dryrun/global_comment_{args.pr_id}.md", "w", encoding="utf-8") as f:
            f.write(global_text)
        with open(f"/tmp/cr_dryrun/inline_comments_{args.pr_id}.json", "w", encoding="utf-8") as f:
            json.dump(inline_comments, f, ensure_ascii=False, indent=2)

    # Step 7: 评论到 PR
    log("▶ Step 7: 评论到 PR...")
    # 固化 P0/P1 总数口径，供 step7 发送后改写全局评论头部
    # 「已作为行内评论标注」声明（含未进入行内计划的兜底条目）
    args._p0p1_total = sum(1 for it in issues
                           if isinstance(it, dict)
                           and _inline_severity(it) in ("P0", "P1"))
    if args.dry_run:
        step7_result = {"ok": True, "inline_count": len(inline_comments), "global_ok": True, "error": "", "dry_run": True}
        log(f"🧪 Step 7 DRY-RUN：跳过 {len(inline_comments)} 条行内 + 1 条全局评论")
    else:
        step7_result = step7_comment_to_pr(args, inline_comments, global_text)
    output["step7"] = step7_result

    # Step 8: 大象群推送
    log("▶ Step 8: 大象群推送...")
    message_text = assemble_daxiang_message(args, issues, counts, conclusion, km_url)
    if _capacity_warn:
        message_text = message_text + "\n\n" + _capacity_warn
    if args.dry_run:
        with open(f"/tmp/cr_dryrun/daxiang_msg_{args.pr_id}.md", "w", encoding="utf-8") as f:
            f.write(message_text)
        step8_result = {"ok": True, "global_group_ok": True, "team_group_ok": True, "error": "", "dry_run": True}
        log("🧪 Step 8 DRY-RUN：跳过大象推送")
    else:
        step8_result = step8_daxiang_push(args, message_text)
    output["step8"] = step8_result

    # Step 9: 回写结构化 CR 结果到 cr_task（会话 ID 自动读环境变量 X_AI_SESSIONID → rootConversationId）
    log("▶ Step 9: 回写 CR 结果...")
    summary_parts = split_summary_file(read_text_file(args.summary_file, ""))
    cr_result = build_cr_result(args, issues, counts, conclusion, km_url, summary_parts=summary_parts)
    if args.dry_run:
        with open(f"/tmp/cr_dryrun/cr_result_{args.pr_id}.json", "w", encoding="utf-8") as f:
            json.dump(cr_result, f, ensure_ascii=False, indent=2)
        step9_result = {"ok": True, "skipped": True, "status": "dry-run", "error": "", "dry_run": True}
        log("🧪 Step 9 DRY-RUN：cr_result 落盘 /tmp/cr_dryrun/，不回写")
    else:
        step9_result = step9_submit_cr_result(args, cr_result)
    output["step9"] = step9_result

    log("=" * 60)
    log("发布结果脚本完成")
    log("=" * 60)

    print(json.dumps(output, ensure_ascii=False))
    # 退出码：学城文档(6)与 cr_task 回写(9)为准入门槛；
    # PR 评论(7)与大象推送(8)是广播通道，其一成功即视为有效触达，
    # 全部失败才整体判负（重跑由同 runId 幂等 + 评论去重兜底，不会重复发布）
    return 0 if all(output[step].get("ok") for step in ("step6", "step9")) and (
        output["step7"].get("ok") or output["step8"].get("ok")
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
