#!/usr/bin/env python3
"""
使用示例：解析学城文档中的跳链并生成对比报告
"""

from parse_deeplinks import parse_deeplink, parse_comparison_cell, generate_page_report


# 示例数据：模拟从学城文档提取的表格数据
example_pages = [
    {
        "page_name": "首页",
        "before": {
            "ios": "imeituan://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-home-page&mrn_component=main-flow-home&tab=home",
            "android": "imeituan://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-home-page&mrn_component=main-flow-home&mrn_identify_key=mrn-abc123&tab=home",
        },
        "after": {
            "ios": "standardmrn://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-home-page&mrn_component=main-flow-home&tab=home",
            "android": "standardmrn://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-home-page&mrn_component=main-flow-home&mrn_identify_key=mrn-abc123&tab=home",
        },
    },
    {
        "page_name": "我的订单",
        "before": {
            "ios": "imeituan://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-order-list&mrn_component=order-list&status=all",
            "android": "imeituan://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-order-list&mrn_component=order-list&mrn_identify_key=mrn-order123&status=all",
        },
        "after": {
            "ios": "standardmrn://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-order-list&mrn_component=order-list&status=all",
            "android": "standardmrn://www.meituan.com/mrn?mrn_biz=mtm&mrn_entry=standard-order-list&mrn_component=order-list&mrn_identify_key=mrn-order123&status=all",
        },
    },
]


def main():
    """生成示例报告"""
    report = "# 跳链参数对比分析报告\n\n"

    for i, page in enumerate(example_pages, 1):
        ios_before = parse_deeplink(page["before"]["ios"])
        ios_after = parse_deeplink(page["after"]["ios"])
        android_before = parse_deeplink(page["before"]["android"])
        android_after = parse_deeplink(page["after"]["android"])

        page_report = generate_page_report(
            page_num=i,
            page_name=page["page_name"],
            ios_before=ios_before,
            ios_after=ios_after,
            android_before=android_before,
            android_after=android_after,
        )

        report += page_report

    print(report)

    # 保存到文件
    with open("跳链参数对比报告.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n报告已保存到：跳链参数对比报告.md")


if __name__ == "__main__":
    main()

