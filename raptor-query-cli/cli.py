#!/usr/bin/env python3
"""
Raptor CLI - 美团 Raptor 监控平台命令行工具
"""
import sys
import os
import argparse

from client import RaptorClient
from commands import COMMAND_MAP, ALIASES, ALL_COMMANDS


def _read_skill_version() -> str:
    """从 SKILL.md frontmatter 读取 version，失败时返回 'unknown'。"""
    skill_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SKILL.md")
    try:
        with open(skill_md, encoding="utf-8") as f:
            in_front = False
            for line in f:
                line = line.rstrip()
                if line == "---":
                    if not in_front:
                        in_front = True
                        continue
                    else:
                        break
                if in_front and line.startswith("version:"):
                    return line.split(":", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


VERSION = _read_skill_version()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Raptor CLI - 美团 Raptor 监控平台命令行工具 v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--version", action="version", version=f"Raptor CLI v{VERSION}")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 注册所有命令
    for cmd_class in ALL_COMMANDS:
        cmd_class.add_parser(subparsers)
    
    return parser


def show_help():
    print(f"""
Raptor CLI - 美团 Raptor 监控平台命令行工具 v{VERSION}

用法: raptor-prod <command> [options]

可用命令:
  ips             获取 IP 列表
  hosts           获取主机列表
  sets            查询机器分组列表（set/机房/region/custom）
  types           获取类型列表
  names           获取名称列表
  business        业务指标查询
  logview         获取 Logview IDs
  logview-detail  查询 Logview 详情（支持 --url 粘贴 Raptor 页面 URL）
  topology        获取上下游拓扑
  topo-api        接口级拓扑（1跳）：查询指定接口的直接上下游依赖
  host-metrics    获取主机指标
  rpc             查询上/下游 RPC 调用统计
  transaction     查询 Transaction 指标 (QPS, TP99, 成功率)
  event           查询 Event 指标 (事件统计)
  problem         查询 Problem 指标 (异常、报错)
  trace           通过 traceId 查询调用链（全量或按 appKey 过滤 span）
  methods         查询指定 appkey 下的接口/方法列表
  offline-stat    离线统计（Event 指标 Appkey 请求量/成功率/QPS）

快捷别名:
  bk, biz  → business
  lv       → logview
  ld       → logview-detail
  topo     → topology
  topoapi  → topo-api
  hm       → host-metrics
  tx       → transaction
  ev       → event
  pb       → problem
  tr       → trace
  ofs      → offline-stat
  method   → methods

示例:
  raptor-prod ips -a cat -s 1h
  raptor-prod hosts -a cat
  raptor-prod names -a cat -s 1h
  raptor-prod business -a cat
  raptor-prod topology -a cat -s 1h -d up
  raptor-prod transaction -a cat -t URL -s 5m
  raptor-prod tx -a cat -t System -s 1h
  raptor-prod problem -a cat -t error -s 5m

配置:
  默认 Token 内置在代码中
  可通过环境变量覆盖:
    RAPTOR_TOKEN=xxx raptor ...
""")


def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    # 处理 help 命令
    if sys.argv[1] in ["help", "--help", "-h"]:
        show_help()
        return
    
    # 预处理别名：在 argparse 解析前替换 sys.argv，避免 subparser 不认识别名
    if sys.argv[1] in ALIASES:
        sys.argv[1] = ALIASES[sys.argv[1]]
    
    # 解析参数
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        show_help()
        return
    
    # 处理别名
    cmd_name = ALIASES.get(args.command, args.command)
    
    if cmd_name not in COMMAND_MAP:
        print(f"❓ 未知命令: {args.command}", file=sys.stderr)
        print(f"   使用 raptor-prod help 查看可用命令", file=sys.stderr)
        sys.exit(1)
    
    # 创建客户端并执行命令
    client = RaptorClient()
    command_class = COMMAND_MAP[cmd_name]
    command = command_class(client)
    
    try:
        command.run(args)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
