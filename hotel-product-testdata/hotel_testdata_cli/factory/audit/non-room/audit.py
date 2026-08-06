#!/usr/bin/env python3
"""
⚠️ 已废弃 - 请使用 factory/audit/gift/audit.py

非房审核与礼包审核已合并到同一脚本：
  factory/audit/gift/audit.py

用法完全相同：
  python3 factory/audit/gift/audit.py --xgoods-id <xgoodsId> --partner-id <partnerId> --shop-id <shopId>
"""

import sys
import os
import importlib.util

_gift_path = os.path.join(os.path.dirname(__file__), "..", "gift", "audit.py")
_spec = importlib.util.spec_from_file_location("gift_audit", _gift_path)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    print("⚠️  non-room/audit.py 已废弃，已自动转发到 gift/audit.py", file=sys.stderr)
    _mod.main()

