#!/usr/bin/env python3
"""
Step 1~2: 多团队多维表格采集 + 过滤 + 优先级评分

支持两种输入模式：
  A) --input raw_records.json        单文件模式（兼容老逻辑）
  B) --tables <table_config.json>    多表模式（从配置拉取所有团队表）

多表配置格式（table_config.json）：
[
  {"content_id": "2751017775", "table_id": "2751197605", "team": "服务零售组"},
  {"content_id": "xxx", "table_id": "yyy", "team": "增长组"},
  ...
]

Usage:
  python3 harvest.py --input raw_records.json --output candidates.json
  python3 harvest.py --tables table_config.json --output candidates.json
"""

import json
import subprocess
import sys
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# === 配置 ===
MAX_AGE_MONTHS = 6
MIN_FINDINGS = 1
MAX_BUGS_PER_PR = 5
FETCH_PAGE_SIZE = 500
FETCH_SLEEP_SEC = 1  # 每次 API 调用间隔，防限流

# 优先级评分权重
WEIGHTS = {
    "conclusion_orange_red": 30,
    "p0_gte_1": 40,
    "p1_gte_2": 20,
    "recent_3months": 10,
    # Step 4 追加（PR评论拉取后更新）
    "has_accept_mark": 50,
    "has_fp_mark": 25,
}

CUTOFF_DAYS = MAX_AGE_MONTHS * 30


def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str[:len(fmt)], fmt)
        except ValueError:
            continue
    return None


def extract_pr_id(pr_url: str) -> Optional[str]:
    """从 dev.sankuai.com PR URL 提取 pr_id"""
    m = re.search(r'/pr[s]?/(\d+)', pr_url)
    return m.group(1) if m else None


def extract_repo(pr_url: str) -> Optional[str]:
    """从 URL 提取 repo slug，格式：org/repo"""
    # https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff
    m = re.search(r'/repo-detail/([^/]+/[^/]+)/', pr_url)
    if m:
        return m.group(1)
    # https://dev.sankuai.com/code/repos/org/repo/prs/123
    m = re.search(r'/repos/([^/]+/[^/]+)/', pr_url)
    return m.group(1) if m else None


def extract_doc_id(doc_url: str) -> Optional[str]:
    """从学城 URL 提取 content_id"""
    if not doc_url:
        return None
    m = re.search(r'/collabpage/(\d+)', doc_url)
    return m.group(1) if m else None


def calculate_priority(record: Dict[str, Any]) -> int:
    score = 0

    conclusion = record.get("review_conclusion", "") or ""
    if "🟠" in conclusion or "🔴" in conclusion:
        score += WEIGHTS["conclusion_orange_red"]

    p0 = _to_int(record.get("p0_count"))
    p1 = _to_int(record.get("p1_count"))
    if p0 >= 1:
        score += WEIGHTS["p0_gte_1"]
    if p1 >= 2:
        score += WEIGHTS["p1_gte_2"]

    date_str = record.get("date", "") or ""
    dt = parse_date(date_str)
    if dt and (datetime.now() - dt).days <= 90:
        score += WEIGHTS["recent_3months"]

    return score


def _to_int(val) -> int:
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def is_valid(record: Dict[str, Any]):
    pr_url = record.get("pr_url", "") or ""
    if not pr_url or "dev.sankuai.com" not in pr_url:
        return False, "no valid pr_url"

    p0 = _to_int(record.get("p0_count"))
    p1 = _to_int(record.get("p1_count"))
    p2 = _to_int(record.get("p2_count"))
    if (p0 + p1 + p2) < MIN_FINDINGS:
        return False, f"findings={p0+p1+p2} < {MIN_FINDINGS}"

    doc_url = record.get("cr_doc_url", "") or ""
    if not extract_doc_id(doc_url):
        return False, "no cr_doc_url"

    date_str = record.get("date", "") or ""
    dt = parse_date(date_str)
    if dt and (datetime.now() - dt).days > CUTOFF_DAYS:
        return False, f"too old: {date_str}"

    return True, "ok"


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """统一字段名，兼容多维表格不同列名"""
    aliases = {
        "pr_url": ["pr链接", "pr_link", "PR链接", "PR Link"],
        "date": ["日期", "merge_date", "create_date"],
        "review_conclusion": ["review结论", "结论", "Review结论"],
        "p0_count": ["p0数", "P0数", "p0_num"],
        "p1_count": ["p1数", "P1数", "p1_num"],
        "p2_count": ["p2数", "P2数", "p2_num"],
        "cr_doc_url": ["学城文档url", "学城文档URL", "cr_doc", "km_url"],
        "submitter": ["提交人", "author", "mis"],
        "repo": ["仓库名", "repo_name"],
        "title": ["标题", "pr_title"],
        "org": ["组织", "department"],
    }
    normalized = dict(record)
    for canonical, alias_list in aliases.items():
        if canonical not in normalized or not normalized[canonical]:
            for alias in alias_list:
                if alias in record and record[alias]:
                    normalized[canonical] = record[alias]
                    break
    return normalized


def filter_and_score(records: List[Dict]) -> List[Dict]:
    candidates = []
    skipped = {"no valid pr_url": 0, "no cr_doc_url": 0, "too old": 0, "findings": 0}

    for raw in records:
        record = normalize_record(raw)
        valid, reason = is_valid(record)
        if not valid:
            key = reason.split(":")[0].strip()
            skipped[key] = skipped.get(key, 0) + 1
            continue

        # 补充解析字段
        pr_url = record.get("pr_url", "")
        record["pr_id"] = extract_pr_id(pr_url)
        record["repo_slug"] = record.get("repo") or extract_repo(pr_url)
        record["cr_doc_id"] = extract_doc_id(record.get("cr_doc_url", ""))
        record["priority_score"] = calculate_priority(record)

        candidates.append(record)

    # 去重（同 PR URL 保留最高分）
    seen: Dict[str, Dict] = {}
    for c in candidates:
        url = c.get("pr_url", "")
        if url not in seen or c["priority_score"] > seen[url]["priority_score"]:
            seen[url] = c

    result = sorted(seen.values(), key=lambda x: x["priority_score"], reverse=True)

    print(f"📥 输入: {len(records)} 条")
    print(f"✅ 候选: {len(result)} 条")
    print(f"🚫 过滤: {sum(skipped.values())} 条 → {skipped}")
    print(f"📊 优先级分布:")
    print(f"   Gold  (≥80): {sum(1 for c in result if c['priority_score'] >= 80)}")
    print(f"   Silver(40~79): {sum(1 for c in result if 40 <= c['priority_score'] < 80)}")
    print(f"   Bronze(<40): {sum(1 for c in result if c['priority_score'] < 40)}")

    return result


def fetch_table_records(content_id: str, table_id: str, team: str = "unknown") -> List[Dict]:
    """从多维表格拉取全部记录，自动翻页"""
    all_records = []
    page = 1

    while True:
        cmd = [
            "oa-skills", "citadel-database", "query",
            "--content-id", content_id,
            "--table-id", table_id,
            "--page-size", str(FETCH_PAGE_SIZE),
            "--page", str(page),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                print(f"  ⚠️  [{team}] 拉取失败 page={page}: {result.stderr[:200]}", file=sys.stderr)
                break

            data = json.loads(result.stdout)
            # citadel-database 输出可能是 {records: [...], total: N} 或直接 [...]
            if isinstance(data, dict):
                records = data.get("records", data.get("data", []))
                total = data.get("total", 0)
            elif isinstance(data, list):
                records = data
                total = len(records)
            else:
                break

            if not records:
                break

            # 标记来源团队
            for r in records:
                r["_source_team"] = team
                r["_source_table"] = table_id

            all_records.extend(records)
            print(f"  [{team}] page {page}: +{len(records)} 条（累计 {len(all_records)}）")

            if len(all_records) >= total or len(records) < FETCH_PAGE_SIZE:
                break

            page += 1
            time.sleep(FETCH_SLEEP_SEC)

        except Exception as e:
            print(f"  ⚠️  [{team}] 异常: {e}", file=sys.stderr)
            break

    return all_records


def load_from_tables(config_path: str) -> List[Dict]:
    """从多表配置文件拉取所有团队数据"""
    with open(config_path, "r", encoding="utf-8") as f:
        tables = json.load(f)

    all_records = []
    print(f"📋 多表模式：共 {len(tables)} 个团队表\n")

    for i, table in enumerate(tables):
        content_id = table.get("content_id", "")
        table_id = table.get("table_id", "")
        team = table.get("team", f"team_{i+1}")

        if not content_id or not table_id:
            print(f"  ⚠️  [{team}] 缺少 content_id/table_id，跳过")
            continue

        print(f"[{i+1}/{len(tables)}] 拉取 {team}（table={table_id}）...")
        records = fetch_table_records(content_id, table_id, team)
        all_records.extend(records)

        if i < len(tables) - 1:
            time.sleep(FETCH_SLEEP_SEC)

    print(f"\n📥 全部拉取完成：{len(all_records)} 条（{len(tables)} 个团队）")
    return all_records


def main():
    args = sys.argv[1:]

    if "--output" not in args:
        print("Usage:")
        print("  python3 harvest.py --input <raw_records.json> --output <candidates.json>")
        print("  python3 harvest.py --tables <table_config.json> --output <candidates.json>")
        sys.exit(1)

    output_file = args[args.index("--output") + 1]

    # 多表模式
    if "--tables" in args:
        config_path = args[args.index("--tables") + 1]
        records = load_from_tables(config_path)
    elif "--input" in args:
        input_file = args[args.index("--input") + 1]
        with open(input_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        print("❌ 需要 --input 或 --tables 参数")
        sys.exit(1)

    candidates = filter_and_score(records)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    print(f"\n💾 输出: {output_file}")


if __name__ == "__main__":
    main()
