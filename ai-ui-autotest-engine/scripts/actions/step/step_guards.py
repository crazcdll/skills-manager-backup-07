"""步骤前置守卫：漂移检测、设备连通性/熄屏检查、Recce 浮层清理。"""
import time
from core.errors import DeviceError
from context import get_onboarding_profile
from screen_state.inspect_tree import invalidate_cache
from actions.assertion_utils import auto_dismiss_recce
from core.util.records import StepRecord, SRC_STEP
from core.flow.step_scheduler import check_drift as fc_check_drift, update_step_result as fc_update_step
from core.audit.runtime_audit import append_event


def _check_prior_drift(root_dir, current_sid):
    """检查上一步 hooks 是否完成。"""
    warning, prior_sid, _ = fc_check_drift(root_dir, current_sid)
    return warning, prior_sid
def _fail_device_unreachable(root_dir, case_ws, args, _ci, ops):
    """设备不可达时的故障记录与退出。"""
    print(f"STEP ABORT: 设备 {ops.serial} 不可达（模拟器可能已被销毁或 adb 断连）")
    sid = getattr(args, "sid", None)
    record = StepRecord(
        sid=sid or "", src=SRC_STEP, type=args.step_type or "misc",
        desc=args.desc or "", ok=0, status="FAIL", ms=0,
        failure={"error": "设备不可达", "reason": "DEVICE_UNREACHABLE"},
    )
    if sid:
        fc_update_step(root_dir, sid, 0, args.step_action or "", fail_reason="设备不可达")
    record.append(case_ws)
    append_event(root_dir, "step.failed", {"case_index": _ci, "sid": sid or "", "reason": "DEVICE_UNREACHABLE"})
    raise DeviceError("设备不可达（模拟器可能已被销毁或 adb 断连）")
def _fail_screen_off(root_dir, case_ws, ops, args, _ci):
    """设备熄屏/锁屏时的故障记录与退出。"""
    _screen_state = ops.screen_state()
    print(f"STEP ABORT: 设备 {ops.serial} 当前处于熄屏/非交互状态（{_screen_state}），"
          f"本地真机场景无法自动恢复，自动化执行终止")
    sid = getattr(args, "sid", None)
    record = StepRecord(
        sid=sid or "", src=SRC_STEP, type=args.step_type or "misc",
        desc=args.desc or "", ok=0, status="FAIL", ms=0,
        failure={"error": f"设备熄屏（{_screen_state}）", "reason": "SCREEN_OFF",
                 "screen_state": _screen_state},
    )
    if sid:
        fc_update_step(root_dir, sid, 0, args.step_action or "", fail_reason=f"设备熄屏（{_screen_state}）")
    record.append(case_ws)
    append_event(root_dir, "step.failed", {"case_index": _ci, "sid": sid or "", "reason": "SCREEN_OFF"})
    raise DeviceError("设备熄屏/锁屏，本地真机场景无法自动恢复")
def _check_device_connectivity(ops, root_dir, case_workspace, args, case_index):
    """检查设备连通性和屏幕状态。"""
    if not ops.device_alive():
        _fail_device_unreachable(root_dir, case_workspace, args, case_index, ops)
    profile = get_onboarding_profile()
    if profile.needs_screen_check() and not ops.is_screen_interactive():
        _fail_screen_off(root_dir, case_workspace, ops, args, case_index)
def _dismiss_recce_layer(args):
    """自动移除 Recce 调试浮层。"""
    if args.step_action and args.step_action in ("tap", "tap-text", "scroll-until", "blur-input", "input-text"):
        try:
            recce_dismissed = auto_dismiss_recce()
            if recce_dismissed:
                invalidate_cache()
                time.sleep(0.3)
                print("  [PRE-STEP] Recce 浮层已自动移除")
        except Exception as e:
            print(f"  [PRE-STEP] dismiss-recce 异常（不影响继续）: {e}")
