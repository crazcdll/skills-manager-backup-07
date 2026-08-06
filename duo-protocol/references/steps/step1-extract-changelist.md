# Step 1 — 读取输入文档并提取改动清单

> **阻塞级别**：🔴 阻塞（输入缺失则终止流程）

## 输入

| 输入 | 来源 | 必填 |
|------|------|------|
| `spec.md` | duo-docs 阶段产出 | 必填 |
| `plan.md` | duo-docs 阶段产出 | 必填 |
| `tasks.md` | duo-docs 阶段产出 | 必填 |

> ⚠️ **唯一输入来源**：spec.md / plan.md / tasks.md，禁止从学城/PRD/其他外部文档读取需求信息。
> 原因：spec/plan/tasks 已是结构化最终产物，重复解读原始文档浪费上下文且可能引入理解偏差。

## 过程

### 1.1 读取 spec.md

重点关注以下章节：

- §2 需求范围识别 → 识别涉及的 DUO 页面
- §3 需求分类分析 → 提取已确认的改动项
- §5 组件规划 → 明确组件/物料改动
- §6 数据层设计 → 明确接口/数据源改动
- §7 交互逻辑 → 明确事件/埋点改动

### 1.2 读取 plan.md

关注执行阶段和步骤顺序。

### 1.3 读取 tasks.md

关注编码性任务（C-xxx）的改动文件和验收标准。

## 输出

完成后进入 Step 2。

## 前提验证

| 前提条件 | 验证方式 | 不满足时 |
|----------|----------|----------|
| spec.md / plan.md / tasks.md 存在 | 读取文件路径 | 提示用户先完成前置步骤 |
| 协议文件目录存在 | 检查目录 | 向用户确认文件位置，禁止静默跳过 |
| materialId 可获取 | CLI/MCP 工具查询或 materials.json 备选 | 不使用该物料，禁止编造 |

## 独立执行时

如果调用入口上下文中未包含spec.md / plan.md / tasks.md 的实际路径，MUST 向用户询问 ，不得自行猜测。

调用本 Skill 时注入的运行时数据：

```ts
{
  spec_path: string,    // spec.md 绝对路径
  plan_path: string,    // plan.md 绝对路径
  tasks_path: string,   // tasks.md 绝对路径
  work_root: string,    // 项目仓库根目录
  mis: string,          // 用户 MIS 号
}
```
