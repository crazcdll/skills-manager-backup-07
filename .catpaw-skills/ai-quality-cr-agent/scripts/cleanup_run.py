#!/usr/bin/env python3
"""CR 中间目录安全清理（SKILL.md Step 9 清理规则配套，替代裸 rm -rf）。

防御逻辑（全部通过才执行删除，任一失败直接退出非 0）：
  1. 路径必须匹配白名单模式 /tmp/aicr_<prId>_<XXXXXX>(mktemp 生成的固定形态)
  2. 只允许删除目录本身，不做递归通配

用法: python3 cleanup_run.py "$CR_RUN_DIR"
"""
import re
import shutil
import sys

SAFE_PATTERN = re.compile(r"^/tmp/aicr_[0-9]+_[A-Za-z0-9]{6}$")
# 与 SKILL.md Step 3 的 CR_RUN_DIR 生成约定对齐:
#   CR_RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/aicr_${PR_ID}_XXXXXX")
# 即 /tmp/aicr_<prId>_<6位随机>。仅当 TMPDIR 为默认 /tmp 时匹配（mktemp 若用其它 TMPDIR
# 则目录不在 /tmp，扫描器关心的本机误删面主要即 /tmp，非默认环境下拒绝并留提示）


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: cleanup_run.py $CR_RUN_DIR", file=sys.stderr)
        return 2
    target = sys.argv[1].strip()

    if not SAFE_PATTERN.match(target):
        print(f"refuse cleanup: path not matching whitelist pattern: {target!r}", file=sys.stderr)
        return 3

    shutil.rmtree(target)
    print(f"cleaned: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
