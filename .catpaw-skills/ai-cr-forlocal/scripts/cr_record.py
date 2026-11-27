#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cr_record.py — AI-CR 记录写入脚本（Step 9 专用）

职责：
  1. 优先调用 DB API（aicr submit-task）写入 cr_task 表
  2. DB 失败 → 降级到多维表格 addData
  3. 全部失败 → 输出错误，AI 再通知提交人

AI 只需调这一条命令，传业务参数即可。
不接触 columnIds / data JSON / 时间戳计算等脆弱操作。

用法:
  python3 cr_record.py \
    --pr-url "https://dev.sankuai.com/code/repo-detail/<org>/<repo>/pr/0/overview?branch=<branch>" \
    --repo "<org>/<repo>" \
    --pr-title "<标题>" \
    --author-mis "<MIS>" \
    --conclusion "🟠需修复" \
    --p0 <n> --p1 <n> --p2 <n> --p3 <n> \
    --doc-url "<学城文档 URL>" \
    --operator-mis "<MIS>" \
    --source-branch "<branch>" --target-branch "master"
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ── 配置 ────────────────────────────────────────────────────────────────────
DB_HOST = "spt.sankuai.com"
DB_PATH = "/api/v1/aicr/submit-task"
DB_TIMEOUT = 20

DEFAULT_TABLE_ID = "2751197605"  # 降级多维表格兜底，可由 cr-config.yaml table_id 覆盖

MAX_RETRIES = 4
RETRY_INTERVAL = 2  # seconds

# 多维表格列 ID（固定，与 table-write-guide.md 一致）
# 列1=日期, 列2=PR链接, 列3=仓库名, 列4=PR标题, 列5=提交人MIS,
# 列6=组织架构, 列7=结论, 列8=P0, 列9=P1, 列11=学城URL, 列12=备注
TABLE_COLUMN_IDS = "1,2,3,4,5,6,7,8,9,11,12"


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def run_cmd(cmd, timeout=120):
    """执行外部命令，返回 (returncode, stdout, stderr)。"""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=os.environ, shell=False
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        # oa-skills 输出在 stderr，stdout 为空时 fallback
        if not out and err:
            out = err
        return r.returncode, out, err
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 125, "", str(e)


def retry(fn, retries=MAX_RETRIES, interval=RETRY_INTERVAL):
    """重试包装器，返回 (result, error)。result 为 None 表示全部失败。"""
    last_err = ""
    for i in range(retries):
        try:
            return fn(), None
        except Exception as e:
            last_err = str(e)
            if i < retries - 1:
                time.sleep(interval)
    return None, last_err


# ── 路径 A：DB 写入 ──────────────────────────────────────────────────────────

def _expand_rids(it):
    """将 issue 的 ruleId 拆分为列表（处理合并情况）"""
    merged = it.get("mergedRuleIds", [])
    if merged:
        return merged
    rid = it.get("ruleId", "") or ""
    if "+" in rid:
        return [p.strip() for p in rid.split("+")]
    return [rid] if rid else []


# 技术栈由审查 Agent 根据模块证据确定，发布阶段只校验显式值。
VALID_TECH_STACKS = ["java", "nodejs", "mrn", "max", "miniprogram", "duo", "react",
                     "android", "ios", "harmony", "native", "flutter", "unknown"]


def _resolve_tech_stack(args):
    """规范化显式判定；缺失或非法值登记 unknown。"""
    explicit = (getattr(args, "tech_stack", "") or "").strip().lower()
    if explicit in VALID_TECH_STACKS:
        return explicit
    print("⚠️ 技术栈缺失或不在支持值域内，登记 unknown；需核对本轮模块证据")
    return "unknown"


def _build_doc_issues(issues, extra_fields):
    """结构化逐条 issue 列表（覆盖学城文档展示的全部字段，含 confirm 专属字段）。
    与 ai-quality-cr-agent publish_results.py 的同名函数保持一致。"""
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
    """结构化「规则命中摘要」。与 ai-quality-cr-agent publish_results.py 的同名函数保持一致。"""
    if not issues:
        return {}
    p0_rules = sorted(set(r for it in issues if it.get("severity") == "P0" for r in _expand_rids(it)))
    p1_rules = sorted(set(r for it in issues if it.get("severity") == "P1" for r in _expand_rids(it)))
    p2_rules = sorted(set(r for it in issues if it.get("severity") == "P2" for r in _expand_rids(it)))
    p3_rules = sorted(set(r for it in issues if it.get("severity") == "P3" for r in _expand_rids(it)))
    confirm_count = len([it for it in issues if it.get("severity") == "confirm"])

    cr_count = mt_count = cu_count = fe_count = 0
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
            elif r.startswith("FE:"):
                fe_count += 1
    if cr_count == 0 and mt_count == 0 and cu_count == 0 and fe_count == 0:
        cr_count = len([it for it in issues if it.get("source") == "step4a"])
        mt_count = len([it for it in issues if it.get("source") == "step4b"])
        cu_count = len([it for it in issues if it.get("source") == "step4c"])
        fe_count = len([it for it in issues if it.get("source") in ("fe_review", "fe-ai-review")])

    return {
        "total_rules": len(set(all_rids)),
        "cr_rule_count": cr_count,
        "mt_rule_count": mt_count,
        "cu_rule_count": cu_count,
        "fe_rule_count": fe_count,
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


def _resolve_ones_fields(args):
    """解析 ONES 四字段（供 overview + 顶层 payload 共用）。

    id/url 由上游显式传参；name/type 缺省从 /tmp/cr_ones_db_info.json
    （prep 1B `ones workitem-detail` 产出）自动补；ones_id 非纯数字一律判
    无效（项目内键如 FEVUO-xxx 的尾号为项目内序号，非全局 ID，误用会关联
    到无关工作项）。
    返回 (ones_id_int, ones_url, ones_type, ones_name)。
    """
    ones_id = (getattr(args, "ones_id", None) or "").strip()
    ones_url = (getattr(args, "ones_url", None) or "").strip()
    ones_type = (getattr(args, "ones_type", None) or "").strip()
    ones_name = (getattr(args, "ones_name", None) or "").strip()
    if not (ones_type and ones_name) or not ones_id:
        try:
            with open("/tmp/cr_ones_db_info.json", "r", encoding="utf-8") as f:
                dbinfo = json.load(f)
            ones_type = ones_type or str(dbinfo.get("onesType", "") or "")
            ones_name = ones_name or str(dbinfo.get("onesName", "") or "")
            if not ones_id:
                ones_id = str(dbinfo.get("onesId", "") or "")
            if not ones_url:
                ones_url = str(dbinfo.get("onesUrl", "") or "")
        except Exception:
            pass
    ones_id_int = int(ones_id) if (ones_id.isdigit() and len(ones_id) < 15) else None
    return ones_id_int, ones_url, ones_type, ones_name


def _build_cr_result_json(args, issues):
    """构造 cr_result_json —— 与 ai-quality-cr-agent publish_results.py 的 build_cr_result 对齐。

    counts 在 P0~P3 计数基础上补充变更规模信息；issues 为全量结构化明细
    （P0~P3 + confirm，覆盖文档展示的全部字段）；含规则命中摘要、自定义规则
    子节与本地 CR 概述（本地模式无 PR，pr_id/pr_url 等字段置空/伪值对齐结构）。
    """
    # issues 规范化 severity（publish_results_local.load_issues 已去重，这里只补缺省）
    for it in issues:
        if not isinstance(it, dict):
            continue
        sev = (it.get("severity") or "P2").strip()
        sl = sev.lower()
        it["severity"] = "confirm" if sl == "confirm" else ("dismissed" if sl == "dismissed" else sev.upper())

    p0 = sum(1 for it in issues if it.get("severity") == "P0")
    p1 = sum(1 for it in issues if it.get("severity") == "P1")
    p2 = sum(1 for it in issues if it.get("severity") == "P2")
    p3 = sum(1 for it in issues if it.get("severity") == "P3")

    counts = {
        "p0": p0, "p1": p1, "p2": p2, "p3": p3,
        "changedFiles": getattr(args, "file_count", None) or 0,
        "additions": getattr(args, "added_lines", None) or 0,
        "deletions": getattr(args, "removed_lines", None) or 0,
    }

    is_sdd = bool(getattr(args, "is_sdd", False))
    consistency_rate = (getattr(args, "alignment", None) or "").strip()
    if consistency_rate == "N/A":
        consistency_rate = ""

    org, _, repo_name = (args.repo or "").partition("/")
    overview = {
        "org": org,
        "repo": repo_name,
        "pr_id": 0,
        "pr_title": getattr(args, "pr_title", "") or "",
        "submitter_mis": getattr(args, "operator_mis", "") or "",
        "author_name": "",
        "trigger_mis": getattr(args, "operator_mis", "") or "",
        "trigger_name": "",
        "branch": getattr(args, "source_branch", "") or "",
        "file_count": getattr(args, "file_count", None),
        "line_changes": getattr(args, "line_changes", "") or "",
        "added_lines": getattr(args, "added_lines", None),
        "removed_lines": getattr(args, "removed_lines", None),
        "total_changed_lines": ((getattr(args, "added_lines", 0) or 0) + (getattr(args, "removed_lines", 0) or 0))
                                if (getattr(args, "added_lines", None) is not None or getattr(args, "removed_lines", None) is not None) else None,
        "cr_mode": "full",  # 本地分支模式固定全量
        "base_commit": None,
        "target_commit": None,
        "commit_count": None,
        "skill_version": getattr(args, "skill_version", ""),
    }
    # ONES 工作项关联（与 agent 版对齐；id 无效时四键置 None，后端不更新列）
    ov_id, ov_url, ov_type, ov_name = _resolve_ones_fields(args)
    overview.update({
        "ones_id": ov_id,
        "ones_type": ov_type if ov_id is not None else None,
        "ones_url": ov_url if ov_id is not None else None,
        "ones_name": ov_name if ov_id is not None else None,
    })

    cr_result = {
        "pr_id": 0,                     # 本地模式无 PR，置 0 对齐结构
        "org": org,
        "repo": repo_name,
        "pr_title": getattr(args, "pr_title", "") or "",
        "pr_url": args.pr_url,          # 伪 PR URL（pr/0?branch=...）
        "conclusion": args.conclusion,
        "counts": counts,
        "is_sdd": is_sdd,
        "text_code_consistency_rate": consistency_rate if is_sdd else "",
        "skill_version": getattr(args, "skill_version", ""),
        "tech_stack": _resolve_tech_stack(args),
        "km_url": getattr(args, "doc_url", "") or "",
        "review_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "issues": _build_doc_issues(
            issues,
            ("reach_analysis", "online_scenario", "impact_scope",
             "confirm_reason", "possible_risk", "confirm_suggestion"),
        ),
        # ── 文档章节内容铺平（对齐 agent 版）──
        "doc_title": getattr(args, "pr_title", "") or "",
        "overview": overview,
        "change_summary": getattr(args, "overview_text", "") or "",
        "changed_files": getattr(args, "changed_files_list", None) or [],
        "sdd_check": {
            "is_sdd": is_sdd,
            "consistency_rate": consistency_rate if is_sdd else "",
            "content": getattr(args, "sdd_content", "") or "",
        },
        "rule_hit_summary": _build_rule_hit_summary_data(issues),
        "custom_rules": _build_custom_rules_data(issues),
        "overall_eval": getattr(args, "overall_eval", "") or "",
        "manual_review": getattr(args, "manual_review", "") or "",
    }
    return cr_result


def write_db(args):
    """调用 DB API 写入 cr_task 表。"""
    # issues 明细：从 --issues-file 读取 JSON 数组
    issues = []
    if getattr(args, "issues_file", "") and os.path.isfile(args.issues_file):
        try:
            with open(args.issues_file, "r", encoding="utf-8") as f:
                issues = json.load(f)
            if not isinstance(issues, list):
                issues = []
        except Exception:
            issues = []

    # 构造 cr_result_json（与 ai-quality-cr-agent publish_results.py 的 build_cr_result 对齐）
    cr_result = _build_cr_result_json(args, issues)

    # 构造 cr_report（从文件读取或直接用）
    cr_report = None
    if args.cr_report_file and os.path.isfile(args.cr_report_file):
        try:
            with open(args.cr_report_file, "r", encoding="utf-8") as f:
                cr_report = f.read()
        except IOError:
            pass

    # 构造 payload（trigger_source/trigger_event 可选覆盖；ones 四字段随报）
    ones_id_int, ones_url, ones_type, ones_name = _resolve_ones_fields(args)
    payload = {
        "pr_url": args.pr_url,
        "author_mis": args.author_mis,
        "source_branch": args.source_branch,
        "target_branch": args.target_branch,
        "trigger_source": (getattr(args, "trigger_source", None) or "").strip() or "forlocal",
        "trigger_event": (getattr(args, "trigger_event", None) or "").strip() or "sdlc",
        "cr_result_json": json.dumps(cr_result, ensure_ascii=False),
    }
    if ones_id_int is not None:
        payload["ones_id"] = ones_id_int
        if ones_url:
            payload["ones_url"] = ones_url
        if ones_type:
            payload["ones_type"] = ones_type
        if ones_name:
            payload["ones_name"] = ones_name
    if cr_report:
        payload["cr_report"] = cr_report

    # 发送 HTTP POST
    url = f"{args.scheme}://{args.host}{DB_PATH}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    # 代理 + SSL 处理（HTTPSHandler 需在 build_opener 时传入，事后 add_handler 会被默认 https handler 优先级抢占）
    import ssl

    def _make_opener(skip_verify):
        """构造 opener。skip_verify=True 时跳过证书校验。"""
        context = None
        if args.scheme == "https":
            context = ssl.create_default_context()
            if skip_verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
        handlers = []
        if args.no_proxy:
            handlers.append(urllib.request.ProxyHandler({}))
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        return urllib.request.build_opener(*handlers)

    # 内网服务（*.sankuai.com）大量开发机 Python 无内网 CA 信任链，CERTIFICATE_VERIFY_FAILED
    # 是常态而非异常。策略：默认先严格校验，失败自动降级跳过校验重试一次，无需用户传 --insecure。
    opener = _make_opener(skip_verify=args.insecure)

    def _db_write():
        with opener.open(req, timeout=DB_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        if status != 200:
            raise RuntimeError(f"DB HTTP {status}: {body}")

        # 解析响应检查业务错误
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

    result, err = retry(_db_write)
    # SSL 证书校验失败自动降级：开发机 Python 普遍缺内网 CA，属环境问题而非安全问题
    # （目标为 *.sankuai.com 内网服务）。跳过校验重试一轮，免除全员手动加 --insecure。
    if result is None and err and "CERTIFICATE_VERIFY_FAILED" in str(err) and not args.insecure:
        print("   ⚠️  SSL 证书校验失败（本机缺内网 CA），自动降级跳过校验重试")
        opener_ssl_fallback = _make_opener(skip_verify=True)

        def _db_write_noverify(opener_ssl_fallback=opener_ssl_fallback):
            with opener_ssl_fallback.open(req, timeout=DB_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.status
            if status != 200:
                raise RuntimeError(f"DB HTTP {status}: {body}")
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

        result, err = retry(_db_write_noverify)
    if result is not None:
        # 尝试提取记录 ID
        record_id = ""
        try:
            body_json = json.loads(result)
            record_id = body_json.get("id", body_json.get("data", {}).get("id", ""))
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return {"status": "success", "method": "db", "record_id": record_id, "error": ""}
    return {"status": "failed", "method": "db", "error": err}


# ── 路径 B：多维表格降级写入 ─────────────────────────────────────────────────

def write_table(args):
    """降级到多维表格 addData 写入。"""
    table_id = args.table_id or DEFAULT_TABLE_ID
    operator_mis = args.operator_mis or args.author_mis

    # 1. getTableMeta（刷新 schema，失败不阻塞继续）
    def _get_table_meta():
        cmd = [
            "oa-skills", "citadel-database", "getTableMeta",
            "--tableId", table_id, "--mis", operator_mis,
        ]
        rc, out, err = run_cmd(cmd, timeout=60)
        if rc != 0:
            raise RuntimeError(f"getTableMeta failed (rc={rc}): {err or out}")
        return out

    _, meta_err = retry(_get_table_meta)
    # 即使 getTableMeta 失败也继续尝试 addData

    # 2. addData 写入
    def _add_data():
        # 计算今日 0 点毫秒时间戳（脚本内部算，不依赖 AI）
        now_midnight = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        date_ms = int(now_midnight.timestamp() * 1000)
        # 时间戳校验
        assert len(str(date_ms)) == 13 and date_ms > 1735660800000, \
            f"timestamp validation failed: {date_ms}"

        # 结论校验
        assert args.conclusion.startswith(("✅", "💚", "🟠", "🔴")), \
            f"invalid conclusion: {args.conclusion}"

        # 备注：优先用 --remark，否则用 skill-version
        remark = args.remark or args.skill_version

        # org_id 校验：必须纯数字或空字符串
        org_id = args.org_id or ""
        if org_id and not org_id.isdigit():
            # 如果传入的不是数字（如组织路径），留空
            org_id = ""

        # 构造 data（二维数组，与 TABLE_COLUMN_IDS 对齐）
        data_value = json.dumps([[
            date_ms,          # 列1: 日期
            args.pr_url,      # 列2: PR链接
            args.repo,        # 列3: 仓库名
            args.pr_title,    # 列4: PR标题
            args.author_mis,  # 列5: 提交人MIS
            org_id,           # 列6: 组织架构orgId
            args.conclusion,  # 列7: 结论
            args.p0,          # 列8: P0
            args.p1,          # 列9: P1
            args.doc_url,     # 列11: 学城URL
            remark,           # 列12: 备注
        ]], ensure_ascii=False)

        cmd = [
            "oa-skills", "citadel-database", "addData",
            "--tableId", table_id,
            "--columnIds", TABLE_COLUMN_IDS,
            "--mis", operator_mis,
            "--data", data_value,
        ]
        rc, out, err = run_cmd(cmd, timeout=60)
        if rc != 0:
            raise RuntimeError(f"addData failed (rc={rc}): {err or out}")
        return out

    result, err = retry(_add_data)
    if result is not None:
        return {"status": "degraded", "method": "table", "error": ""}
    return {"status": "failed", "method": "table", "error": err}


# ── 主函数 ───────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="AI-CR 记录写入脚本（DB 优先，多维表格降级）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 必填（DB + 多维表格都需要）
    p.add_argument("--pr-url", required=True, help="PR 链接")
    p.add_argument("--repo", required=True, help="仓库 (org/repo)")
    p.add_argument("--pr-title", required=True, help="PR 标题")
    p.add_argument("--author-mis", required=True, help="提交人 MIS")
    p.add_argument("--conclusion", required=True,
                   help="结论：✅通过 / 💚通过有建议 / 🟠需修复 / 🔴需重新设计")
    p.add_argument("--p0", type=int, required=True, help="P0 问题数")
    p.add_argument("--p1", type=int, required=True, help="P1 问题数")
    p.add_argument("--p2", type=int, required=True, help="P2 问题数")
    p.add_argument("--p3", type=int, required=True, help="P3 问题数")
    p.add_argument("--doc-url", required=True, help="学城文档 URL")
    p.add_argument("--operator-mis", required=True, help="操作人 MIS（用于多维表格 --mis）")

    # DB 专属
    p.add_argument("--source-branch", default="", help="源分支")
    p.add_argument("--target-branch", default="", help="目标分支")
    p.add_argument("--is-sdd", action="store_true", default=False, help="是否 SDD 流程")
    p.add_argument("--no-sdd", action="store_false", dest="is_sdd", default=False, help="非 SDD 流程")
    p.add_argument("--alignment", default="N/A", help="文本/代码一致性率")
    p.add_argument("--skill-version", default="ai-pr-code-review-testn", help="Skill 版本标识")
    p.add_argument("--cr-report-file", default="", help="CR 报告文件路径（DB 存储用）")
    p.add_argument("--issues-file", default="", help="issues 明细 JSON 文件路径（JSON 数组，写入 cr_result_json.issues）")
    # cr_result_json 对齐字段（ai-quality-cr-agent build_cr_result 同构）
    p.add_argument("--file-count", type=int, default=None, help="变更文件数（counts.changedFiles / overview.file_count）")
    p.add_argument("--line-changes", default="", help="行数变化如 +120 -30（overview.line_changes 原样透传）")
    p.add_argument("--added-lines", type=int, default=None, help="新增行数（counts.additions / overview.added_lines）")
    p.add_argument("--removed-lines", type=int, default=None, help="删除行数（counts.deletions / overview.removed_lines）")
    p.add_argument("--overview-text", default="", help="变更综述（cr_result_json.change_summary）")
    p.add_argument("--overall-eval", default="", help="总体评价（cr_result_json.overall_eval）")
    p.add_argument("--manual-review", default="", help="人工复审要点（cr_result_json.manual_review）")
    p.add_argument("--sdd-content", default="", help="SDD 校验章节内容（cr_result_json.sdd_check.content）")
    p.add_argument("--changed-files-list", default=None, help="变更文件清单 JSON 数组字符串（cr_result_json.changed_files）")
    p.add_argument("--tech-stack", default="",
                  help="技术栈（java/nodejs/mrn/max/miniprogram/duo/react/android/ios/harmony/native/flutter/unknown；缺失或非法值登记 unknown）")

    # 多维表格专属
    p.add_argument("--org-id", default="", help="组织架构 orgId（纯数字）")
    p.add_argument("--table-id", default="", help="多维表格 ID")
    p.add_argument("--remark", default="", help="备注（默认填 skill-version）")
    # ONES 工作项关联 + 触发源覆盖
    p.add_argument("--ones-id", default="", help="ONES 工作项全局 ID（纯数字）")
    p.add_argument("--ones-url", default="", help="ONES 工作项链接")
    p.add_argument("--ones-type", default="", help="ONES 工作项类型（缺省自动补齐）")
    p.add_argument("--ones-name", default="", help="ONES 工作项标题（缺省自动补齐）")
    p.add_argument("--trigger-source", default="", help="触发来源覆盖（默认 forlocal；ADC 触发传 adc）")
    p.add_argument("--trigger-event", default="", help="触发事件覆盖（默认 sdlc）")

    # DB 连接
    p.add_argument("--host", default=DB_HOST, help=f"DB 主机（默认 {DB_HOST}）")
    p.add_argument("--scheme", default="https", choices=["http", "https"], help="协议")
    p.add_argument("--no-proxy", action="store_true", help="不走代理，直连内网 IP")
    p.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验")

    # 调试
    p.add_argument("--dry-run", action="store_true", help="只打印参数，不执行写入")
    p.add_argument("--table-only", action="store_true", help="跳过 DB，直接写多维表格")

    return p.parse_args()


def main():
    args = parse_args()

    print(f"🚀 cr_record.py 启动")
    print(f"   PR: {args.repo} | 结论: {args.conclusion} | P0:{args.p0} P1:{args.p1} P2:{args.p2} P3:{args.p3}")

    if args.dry_run:
        print(f"\n🧪 DRY-RUN 模式，参数概览：")
        print(f"   pr_url:        {args.pr_url}")
        print(f"   repo:          {args.repo}")
        print(f"   pr_title:      {args.pr_title}")
        print(f"   author_mis:    {args.author_mis}")
        print(f"   conclusion:    {args.conclusion}")
        print(f"   doc_url:       {args.doc_url}")
        print(f"   operator_mis:  {args.operator_mis}")
        print(f"   source_branch: {args.source_branch}")
        print(f"   target_branch: {args.target_branch}")
        print(f"   is_sdd:        {args.is_sdd}")
        print(f"   alignment:     {args.alignment}")
        print(f"   skill_version: {args.skill_version}")
        print(f"   org_id:        {args.org_id}")
        print(f"   table_id:      {args.table_id or DEFAULT_TABLE_ID}")
        print(f"   remark:        {args.remark or args.skill_version}")
        print(f"   host:          {args.host}")
        print(f"   table_only:    {args.table_only}")
        return

    # ── 路径选择 ────────────────────────────────────────────────────────────
    result = None

    if not args.table_only:
        # 1. 先试 DB
        print(f"\n📝 路径 A：DB 写入 ({args.host})...")
        result = write_db(args)

        if result["status"] == "success":
            record_id = result.get("record_id", "")
            print(f"✅ DB 写入成功" + (f"，记录 ID: {record_id}" if record_id else ""))
            print(f"\n📋 结果: {json.dumps(result, ensure_ascii=False)}")
            sys.exit(0)

        print(f"❌ DB 写入失败: {result['error']}")
        print(f"\n📝 路径 B：降级到多维表格写入...")

    else:
        print(f"\n📝 直接写多维表格（--table-only）...")

    # 2. 降级到多维表格
    result2 = write_table(args)

    if result2["status"] in ("success", "degraded"):
        method = result2["method"]
        if method == "table":
            print(f"✅ 多维表格写入成功（{'降级' if not args.table_only else '直写'}）")
        print(f"\n📋 结果: {json.dumps(result2, ensure_ascii=False)}")
        sys.exit(0)

    print(f"❌ 多维表格写入失败: {result2['error']}")

    # 全部失败
    final_result = {
        "db": result,
        "table": result2,
    }
    print(f"\n❌ 全部失败！")
    print(f"📋 结果: {json.dumps(final_result, ensure_ascii=False)}")
    sys.exit(2)


if __name__ == "__main__":
    main()
