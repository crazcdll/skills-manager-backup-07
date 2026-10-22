"""
命令模块
"""
from commands.base import Command
from commands.transaction import IpsCommand, TypesCommand, NamesCommand
from commands.business import BusinessCommand
from commands.host import HostsCommand, HostMetricsCommand, SetsCommand
from commands.logview import LogviewCommand, LogviewDetailCommand
from commands.topology import TopologyCommand
from commands.rpc import RpcCommand
from commands.trace import TraceCommand
from commands.metrics import TransactionCommand, EventCommand, ProblemCommand
from commands.statistics import OfflineStatCommand
from commands.methods import MethodsCommand

# 所有命令
ALL_COMMANDS = [
    IpsCommand,
    TypesCommand,
    NamesCommand,
    BusinessCommand,
    HostsCommand,
    HostMetricsCommand,
    SetsCommand,
    LogviewCommand,
    LogviewDetailCommand,
    RpcCommand,
    TopologyCommand,
    TransactionCommand,
    EventCommand,
    ProblemCommand,
    TraceCommand,
    OfflineStatCommand,
    MethodsCommand,
]

# 命令映射
COMMAND_MAP = {cmd.name: cmd for cmd in ALL_COMMANDS}

# 别名映射
ALIASES = {
    "bk": "business",
    "biz": "business",
    "lv": "logview",
    "ld": "logview-detail",
    "rpc": "rpc",
    "topo": "topology",
    "hm": "host-metrics",
    "tx": "transaction",
    "ev": "event",
    "pb": "problem",
    "tr": "trace",
    "ofs": "offline-stat",
    "method": "methods",
}

# topo-api（接口级拓扑，1跳）
from commands.topo_api import TopoApiCommand
ALL_COMMANDS.append(TopoApiCommand)
COMMAND_MAP[TopoApiCommand.name] = TopoApiCommand
ALIASES["topoapi"] = "topo-api"
