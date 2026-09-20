#!/usr/bin/env python3
"""
修复效果观测入口（给 cron/定时任务用）

用法：
  python3 watch.py --group android:babel --notify nieyunlong
  python3 watch.py --group android:babel --notify nieyunlong --compare yesterday
  python3 watch.py --group android:babel --notify nieyunlong --compare-days 3

触发方式（用户对话）：
  "帮我盯着 android babel crash 修复效果，2小时后推结果"
  → Agent 创建 cron，2小时后执行：
    python3 /root/.openclaw/skills/component-crash-chart/scripts/watch.py
      --group android:babel --notify nieyunlong

本脚本等同于 generate_chart.py --date today --notify <misid> [其他参数]，
会自动取当天日期，生成小时级同比图并推送到大象。
"""

import subprocess
import sys
from datetime import datetime


def main():
    import argparse
    parser = argparse.ArgumentParser(description="修复效果观测：生成 crash 图并推送大象")
    parser.add_argument("--group", required=True, help="e.g. android:babel, harmony:pike")
    parser.add_argument("--notify", required=True, metavar="MISID",
                        help="大象推送目标 misid（如 nieyunlong）")
    parser.add_argument("--compare", default="yesterday",
                        help="对比日期：yesterday / YYYY-MM-DD,YYYY-MM-DD（默认 yesterday）")
    parser.add_argument("--compare-days", type=int, default=0,
                        help="同比天数（覆盖 --compare）")
    parser.add_argument("--label", default="", help="备注标签，附在消息标题后")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    script = "/root/.openclaw/skills/component-crash-chart/scripts/generate_chart.py"

    cmd = ["python3", script,
           "--date", today,
           "--group", args.group,
           "--notify", args.notify]

    if args.compare_days > 0:
        cmd += ["--compare-days", str(args.compare_days)]
    elif args.compare:
        cmd += ["--compare", args.compare]

    print(f"[watch] Running: {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd, timeout=300)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
