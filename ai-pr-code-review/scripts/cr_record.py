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
    --pr-url "https://dev.sankuai.com/code/repo-detail/fun/scp-dzbiz-process-server/pr/1278/overview" \
    --repo "fun/scp-dzbiz-process-server" \
    --pr-title "放心美履约保障" \
    --author-mis "wb_luanchaoshun" \
    --conclusion "🟠需修复" \
    --p0 1 --p1 4 --p2 6 --p3 2 \
    --doc-url "https://km.sankuai.com/collabpage/2776473886" \
    --operator-mis "mengmuzi" \
    --source-branch "feature/fangxinmei" \
    --target-branch "master" \
    --no-sdd --alignment "N/A" \
    --skill-version "ai-pr-code-review"  # 版本号由脚本自动从 SKILL.md 读取 \
    --org-id "103461" \
    --table-id "2757772610"
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

# 动态从 SKILL.md frontmatter 读取 skillhub.version
import re as _re
import os as _os
_SKILL_MD_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "SKILL.md")
try:
    with open(_SKILL_MD_PATH, "r", encoding="utf-8") as _f:
        _content = _f.read()
    _m = _re.search(r'skillhub\.version:\s*"(V\d+)"', _content)
    _SKILL_VER = _m.group(1) if _m else ""
except Exception:
    _SKILL_VER = ""

# ── 配置 ────────────────────────────────────────────────────────────────────
DB_HOST = "33.18.123.212:8098"
DB_PATH = "/api/aicr/submit-task"
DB_TIMEOUT = 20

DEFAULT_TABLE_ID = "2751197605"
DEFAULT_ORG_PATH = "美团/核心本地商业/业务研发平台/业务系统平台部"

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

def write_db(args):
    """调用 DB API 写入 cr_task 表。"""
    # 构造 cr_result_json
    cr_result = {
        "conclusion": args.conclusion,
        "counts": {
            "p0": args.p0,
            "p1": args.p1,
            "p2": args.p2,
            "p3": args.p3,
        },
        "is_sdd": args.is_sdd,
        "text_code_consistency_rate": args.alignment,
        "skill_version": args.skill_version,
    }

    # 构造 cr_report（从文件读取或直接用）
    cr_report = None
    if args.cr_report_file and os.path.isfile(args.cr_report_file):
        try:
            with open(args.cr_report_file, "r", encoding="utf-8") as f:
                cr_report = f.read()
        except IOError:
            pass

    # 构造 payload
    payload = {
        "pr_url": args.pr_url,
        "author_mis": args.author_mis,
        "source_branch": args.source_branch,
        "target_branch": args.target_branch,
        "trigger_source": "skills",
        "trigger_event": "manual",
        "cr_result_json": json.dumps(cr_result, ensure_ascii=False),
    }
    if cr_report:
        payload["cr_report"] = cr_report

    # 发送 HTTP POST
    url = f"{args.scheme}://{args.host}{DB_PATH}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    # 代理处理
    if args.no_proxy:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    # SSL 处理
    context = None
    if args.scheme == "https":
        import ssl
        context = ssl.create_default_context()
        if args.insecure or not args.host.endswith(".sankuai.com"):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        if context:
            opener.add_handler(urllib.request.HTTPSHandler(context=context))

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
    p.add_argument("--skill-version", default=f"ai-pr-code-review {_SKILL_VER}".strip(), help="Skill 版本标识（自动从 SKILL.md 读取版本号）")
    p.add_argument("--cr-report-file", default="", help="CR 报告文件路径（DB 存储用）")

    # 多维表格专属
    p.add_argument("--org-id", default="", help="组织架构 orgId（纯数字）")
    p.add_argument("--table-id", default="", help="多维表格 ID")
    p.add_argument("--remark", default="", help="备注（默认填 skill-version）")

    # DB 连接
    p.add_argument("--host", default=DB_HOST, help=f"DB 主机（默认 {DB_HOST}）")
    p.add_argument("--scheme", default="http", choices=["http", "https"], help="协议")
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
