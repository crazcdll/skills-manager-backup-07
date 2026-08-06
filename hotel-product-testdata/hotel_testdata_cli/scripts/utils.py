#!/usr/bin/env python3
"""
公共工具函数 - skill
"""

import datetime
import sys
from typing import Optional


def get_operator() -> str:
    """
    获取操作人 MIS。

    推断逻辑统一由 scripts/config.py 处理（优先级：环境变量 MIS_ID > git email > 硬编码兜底）。
    config 模块加载时若无法获取有效 MIS 会直接 exit(1)，此处无需重复校验。
    """
    try:
        from hotel_testdata_cli.scripts.config import MIS_ID
    except ImportError:
        from scripts.config import MIS_ID
    return MIS_ID


def get_audit_operator() -> str:
    """
    获取审核操作人 MIS。

    用于非房/套餐/超团/礼包等审核场景的默认 --mis，与数据构造操作人分开管理。
    默认值在 scripts/config.py 的 AUDIT_MIS_ID 中配置。
    """
    try:
        from hotel_testdata_cli.scripts.config import AUDIT_MIS_ID
    except ImportError:
        from scripts.config import AUDIT_MIS_ID
    return AUDIT_MIS_ID


def make_product_name(prefix: str, operator: Optional[str] = None) -> str:
    """
    生成标准商品名称，格式：<operator><prefix>_<时间戳>

    注意：名称不能含"测试"字样。

    示例：
        make_product_name("全日房")        → "zhangsan全日房_20260519153042"
        make_product_name("钟点房", "abc") → "abc钟点房_20260519153042"
    """
    op = operator or get_operator()
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{op}{prefix}_{ts}"


def print_summary(title: str, items: dict) -> None:
    """打印汇总输出（脚本末尾统一调用）。"""
    print(f"\n{'='*50}")
    print(f"  📋 {title}")
    print(f"{'='*50}")
    for k, v in items.items():
        if v is not None and v != "":
            print(f"  {k}: {v}")
    print(f"{'='*50}\n")


def check_required_params(params: dict, required_keys: list) -> None:
    """检查必填参数，缺失时打印错误并退出。"""
    missing = [k for k in required_keys if not params.get(k)]
    if missing:
        print(f"[错误] 必填参数缺失: {', '.join(missing)}", file=sys.stderr)
        print("请通过命令行参数传入对应值，或先运行基础设施创建脚本。", file=sys.stderr)
        sys.exit(1)


def parse_bool(value: str) -> bool:
    """将字符串解析为布尔值（支持 true/false/1/0/yes/no）。"""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes")


def price_to_fen(price_yuan: float) -> int:
    """将元转换为分（接口要求单位为分）。"""
    return int(float(price_yuan) * 100)

