#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用 AICR submit-task 接口往 cr_task 表写入一条记录。

两种用法：

1. 离散参数（推荐，脚本自动构造 cr_result_json）：
  python scripts/aicr_submit_task.py \
      --pr-url "https://dev.sankuai.com/code/repo-detail/FUN/sku-operation-server/pr/80/overview" \
      --author-mis zengjiantao --source-branch feature/x --target-branch master \
      --cr-report-file ${CR_TMP_DIR:-/tmp}/cr_global_comment_80.txt \
      --conclusion "💚通过有建议" --p0 0 --p1 0 --p2 3 --p3 0 \
      --is-sdd --alignment "85%" \
      --skill-version "ai-pr-code-review-test V18.5" \
      --scheme http --no-proxy

2. 完整 JSON（fallback，覆盖离散参数）：
  python scripts/aicr_submit_task.py \
      --pr-url "..." --cr-result '{"conclusion":"...","counts":{...},...}'

cr_result_json 结构：
  {
    "conclusion": "💚通过有建议",
    "counts": {"p0": 0, "p1": 0, "p2": 3, "p3": 0},
    "is_sdd": true,
    "text_code_consistency_rate": "85%",
    "skill_version": "ai-pr-code-review-test V18.5"
  }
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_HOST = "spt.sankuai.com"
PATH = "/api/aicr/submit-task"
TIMEOUT = 20
DEFAULT_SCHEME = "https"


def build_cr_result(args):
    """从离散参数构造 cr_result_json，如果传了 --cr-result 则直接用。"""
    if args.cr_result is not None:
        return args.cr_result
    # 任一离散参数存在才构造
    has_discrete = any([args.conclusion is not None, args.p0 is not None,
                         args.p1 is not None, args.p2 is not None, args.p3 is not None,
                         args.is_sdd is not None, args.alignment is not None,
                         args.skill_version is not None])
    if not has_discrete:
        return None
    result = {}
    if args.conclusion is not None:
        result["conclusion"] = args.conclusion
    counts = {}
    for level in ("p0", "p1", "p2", "p3"):
        val = getattr(args, level)
        if val is not None:
            counts[level] = val
    if counts:
        result["counts"] = counts
    if args.is_sdd is not None:
        result["is_sdd"] = args.is_sdd
    if args.alignment is not None:
        result["text_code_consistency_rate"] = args.alignment
    if args.skill_version is not None:
        result["skill_version"] = args.skill_version
    # issues 明细：从 --issues-file 读取 JSON 数组，直接透传
    if args.issues_file:
        try:
            with open(args.issues_file, "r", encoding="utf-8") as f:
                issues_data = json.load(f)
            if isinstance(issues_data, list):
                result["issues"] = issues_data
        except Exception:
            pass
    return json.dumps(result, ensure_ascii=False)


def build_payload(args):
    payload = {"pr_url": args.pr_url}
    if args.author_mis is not None:
        payload["author_mis"] = args.author_mis
    if args.source_branch is not None:
        payload["source_branch"] = args.source_branch
    if args.target_branch is not None:
        payload["target_branch"] = args.target_branch
    if args.trigger_source is not None:
        payload["trigger_source"] = args.trigger_source
    if args.trigger_event is not None:
        payload["trigger_event"] = args.trigger_event
    if args.cr_report is not None:
        payload["cr_report"] = args.cr_report
    cr_result = build_cr_result(args)
    if cr_result is not None:
        payload["cr_result_json"] = cr_result

    return payload


def submit(host, payload, scheme="https", insecure_skip_verify=False, no_proxy=False):
    url = f"{scheme}://{host}{PATH}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    # 处理代理：内网 IP 直连不走代理
    if no_proxy:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()
    # HTTPS 才需要 SSL context
    context = None
    if scheme == "https":
        import ssl
        context = ssl.create_default_context()
        if insecure_skip_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
    try:
        if context:
            opener.add_handler(urllib.request.HTTPSHandler(context=context))
        with opener.open(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def main():
    p = argparse.ArgumentParser(description="调用 AICR submit-task 写入 cr_task 记录")
    p.add_argument("--host", default=DEFAULT_HOST, help=f"目标主机（默认 {DEFAULT_HOST}）")
    p.add_argument("--pr-url", required=True, help="PR 链接（必填），格式 .../code/repo-detail/<project>/<repo>/pr/<prId>/overview")
    p.add_argument("--author-mis", default=None)
    p.add_argument("--source-branch", default=None)
    p.add_argument("--target-branch", default=None)
    p.add_argument("--trigger-source", default=None, help="触发源，缺省自动从 X_AI_SOURCE 环境变量获取")
    p.add_argument("--trigger-event", default=None, help="触发事件，如 manual / agent / code-cli")
    p.add_argument("--cr-report", default=None, help="cr_report 文本（短文本可直接传，长文本请用 --cr-report-file）")
    p.add_argument("--cr-report-file", default=None, help="从文件读取 cr_report 内容（优先于 --cr-report）")
    p.add_argument("--cr-result", default=None,
                   help="完整 cr_result JSON 字符串（fallback，优先于离散参数）")
    # 离散参数（脚本自动构造 cr_result_json）
    p.add_argument("--conclusion", default=None, help="CR 结论，如 ✅通过 / 💚通过有建议 / 🟠需修复 / 🔴需重新设计")
    p.add_argument("--p0", type=int, default=None, help="P0 问题数")
    p.add_argument("--p1", type=int, default=None, help="P1 问题数")
    p.add_argument("--p2", type=int, default=None, help="P2 问题数")
    p.add_argument("--p3", type=int, default=None, help="P3 问题数")
    p.add_argument("--is-sdd", action="store_true", default=None, help="是否 SDD 流程")
    p.add_argument("--no-sdd", action="store_false", dest="is_sdd", default=None, help="非 SDD 流程")
    p.add_argument("--alignment", default=None, help="文本/代码一致性率，如 95%")
    p.add_argument("--issues-file", default=None, help="issues 明细 JSON 文件路径（JSON 数组，直接写入 cr_result_json）")
    p.add_argument("--skill-version", default=None, help="Skill 名称+版本，如 ai-pr-code-review-test V18.5")
    p.add_argument("--scheme", default=DEFAULT_SCHEME, choices=["http", "https"], help=f"协议（默认 {DEFAULT_SCHEME}，内网 IP 直连建议 http）")
    p.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验")
    p.add_argument("--no-proxy", action="store_true", help="不走代理，直连内网 IP")
    p.add_argument("--verify", action="store_true", help="强制 TLS 证书校验（默认对 *.sankuai.com 跳过）")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出新 id")
    args = p.parse_args()

    insecure = args.insecure or (args.host.endswith(".sankuai.com") and not args.verify)

    # --cr-report-file 优先于 --cr-report
    if args.cr_report_file:
        try:
            with open(args.cr_report_file, "r", encoding="utf-8") as f:
                args.cr_report = f.read()
        except IOError as e:
            print(f"❌ 读取 cr_report_file 失败: {e}", file=sys.stderr)
            sys.exit(1)

    # trigger_source: 优先命令行参数，否则从环境变量自动获取
    if args.trigger_source is None:
        args.trigger_source = os.getenv("X_AI_SOURCE", "agent").lower()

    payload = build_payload(args)
    status, body = submit(args.host, payload, args.scheme, insecure, args.no_proxy)

    if args.quiet and status == 200:
        try:
            print(json.loads(body)["id"])
        except (ValueError, KeyError):
            print(body)
        return

    print(f"[HTTP {status}] {body}")
    if status == 200:
        try:
            print(f"-> 新记录 id = {json.loads(body)['id']}")
        except (ValueError, KeyError):
            pass
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
