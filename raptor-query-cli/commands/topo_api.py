"""
topo-api 接口级拓扑命令

通过 MCP get_method_topology_onestep 获取指定接口的上下游依赖关系。
⚠️  限制：只支持 1 跳，不递归多层
底层：Raptor MCP `get_method_topology_onestep`
"""
import json

from commands.base import Command
from commands.mcp_client import call_mcp_tool


# ─────────────────────────────────────────────
# MCP 调用层（统一走 commands/mcp_client.py）
# ─────────────────────────────────────────────

def _call_mcp_topo_api(app_key: str, method_name: str, timeout: int = 30) -> dict:
    data = call_mcp_tool("topo_api_onestep",
                         {"appkey": app_key, "method": method_name},
                         timeout=timeout)
    if not isinstance(data, dict) or not data.get('success', True):
        raise RuntimeError(f"MCP 返回错误: {str(data)[:300]}")
    return data.get('data', {})


# ─────────────────────────────────────────────
# 格式化输出
# ─────────────────────────────────────────────

def _fmt_items(items: list, label: str) -> None:
    print(f"\n{label} ({len(items)} 个)")
    if not items:
        print("   （无）")
        return
    for item in items:
        ak = item.get('appkey', '?')
        mn = item.get('methodName', '?')
        cl = item.get('type', '')
        print(f"   {ak}  {mn}  [{cl}]")


def _format_topo_api(result: dict, direction: str) -> None:
    node     = result.get('node', {}) or {}
    method   = node.get('methodName', '')
    app_key  = node.get('appkey', '')
    classify = node.get('type', '')
    parents  = result.get('parents', [])
    children = result.get('childrens', [])

    print(f"\n🔗 接口级拓扑（仅 1 跳）：{method}")
    print(f"   服务：{app_key}  协议：{classify}")
    print(f"   ⚠️  get_method_topology_onestep 只返回直接上下游（不递归多层）")

    if direction in ("up", "all"):
        _fmt_items(parents, "⬆️  上游（谁调了我）")
    if direction in ("down", "all"):
        _fmt_items(children, "⬇️  下游（我调了谁）")


# ─────────────────────────────────────────────
# Command 类
# ─────────────────────────────────────────────

class TopoApiCommand(Command):
    name = "topo-api"
    help_text = "接口级拓扑（1跳）：查询指定接口的直接上下游依赖"

    def run(self, args):
        if not args.json:
            print(f"🔍 查询接口级拓扑：{args.appkey}  {args.method}")
            print(f"   请稍候（约 15~20 秒）...\n")

        result = _call_mcp_topo_api(args.appkey, args.method, timeout=args.timeout)

        if args.json:
            # 按 direction 过滤，只输出用户指定方向的数据
            output = dict(result)
            if args.direction == "down":
                output.pop("parents", None)
            elif args.direction == "up":
                output.pop("childrens", None)
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            _format_topo_api(result, args.direction)

    @staticmethod
    def add_parser(subparsers):
        import argparse
        p = subparsers.add_parser(
            "topo-api",
            help="接口级拓扑（1跳）：查询指定接口的直接上下游依赖",
            description="""查询指定接口的直接上游（谁调了我）和下游（我调了谁）。

⚠️  限制：底层 get_method_topology_onestep 只返回 1 跳，不递归多层。

示例:
  raptor topo-api -a com.sankuai.order -m /api/order/create
  raptor topo-api -a com.sankuai.order -m /api/order/create -d down
  raptor topo-api -a com.sankuai.order -m /api/order/create --json
""",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        p.add_argument("-a", "--appkey", required=True, help="服务 appKey（必填）")
        p.add_argument("-m", "--method", required=True,
                       help="接口名 methodName（必填，如 /api/order/create）")
        p.add_argument("-d", "--direction", default="all",
                       choices=["up", "down", "all"],
                       help="方向：up 上游 / down 下游 / all 全部（默认）")
        p.add_argument("--timeout", type=int, default=30, help="超时秒数（默认 30）")
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p


ALIASES = {
    "topoapi": "topo-api",
}
