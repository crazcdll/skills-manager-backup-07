#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把结果数据渲染成可追加到学城文档末尾的 CitadelXML 片段（小标题 + 表格）。

输入 JSON 结构：
{
  "caption": "2026-10-21 W43 任务创建结果",
  "header": ["序号", "开发人员", "需求名称", ...],
  "widths": [60, 110, 240, 150, 150, 90, 140, 120, 90, 200],
  "rows": [
     ["1", "王宇", "积分抵后价-交易前端",
      {"text": "96256682", "href": "https://ones.sankuai.com/..."},
      {"text": "PRD", "href": "https://km.sankuai.com/collabpage/123"},
      "提单页", "酒店提单页",
      {"text": "WS-170", "href": "https://mlt.sankuai.com/hotel-trade-fullstack/issues/WS-170"},
      "已创建", "—"]
  ]
}

单元格可以是纯字符串，也可以是 {"text","href"} 生成超链接。

用法：
  python3 render_result_table.py --input /tmp/result.json --output /tmp/result.xml
  # 然后把输出片段插入 getDocumentXml 的 </km-doc> 之前
"""

import argparse
import json
import re


def esc(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_cell(value, width):
    if isinstance(value, dict):
        text = esc(value.get("text", ""))
        href = value.get("href", "")
        if href:
            inner = f'<a href="{esc(href)}">{text}</a>' if text else ""
            if not text:
                inner = f'<a href="{esc(href)}">{esc(href)}</a>'
        else:
            inner = text
    else:
        text = esc(str(value))
        url = re.match(r"^https?://\S+$", str(value or ""))
        inner = f'<a href="{text}">{text}</a>' if url else text
    return f'<td colwidth="[{width}]"><p>{inner}</p></td>'


def render(data):
    header = data.get("header") or []
    rows = data.get("rows") or []
    widths = data.get("widths") or [150] * len(header)
    if len(widths) < len(header):
        widths = list(widths) + [150] * (len(header) - len(widths))

    parts = []
    caption = data.get("caption")
    if caption:
        parts.append(f"<p>{esc(caption)}</p>")
    parts.append('<table responsive="false">')
    parts.append("<tr>")
    for idx, name in enumerate(header):
        parts.append(f'<th colwidth="[{widths[idx]}]"><p>{esc(name)}</p></th>')
    parts.append("</tr>")
    for row in rows:
        parts.append("<tr>")
        for idx in range(len(header)):
            cell = row[idx] if idx < len(row) else ""
            parts.append(render_cell(cell, widths[idx]))
        parts.append("</tr>")
    parts.append("</table>")
    return "\n".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = json.load(open(args.input, encoding="utf-8"))
    xml = render(data)
    open(args.output, "w", encoding="utf-8").write(xml)
    print(f"[ok] 已生成 {args.output}（{len(data.get('rows') or [])} 行）")


if __name__ == "__main__":
    main()
