#!/usr/bin/env python3
"""
基础实体 - 创建酒店门店（POI）

工具：工具26（CreatePoi）
协议：HTTP POST DataUnity
接口：CreatePoi（创建酒店门店）

返回 mtPoiId，后续创建供应商/房型/商品时必填。

使用方式：
  # 创建境内北京门店（默认）
  python3 create-poi.py

  # 创建境外东京门店
  python3 create-poi.py --overseas --city 东京

  # 指定门店名称和城市
  python3 create-poi.py --poi-name 我的测试酒店 --city 上海

  # 仅打印参数，不执行
  python3 create-poi.py --dry-run
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

def _load_interface():
    spec = ilu.spec_from_file_location(
        "infra_interface",
        os.path.join(ROOT, "interface/infra/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_iface = _load_interface()
call_poi = _iface.call_poi

from scripts.du_runner import get_result, check_ok  # noqa
from scripts.utils import get_operator  # noqa

TOOL_ID = 26


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具26 - 创建酒店门店（CreatePoi）

【必填参数】
  无（所有参数均有默认值，可直接执行）

【可选参数】
  --city <城市名>
      城市名称，如 北京、上海、广州、东京
      默认值：北京

  --poi-name <名称>
      门店名称，建议唯一
      默认值：<mis>酒店门店_<时间戳>

  --overseas
      Flag，加上则创建境外门店（默认境内）
      境外时 category-id 默认切换为 387

  --category-id <ID>
      门店品类ID
      境内默认：352（四星级酒店）
      境外默认：387（其他酒店）

  --dry-run
      仅打印参数，不实际执行

【输出】
  mtPoiId  门店ID，后续创建供应商/房型/商品时必填

【使用示例】
  python3 factory/infra/create-poi.py
  python3 factory/infra/create-poi.py --city 上海
  python3 factory/infra/create-poi.py --overseas --city 东京""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="创建酒店门店（POI）")
    parser.add_argument("--city", default="北京", help="城市名（默认：北京）")
    parser.add_argument("--poi-name", default=None, help="门店名称（默认：<mis>酒店门店）")
    parser.add_argument("--overseas", action="store_true", help="境外门店（默认境内）")
    parser.add_argument("--category-id", default=None,
                        help="门店品类ID（境内默认352=四星级，境外默认387=其他酒店）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    operator = get_operator()
    is_overseas = args.overseas
    poi_name = args.poi_name or f"{operator}酒店门店_{int(time.time())}"
    category_id = args.category_id or ("387" if is_overseas else "352")

    print(f"=== 创建{'境外' if is_overseas else '境内'}酒店门店（工具{TOOL_ID}）===")
    print(f"  城市        : {args.city}")
    print(f"  门店名称    : {poi_name}")
    print(f"  品类ID      : {category_id}")
    print(f"  是否境外    : {is_overseas}")

    resp = call_poi(
        city=args.city,
        poi_name=poi_name,
        is_overseas=is_overseas,
        category_id=category_id,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "创建门店")
    poi_id = get_result(resp, "mtPoiId")
    if not poi_id:
        print("[ERROR] 未获取到 mtPoiId，完整响应：")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(f"\n✅ 门店创建成功")
    print(f"  mtPoiId : {poi_id}")
    print(f"  城市    : {args.city}")
    print(f"  门店名  : {poi_name}")


if __name__ == "__main__":
    main()

