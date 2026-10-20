"""记录与结论管理 — 写入 steps.jsonl 并更新 flow-context。

_log_record / _override_step_result / _assert_fields / _relay_hook_result
处理日志记录、终态覆盖、数据中继等 flow 生命周期操作。
"""
from execution.steps.recording.log_cmd import _cmd_log_record
from execution.steps.recording.override_cmd import _cmd_override_step_result
from execution.steps.recording.relay_cmd import _cmd_relay_hook_result
from execution.steps.recording.assert_fields_cmd import _cmd_assert_fields

__all__ = [
    "_cmd_log_record",
    "_cmd_override_step_result",
    "_cmd_relay_hook_result",
    "_cmd_assert_fields",
]