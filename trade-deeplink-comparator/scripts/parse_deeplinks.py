#!/usr/bin/env python3
"""
跳链参数解析与对比工具
从学城文档表格中提取 iOS 和 Android 跳链，解析参数并对比差异
"""

import json
import re
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, List, Any, Tuple


def normalize_value(value):
    """标准化参数值用于比较"""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else ""
    value = str(value).lower().strip()
    if value in ("0", "false", "null", "none", ""):
        return "0"
    if value in ("1", "true"):
        return "1"
    return value


def parse_deeplink(url: str) -> Dict[str, Any]:
    """
    解析深链 URL，提取 scheme、host、path 和参数
    """
    if not url or not isinstance(url, str):
        return None

    try:
        parsed = urlparse(url)
        scheme = parsed.scheme

        # 解析参数
        params = parse_qs(parsed.query, keep_blank_values=True)
        result_params = {}
        for key, values in params.items():
            decoded_key = unquote(key)
            decoded_values = [unquote(v) for v in values]
            result_params[decoded_key] = (
                decoded_values[0] if len(decoded_values) == 1 else decoded_values
            )

        return {
            "scheme": scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "params": result_params,
            "raw_url": url,
        }
    except Exception as e:
        return {"error": str(e), "raw_url": url}


def compare_params(before_params: Dict, after_params: Dict) -> List[Dict]:
    """
    对比替换前后的参数变化
    """
    all_keys = set(before_params.keys()) | set(after_params.keys())
    result = []

    for key in sorted(all_keys):
        before_val = before_params.get(key, "")
        after_val = after_params.get(key, "")

        if before_val == after_val:
            change = "✅"  # 无变化
        elif not before_val:
            change = "🆕"  # 新增
        elif not after_val:
            change = "🗑"  # 删除
        else:
            change = "❓"  # 有变化

        result.append(
            {"key": key, "before": before_val, "after": after_val, "change": change}
        )

    return result


def compare_ios_android(ios_params: Dict, android_params: Dict) -> List[Dict]:
    """
    对比 iOS 和 Android 的参数差异
    """
    all_keys = set(ios_params.keys()) | set(android_params.keys())
    result = []

    for key in sorted(all_keys):
        ios_val = ios_params.get(key, "")
        android_val = android_params.get(key, "")

        # 标准化比较
        ios_norm = normalize_value(ios_val)
        android_norm = normalize_value(android_val)

        is_consistent = (
            ios_norm == android_norm if ios_norm and android_norm else ios_val == android_val
        )

        note = ""
        if key == "mrn_identify_key":
            note = "Android 特有参数"
        elif not ios_val:
            note = "iOS 缺失"
        elif not android_val:
            note = "Android 缺失"
        elif ios_norm != android_norm:
            note = f"值不一致: iOS={ios_val}, Android={android_val}"

        result.append(
            {
                "key": key,
                "ios": ios_val,
                "android": android_val,
                "consistent": "✅" if is_consistent else "❌",
                "note": note,
            }
        )

    return result


def parse_comparison_cell(cell_text: str) -> Tuple[str, str]:
    """
    解析包含两个链接的单元格（iOS 和 Android）
    返回 (ios_link, android_link)
    """
    if not cell_text:
        return "", ""

    # 匹配 iOS 和 Android 链接
    ios_match = re.search(r"iOS[：:]\s*(\S+)", cell_text, re.IGNORECASE)
    android_match = re.search(r"Android[：:]\s*(\S+)", cell_text, re.IGNORECASE)

    ios_link = ios_match.group(1) if ios_match else ""
    android_link = android_match.group(1) if android_match else ""

    return ios_link, android_link


def generate_page_report(
    page_num: int,
    page_name: str,
    ios_before: Dict,
    ios_after: Dict,
    android_before: Dict,
    android_after: Dict,
) -> str:
    """
    生成单页的参数对比报告
    """
    report = f"## 第 {page_num} 页：{page_name}\n\n"

    # iOS 跳链地址
    report += f"### {page_name}-iOS\n\n"

    ios_before_url = ios_before.get("raw_url", "") if ios_before else ""
    ios_after_url = ios_after.get("raw_url", "") if ios_after else ""

    if ios_before_url:
        report += "替换前跳链地址：\n```\n"
        report += ios_before_url
        report += "\n```\n\n"

    if ios_after_url:
        report += "替换后跳链地址：\n```\n"
        report += ios_after_url
        report += "\n```\n\n"

    # iOS 参数对比
    report += "#### iOS 跳链参数\n\n"
    report += "| 参数名 | 替换前值 | 替换后值 | 变化 |\n"
    report += "|--------|----------|----------|------|\n"

    ios_comparison = compare_params(
        ios_before.get("params", {}) if ios_before else {},
        ios_after.get("params", {}) if ios_after else {},
    )
    for item in ios_comparison:
        report += (
            f"| {item['key']} | {item['before']} | {item['after']} | {item['change']} |\n"
        )

    report += "\n"

    # Android 跳链地址
    report += f"### {page_name}-Android\n\n"

    android_before_url = android_before.get("raw_url", "") if android_before else ""
    android_after_url = android_after.get("raw_url", "") if android_after else ""

    if android_before_url:
        report += "替换前跳链地址：\n```\n"
        report += android_before_url
        report += "\n```\n\n"

    if android_after_url:
        report += "替换后跳链地址：\n```\n"
        report += android_after_url
        report += "\n```\n\n"

    # Android 参数对比
    report += "#### Android 跳链参数\n\n"
    report += "| 参数名 | 替换前值 | 替换后值 | 变化 |\n"
    report += "|--------|----------|----------|------|\n"

    android_comparison = compare_params(
        android_before.get("params", {}) if android_before else {},
        android_after.get("params", {}) if android_after else {},
    )
    for item in android_comparison:
        report += (
            f"| {item['key']} | {item['before']} | {item['after']} | {item['change']} |\n"
        )

    report += "\n"

    # iOS vs Android 对比
    report += "### iOS vs Android 对比\n\n"
    report += "| 参数名 | iOS替换后 | Android替换后 | 是否一致 | 备注 |\n"
    report += "|--------|-----------|---------------|----------|------|\n"

    cross_comparison = compare_ios_android(
        ios_after.get("params", {}) if ios_after else {},
        android_after.get("params", {}) if android_after else {},
    )
    for item in cross_comparison:
        report += f"| {item['key']} | {item['ios']} | {item['android']} | {item['consistent']} | {item['note']} |\n"

    report += "\n---\n\n"

    return report


def main():
    """示例用法"""
    # 示例：解析单个 URL
    test_url = "imeituan://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-home-page&mrn_component=main-flow-home&tab=home"
    result = parse_deeplink(test_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

