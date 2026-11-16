#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_design_links.py - PR 描述夹带学城方案文档：确定性提取链路

职责（仅确定性部分，语义判断由主 Agent 在 3C 执行）：
  1. 从 PR description 提取 km.sankuai.com/(page|collabpage)/{id} 链接，按 docId 去重
  2. xtable 链接只登记不拉取；非 km 域名忽略
  3. 逐个调用 oa-skills citadel getSimpleMarkdown 拉取落盘（单文档超时 30s）
  4. 单文档 raw 截断 30KB；合并冻结快照 wiki_spec_frozen.md（头部含来源链接+时间戳）
  5. 输出 design_links.json 回执到 stdout

零影响契约：描述无链接 → exit 0，输出 {"links":[],"frozen":null}，不产生任何文件副作用。

用法：
  python3 extract_design_links.py --description-file <file> --run-dir <dir>
  echo "$PR_DESC" > desc.txt && python3 extract_design_links.py --description-file desc.txt --run-dir "$CR_RUN_DIR"
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

LINK_RE = re.compile(r'km\.sankuai\.com/(page|collabpage|md)/(\d+)')
XTABLE_RE = re.compile(r'km\.sankuai\.com/(?:xtable|table)/(\d+)')
RAW_LIMIT = 30 * 1024          # 单文档 raw 截断上限
FETCH_TIMEOUT = 30             # 单文档拉取超时(秒)
MAX_DOCS = 3                   # 最多拉取文档数, 上限 3 篇, 防止描述携带大量链接导致拉取超时


def log(msg):
    print(msg, file=sys.stderr)


def extract_links(text):
    """提取链接,按 docId 去重。返回 (docs, xtable_ids)。"""
    docs, seen = [], set()
    for m in LINK_RE.finditer(text or ''):
        doc_id = m.group(2)
        if doc_id not in seen:
            seen.add(doc_id)
            docs.append({'docId': doc_id, 'url': 'https://km.sankuai.com/%s/%s' % (m.group(1), doc_id)})
    xtable_ids = sorted(set(m.group(1) for m in XTABLE_RE.finditer(text or '')))
    return docs, xtable_ids


def read_truncated_bytes(path, limit):
    """按字节读取并截断,返回 (content, truncated)。防止多字节字符被切半。"""
    with open(path, 'rb') as f:
        raw = f.read(limit + 8)  # 多读 8 字节用于判断是否超限
    truncated = len(raw) > limit
    if truncated:
        raw = raw[:limit]
        # 回退至 UTF-8 字符边界,避免多字节字符被切半
        while raw and (raw[-1] & 0xC0) == 0x80:
            raw = raw[:-1]
        content = raw.decode('utf-8', errors='ignore') \
            + '\n\n<!-- [TRUNCATED at %d bytes by extract_design_links] -->\n' % limit
    else:
        content = raw.decode('utf-8', errors='ignore')
    return content, truncated


def fetch_doc(doc, run_dir):
    """拉取单篇文档。成功填充 raw_path/title/size,失败 status=fetch_failed。"""
    raw_path = os.path.join(run_dir, 'wiki_raw_%s.md' % doc['docId'])
    cmd = ['oa-skills', 'citadel', 'getSimpleMarkdown',
           '--contentId', doc['docId'], '--output', raw_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=FETCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        doc['status'] = 'fetch_failed'
        doc['error'] = 'timeout(%ds)' % FETCH_TIMEOUT
        return doc
    except FileNotFoundError:
        doc['status'] = 'fetch_failed'
        doc['error'] = 'oa-skills not found'
        return doc
    if proc.returncode != 0 or not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
        err_text = (proc.stderr or proc.stdout or '')
        err_text = '\n'.join(l for l in err_text.splitlines()
                              if 'Warning' not in l and 'trace-warnings' not in l).strip()
        doc['status'] = 'fetch_failed'
        doc['error'] = err_text[:200]
        return doc
    content, _ = read_truncated_bytes(raw_path, RAW_LIMIT)
    if 'TRUNCATED at' in content:
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(content)
    # 标题树（# 到 ### 行,去重）
    titles, t_seen = [], set()
    for line in content.splitlines():
        m = re.match(r'^(#{1,3})\s+(.+)$', line.strip())
        if m and m.group(2).strip() not in t_seen:
            t_seen.add(m.group(2).strip())
            titles.append(m.group(2).strip())
        if len(titles) >= 40:
            break
    doc.update({'status': 'fetched', 'rawPath': raw_path,
                'title': titles[0] if titles else '',
                'titleTree': titles, 'size': len(content.encode('utf-8'))})
    return doc


def freeze(docs, run_dir):
    """合并全部拉取成功的文档为冻结快照。"""
    fetched = [d for d in docs if d.get('status') == 'fetched']
    if not fetched:
        return None
    frozen_path = os.path.join(run_dir, 'wiki_spec_frozen.md')
    parts = [
        '<!-- wiki_spec_frozen: 随单方案冻结快照 -->',
        '<!-- fetched_at: %s -->' % time.strftime('%Y-%m-%d %H:%M:%S %z'),
    ]
    for d in fetched:
        parts.append('\n<!-- source: %s -->\n' % d['url'])
        with open(d['rawPath'], encoding='utf-8', errors='ignore') as f:
            parts.append(f.read())
    with open(frozen_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return frozen_path


def main():
    ap = argparse.ArgumentParser(description='PR 描述学城方案链接确定性提取')
    ap.add_argument('--description-file', required=True, help='PR 描述文本文件')
    ap.add_argument('--run-dir', required=True, help='CR 运行目录($CR_RUN_DIR)')
    args = ap.parse_args()

    try:
        with open(args.description_file, encoding='utf-8', errors='ignore') as f:
            desc = f.read()
    except OSError as e:
        print(json.dumps({'links': [], 'frozen': None, 'error': 'read_desc_failed: %s' % e},
                         ensure_ascii=False))
        sys.exit(0)  # 描述读不到 = 无法判定有链接 = 零影响退出

    docs, xtable_ids = extract_links(desc)
    if not docs:
        print(json.dumps({'links': [], 'xtableIgnored': xtable_ids, 'frozen': None},
                         ensure_ascii=False))
        return

    os.makedirs(args.run_dir, exist_ok=True)
    ignored = []
    if len(docs) > MAX_DOCS:
        ignored = [{'docId': d['docId'], 'url': d['url'],
                    'reason': 'over_max_docs'} for d in docs[MAX_DOCS:]]
        log('WARN: %d links found, only first %d fetched, %d ignored'
            % (len(docs), MAX_DOCS, len(ignored)))
        docs = docs[:MAX_DOCS]

    for d in docs:
        fetch_doc(d, args.run_dir)
        log('%s -> %s' % (d['url'], d.get('status')))

    frozen = freeze(docs, args.run_dir)
    print(json.dumps({'links': docs, 'xtableIgnored': xtable_ids,
                      'ignored': ignored, 'frozen': frozen},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
