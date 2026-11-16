# Changelog — crash-wave-analysis

## v1.0.1 (2026-05-22)

- 修复：补充 `--start` / `--end` 时间参数格式说明（`YYYY-MM-DD HH:MM:SS`），修复不带时分秒时 API 返回 400 的问题
- 修复：`timeseries-by-version` / `ratio-by-version` 示例补充必传 `--filter appVersion`
- 修复：`eventcenter event timeline` 速查示例时间格式统一为带时分秒

## v1.0.0 (2026-04-24)

- 初始版本
- 支持 Crash / ANR / FOOM 多维度波动分析（时间趋势、版本分布、组件分布、栈顶聚类、设备型号、前后台、多维交叉）
- 支持自然语言分析请求和 Raptor 页面链接两种触发方式
- 覆盖美团/外卖/点评，Android/iOS/HarmonyOS
- 集成 eventcenter CLI 查版本发布事件
- 可选调用 infra-app-stability 进行深度堆栈分析
