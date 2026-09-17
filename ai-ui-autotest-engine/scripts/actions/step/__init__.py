"""Step 执行引擎：ui / api / track 三种步骤的分发与执行。

核心入口 `_cmd_step()` 只做编排，按序调用各阶段函数：
    设备检查 → 偏移检测 → action 执行 → 页面等待 → 截图 → 断言 → 收口日志

模块划分：
    engine.py        薄编排（_cmd_step / _dispatch_non_ui_step）
    step_run.py      运行状态容器 StepRun
    step_pipeline.py 阶段编排单元（操作/等待/截图/断言/结论/落盘/打印）
    step_context.py  上下文初始化 / sid 冲突 / 参数校验
    step_guards.py   漂移检测 / 设备连通性 / Recce 清理
    step_action.py   动作执行（委派 handlers）
    step_capture.py  截图
    step_assert.py   断言数据收集
    step_finalize.py 失败分析 / Review 指引 / flow-context 回写 / AI checklist
"""
from actions.step.engine import _cmd_step

__all__ = ["_cmd_step"]
