#!/usr/bin/env python3
"""
基础实体 - 创建酒店房型

接口：fd.banma createRoomAction（POST http://fd.banma.test.sankuai.com/api/autoCase/run）
      sceneId=47034, actionId=356285
      内部自动串联：创建物理房型 → 审核 → 上传图片 → 查询 roomInfoId

返回 roomInfoId（逻辑房型ID，上单必填）+ realRoomId（物理房型ID）。

使用方式：
  # 境内大床间（最常用，仅传必填参数）
  python3 create-room.py --partner-id 4548884 --poi-id 1085918666109517

  # 境外房型
  python3 create-room.py --partner-id 4548884 --poi-id 1234567890 --overseas

  # 指定房型类型（双床间）
  python3 create-room.py --partner-id 4548884 --poi-id 123 --room-type 2

  # 自定义房型名
  python3 create-room.py --partner-id 4548884 --poi-id 123 --room-name 大床房

  # 全参数示例
  python3 create-room.py --partner-id 4548884 --poi-id 123 \
      --room-type 0 --room-area "16-20" --capacity 2 --window-type 0 --floor 5

  # 仅打印参数
  python3 create-room.py --partner-id 123 --poi-id 456 --dry-run
"""

import argparse
import datetime
import importlib.util as ilu
import json
import os
import sys

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
call_room = _iface.call_room

from scripts.utils import get_operator  # noqa


def _build_room_name(base: str = "") -> str:
    """生成房型名：base（或 mis）+ 时间戳（格式 YYYYMMDDHHmmss）。"""
    prefix = base if base else get_operator()
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{ts}"


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""创建酒店房型（fd.banma createRoomAction）

【必填参数】
  --partner-id <partnerId>
      供应商ID（create-partner.py 输出的 partnerId）

  --poi-id <poiId>
      门店ID（create-poi.py 输出的 mtPoiId）

【可选参数】
  --room-name <名称>
      房型名称前缀，始终自动追加时间戳以保证全局唯一：
        不传 → 「<mis><时间戳>」，如 zhaoshichuan2026-05-27-15:30:42
        传了 → 「<传入值><时间戳>」，如 大床房2026-05-27-15:30:42
      ⚠️  上单时 --room-name 需填写输出的完整名称（含时间戳）

  --room-type <0-6>
      房间类型（默认0=大床间）：
        0=大床间  1=单人间  2=双床间  3=三人间
        4=套房    5=独栋    6=床位房

  --overseas
      Flag，加上则创建境外房型（默认境内）

  --room-area <面积范围>
      房间面积（平方米），支持范围值，如 11-15 / 16-20（接口默认 11-15）

  --capacity <人数>
      最大入住人数（接口默认 2）

  --window-type <0-2>
      窗户情况（接口默认2=全部无窗）：0=全部有窗 1=部分有窗 2=全部无窗

  --floor <楼层>
      楼层信息（接口默认 1）

  --dry-run
      仅打印参数，不实际执行

【输出】
  roomInfoId  逻辑房型ID（上单必填，等同于旧版 roomId）
  realRoomId  物理房型ID

【注意事项】
  ⚠️  供应商创建（工具49）是异步的，需等待约 1 分钟后再创建房型
      若报「供应商不存在」，等待后重试

【使用示例】
  python3 factory/infra/create-room.py --partner-id 4553737 --poi-id 1085927256096396
  python3 factory/infra/create-room.py --partner-id 4553737 --poi-id 123 --overseas""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="创建酒店房型（fd.banma createRoomAction）")
    parser.add_argument("--partner-id",  required=True, help="供应商ID")
    parser.add_argument("--poi-id",      required=True, help="门店ID")
    parser.add_argument("--room-name",   default=None,  help="房型名称（不传则自动生成 <mis><时间戳>）")
    parser.add_argument("--room-type",   type=int, default=0,
                        help="房间类型：0=大床间,1=单人间,2=双床间,3=三人间,4=套房,5=独栋,6=床位房（默认0）")
    parser.add_argument("--overseas",    action="store_true", help="境外房型（默认境内）")
    parser.add_argument("--room-area",   default=None, help="房间面积范围，如 11-15（接口默认 11-15）")
    parser.add_argument("--capacity",    type=int, default=None, help="最大入住人数（接口默认 2）")
    parser.add_argument("--window-type", type=int, default=None,
                        help="窗户情况：0=全部有窗,1=部分有窗,2=全部无窗（接口默认 2）")
    parser.add_argument("--floor",       type=int, default=None, help="楼层信息（接口默认 1）")
    parser.add_argument("--dry-run",     action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    room_type_names = {0: "大床间", 1: "单人间", 2: "双床间", 3: "三人间", 4: "套房", 5: "独栋", 6: "床位房"}
    room_type_name = room_type_names.get(args.room_type, f"类型{args.room_type}")

    # 始终拼接时间戳：未传名称用 mis 作前缀，传了名称则以传入值作前缀
    args.room_name = _build_room_name(args.room_name or "")

    print(f"=== 创建{'境外' if args.overseas else '境内'}酒店房型（fd.banma createRoomAction）===")
    print(f"  partnerId  : {args.partner_id}")
    print(f"  poiId      : {args.poi_id}")
    print(f"  roomName   : {args.room_name}  ← 上单时需填写此值")
    print(f"  roomType   : {args.room_type}（{room_type_name}）")
    print(f"  isOverSea  : {args.overseas}")
    if args.room_area:   print(f"  roomArea   : {args.room_area} m²")
    if args.capacity:    print(f"  capacity   : {args.capacity} 人")
    if args.window_type is not None: print(f"  windowType : {args.window_type}")
    if args.floor:       print(f"  floor      : {args.floor} 楼")

    resp = call_room(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_name=args.room_name,
        is_overseas=args.overseas,
        room_type=args.room_type,
        room_area=args.room_area,
        capacity=args.capacity,
        window_type=args.window_type,
        floor=args.floor,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    if not isinstance(resp, dict):
        print(f"\n[ERROR] 创建物理房型失败（响应非预期格式）: {resp}", file=sys.stderr)
        sys.exit(1)

    if not resp.get("success"):
        msg = resp.get('message') or resp.get('error') or str(resp)
        trace_id = resp.get('traceId', '')
        print(f"\n[ERROR] 创建物理房型失败: {msg}", file=sys.stderr)
        if trace_id:
            print(f"  traceId : {trace_id}", file=sys.stderr)
        print(json.dumps(resp, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    room_info_id = resp.get("roomInfoId")
    real_room_id = resp.get("realRoomId")
    room_name    = resp.get("roomName") or args.room_name

    if not room_info_id:
        print("[ERROR] 未获取到 roomInfoId，完整响应：", file=sys.stderr)
        print(json.dumps(resp, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"\n✅ 房型创建成功")
    print(f"  roomInfoId : {room_info_id}  ← 上单必填（等同于 roomId）")
    print(f"  realRoomId : {real_room_id}")
    print(f"  roomName   : {room_name}  ← 上单时 --room-name 填此值")
    print(f"  partnerId  : {args.partner_id}")
    print(f"  poiId      : {args.poi_id}")


if __name__ == "__main__":
    main()

