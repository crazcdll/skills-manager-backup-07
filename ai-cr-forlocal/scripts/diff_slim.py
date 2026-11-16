#!/usr/bin/env python3
"""
diff_slim.py — diff 瘦身预处理（prep 阶段，git diff 之后、信号检测之前）

对 /tmp/local_cr_diff.txt 做以下瘦身，输出 /tmp/local_cr_diff_slim.txt：
  1. 剥离 import 语句行（+import / -import）
  2. 剥离 Lombok 注解行（@Getter/@Setter/@Builder/@Data 等）
  3. 剥离纯空行/括号变更（只有 {}(); 的行）

不压缩 context 行——保留完整的 ±3 行上下文，避免子 Agent 丢失代码定位信息。

调用方式：
  python3 diff_slim.py --diff /tmp/local_cr_diff.txt --output /tmp/local_cr_diff_slim.txt
  python3 diff_slim.py
"""
import re, sys, argparse
from pathlib import Path


def slim_diff(raw: str) -> str:
    """瘦身后仍保持 unified diff 格式，只剥离零价值行"""
    lines = raw.splitlines(keepends=False)
    out = []

    IMPORT_RE = re.compile(r'^[+-]\s*(?:import\s|from\s+.*\s+import\s|const\s+.*\s*=\s*require\()')
    LOMBOK_RE = re.compile(r'^[+-]\s*@(?:Getter|Setter|Builder|Data|AllArgsConstructor|NoArgsConstructor|ToString|EqualsAndHashCode|Slf4j|Log)\b')
    EMPTY_RE = re.compile(r'^[+-]\s*[{}();\s]*$')

    for ln in lines:
        # import 行 → 剥离
        if IMPORT_RE.match(ln):
            continue
        # Lombok 注解行 → 剥离
        if LOMBOK_RE.match(ln):
            continue
        # 纯空行/括号行变更 → 剥离
        if EMPTY_RE.match(ln):
            continue
        # 其余全部保留（含 context 行、hunk 头、文件头、实质 +/- 行）
        out.append(ln)

    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='diff 瘦身预处理')
    ap.add_argument('--diff', default='/tmp/local_cr_diff.txt', help='输入 diff 文件')
    ap.add_argument('--output', default='/tmp/local_cr_diff_slim.txt', help='输出瘦身后 diff')
    args = ap.parse_args()

    src = Path(args.diff)
    if not src.exists() or src.stat().st_size == 0:
        print(f"FATAL: diff 文件不存在或为空: {src}", file=sys.stderr)
        sys.exit(1)

    raw = src.read_text(encoding='utf-8', errors='replace')
    raw_lines = len(raw.splitlines())
    raw_bytes = len(raw.encode('utf-8'))

    slimmed = slim_diff(raw)
    slim_lines = len(slimmed.splitlines())
    slim_bytes = len(slimmed.encode('utf-8'))

    out = Path(args.output)
    out.write_text(slimmed, encoding='utf-8')

    line_cut = raw_lines - slim_lines
    byte_cut = raw_bytes - slim_bytes
    print(f"diff_slim: {raw_lines}→{slim_lines} 行 (-{line_cut}, {line_cut*100//max(raw_lines,1)}%)")
    print(f"diff_slim: {raw_bytes}→{slim_bytes} bytes (-{byte_cut}, {byte_cut*100//max(raw_bytes,1)}%)")
    print(f"diff_slim: token 估算 {raw_bytes//4}→{slim_bytes//4} (-{(raw_bytes-slim_bytes)//4})")
    print(f"diff_slim: 输出 {out}")


if __name__ == '__main__':
    main()
