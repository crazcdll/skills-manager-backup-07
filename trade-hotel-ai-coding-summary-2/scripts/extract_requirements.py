#!/usr/bin/env python3
"""
从酒店排期文档中提取"本周需求池"需求。

读取排期文档 XML，解析其中的多维表格引用，
查询每个表格中"需求排期"为"本周需求池"的需求行，
输出为需求列表 Markdown 格式（兼容 sync_ai_coding.py 的 parse_requirement_md）。
"""

import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
import tempfile


def run_cli(cmd: str) -> str:
    """运行 CLI 命令并返回输出"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}", file=sys.stderr)
        if result.stderr:
            print(f"[ERROR] stderr: {result.stderr[:500]}", file=sys.stderr)
    return result.stdout


def fetch_document_xml(content_id: str, mis: str) -> str:
    """获取学城文档 XML"""
    tmp_path = tempfile.mktemp(suffix='.xml', dir='/tmp')

    cmd = f"oa-skills citadel getDocumentXml --contentId {content_id} --mis {mis} --output {tmp_path}"
    run_cli(cmd)

    if not os.path.exists(tmp_path):
        print("[ERROR] XML 文件未生成", file=sys.stderr)
        return ""

    with open(tmp_path, 'r') as f:
        xml_content = f.read()

    os.unlink(tmp_path)
    return xml_content


def extract_xtable_sections(xml_content: str) -> list[dict]:
    """
    从 XML 中提取多维表格 ID 及其对应的业务线名称。

    策略：找到所有 h3/h4 标题和 km-xtable 标签，按出现顺序配对。
    每个 xtable 取其前面最近的 h4 或 h3 标题作为业务线名称。
    只保留含"酒店"或"民宿"关键词的业务表格。

    返回: [{"section": "国内酒店", "xtable_id": "2779375568"}, ...]
    """
    sections = []

    h_pattern = re.compile(r'<h[34][^>]*>(.*?)</h[34]>', re.IGNORECASE | re.DOTALL)
    xtable_pattern = re.compile(r'<km-xtable\s+xtableId="(\d+)"', re.IGNORECASE)

    h_matches = [(m.start(), m.group(1)) for m in h_pattern.finditer(xml_content)]
    xtable_matches = [(m.start(), m.group(1)) for m in xtable_pattern.finditer(xml_content)]

    for xt_pos, xt_id in xtable_matches:
        section_name = None
        for h_pos, h_text in h_matches:
            if h_pos < xt_pos:
                section_name = h_text
            else:
                break

        if section_name:
            # 清理 HTML 标签
            clean_name = re.sub(r'<[^>]+>', '', section_name).strip()
            # 提取业务线名称（如 "1.1 国内酒店" -> "国内酒店"）
            name_match = re.search(r'[\d.]+\s*(.+)', clean_name)
            if name_match:
                clean_name = name_match.group(1).strip()
            # 只保留业务相关的表格（含"酒店"或"民宿"关键词）
            if any(kw in clean_name for kw in ['酒店', '民宿']):
                sections.append({"section": clean_name, "xtable_id": xt_id})

    return sections


def get_table_meta(table_id: str, mis: str) -> dict:
    """获取多维表格元数据，返回列信息字典"""
    cmd = f"oa-skills citadel-database getTableMeta --tableId {table_id} --mis {mis}"
    output = run_cli(cmd)

    columns = {}
    # 匹配格式: "  1. TG (ID: 1, 类型: 3，列配置：...)"
    col_pattern = re.compile(r'\d+\.\s*(.+?)\s*\(ID:\s*(\d+),\s*类型:\s*(\d+)')
    for match in col_pattern.finditer(output):
        col_name = match.group(1).strip()
        col_id = match.group(2)
        col_type = int(match.group(3))
        columns[col_name] = {"id": col_id, "type": col_type, "name": col_name}

    return columns


def find_column(columns: dict, keywords: list[str]) -> dict | None:
    """根据关键词查找列"""
    for name, info in columns.items():
        if any(kw in name for kw in keywords):
            return info
    return None


def query_weekly_requirements(table_id: str, columns: dict, mis: str) -> list[dict]:
    """查询"本周需求池"需求"""
    # 找到关键列
    schedule_col = find_column(columns, ['需求排期'])
    ones_col = find_column(columns, ['需求ones', '需求ones'])
    prd_col = find_column(columns, ['需求文档'])
    owner_col = find_column(columns, ['需求主R', '需求主'])
    dev_status_col = find_column(columns, ['研发状态'])

    if not schedule_col:
        print(f"[WARN] 未找到'需求排期'列", file=sys.stderr)
        return []

    # 构建列 ID 列表（按 ones, prd, schedule, owner, dev_status 顺序）
    col_ids = []
    col_map = {}
    if ones_col:
        col_ids.append(ones_col['id'])
        col_map[ones_col['id']] = 'ones'
    if prd_col:
        col_ids.append(prd_col['id'])
        col_map[prd_col['id']] = 'prd'
    if schedule_col:
        col_ids.append(schedule_col['id'])
        col_map[schedule_col['id']] = 'schedule'
    if owner_col:
        col_ids.append(owner_col['id'])
        col_map[owner_col['id']] = 'owner'
    if dev_status_col:
        col_ids.append(dev_status_col['id'])
        col_map[dev_status_col['id']] = 'dev_status'

    col_id_str = ','.join(col_ids)

    # 构建筛选条件
    filter_obj = json.dumps({
        "conjunction": "and",
        "conditions": [
            {
                "columnId": int(schedule_col['id']),
                "operator": "==",
                "filterValue": ["本周需求池"]
            }
        ]
    }, ensure_ascii=False)

    cmd = (
        f"oa-skills citadel-database queryTableData "
        f"--tableId {table_id} --mis {mis} "
        f'--columnIds "{col_id_str}" '
        f"--filter '{filter_obj}' "
        f"--max-pages 10"
    )
    output = run_cli(cmd)

    return parse_query_output(output, col_map)


def parse_query_output(output: str, col_map: dict) -> list[dict]:
    """解析 queryTableData 的文本输出"""
    requirements = []

    # 按 "行 N (ID: ...):" 分割
    row_pattern = re.compile(r'行\s+\d+\s*\(ID:\s*\d+\):')
    rows = row_pattern.split(output)

    for row_text in rows[1:]:  # 跳过头部
        req = {}

        # 解析各列: "  列 123: value"
        # 需要处理值中包含换行的情况
        col_pattern = re.compile(r'列\s+(\d+):\s*(.*?)(?=\n\s*列\s+\d+:|\n\n|\Z)', re.DOTALL)
        col_values = {}
        for match in col_pattern.finditer(row_text):
            col_id = match.group(1)
            col_value = match.group(2).strip()
            col_values[col_id] = col_value

        # 按列类型解析
        for col_id, col_type in col_map.items():
            value = col_values.get(col_id, '')

            if col_type == 'ones':
                parse_ones_column(value, req)
            elif col_type == 'prd':
                parse_prd_column(value, req)
            elif col_type == 'owner':
                parse_owner_column(value, req)
            elif col_type == 'dev_status':
                parse_dev_status_column(value, req)

        if req.get('ones_id') or req.get('ones_title'):
            requirements.append(req)

    return requirements


def parse_dev_status_column(value: str, req: dict):
    """解析研发状态列"""
    if not value:
        return
    # 研发状态是单选项，直接取文本值
    req['dev_status'] = value.strip()


def get_dev_status_excludes(section: str) -> set:
    """
    返回该业务线需要排除的研发状态集合。
    已上线/已归档的需求虽然还挂在"本周需求池"，但实际已完成，不应计入本周需求。
    """
    if section in ('国内酒店', '境外酒店'):
        return {'已上线', '已归档'}
    elif section == '民宿':
        return {'已完成'}
    return set()


def parse_ones_column(value: str, req: dict):
    """解析 ONES 需求列"""
    if not value:
        return

    req['ones_raw'] = value

    # 提取 ONES ID
    ones_match = re.search(r'ones\.sankuai\.com/.*?/detail/(\d+)', value)
    if ones_match:
        req['ones_id'] = ones_match.group(1)

    # 提取 ONES URL
    url_match = re.search(r'(https?://ones\.sankuai\.com[^\s)]+)', value)
    if url_match:
        req['ones_url'] = url_match.group(1)

    # 提取标题（从 markdown 链接格式）
    title_match = re.search(r'\[([^\]]+)\]', value)
    if title_match:
        title = title_match.group(1).strip()
        # 去掉 "需求 " 前缀
        title = re.sub(r'^需求\s*', '', title)
        req['ones_title'] = title
    else:
        # 纯文本
        req['ones_title'] = value


def parse_prd_column(value: str, req: dict):
    """解析 PRD 文档列"""
    if not value or value == '-':
        return

    req['prd_raw'] = value

    # 提取 km 链接 ID
    km_match = re.search(r'collabpage/(\d+)', value)
    if km_match:
        req['prd_km_id'] = km_match.group(1)
        req['prd_url'] = f'https://km.sankuai.com/collabpage/{km_match.group(1)}'

    # 提取 PRD 标题
    title_match = re.search(r'\[([^\]]+)\]', value)
    if title_match:
        req['prd_title'] = title_match.group(1).strip()
    elif not km_match:
        # 纯文本作为标题
        req['prd_title'] = value


def parse_owner_column(value: str, req: dict):
    """解析需求主R列"""
    if not value:
        return

    req['owner_raw'] = value

    # 格式: @王宇(6051462) [mis=wangyu193]
    owner_match = re.search(r'@(.+?)\((\d+)\)\s*\[mis=(\w+)\]', value)
    if owner_match:
        req['owner_name'] = owner_match.group(1).strip()
        req['owner_emp_id'] = owner_match.group(2)
        req['owner_mis'] = owner_match.group(3)
    else:
        # 尝试提取 @人名
        name_match = re.search(r'@([^\s(]+)', value)
        if name_match:
            req['owner_name'] = name_match.group(1).strip()


def generate_markdown(requirements_by_section: dict) -> str:
    """生成需求列表 Markdown（兼容 sync_ai_coding.py 的 parse_requirement_md）"""
    lines = []
    lines.append("| ones | prd | 研发同学 |")
    lines.append("| --- | --- | --- |")

    for section, reqs in requirements_by_section.items():
        for req in reqs:
            # ONES 列
            ones_cell = ""
            if req.get('ones_url') and req.get('ones_title'):
                ones_cell = f"[{req['ones_title']}]({req['ones_url']})"
            elif req.get('ones_title'):
                ones_cell = req['ones_title']

            # PRD 列
            prd_cell = "-"
            if req.get('prd_url') and req.get('prd_title'):
                prd_cell = f"[{req['prd_title']}]({req['prd_url']})"
            elif req.get('prd_title'):
                prd_cell = req['prd_title']

            # 研发同学列
            # 输出学城原生 mention markdown 语法：[mention]{name="姓名" uid="mis" empId="empId"}
            # 这样 createDocument 创建的子文档里研发同学会渲染成蓝色 @（而非纯文本），
            # 同时下游 sync_ai_coding.py 的 parse_requirement_md 也能解析出 mis/empId/name。
            # 降级链：三件套齐全 -> 仅 mis -> 纯文本姓名
            owner_cell = ""
            name = req.get('owner_name', '')
            mis = req.get('owner_mis', '')
            emp_id = req.get('owner_emp_id', '')
            if mis and emp_id:
                # name 缺失时用 mis 兜底，学城会按 empId 解析出正确姓名
                display_name = name if name else mis
                owner_cell = f'[mention]{{name="{display_name}" uid="{mis}" empId="{emp_id}"}}'
            elif mis:
                owner_cell = f"@{mis}"
            elif name:
                # 纯文本姓名回退——无法生成蓝色 @，仅作占位
                owner_cell = f"@{name}"

            if ones_cell:
                lines.append(f"| {ones_cell} | {prd_cell} | {owner_cell} |")

    return '\n'.join(lines)


def _xml_escape(text: str) -> str:
    """转义 XML 文本节点中的特殊字符"""
    if not text:
        return ''
    return html.escape(text, quote=False)


def _make_mention_xml(name: str, mis: str, emp_id: str) -> str:
    """生成单个 km-mention 标签；信息不全时降级为纯文本 @"""
    if mis and emp_id:
        display = name if name else mis
        return f'<km-mention name="{_xml_escape(display)}" uid="{_xml_escape(mis)}" empId="{_xml_escape(emp_id)}" />'
    if mis:
        return f'@{_xml_escape(mis)}'
    if name:
        return f'@{_xml_escape(name)}'
    return ''


def default_subdoc_title() -> str:
    """默认子文档标题：酒店 YYYY-MM-DD-AICoding 需求列表（取当天日期）"""
    today = datetime.date.today().strftime('%Y-%m-%d')
    return f'酒店 {today}-AICoding 需求列表'


def generate_subdoc_xml(requirements_by_section: dict, title: str = '') -> str:
    """
    生成带 km-mention 的 CitadelXML，用于创建子文档。

    与 generate_markdown 的区别：研发同学列用 <km-mention> 标签而非 [mention]{} 文本，
    这样通过 createDocument --file xxx.xml 创建后，子文档里研发同学会渲染成蓝色 @。
    （markdown 方式创建的文档不会解析 [mention]{} 语法，会是字面文本。）
    """
    rows_xml = []
    for section, reqs in requirements_by_section.items():
        for req in reqs:
            # ONES 列
            ones_title = req.get('ones_title', '') or ''
            ones_url = req.get('ones_url', '') or ''
            if ones_url and ones_title:
                ones_cell = f'<p><a href="{_xml_escape(ones_url)}" title="{_xml_escape(ones_title)}">{_xml_escape(ones_title)}</a></p>'
            elif ones_title:
                ones_cell = f'<p>{_xml_escape(ones_title)}</p>'
            else:
                continue

            # PRD 列
            prd_title = req.get('prd_title', '') or ''
            prd_url = req.get('prd_url', '') or ''
            if prd_url and prd_title:
                prd_cell = f'<p><a href="{_xml_escape(prd_url)}" title="{_xml_escape(prd_title)}">{_xml_escape(prd_title)}</a></p>'
            elif prd_title:
                prd_cell = f'<p>{_xml_escape(prd_title)}</p>'
            else:
                prd_cell = '<p />'

            # 研发同学列：km-mention
            mention = _make_mention_xml(
                req.get('owner_name', ''),
                req.get('owner_mis', ''),
                req.get('owner_emp_id', ''),
            )
            owner_cell = f'<p>{mention}</p>' if mention else '<p />'

            rows_xml.append(
                f'<tr>\n'
                f'<td>{ones_cell}</td>\n'
                f'<td>{prd_cell}</td>\n'
                f'<td>{owner_cell}</td>\n'
                f'</tr>'
            )

    body = '\n'.join([
        '<km-doc>',
        f'<km-title>{_xml_escape(title)}</km-title>',
        f'<h1>{_xml_escape(title)}</h1>',
        '<table>',
        '<tr>',
        '<th><p>ones</p></th>',
        '<th><p>prd</p></th>',
        '<th><p>研发同学</p></th>',
        '</tr>',
        '\n'.join(rows_xml),
        '</table>',
        '</km-doc>',
    ])
    return body


def main():
    parser = argparse.ArgumentParser(description='从酒店排期文档提取"本周需求池"需求')
    parser.add_argument('--contentId', required=True, help='排期文档 contentId')
    parser.add_argument('--mis', default=os.environ.get('SSO_USER_ID', ''), help='MIS 账号')
    parser.add_argument('--output', default=None, help='输出文件路径（默认输出到 stdout）')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown', help='输出格式')
    parser.add_argument('--subdoc-xml', default=None, help='同时输出一份带 km-mention 的 CitadelXML，用于创建可渲染蓝色@的子文档')
    parser.add_argument('--subdoc-title', default=None, help='子文档标题，默认“酒店 YYYY-MM-DD-AICoding 需求列表”（当天日期）')

    args = parser.parse_args()

    if not args.mis:
        print("[ERROR] 请提供 --mis 参数或设置 SSO_USER_ID 环境变量", file=sys.stderr)
        sys.exit(1)

    # 1. 获取排期文档 XML
    print(f"[INFO] 获取排期文档 XML (contentId={args.contentId})...", file=sys.stderr)
    xml_content = fetch_document_xml(args.contentId, args.mis)
    if not xml_content:
        print("[ERROR] 无法获取文档 XML", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] XML 长度: {len(xml_content)} 字符", file=sys.stderr)

    # 2. 提取多维表格 ID 和业务线名称
    sections = extract_xtable_sections(xml_content)
    if not sections:
        print("[ERROR] 未找到多维表格", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 找到 {len(sections)} 个业务线表格:", file=sys.stderr)
    for s in sections:
        print(f"  - {s['section']}: tableId={s['xtable_id']}", file=sys.stderr)

    # 3. 查询每个表格的"本周需求池"需求
    all_requirements = {}
    for section in sections:
        print(f"[INFO] 查询 {section['section']} 的本周需求池...", file=sys.stderr)

        # 获取表格元数据
        columns = get_table_meta(section['xtable_id'], args.mis)
        if not columns:
            print(f"[WARN] 无法获取 {section['section']} 的表格元数据", file=sys.stderr)
            continue

        # 查询数据
        reqs = query_weekly_requirements(section['xtable_id'], columns, args.mis)

        # 按业务线过滤研发状态（排除已上线/已归档/已完成等终态需求）
        excludes = get_dev_status_excludes(section['section'])
        if excludes:
            before = len(reqs)
            reqs = [r for r in reqs if r.get('dev_status', '') not in excludes]
            filtered_out = before - len(reqs)
            if filtered_out:
                print(f"  -> 过滤掉 {filtered_out} 个终态需求（研发状态∈{excludes}）", file=sys.stderr)

        all_requirements[section['section']] = reqs
        print(f"  -> 找到 {len(reqs)} 个需求", file=sys.stderr)

    # 4. 输出
    if args.format == 'json':
        output = json.dumps(all_requirements, ensure_ascii=False, indent=2)
    else:
        output = generate_markdown(all_requirements)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"[INFO] 输出已保存到 {args.output}", file=sys.stderr)
    else:
        print(output)

    # 额外输出子文档 XML（带 km-mention，用于创建蓝色@的子文档）
    if args.subdoc_xml:
        subdoc_title = args.subdoc_title or default_subdoc_title()
        subdoc_xml = generate_subdoc_xml(all_requirements, title=subdoc_title)
        with open(args.subdoc_xml, 'w') as f:
            f.write(subdoc_xml)
        print(f"[INFO] 子文档 XML 已保存到 {args.subdoc_xml}（标题：{subdoc_title}）", file=sys.stderr)

    # 统计
    total = sum(len(reqs) for reqs in all_requirements.values())
    print(f"\n[INFO] 共提取 {total} 个本周需求池需求", file=sys.stderr)
    for section, reqs in all_requirements.items():
        print(f"  - {section}: {len(reqs)} 个", file=sys.stderr)


if __name__ == '__main__':
    main()
