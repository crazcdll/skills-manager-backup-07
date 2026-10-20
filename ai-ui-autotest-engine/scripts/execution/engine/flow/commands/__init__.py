"""Flow CLI 命令 — 流程级命令入口薄壳，按职责拆分到各子模块。

每个命令函数仅做参数解析 + 调用下层 + 格式化输出。
"""
from execution.engine.flow.commands.init_cmd import _cmd_flow_init, _cmd_flow_add_case, _cmd_case_init
from execution.engine.flow.commands.validate_cmd import _cmd_validate, _format_json_error
from execution.engine.flow.commands.status_cmd import _cmd_flow_status, _cmd_flow_case_status
from execution.engine.flow.commands.next_cmd import _cmd_flow_next, _cmd_flow_advance
from execution.engine.flow.commands.ack_cmd import _cmd_ack
from execution.engine.flow.commands.finalize_cmd import _cmd_flow_finalize
from execution.engine.flow.commands.fail_cmd import _cmd_flow_fail, _cmd_skip_case
from execution.engine.flow.commands.event_cmd import _cmd_record_event

__all__ = [
    "_cmd_flow_init", "_cmd_flow_add_case", "_cmd_case_init",
    "_cmd_validate", "_format_json_error",
    "_cmd_flow_status", "_cmd_flow_case_status",
    "_cmd_flow_next", "_cmd_flow_advance",
    "_cmd_ack",
    "_cmd_flow_finalize",
    "_cmd_flow_fail", "_cmd_skip_case",
    "_cmd_record_event",
]