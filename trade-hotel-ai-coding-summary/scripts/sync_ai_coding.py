#!/usr/bin/env python3
"""
同步酒店 AI-Coding 需求开发统计文档与需求列表。

用法:
    python3 sync_ai_coding.py \
        --xml-path /tmp/aicoding.xml \
        --requirement-md /tmp/requirement.md \
        --output /tmp/aicoding_synced.xml \
        [--changes-output /tmp/changes.json]

输入:
  --xml-path: AI-Coding 文档的 XML（通过 citadel getDocumentXml 获取）
  --requirement-md: 需求列表文档的 markdown（通过 citadel getSimpleMarkdown 获取）

输出:
  --output: 更新后的 AI-Coding XML
  --changes-output: 变更日志（可选）
"""

import argparse
import json
import re
import sys
from typing import Optional


def parse_requirement_md(md_text: str) -> list[dict]:
    """
    解析需求列表 markdown，提取酒店方向的需求项。
    
    支持两种格式：
    - 基础格式: | ones | 研发同学 |
    - 增强格式: | ones | prd | 研发同学 |
    
    返回每项包含: ones_id, ones_title, prd_km_id, prd_title, prd_url, assignees
    """
    items = []
    lines = md_text.split('\n')
    
    # 检测表头格式（从文档原始表头判断）
    has_prd_col = False
    for line in lines:
        raw_cells = line.split('|')
        cells = [c.strip() for c in raw_cells]
        cells = [c for c in cells if c]
        if len(cells) >= 2 and 'ones' in cells[0].lower() and 'prd' in cells[1].lower():
            has_prd_col = True
            break
    
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            continue
        raw_cells = line.split('|')
        # 保留空列：先 strip 首尾空格，但保留内容（包括空字符串）
        cells = [c.strip() for c in raw_cells]
        # 去除首尾的空元素（表格行的前导和尾随空列）
        while cells and not cells[0]:
            cells.pop(0)
        while cells and not cells[-1]:
            cells.pop()
        
        # 跳过表头行
        if len(cells) >= 1 and ('---' in cells[0] or ('ones' in cells[0].lower() and '链接卡片' not in cells[0])):
            continue
        
        # 至少需要 ones 列 + 负责人列
        if len(cells) < 2:
            continue
        
        if has_prd_col:
            # 格式: ones | prd | assignee
            ones_cell = cells[0]
            prd_cell = cells[1] if len(cells) >= 3 else None
            assignee_cell = cells[2] if len(cells) >= 3 else cells[1]
        else:
            ones_cell = cells[0]
            prd_cell = None
            assignee_cell = cells[1] if len(cells) > 1 else cells[-1]
        
        # 解析 ones 链接（URL格式: ones.sankuai.com/ones/product/20645/workItem/requirement/detail/94913075）
        ones_match = re.search(r'ones\.sankuai\.com/.*?/detail/(\d+)', ones_cell)
        if not ones_match:
            continue
        ones_id = ones_match.group(1)
        # 提取标题
        ones_title = ''
        # 尝试从 Markdown 链接文字提取: [文字](url)
        md_text_match = re.search(r'\[([^\]]*?)\]\(https?://ones\.sankuai\.com', ones_cell)
        if md_text_match:
            raw_title = md_text_match.group(1).strip()
            # 过滤掉「链接卡片」占位符
            if raw_title and '链接卡片' not in raw_title:
                ones_title = raw_title
        if not ones_title:
            # 尝试从 HTML title 属性提取
            title_match = re.search(r'title="([^"]+)"', ones_cell)
            ones_title = title_match.group(1) if title_match else ''
        if not ones_title:
            # 尝试从 >文本</a> 提取
            a_text_match = re.search(r'>([^<]+)</a>', ones_cell)
            ones_title = a_text_match.group(1) if a_text_match else ''
        if not ones_title:
            # ONES 卡片链接可能只有占位符（如「链接卡片」），使用 ID 作为伪标题
            ones_title = f'ONES需求{ones_id}'
        
        # 判断是否为酒店方向（product=20645 或 20421）
        is_hotel = '20645' in ones_cell or '20421' in ones_cell
        # 如果没有 product id（格式不同），通过排除法判断（排除已知的非酒店产品ID）
        if not is_hotel and 'product/' in ones_cell:
            # 包含产品ID但非酒店，跳过
            non_hotel_ids = ['15778', '13548', '51105', '3198', '13581', '18888', '32446', '45542', '23603', '20421']
            is_hotel = not any(pid in ones_cell for pid in ['15778', '13548', '51105', '18888', '32446', '45542', '23603'])
        
        if not is_hotel:
            continue
        
        # 解析 prd 列
        prd_km_id = None
        prd_title = None
        prd_url = None
        if prd_cell:
            prd_km_match = re.search(r'collabpage/(\d+)', prd_cell)
            if prd_km_match:
                prd_km_id = prd_km_match.group(1)
                prd_title_match = re.search(r'title="([^"]+)"', prd_cell)
                prd_title = prd_title_match.group(1) if prd_title_match else None
                if not prd_title:
                    # 从链接文字或括号中提取
                    text_match = re.search(r'\[([^\]]+)\]', prd_cell)
                    if text_match:
                        prd_title = text_match.group(1)
                    else:
                        paren_match = re.search(r'\(([^)]+)\)', prd_cell)
                        prd_title = paren_match.group(1) if paren_match else prd_km_id
                prd_url = f'https://km.sankuai.com/collabpage/{prd_km_id}'
        
        # 解析研发同学
        assignee_matches = re.findall(r'@(\S+)', assignee_cell)
        assignees = assignee_matches if assignee_matches else []
        
        items.append({
            'ones_id': ones_id,
            'ones_title': ones_title,
            'ones_url': f'https://ones.sankuai.com/ones/product/20645/workItem/requirement/detail/{ones_id}',
            'prd_km_id': prd_km_id,
            'prd_title': prd_title,
            'prd_url': prd_url,
            'assignees': assignees,
        })
    
    return items


def extract_empid_map(xml_text: str) -> dict[str, dict]:
    """从 XML 中提取 name → {uid, empId} 映射"""
    empid_map = {}
    for match in re.finditer(r'<km-mention name="([^"]+)" uid="([^"]+)" empId="([^"]+)"', xml_text):
        name, uid, emp_id = match.group(1), match.group(2), match.group(3)
        short_name = re.sub(r'[（(].*?[）)]', '', name).strip()
        if short_name and short_name not in empid_map:
            empid_map[short_name] = {'uid': uid, 'empId': emp_id, 'full_name': name}
        if name not in empid_map:
            empid_map[name] = {'uid': uid, 'empId': emp_id, 'full_name': name}
    return empid_map


def find_table_bounds(xml_lines: list[str]) -> tuple[Optional[int], Optional[int]]:
    """找到主统计表的起止行"""
    table_start = None
    table_end = None
    for i, line in enumerate(xml_lines):
        if 'nodeId="1e95d1029cfa4938940398159f4d2bac"' in line:
            table_start = i
        if table_start is not None and i > table_start and '</table>' in line:
            table_end = i
            break
    return table_start, table_end


def find_hotel_section(xml_lines: list[str], table_start: int, table_end: int):
    """找到酒店区域。返回: (first_hotel_tr_start, last_hotel_tr_end, rowspan_value)"""
    tr_starts = []
    tr_ends = []
    for i in range(table_start, table_end + 1):
        s = xml_lines[i].strip()
        if s.startswith('<tr'):
            tr_starts.append(i)
        if s == '</tr>':
            tr_ends.append(i)
    
    if not tr_starts:
        return None, None, 0
    
    data_tr_starts = tr_starts[1:]
    data_tr_ends = tr_ends[1:]
    
    hotel_start_idx = None
    rowspan_value = 0
    for idx, ts in enumerate(data_tr_starts):
        if idx >= len(data_tr_ends):
            break
        row_text = '\n'.join(xml_lines[ts:data_tr_ends[idx]+1])
        rowspan_match = re.search(r'rowspan="(\d+)"', row_text)
        if rowspan_match and ('酒店' in row_text or '鲍立磊' in row_text):
            hotel_start_idx = idx
            rowspan_value = int(rowspan_match.group(1))
            break
    
    if hotel_start_idx is None:
        return None, None, 0
    
    hotel_first_ts = data_tr_starts[hotel_start_idx]
    hotel_last_te = data_tr_ends[hotel_start_idx + rowspan_value - 1]
    
    return hotel_first_ts, hotel_last_te, rowspan_value


def get_row_km_id(xml_lines: list[str], tr_start: int, tr_end: int) -> Optional[str]:
    """获取行中的 km ID"""
    row_text = '\n'.join(xml_lines[tr_start:tr_end+1])
    match = re.search(r'collabpage/(\d+)', row_text)
    return match.group(1) if match else None


def get_row_ones_id(xml_lines: list[str], tr_start: int, tr_end: int) -> Optional[str]:
    """获取行中的 ones ID"""
    row_text = '\n'.join(xml_lines[tr_start:tr_end+1])
    match = re.search(r'workItem/requirement/detail/(\d+)', row_text)
    return match.group(1) if match else None


def get_row_assignees(xml_lines: list[str], tr_start: int, tr_end: int) -> list[str]:
    """获取行中的所有 mention 名称（排除方向标签）"""
    row_text = '\n'.join(xml_lines[tr_start:tr_end+1])
    mentions = re.findall(r'<km-mention name="([^"]+)"', row_text)
    cleaned = []
    for m in mentions:
        if '鲍立磊' not in m and m not in cleaned:
            cleaned.append(m)
    return cleaned


def get_row_title(xml_lines: list[str], tr_start: int, tr_end: int) -> str:
    """获取行的需求标题"""
    row_text = '\n'.join(xml_lines[tr_start:tr_end+1])
    match = re.search(r'<a[^>]*title="([^"]+)"[^>]*>[^<]*</a>', row_text)
    if match:
        title = match.group(1)
        if title.startswith('http'):
            text_match = re.search(r'>([^<]+)</a>', row_text)
            if text_match:
                title = text_match.group(1)
        return title
    return ''


def get_row_first_link(xml_lines: list[str], tr_start: int, tr_end: int):
    """获取行中第一个链接的信息。返回: (url, link_type, title)"""
    row_text = '\n'.join(xml_lines[tr_start:tr_end+1])
    matches = re.findall(r'<a href="([^"]+)" title="([^"]+)"', row_text)
    for href, title in matches:
        if 'collabpage' in href:
            return href, 'km', title
        elif 'ones.sankuai.com' in href:
            return href, 'ones', title
    return None, None, None


def count_cells(row_lines: list[str]) -> int:
    """计算 <td> 单元格数量（处理 colspan）"""
    count = 0
    for line in row_lines:
        if '<td' in line:
            colspan_match = re.search(r'colspan="(\d+)"', line)
            if colspan_match:
                count += int(colspan_match.group(1))
            else:
                count += 1
    return count


def remove_rowspan_cell(row_lines: list[str]) -> list[str]:
    """移除行中的 rowspan 方向单元格"""
    output = []
    i = 0
    while i < len(row_lines):
        line = row_lines[i]
        stripped = line.strip()
        if stripped.startswith('<td') and 'rowspan=' in stripped:
            # 检查是否方向单元格
            cell_block = '\n'.join(row_lines[i:min(i+10, len(row_lines))])
            if any(kw in cell_block for kw in ['酒店', '鲍立磊', '到餐', '服务零售', '门票', '毕杰涛', '徐俊', '王松']):
                # 跳过整个 td
                depth = 0
                while i < len(row_lines):
                    l = row_lines[i]
                    depth += l.count('<td') - l.count('</td>')
                    i += 1
                    if depth <= 0:
                        break
                continue
        output.append(line)
        i += 1
    return output


def make_standard_hotel_row(ones_url: str, title: str, 
                             prd_url: Optional[str] = None, prd_title: Optional[str] = None,
                             person_name: str = '', person_uid: str = '',
                             person_empid: str = '') -> str:
    """创建标准 16 列酒店数据行"""
    link_url = prd_url if prd_url else ones_url
    link_text = prd_title if prd_title else title
    
    mention = ''
    if person_name:
        if person_uid and person_empid:
            mention = f'<p><km-mention name="{person_name}" uid="{person_uid}" empId="{person_empid}" /></p>'
        else:
            mention = f'<p>@{person_name}</p>'
    
    return f'''<tr>
<td colwidth="[50]" numCell="true">
<p />
</td>
<td colwidth="[401]">
<p><a href="{link_url}" title="{link_text}">{link_text}</a></p>
</td>
<td colwidth="[123]">
{mention}
</td>
<td colwidth="[94]">
<p />
</td>
<td colwidth="[114]">
<p align="center" />
</td>
<td colwidth="[395]">
<p />
</td>
<td colwidth="[243]">
<p />
</td>
<td colwidth="[343]">
<p />
</td>
<td colwidth="[189]">
<p />
</td>
<td colwidth="[112]">
<p />
</td>
<td colwidth="[150]">
<p />
</td>
<td colwidth="[119]">
<p />
</td>
<td colwidth="[152]">
<p />
</td>
<td colwidth="[152]">
<p />
</td>
<td colwidth="[258]">
<p />
</td>
<td colwidth="[XXX]">
<p />
</td>
</tr>'''


def make_first_hotel_row(rowspan: int, ones_url: str, title: str,
                          prd_url: Optional[str] = None, prd_title: Optional[str] = None,
                          mentions_xml: str = '') -> str:
    """创建酒店首行（17 逻辑列含 rowspan 方向列）"""
    link_url = prd_url if prd_url else ones_url
    link_text = prd_title if prd_title else title
    
    return f'''<tr>
<td colwidth="[50]" numCell="true">
<p />
</td>
<td rowspan="{rowspan}" colwidth="[184]" verticalAlign="middle">
<p>酒店<km-mention name="鲍立磊(Andrew Bao)" uid="baolilei" empId="22624690" /></p>
</td>
<td colwidth="[401]">
<p><a href="{link_url}" title="{link_text}">{link_text}</a></p>
</td>
<td colwidth="[123]">
{mentions_xml}
</td>
<td colwidth="[94]">
<p />
</td>
<td colwidth="[114]">
<p align="center" />
</td>
<td colwidth="[395]">
<p />
</td>
<td colwidth="[243]">
<p />
</td>
<td colwidth="[343]">
<p />
</td>
<td colwidth="[189]">
<p />
</td>
<td colwidth="[112]">
<p />
</td>
<td colwidth="[150]">
<p />
</td>
<td colwidth="[119]">
<p />
</td>
<td colwidth="[152]">
<p />
</td>
<td colwidth="[152]">
<p />
</td>
<td colwidth="[258]">
<p />
</td>
<td colwidth="[XXX]">
<p />
</td>
</tr>'''


def normalize_title(title: str) -> str:
    """标准化标题用于模糊比较"""
    t = title.lower()
    t = re.sub(r'^【[^】]*】', '', t)
    t = re.sub(r'^(prd|已上线|待评审|需求)', '', t)
    t = re.sub(r'[\s\-_—–·。,，、！!？?（）()【】\[\]{}「」\'\'\"\″«»<>《》~@#$%^&*+=|/\\。，；：]', '', t)
    t = re.sub(r'[一二三四五六七八九十\d]+期', '', t)
    t = re.sub(r'v\d+(\.\d+)*', '', t)
    return t.strip()


def match_score(req_item: dict, xml_km_id: Optional[str], xml_ones_id: Optional[str],
                xml_title: str, xml_assignees: list[str]) -> float:
    """计算需求项与 XML 行的匹配分数 (0-1)"""
    score = 0.0
    
    if req_item['prd_km_id'] and req_item['prd_km_id'] == xml_km_id:
        score += 0.9
    
    if req_item['ones_id'] == xml_ones_id:
        score += 0.8
    
    # ONES ID 冲突惩罚：两者都有 ONES ID 但不同 → 极不可能匹配
    if req_item['ones_id'] and xml_ones_id and req_item['ones_id'] != xml_ones_id:
        score -= 0.5
    
    req_title_norm = normalize_title(req_item.get('prd_title') or req_item.get('ones_title', ''))
    xml_title_norm = normalize_title(xml_title)
    if req_title_norm and xml_title_norm:
        if req_title_norm == xml_title_norm:
            score += 0.7
        elif req_title_norm in xml_title_norm or xml_title_norm in req_title_norm:
            score += 0.5
        else:
            common = set(req_title_norm) & set(xml_title_norm)
            total = set(req_title_norm) | set(xml_title_norm)
            if total:
                score += len(common) / len(total) * 0.3
    
    if xml_assignees and req_item.get('assignees'):
        req_set = set(a.strip('@') for a in req_item['assignees'])
        xml_names = set()
        for a in xml_assignees:
            short = re.sub(r'[（(].*?[）)]', '', a).strip()
            xml_names.add(short)
        if req_set & xml_names:
            score += 0.3
    
    return max(min(score, 1.0), 0.0)


def get_person_info(name: str, empid_map: dict) -> tuple[str, str]:
    """获取人员的 uid 和 empId"""
    clean_name = name.strip('@').strip()
    if clean_name in empid_map:
        return empid_map[clean_name]['uid'], empid_map[clean_name]['empId']
    short = re.sub(r'[（(].*?[）)]', '', clean_name).strip()
    if short in empid_map:
        return empid_map[short]['uid'], empid_map[short]['empId']
    return '', ''


def main():
    parser = argparse.ArgumentParser(description='同步酒店 AI-Coding 需求文档')
    parser.add_argument('--xml-path', required=True, help='AI-Coding XML 文件路径')
    parser.add_argument('--requirement-md', required=True, help='需求列表 markdown 文件路径')
    parser.add_argument('--output', required=True, help='输出 XML 文件路径')
    parser.add_argument('--changes-output', help='变更日志 JSON 文件路径')
    args = parser.parse_args()
    
    with open(args.xml_path, 'r', encoding='utf-8') as f:
        xml_text = f.read()
    xml_lines = xml_text.split('\n')
    
    with open(args.requirement_md, 'r', encoding='utf-8') as f:
        req_md = f.read()
    
    req_items = parse_requirement_md(req_md)
    print(f"[INFO] 需求列表中提取到 {len(req_items)} 个酒店需求项")
    
    empid_map = extract_empid_map(xml_text)
    print(f"[INFO] 提取到 {len(empid_map)} 个人员映射")
    
    table_start, table_end = find_table_bounds(xml_lines)
    if table_start is None:
        print("[ERROR] 未找到主统计表", file=sys.stderr)
        sys.exit(1)
    
    hotel_first_ts, hotel_last_te, rowspan = find_hotel_section(xml_lines, table_start, table_end)
    if hotel_first_ts is None:
        print("[ERROR] 未找到酒店区域", file=sys.stderr)
        sys.exit(1)
    
    print(f"[INFO] 酒店区域: 行 {hotel_first_ts+1}-{hotel_last_te+1}, rowspan={rowspan}")
    
    tr_starts = []
    tr_ends = []
    for i in range(table_start, table_end + 1):
        s = xml_lines[i].strip()
        if s.startswith('<tr'):
            tr_starts.append(i)
        if s == '</tr>':
            tr_ends.append(i)
    
    data_tr_starts = tr_starts[1:]
    data_tr_ends = tr_ends[1:]
    
    first_hotel_data_idx = None
    for idx, ts in enumerate(data_tr_starts):
        if ts == hotel_first_ts:
            first_hotel_data_idx = idx
            break
    
    if first_hotel_data_idx is None:
        print("[ERROR] 无确定位酒店行索引", file=sys.stderr)
        sys.exit(1)
    
    hotel_range = range(first_hotel_data_idx, first_hotel_data_idx + rowspan)
    
    current_hotel_rows = []
    for idx in hotel_range:
        if idx >= len(data_tr_starts) or idx >= len(data_tr_ends):
            break
        ts = data_tr_starts[idx]
        te = data_tr_ends[idx]
        current_hotel_rows.append({
            'tr_start': ts,
            'tr_end': te,
            'km_id': get_row_km_id(xml_lines, ts, te),
            'ones_id': get_row_ones_id(xml_lines, ts, te),
            'title': get_row_title(xml_lines, ts, te),
            'assignees': get_row_assignees(xml_lines, ts, te),
            'link_url': get_row_first_link(xml_lines, ts, te)[0],
            'link_type': get_row_first_link(xml_lines, ts, te)[1],
            'link_text': get_row_first_link(xml_lines, ts, te)[2],
        })
    
    print(f"[INFO] 当前 AI-Coding 中酒店行数: {len(current_hotel_rows)}")
    
    # 贪心匹配
    all_pairs = []
    for ri, req in enumerate(req_items):
        ci_first = first_hotel_data_idx
        for ci_offset in range(len(current_hotel_rows)):
            row = current_hotel_rows[ci_offset]
            score = match_score(req, row['km_id'], row['ones_id'], row['title'], row['assignees'])
            if score > 0.3:
                all_pairs.append((ri, ci_offset, score))
    
    all_pairs.sort(key=lambda x: -x[2])
    
    matches = []
    used_req = set()
    used_row = set()
    for ri, ci, score in all_pairs:
        if ri in used_req or ci in used_row:
            continue
        matches.append((ri, ci, score))
        used_req.add(ri)
        used_row.add(ci)
    
    # 过滤标题不匹配的匹配：如果需求名称变了，不是同一个需求
    # 应该删除旧行、新增空白行，而不是保留旧行只更新链接
    filtered_matches = []
    for ri, ci, score in matches:
        req = req_items[ri]
        row = current_hotel_rows[ci]
        req_title = req.get('prd_title') or req.get('ones_title', '')
        if normalize_title(req_title) != normalize_title(row['title']):
            # 标题不同，不是同一个需求，取消匹配
            continue
        filtered_matches.append((ri, ci, score))
    matches = filtered_matches
    
    matched_row_indices = set(ci for _, ci, _ in matches)
    matched_req_indices = set(ri for ri, _, _ in matches)
    rows_to_delete = [ci for ci in range(len(current_hotel_rows)) if ci not in matched_row_indices]
    reqs_to_add = [ri for ri in range(len(req_items)) if ri not in matched_req_indices]
    
    print(f"[INFO] 保留: {len(matches)}, 删除: {len(rows_to_delete)}, 新增: {len(reqs_to_add)}")
    
    new_hotel_row_count = len(matches) + len(reqs_to_add)
    
    # 准备保留行的输出（16列格式）- 保持原文行顺序
    link_updates = []
    
    # 按原始行索引排序匹配结果，保持原文顺序
    matches_by_row = sorted(matches, key=lambda x: x[1])  # 按 ci (行索引) 排序
    
    kept_rows_by_idx = {}  # ci -> row_text
    
    for ri, ci, score in matches_by_row:
        row = current_hotel_rows[ci]
        req = req_items[ri]
        row_lines = xml_lines[row['tr_start']:row['tr_end']+1]
        
        # 检查是否需要更新链接为 PRD（仅第一列的链接）
        if req['prd_km_id'] and req['prd_url'] and req.get('prd_title'):
            if row['link_type'] == 'ones' or row['km_id'] != req['prd_km_id']:
                row_text = '\n'.join(row_lines)
                new_url = req['prd_url']
                new_title = req['prd_title']
                # 匹配含任意属性的 <a> 标签
                row_text = re.sub(
                    r'<a\s+href="[^"]+"[^>]*>[^<]*</a>',
                    f'<a href="{new_url}" title="{new_title}">{new_title}</a>',
                    row_text,
                    count=1
                )
                row_lines = row_text.split('\n')
                link_updates.append({
                    'title': row['title'],
                    'old_url': row['link_url'],
                    'new_url': new_url,
                    'new_title': new_title,
                })
        
        # 移除 rowspan 方向单元格（标准化为 16 列）
        row_lines = remove_rowspan_cell(row_lines)
        kept_rows_by_idx[ci] = '\n'.join(row_lines)
    
    # 准备新增行
    new_rows_text = []
    added_details = []
    for ri in reqs_to_add:
        req = req_items[ri]
        person_name = req['assignees'][0] if req['assignees'] else ''
        person_uid, person_empid = get_person_info(person_name, empid_map)
        
        row_text = make_standard_hotel_row(
            ones_url=req['ones_url'],
            title=req['ones_title'],
            prd_url=req.get('prd_url'),
            prd_title=req.get('prd_title'),
            person_name=person_name,
            person_uid=person_uid,
            person_empid=person_empid,
        )
        new_rows_text.append(row_text)
        added_details.append({
            'title': req.get('prd_title') or req['ones_title'],
            'assignee': person_name,
            'has_prd': bool(req.get('prd_km_id')),
        })
    
    # 构建输出 XML
    output_lines = []
    output_lines.extend(xml_lines[:table_start])
    
    first_hotel_tr_line = data_tr_starts[first_hotel_data_idx]
    output_lines.extend(xml_lines[table_start:first_hotel_tr_line])
    
    # 找到第一个保留行（最小行索引），用于构建 rowspan 首行
    if kept_rows_by_idx:
        first_kept_ci = min(kept_rows_by_idx.keys())
        first_kept_row_text = kept_rows_by_idx[first_kept_ci]
        
        # 为首行添加 rowspan 方向单元格
        # 在第一个 td (numCell) 之后插入 rowspan 单元格
        first_row_lines = first_kept_row_text.split('\n')
        # 找到 numCell td 的结束位置
        num_cell_end = -1
        for i, l in enumerate(first_row_lines):
            if 'numCell="true"' in l:
                # 找到这个 td 的下面几行
                for j in range(i+1, min(i+5, len(first_row_lines))):
                    if '</td' in first_row_lines[j]:
                        num_cell_end = j
                        break
                break
        
        if num_cell_end >= 0:
            rowspan_cell = [
                f'<td rowspan="{new_hotel_row_count}" colwidth="[184]" verticalAlign="middle">',
                '<p>酒店<km-mention name="鲍立磊(Andrew Bao)" uid="baolilei" empId="22624690" /></p>',
                '</td>',
            ]
            first_row_lines = first_row_lines[:num_cell_end+1] + rowspan_cell + first_row_lines[num_cell_end+1:]
        
        # 按原始行索引顺序输出保留行
        for ci in sorted(kept_rows_by_idx.keys()):
            output_lines.extend(first_row_lines if ci == first_kept_ci else kept_rows_by_idx[ci].split('\n'))
    elif new_rows_text:
        first_new = new_rows_text[0]
        first_new = re.sub(
            r'(<td colwidth="\[50\]" numCell="true">\s*<p />\s*</td>)',
            r'\1\n<td rowspan="' + str(new_hotel_row_count) + r'" colwidth="[184]" verticalAlign="middle">\n<p>酒店<km-mention name="鲍立磊(Andrew Bao)" uid="baolilei" empId="22624690" /></p>\n</td>',
            first_new,
            count=1
        )
        output_lines.extend(first_new.split('\n'))
        for new_text in new_rows_text[1:]:
            output_lines.extend(new_text.split('\n'))
    
    # 新增行（追加在保留行之后）
    for new_text in new_rows_text:
        output_lines.extend(new_text.split('\n'))
    
    # 末尾内容
    last_hotel_line = data_tr_ends[first_hotel_data_idx + rowspan - 1]
    output_lines.extend(xml_lines[last_hotel_line+1:])
    
    result = '\n'.join(output_lines)
    
    # 修复脚注内容：移除 <km-footnote-item> 内的 <del> 标签
    # 这些删除线会导致 hover 注释时不显示内容
    in_footnote = False
    fixed_lines = []
    footnote_fixed_count = 0
    for line in result.split('\n'):
        if '<km-footnote-item' in line:
            in_footnote = True
        if '</km-footnote-item>' in line:
            in_footnote = False
        if in_footnote or '<km-footnote-item' in line or '</km-footnote-item>' in line:
            if '<del>' in line or '</del>' in line:
                footnote_fixed_count += line.count('<del>')
                line = line.replace('<del>', '').replace('</del>', '')
        fixed_lines.append(line)
    result = '\n'.join(fixed_lines)
    if footnote_fixed_count > 0:
        print(f"[INFO] 已修复 {footnote_fixed_count} 处脚注 <del> 标签")
    
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"[INFO] 输出已写入 {args.output}")
    
    # 输出变更日志
    changes = {
        'deleted': [{'title': current_hotel_rows[ci]['title'], 'assignees': current_hotel_rows[ci]['assignees'], 'km_id': current_hotel_rows[ci]['km_id']} for ci in rows_to_delete],
        'added': added_details,
        'kept': [{'title': current_hotel_rows[ci]['title'], 'assignees': current_hotel_rows[ci]['assignees'], 'score': round(s, 2)} for _, ci, s in matches],
        'link_updated': link_updates,
    }
    
    if args.changes_output:
        with open(args.changes_output, 'w', encoding='utf-8') as f:
            json.dump(changes, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 变更日志已写入 {args.changes_output}")
    
    print(f"\n=== 变更摘要 ===")
    print(f"删除 ({len(changes['deleted'])}):")
    for d in changes['deleted']:
        print(f"  ❌ {d['title'][:50]} [{' / '.join(d['assignees'])}]")
    print(f"新增 ({len(changes['added'])}):")
    for a in changes['added']:
        flag = " (PRD)" if a['has_prd'] else " (ONES)"
        print(f"  ➕ {a['title'][:50]} [{a['assignee']}]{flag}")
    print(f"链接更新 ({len(changes['link_updated'])}):")
    for u in changes['link_updated']:
        print(f"  � {u['title'][:50]}: ONES → PRD")
    print(f"保留 ({len(changes['kept'])}):")
    for k in changes['kept']:
        print(f"  ✓  {k['title'][:50]} [{' / '.join(k['assignees'])}] score={k['score']}")


if __name__ == '__main__':
    main()
