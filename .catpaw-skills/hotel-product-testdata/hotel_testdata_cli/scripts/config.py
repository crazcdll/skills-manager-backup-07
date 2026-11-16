#!/usr/bin/env python3
"""
配置文件 - skill

MIS_ID 解析优先级：
  1. 环境变量 MIS_ID（最高优先级，适用于 CI 或多人共用场景）
  2. git config user.email 的 @ 前缀（自动推断，零配置）
  3. 下方硬编码的 _FALLBACK_MIS_ID（兜底）

正常使用无需手动修改本文件。
"""

import os as _os
import subprocess as _sp
import sys as _sys


def _infer_from_git() -> str:
    """从 git config user.email 推断 MIS 号（取 @ 前缀）。"""
    try:
        email = _sp.check_output(
            ["git", "config", "user.email"],
            stderr=_sp.DEVNULL,
            text=True,
        ).strip()
        if "@" in email:
            mis = email.split("@")[0].strip()
            if mis and mis not in ("agent-hotel", "__UNSET__"):
                return mis
    except Exception:
        pass
    return ""


# 兜底值：若环境变量和 git 均无法获取，使用此值；设为空字符串表示未配置
_FALLBACK_MIS_ID = ""

MIS_ID = (
    _os.environ.get("MIS_ID", "").strip()
    or _infer_from_git()
    or _FALLBACK_MIS_ID
)

if not MIS_ID:
    print(
        "\n❌ [配置错误] 无法自动获取 MIS_ID！\n"
        "\n"
        "   尝试了以下方式均未成功：\n"
        "     1. 环境变量 MIS_ID 未设置\n"
        "     2. git config user.email 未配置或格式异常\n"
        "\n"
        "   解决方法（任选其一）：\n"
        "     a) 设置环境变量：export MIS_ID=\"你的MIS号\"\n"
        "     b) 配置 git：git config user.email \"你的MIS号@meituan.com\"\n"
        "     c) 直接修改 scripts/config.py 中的 _FALLBACK_MIS_ID = \"你的MIS号\"\n"
        "\n"
        "\n",
        file=_sys.stderr,
    )
    _sys.exit(1)

# 以下字段如需自定义可手动修改，通常无需改动
USER_ID   = 0       # 操作人内部 userId（留空时部分接口使用默认值）
USER_NAME = ""      # 操作人姓名（留空时部分接口使用默认值）

# 审核操作人 MIS：用于非房/套餐/超团/礼包等审核场景，与数据构造操作人分开管理
# 固定使用 liruzhen（权限较大的专用审核测试账号）。
AUDIT_MIS_ID = "liruzhen"

