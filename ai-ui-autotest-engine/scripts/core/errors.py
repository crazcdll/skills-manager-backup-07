#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一错误体系 —— 错误即数据（code + category + exit_code），不控制进程。

四条设计约束：

  1. 业务 / 核心层只 `raise`，绝不 `sys.exit`；
  2. 每个错误自带稳定身份：`code`（稳定错误码）、`category`（归因）、
     `exit_code`（进程退出码）；
  3. 只有 CLI 边界（`cli_utils.run_with_guard`）把异常转成进程退出码；
  4. 可容忍失败走 `soft_fail()` 落审计时间线，禁止裸 `except: pass`。

`category` 取值与 `core.audit.exception_reporter.CATEGORIES` 对齐，复用同一套
归因 taxonomy（infra/env/payload/device/app/script/assertion/unknown），
避免第二套分类体系。

用法：

    from core.errors import UsageError, DeviceError, MockError, soft_fail

    raise UsageError("mock on 需要 --mock-id <mockId>")
    raise DeviceError("设备不可达", code="DEVICE_UNREACHABLE", stage="B1_device")
    try:
        cleanup()
    except Exception as e:
        soft_fail("infra", "CACHE_RESET_FAILED", e)
"""
from core import exit_codes
from core.audit.exception_reporter import CATEGORIES


class AutotestError(Exception):
    """引擎错误基类。子类用类属性声明身份，实例可覆盖。"""

    code = "UNEXPECTED"
    category = "unknown"
    exit_code = exit_codes.ERROR
    stage = ""
    retryable = False

    def __init__(self, message="", *, code=None, category=None, stage="",
                 detail="", retryable=None, extra=None):
        super().__init__(message)
        self.message = message or self.__class__.__name__
        if code:
            self.code = code
        if category:
            self.category = category
        if stage:
            self.stage = stage
        if retryable is not None:
            self.retryable = retryable
        self.detail = detail
        self.extra = dict(extra or {})

    def to_audit(self) -> dict:
        """ → run-events.jsonl 的 details 载荷。"""
        return {
            "code": self.code,
            "category": self.category,
            "stage": self.stage,
            "message": str(self.message)[:500],
            "detail": str(self.detail)[:500] if self.detail else "",
            "retryable": self.retryable,
            **self.extra,
        }

    def __str__(self):
        return str(self.message)


# ═══════════════════════════════════════════════════════════════════
# 分类错误 —— category 与 exception_reporter.CATEGORIES 一一对齐
# ═══════════════════════════════════════════════════════════════════

class UsageError(AutotestError):
    """参数 / 用法错误（缺参、互斥参数冲突、非法取值）。"""
    code = "USAGE_INVALID"
    category = "payload"
    exit_code = exit_codes.USAGE


class PayloadError(AutotestError):
    """输入数据问题（占位符未替换、结构校验失败）。"""
    code = "PAYLOAD_INVALID"
    category = "payload"
    exit_code = exit_codes.ERROR


class ConfigError(AutotestError):
    """环境配置校验失败（认证信息 / 设备组合 / 配置项非法）。"""
    code = "CONFIG_INVALID"
    category = "env"
    exit_code = exit_codes.ERROR


class EnvError(AutotestError):
    """环境不可用（依赖缺失 / SSO 失效 / 环境不通）。"""
    code = "ENV_UNAVAILABLE"
    category = "env"
    exit_code = exit_codes.ABORT


class DeviceError(AutotestError):
    """设备问题（创建 / 连接 / 安装 / 探测失败）。"""
    code = "DEVICE_FAILED"
    category = "device"
    exit_code = exit_codes.ERROR


class AppError(AutotestError):
    """被测应用问题（安装 / 登录 / 白屏 / Crash）。"""
    code = "APP_FAILED"
    category = "app"
    exit_code = exit_codes.ERROR


class InfraError(AutotestError):
    """基础设施故障（云模拟器 / 网络 / 平台服务）。"""
    code = "INFRA_FAILED"
    category = "infra"
    exit_code = exit_codes.ERROR


class MockError(AutotestError):
    """AppMock 操作失败（规则 / 录制 / 泳道 / 域名映射）。"""
    code = "MOCK_FAILED"
    category = "infra"
    exit_code = exit_codes.ERROR


class FlowStateError(AutotestError):
    """流程状态非法 / 步骤重跑冲突。"""
    code = "FLOW_STATE_INVALID"
    category = "payload"
    exit_code = exit_codes.FLOW_CONFLICT


class StepAssertionError(AutotestError):
    """步骤断言 / 校验未通过（业务结论为 FAIL，不是脚本缺陷）。

    用于 step / api / track 步骤的判定失败：步骤结果已落盘为 FAIL，
    此处抛出以携带非 0 退出码终止本次执行。
    """
    code = "STEP_ASSERTION_FAILED"
    category = "assertion"
    exit_code = exit_codes.ERROR


class ContractError(AutotestError):
    """模块契约违反 / 脚本缺陷（未预期异常的兜底归类）。"""
    code = "CONTRACT_VIOLATION"
    category = "script"
    exit_code = exit_codes.ERROR


def _known_category(category: str) -> str:
    return category if category in CATEGORIES else "unknown"


# ═══════════════════════════════════════════════════════════════════
# 可容忍失败 —— 替代 `except: pass`
# ═══════════════════════════════════════════════════════════════════

def soft_fail(category: str, code: str, detail="", *, severity: str = "warning"):
    """记录一次可容忍失败到 run-events.jsonl 后继续（best-effort，不抛）。

    用于「失败不影响本次结论」的场景：清理残留、缓存失效、可选上报等。
    关键副作用失败不应静默 —— 那属于应当 raise 的真错误。

    Args:
        category: 归因分类（∈ CATEGORIES；未知值归为 unknown）
        code:     稳定错误码，如 "CACHE_RESET_FAILED"
        detail:   失败详情（异常对象或字符串，自动截断）
        severity: 时间线级别 info/warning/error
    """
    try:
        from core.audit.runtime_audit import append_event
        from core.util.paths import get_active_case
        from core.util.case_utils import resolve_case_path

        case_name = get_active_case()
        if not case_name:
            return
        append_event(
            resolve_case_path(case_name), "soft_failure",
            {"code": code, "category": _known_category(category),
             "detail": str(detail)[:500]},
            severity=severity,
        )
    except Exception:
        # 审计自身失败不得反向影响主流程 —— 本文件内唯一允许的静默
        pass
