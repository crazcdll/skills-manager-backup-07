"""
接口列表命令

通过 MCP get_methods_by_appkey 查询指定 appkey 下已记录的方法/接口。
可选按起始日期、set 过滤。
"""
import json

from commands.base import Command
from commands.mcp_client import call_mcp_tool


def _call_mcp_methods(appkey: str, start_date: str = None,
                      set_name: str = None, timeout: int = 30) -> list:
    arguments = {"appkey": appkey}
    if start_date:
        arguments["startDate"] = start_date
    if set_name:
        arguments["set"] = set_name
    data = call_mcp_tool("methods_by_appkey", arguments, timeout=timeout)
    if not isinstance(data, dict) or not data.get('success', True):
        raise RuntimeError(f"MCP 返回错误: {str(data)[:300]}")
    result = data.get('data', [])
    if not isinstance(result, list):
        raise RuntimeError(f"MCP 返回 data 字段不是列表: {type(result).__name__}")
    return result


def _format_methods(methods: list, appkey: str) -> None:
    print(f"✅ {appkey} 共 {len(methods)} 个方法")
    if not methods:
        return
    print()
    for i, item in enumerate(methods, 1):
        method = item.get('methodName', '?')
        method_type = item.get('type', '')
        url = item.get('url', '')
        updated = item.get('updateTime', '')
        suffix = f"  [{method_type}]" if method_type else ""
        if url:
            suffix += f"  url={url}"
        if updated:
            suffix += f"  updated={updated}"
        print(f"{i:>4}. {method}{suffix}")


class MethodsCommand(Command):
    name = "methods"
    help_text = "查询指定 appkey 下的接口/方法列表"

    def run(self, args):
        if not args.json:
            print(f"🔍 查询接口列表：{args.appkey}")
            if args.start_date:
                print(f"   起始日期：{args.start_date}")
            if args.set_name:
                print(f"   Set：{args.set_name}")
            print("   请稍候（约 15~20 秒）...\n")

        methods = _call_mcp_methods(args.appkey, args.start_date,
                                    args.set_name, timeout=args.timeout)
        if args.json:
            print(json.dumps(methods, indent=2, ensure_ascii=False))
        else:
            _format_methods(methods, args.appkey)

    @staticmethod
    def add_parser(subparsers):
        import argparse
        p = subparsers.add_parser(
            "methods",
            help="查询指定 appkey 下的接口/方法列表",
            description="""查询某个 appkey 下已记录的方法/接口。

可选通过 startDate、set 过滤。

示例:
  raptor-prod methods -a com.sankuai.order
  raptor-prod methods -a com.sankuai.order --start-date 2026-09-01
  raptor-prod methods -a com.sankuai.order --set prod --json
""",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        p.add_argument("-a", "--appkey", required=True, help="服务 appkey（必填）")
        p.add_argument("--start-date", help="起始日期（yyyy-MM-dd）")
        p.add_argument("--set", dest="set_name", help="set 信息")
        p.add_argument("--timeout", type=int, default=30, help="超时秒数（默认 30）")
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p
