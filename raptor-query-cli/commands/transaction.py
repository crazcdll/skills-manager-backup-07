"""
Transaction/Event/Problem 相关命令
"""
import json
import sys
import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time


class IpsCommand(Command):
    """IP 列表命令"""
    name = "ips"
    help_text = "获取 IP 列表"
    
    def run(self, args):
        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
        
        url = f"/dw/openapi/{args.type}/meta/ips"
        body = {"appkey": args.appkey, "queryType": "hour", "period": end_ts}
        
        try:
            data = self.client.post(url, body)
            result = data.get("result", [])
            
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            print(f"\n📊 {args.appkey} IP 列表 - {len(result)} 个")
            for ip in result[:15]:
                print(f"   - {ip}")
            if len(result) > 15:
                print(f"   ... 还有 {len(result) - 15} 个")
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
    
    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("ips", help="获取 IP 列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="1h", help="时间范围（默认 1h）或绝对时间（2026-04-06 13:57:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-t", "--type", default="transaction", help="数据类型")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


class TypesCommand(Command):
    """类型列表命令"""
    name = "types"
    help_text = "获取类型列表"
    
    def run(self, args):
        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
        
        url = f"/dw/openapi/{args.type}/meta/types"
        body = {"appkey": args.appkey, "startTime": start_ts, "endTime": end_ts}
        
        try:
            data = self.client.post(url, body)
            result = data.get("result", [])
            
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            print(f"\n📊 {args.appkey} 类型列表 - {len(result)} 个")
            for t in result:
                print(f"   - {t}")
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
    
    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("types", help="获取类型列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="1h", help="时间范围（默认 1h）或绝对时间（2026-04-06 13:57:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-t", "--type", default="transaction", help="数据类型")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


class NamesCommand(Command):
    """名称列表命令"""
    name = "names"
    help_text = "获取名称列表"
    
    def run(self, args):
        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
        data_type = args.data_type
        types = [t.strip() for t in args.type.split(",") if t.strip()]
        
        url = f"/dw/openapi/{data_type}/meta/typeNames"
        body = {"appkey": args.appkey, "types": types, "startTime": start_ts, "endTime": end_ts}
        
        try:
            data = self.client.post(url, body)
            result = data.get("result", {})
            
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            
            if not result:
                print("❌ 无数据", file=sys.stderr)
                return
            
            # 按 type 分组展示
            if len(types) == 1:
                # 单 type：平铺展示
                names = []
                if isinstance(result, dict):
                    for v in result.values():
                        names.extend(v)
                else:
                    names = result
                print(f"\n📊 {args.appkey}/{data_type}/{types[0]} - {len(names)} 个")
                for n in names:
                    print(f"   - {n}")
            else:
                # 多 type：按 type 分组
                total = sum(len(v) for v in result.values() if isinstance(v, list))
                print(f"\n📊 {args.appkey}/{data_type} - 共 {total} 个")
                for t in types:
                    names = result.get(t, [])
                    print(f"\n  [{t}] {len(names)} 个:")
                    for n in names:
                        print(f"    - {n}")
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
    
    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("names", help="获取名称列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="1h", help="时间范围（默认 1h）或绝对时间（2026-04-06 13:57:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-t", "--type", required=True,
                       help="类型名称（必填，支持逗号分隔多个；先用 types 命令查看可用类型）")
        p.add_argument("--data-type", default="transaction", help="数据类型")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


# 命令注册
COMMANDS = {
    "ips": IpsCommand,
    "types": TypesCommand,
    "names": NamesCommand,
}
