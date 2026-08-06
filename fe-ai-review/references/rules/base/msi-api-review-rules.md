# MSI API 契约核对

> 当变更 diff 实质修改 MSI Bridge 调用时，由独立 subagent 执行。当前只核对 API 文档契约，不检查 FE 包版本或 App 版本区间。

## 触发条件

新增或修改以下任一调用时触发：

- `msi.xxx(...)`、`MSI.xxx(...)`、`preset.xxx(...)`
- 从 `@mtfe/msi-*` 容器包导入并调用的方法，例如 `@mtfe/msi-mrn`、`@mtfe/msi-picasso`、`@mtfe/msi-knb`
- 修改 Bridge 名称、入参、返回字段读取、回调、Promise 或错误处理

以下情况不触发：

- Bridge 调用只是 diff 上下文，调用本身未改
- 仅修改注释、格式或无关业务文案
- 仅移动或重命名文件，调用契约未变
- 普通 `KNB.xxx(...)` 调用；`@mtfe/msi-knb` 除外

## 执行方式

创建独立 subagent，与主审查并行执行。只向 subagent 提供相关 diff、修改后的完整调用、import、文件位置和必要的平台分支上下文，不要让它扫描无关代码。

subagent 按以下步骤执行：

1. 载入 `infra-msi` skill，获取基目录和入口指引。
2. 只读取并执行 `reference/api-query/SKILL.md`，不关注 `reference/independent-app-upgrade/SKILL.md`。
3. 按 api-query 指引定位 API 原始明细；不能只根据索引摘要下结论。
4. 对照实际代码核对 API 契约，返回候选问题与未验证项。

`infra-msi` 未安装、载入失败或原始明细缺失时，不阻塞主审查，也不要自动安装或把未验证解释为通过。使用已加载的 MRN / Max 静态规则继续检查，并在覆盖自评中说明降级原因。

## 核对范围

对每个命中的 Bridge 检查：

- API 是否存在，是否已废弃或有推荐替代
- 基础 API、容器 API、业务 API 的选择是否正确
- 入参名称、类型、必填性和嵌套字段是否符合文档
- 代码读取的返回字段及其类型是否符合文档
- 当前平台和容器是否受支持
- callback、Promise、同步返回等调用形态是否正确
- fail、错误码、用户取消等异常路径是否得到合理处理
- 文档明确说明的多端差异是否被错误地当成一致行为

当前阶段不执行：

- `.msi-guard.json` 读取或创建
- `@mtfe/msi` / `@mtfe/preset` / 容器包版本探测
- Guard API 调用及 `BLOCK / WARN / PASS` 判定
- App 版本区间 Breaking Change 分析

## subagent 返回要求

不要求固定 JSON 或 Markdown 模板，但至少说明：

- 已检查的 Bridge、文件和代码位置
- 明确问题的严重度建议、API 契约依据、代码证据和修复建议
- 未验证的 Bridge 或核对维度，以及无法验证的原因
- 本次状态：完成、部分完成或未执行；发生降级时说明原因

subagent 只提供候选问题，不直接生成最终报告。主 Agent 必须结合代码上下文复核真实性、去重并重新定级。

## 与主审查的关系

- 明确违反 API 契约的问题合并到 Step 5，沿用统一的 `P0 / P1 / P2-P3` 发现项格式
- API 文档缺失、Skill 不可用或证据不足时放入 `Open Questions`，不要输出确定性结论
- 未发现问题时不生成发现项，在覆盖自评中记录已检查的 Bridge 数量
