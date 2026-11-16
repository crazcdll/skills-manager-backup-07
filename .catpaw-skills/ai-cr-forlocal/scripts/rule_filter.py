#!/usr/bin/env python3
"""
rule_filter.py — 规则文件级过滤器（prep 阶段，跑在信号扫描后、路由计划前）
三层漏斗滤掉不相干规则文件：
  L0 组级：rule-index.json trigger（已有 matched_groups 基础，这里复核）
  L1 文件级：frontmatter（description/globs/category/priority）+ 条目关键词 ∩ diff/信号
  L2 条目级：### MT:xxx 块级关键词命中 → 文件内只保留命中块（渐进式读取的裁剪版）
输出：
  /tmp/cr_rule_filter.json  — 每组的通过文件清单+命中条目数（4-B 路数依据）
  /tmp/cr_rule_trim/{group}/{file}.md — 裁剪版规则文件（4-B 渐进注入用）
"""
import json, re, sys, argparse
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CHECKLIST_DIR = SKILL_ROOT / "references" / "checklists" / "mt-java-coding-standards"

TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_.@]*')

def has_code_token(s):
    return bool(TOKEN_RE.search(s))


def parse_rule_file(path):
    """规则文件 → (frontmatter dict, 头部, blocks[{id, keywords, raw}])"""
    t = path.read_text(encoding="utf-8")
    fm = {}
    m = re.match(r'^---\n(.*?)\n---\n?', t, re.S)
    body = t
    if m:
        for line in m.group(1).splitlines():
            kv = line.split(":", 1)
            if len(kv) == 2:
                fm[kv[0].strip()] = kv[1].strip()
        body = t[m.end():]
    # 块级：### MT:xxx 到下一个 ###/## 结束
    blocks = []
    cur = None
    head_lines = []
    for ln in body.splitlines():
        bm = re.match(r'^### (MT:[A-Za-z0-9\-]+)\s*(.*)', ln)
        if bm:
            if cur: blocks.append(cur)
            cur = {"id": bm.group(1), "title": bm.group(2).strip(), "lines": [ln], "keywords": []}
        elif cur is not None:
            cur["lines"].append(ln)
        else:
            head_lines.append(ln)
    if cur: blocks.append(cur)
    # 块关键词：标题 + 行内代码 token（`xxx`）取核心 API/注解词
    for b in blocks:
        kws = set()
        title = b["title"]
        for w in re.findall(r'[A-Za-z][A-Za-z0-9_]{3,}', title):
            kws.add(w)
        for ln in b["lines"]:
            for w in re.findall(r'`([A-Za-z_][A-Za-z0-9_.@]*)`', ln):
                kws.add(w)
        b["keywords"] = sorted(kws)
    return fm, "\n".join(head_lines), blocks


def file_hit(fm, blocks, diff_text, active_sigs):
    """文件级判定：frontmatter 描述词或块关键词命中 diff → 通过"""
    desc_words = set()
    for field in ("description", "category"):
        v = fm.get(field, "")
        for w in re.findall(r'[A-Za-z][A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,}', v):
            desc_words.add(w)
    def tok_hit(word):
        """中文子串 / 英文词边界匹配"""
        if re.search(r'[\u4e00-\u9fff]', word):
            return word in diff_text
        return re.search(r'\b' + re.escape(word) + r'\b', diff_text) is not None

    desc_only = []
    for w in desc_words:
        if w and tok_hit(w):
            desc_only.append(w)
    for b in blocks:
        for kw in b["keywords"]:
            if tok_hit(kw):
                return True, f"rule:{b['id']}({kw})"
    if desc_only:
        return False, "desc-only:" + ",".join(desc_only[:3])  # 弱证据：描述命中但无块命中 → 不通过
    return False, ""


def block_hit(b, diff_text):
    """块级：关键词命中 diff"""
    for kw in b["keywords"]:
        if kw and kw in diff_text:
            return True, kw
    return False, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matched", default="/tmp/cr_matched_rules.json")
    ap.add_argument("--signals", default="/tmp/cr_signal_rules.json")
    ap.add_argument("--diff", default="/tmp/local_cr_diff.txt")
    ap.add_argument("--output", default="/tmp/cr_rule_filter.json")
    ap.add_argument("--outdir", default="/tmp/cr_rule_trim")
    args = ap.parse_args()

    dp = Path(args.diff)
    if not dp.exists() or dp.stat().st_size == 0:
        print("FATAL: diff 缺失/为空", file=sys.stderr)
        sys.exit(1)
    raw = dp.read_text(encoding="utf-8", errors="replace")
    # 预清洗：剥离 git 元数据行（index hash/@@/diff --git/+++/---），防 "index"/"name" 类误命中
    body_lines = [ln for ln in raw.splitlines()
                  if not (ln.startswith(("diff --git", "index ", "@@", "--- ", "+++ ", "new file mode",
                                          "similarity index", "rename ", "old mode", "new mode", "Binary files")))]
    # 只保留 + 开头的变更内容行（关键词匹配的目标），context 行对命中判断非必需且可能引入已删除代码
    diff_text = "\n".join(ln[1:] if ln.startswith("+") else ln for ln in body_lines)

    matched = json.loads(Path(args.matched).read_text(encoding="utf-8"))
    try:
        sig = json.loads(Path(args.signals).read_text(encoding="utf-8"))
        active_sigs = set(sig.get("active_signals", []))
    except Exception:
        active_sigs = set()

    # 组→规则文件 映射：rule-index rules 列表去掉编号前缀匹配文件
    import unicodedata
    outdir = Path(args.outdir)
    result = {"groups": {}, "summary": ""}
    total_pass, total_files = 0, 0
    for grp, rule_names in matched.get("rule_files", {}).items():
        files_pass = []
        gdir = outdir / grp
        gdir.mkdir(parents=True, exist_ok=True)
        for rn in rule_names:
            # 规则名如 "HA-06-消息队列高可用规范" → 找文件
            fname = next((f.name for f in CHECKLIST_DIR.glob(rn.split("-")[0] + "-*.md")
                          if unicodedata.normalize("NFC", f.stem) == unicodedata.normalize("NFC", rn.split("-", 1)[1] if "-" in rn else rn)), None)
            # 简化匹配：stem == rn
            cands = list(CHECKLIST_DIR.glob(rn + ".md"))
            path = cands[0] if cands else None
            if path is None:
                # 规则名可能不带全名，跳过（组级兜底：规则名进组级通过清单，不裁剪）
                files_pass.append({"file": rn, "pass": True, "why": "group-level(no-file)", "blocks_kept": None})
                total_files += 1
                continue
            total_files += 1
            fm, head, blocks = parse_rule_file(path)
            hit, why = file_hit(fm, blocks, diff_text, active_sigs)
            if not hit:
                files_pass.append({"file": rn, "pass": False, "why": why or "no-hit"})
                continue
            # 块级裁剪
            kept_blocks, fb = [], True
            for b in blocks:
                bh, _ = block_hit(b, diff_text)
                if bh:
                    kept_blocks.append(b)
            if not kept_blocks:
                kept_blocks = blocks  # 文件命中但块未中（描述级命中）→ 保守全保
                fb = False
            kept_ids = [b["id"] for b in kept_blocks]
            # 写裁剪版
            out_lines = [f"# {path.stem}（路由裁剪版：{len(kept_blocks)}/{len(blocks)} 条规则）", "", head]
            for b in kept_blocks:
                out_lines.extend(b["lines"])
            (gdir / path.name).write_text("\n".join(out_lines), encoding="utf-8")
            files_pass.append({"file": rn, "pass": True, "why": why,
                               "blocks_total": len(blocks), "blocks_kept": len(kept_blocks),
                               "block_ids": kept_ids, "trim_path": str(gdir / path.name)})
            total_pass += 1
        result["groups"][grp] = files_pass

    result["summary"] = f"files {total_pass}/{total_files} passed"
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for g, fs in result["groups"].items():
        det = ", ".join(f"{f['file'].split('-')[0]}:{f.get('blocks_kept', '?')}/{f.get('blocks_total', '?')}" for f in fs if f["pass"])
        print(f"  [{g}] 通过文件: {sum(1 for f in fs if f['pass'])}/{len(fs)}  块级: {det}")
    print(f"rule_filter: {result['summary']}")


if __name__ == "__main__":
    main()
