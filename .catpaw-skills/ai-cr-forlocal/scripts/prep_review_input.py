#!/usr/bin/env python3
"""4-Review 预处理：从 diff 预切 issue 上下文 + 未覆盖文件 hunks + 规则文件合集
子 Agent 零 diff 读取，全部输入经 attachments 注入。

用法：python3 prep_review_input.py --repo {repo} [--diff /tmp/local_cr_diff.txt]
     [--issues /tmp/cr_issues_{repo}_step4.json] [--signals /tmp/cr_signals_{repo}.md]
     [--skill-root <skill dir>]
输出：
  /tmp/cr_review_input_{repo}.json  第一轮输入（issue 5字段 + context ±30行）
  /tmp/cr_review_miss_{repo}.json   第二轮输入（未覆盖文件 hunks）
  /tmp/cr_review_rules_{repo}.md    涉及规则文件内容合集（distinct ruleId）
  /tmp/cr_review_meta_{repo}.json   分流判定（small|large + 分片方案）
"""
import argparse, json, os, re, glob as g

CTX = 30

def parse_diff(diff_text):
    """按文件切 hunks: {file: [lines...]}（带 hunk 头）"""
    files, cur, buf = {}, None, []
    for ln in diff_text.splitlines():
        m = re.match(r'^\+\+\+ b/(.+)$', ln)
        if m:
            if cur: files[cur] = buf
            cur, buf = m.group(1), []
        elif cur is not None:
            if ln.startswith('diff ') or ln.startswith('--- a/'):
                files[cur] = buf; cur, buf = None, []
            else:
                buf.append(ln)
    if cur: files[cur] = buf
    return files

def hunk_context(file_lines, target_line, ctx=CTX):
    """取目标行号 ±ctx 的 hunk 附近内容（基于新文件行号近似定位）"""
    # 在 hunks 中找包含 target_line 的 hunk
    pos = 0
    for i, ln in enumerate(file_lines):
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', ln)
        if m:
            start = int(m.group(1)); span = sum(1 for x in file_lines[i+1:] if not x.startswith('-')) if False else None
            # 近似：从 hunk 头往下数非删除行
            nl = start; ok = False
            for j in range(i+1, len(file_lines)):
                if file_lines[j].startswith('@@'): break
                if not file_lines[j].startswith('-'): nl += 1
                if nl >= target_line: ok = True; break
            if ok:
                lo = max(0, i - 2); hi = min(len(file_lines), j + ctx)
                return '\n'.join(file_lines[lo:hi])
    # 找不到精确 hunk：退化为文件级前 80 行
    return '\n'.join(file_lines[:80])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--repo-path', default=None)  # issue 文件不在 diff 时，预读该文件 ±ctx 行注入，子 Agent 零仓库读取
    ap.add_argument('--diff', default='/tmp/local_cr_diff.txt')
    ap.add_argument('--issues', default=None)
    ap.add_argument('--signals', default=None)
    ap.add_argument('--skill-root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()

    repo = a.repo
    issues_path = a.issues or f'/tmp/cr_issues_{repo}_step4.json'
    signals_path = a.signals or f'/tmp/cr_signals_{repo}.md'

    diff_text = open(a.diff, errors='replace').read()
    files = parse_diff(diff_text)
    issues = json.load(open(issues_path))
    ctx_w = CTX  # 仓库预读窗口与 diff 上下文同宽

    # P0/P1 进第一轮
    p01 = [i for i in issues if i.get('severity') in ('P0', 'P1')]

    # 逐条挂上下文
    review_input = []
    for i in p01:
        fl = files.get(i['file'], [])
        if fl:
            ctx = hunk_context(fl, int(i.get('line', 0)))
        else:
            # 文件不在 diff 中 → 预读仓库文件该行附近 ±ctx 行注入（子 Agent 零仓库读取）
            src = ''
            if a.repo_path:
                try:
                    fp = os.path.join(a.repo_path, i['file'])
                    lines = open(fp, errors='replace').read().splitlines()
                    ln = max(1, int(i.get('line', 1)))
                    lo, hi = max(0, ln - ctx_w), min(len(lines), ln + ctx_w)
                    src = '\n'.join(f'{n+1}: {lines[n]}' for n in range(lo, hi))
                except Exception as e:
                    src = f'(预读失败: {e})'
            ctx = f'(文件不在 diff 中。仓库源码 ±{ctx_w} 行已预读注入：)\n{src}' if src else '(文件不在 diff 中且无法预读 — 请 verdict=open_question/to_human)'
        review_input.append({
            'file': i['file'], 'line': i.get('line'), 'ruleId': i.get('ruleId'),
            'severity': i.get('severity'), 'summary': i.get('summary'), 'context': ctx,
        })

    # 未覆盖文件（diff 文件集 - 有 issue 的文件）
    covered = {i['file'] for i in issues}
    uncovered = {f: hunks for f, hunks in files.items() if f not in covered}
    miss = {f: '\n'.join(h[:120]) for f, h in uncovered.items()}  # 每文件截 120 行防超大

    # 规则文件合集（distinct ruleId 去前缀后到 references/checklists/ 找）
    rids = sorted({i['ruleId'].split(':', 1)[-1] for i in p01 if i.get('ruleId')})
    parts = []
    # 从脚本自身位置推导 checklists 目录，兼容工作区/SkillHub安装/CatPaw等多种部署路径
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    cl_dir = os.path.join(_script_dir, '..', 'references', 'checklists')
    cl_dir = os.path.realpath(cl_dir)
    for rid in rids:
        hits = g.glob(os.path.join(cl_dir, f'*{rid}*.md'))
        for h in hits[:1]:
            parts.append(f"===== {os.path.basename(h)} =====\n" + open(h, errors='replace').read()[:6000])
    rules_md = '\n\n'.join(parts) if parts else '(未匹配到规则文件)'

    # 分流判定
    n_issues, n_files = len(p01), len({i['file'] for i in p01})
    mode = 'small' if (n_issues <= 8 and n_files <= 3) else 'large'
    meta = {'mode': mode, 'p01_count': n_issues, 'file_count': n_files}
    if mode == 'large':
        # 按文件分片，k<=4，实际生成分片 JSON 文件
        by_file = {}
        for r in review_input: by_file.setdefault(r['file'], []).append(r)
        all_files = sorted(by_file.keys())
        k = min(4, len(all_files))
        chunks = [all_files[i::k] for i in range(k)]
        chunks = [c for c in chunks if c]
        meta['shards'] = chunks
        for idx, chunk_files in enumerate(chunks, 1):
            shard_issues = []
            for f in chunk_files:
                shard_issues.extend(by_file[f])
            shard_path = f'/tmp/cr_review_input_{repo}_shard_{idx}.json'
            json.dump(shard_issues, open(shard_path, 'w'), ensure_ascii=False, indent=1)
        meta['shard_count'] = len(chunks)

    json.dump(review_input, open(f'/tmp/cr_review_input_{repo}.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(miss, open(f'/tmp/cr_review_miss_{repo}.json', 'w'), ensure_ascii=False, indent=1)
    open(f'/tmp/cr_review_rules_{repo}.md', 'w').write(rules_md)
    json.dump(meta, open(f'/tmp/cr_review_meta_{repo}.json', 'w'), ensure_ascii=False)

    print(f"✅ 预处理完成: P0/P1={n_issues} 文件={n_files} 模式={mode} 未覆盖文件={len(miss)} 规则={len(rids)}")

if __name__ == '__main__':
    main()
