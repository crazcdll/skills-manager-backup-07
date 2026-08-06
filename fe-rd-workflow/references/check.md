# 阶段恢复检查

> **🔴 每次启动 fe-rd-workflow 主流程时，MUST 先读取 `workflow-context.json` 的 `current_work_ask` 字段，检查各阶段完成状态，再决定从哪个阶段继续。**
> **MUST：使用 `AskQuestion` 工具以多选交互方式，让用户确认哪些阶段确实已完成。**

---

## 触发条件

- `{project_root}/.duo/{demand_description}/workflow-context.json` 文件已存在（即非首次运行）
- `current_work_ask` 字段中有至少一个非 `pending` 状态的阶段

## 匹配规则（精确匹配，不得用路径名推断）
- 读取 workflow-context.json 中的 input.prd_link
- 与用户本次提供的学城链接做字符串精确匹配
- 匹配成功 → 中断恢复流程
- 匹配失败 → 跳过，视为新需求

---

## current_work_ask 字段定义

| 状态值      | 含义                         | 用户确认行为                   |
| ----------- | ---------------------------- | ------------------------------ |
| `resolved`  | 记录为已完成                 | 如果用户确认选中 → 确认已完成 |
| `pending`   | 未开始                       | 不可被用户选中                 |
| `rejected`  | 用户主动跳过（不需要执行）   | 不需要用户选中                 |

---

## 阶段 key 与阶段名称映射

| 阶段 key   | 阶段名称                   | 产物文件（用于校验）                                                    |
| ---------- | -------------------------- | ----------------------------------------------------------------------- |
| `stage1`   | 阶段一：环境检查           | —（无文件产物，仅状态）                                                 |
| `stage2`   | 阶段二：仓库初始化         |    -                                                 |
| `stage2.0` | 步骤 2.0：仓库克隆         | —                                                                       |
| `stage2.1` | 步骤 2.1：创建/切换开发分支 | —                                                                       |
| `stage2.2` | 步骤 2.2：创建标准目录结构 | `.duo/{demand_description}/docs/` 目录存在 +`workflow-context.json`        |
| `stage3`   | 阶段三：需求分析与技术设计 | `demand-spec.md` + `tech-design.md` + `dev-tasks.md`（均在 docs/） |
| `stage4`   | 阶段四：物料组件和协议开发           | —（代码产物，不校验文件）                                               |
| `stage5`   | 阶段五：验证测试           | `.duo/{demand_description}/docs/03-implementation-checklist.md`         |
| `stage6`   | 阶段六：CI/CD              | —（部署结果，不校验文件）                                               |
| `stage7`   | 阶段七：反馈总结           | `.duo/{demand_description}/docs/04-delivery-reports.md`                 |

---

## 执行步骤（单一线性流程）

```
Step 1: 读取 workflow-context.json
  ├─ 文件不存在 → 视为首次运行，跳过恢复检查，从阶段一开始
  └─ 文件存在 → 进入 Step 2

Step 2: 检查 current_work_ask 字段
  ├─ 字段不存在，或所有值均为 pending → 视为首次运行，跳过恢复检查，从阶段一开始
  └─ 存在非 pending 值 → 进入 Step 3

Step 3: 产物文件自动校验（在展示给用户之前先自动执行）
  对所有 status=resolved 的阶段，逐一检查对应产物文件是否存在：
  ├─ 产物文件存在 → 保持 resolved，加入「已完成」展示列表
  └─ 产物文件缺失 → 自动降级为 pending，加入「待执行」列表，并记录缺失文件路径
  （无产物文件的阶段，如 stage1/stage4/stage6，直接保持 resolved）

Step 4: 构建三组展示内容
  - ✅ 已完成（resolved，且产物校验通过）：让用户多选确认哪些确实已完成
  - ⏭️ 已跳过（rejected）：告知用户哪些已被跳过，不需要执行
  - ⬜ 未完成（pending，含产物校验降级的阶段）：告知用户哪些待执行

Step 5: 使用 AskQuestion 工具发起多选交互
  - 交互类型：多选（allow_multiple: true）
  - options 包含所有 resolved 状态的阶段 + 「重新开始」选项
  - rejected 和 pending 阶段在 prompt 文案中列出，不作为 options

Step 6: 根据用户选择结果，更新 current_work_ask 字段
  - 用户选择「重新开始」→ 全部降级为 pending，从阶段一重新开始
  - 用户选中的 resolved 项 → 保持 resolved
  - 用户未选中的 resolved 项 → 降级为 pending（视为未完成，需要重新执行）
  - rejected 项 → 保持 rejected（不可恢复）
  - pending 项 → 保持 pending

Step 7: 从 current_work_ask 中第一个 pending 的阶段开始继续执行
  - rejected 的阶段永久跳过，不计入后续流程
  - 如果没有 pending 项且所有 resolved 都被确认 → 流程已完成，输出完成摘要
```

---

## AskQuestion 交互示例

**假设 `current_work_ask` 为（Step 3 产物校验后）：**

```json
{
  "stage1": "resolved",
  "stage2": "resolved",
  "stage2.0": "resolved",
  "stage2.1": "pending",
  "stage2.2": "pending",
  "stage3": "rejected",
  "stage4": "pending",
  "stage5": "pending"
}
```

**Step 5 发起的 AskQuestion 调用**：

```
AskQuestion({
  title: "📋 阶段恢复检查",
  questions: [{
    id: "stage_confirm",
    prompt: "当前需求进度如下：\n\n✅ 已完成（请确认哪些确实已完成）：\n  - 阶段一：前置准备与环境检查\n  - 阶段二：仓库初始化\n  - 步骤 2.0：仓库克隆\n\n⏭️ 已跳过（不需要执行）：\n  - 阶段三：需求分析与技术设计（已跳过）\n\n⬜ 未完成（待执行）：\n  - 步骤 2.1：创建/切换开发分支\n  - 步骤 2.2：创建标准目录结构\n  - 阶段四：物料组件和协议开发\n  - 阶段五：验证测试\n\n请确认「已完成」列表中哪些阶段确实已完成？（未选中的将被重新执行）",
    input_type: "choice",
    options: [
      { id: "stage1", label: "✅ 阶段一：前置准备与环境检查" },
      { id: "stage2", label: "✅ 阶段二：仓库初始化" },
      { id: "stage2.0", label: "✅ 步骤 2.0：仓库克隆" },
      { id: "restart", label: "🔄 重新开始（全部重新执行）" }
    ],
    allow_multiple: true
  }]
})
```

---

## 状态更新规则

| 用户操作                   | current_work_ask 更新                           | 后续行为             |
| -------------------------- | ----------------------------------------------- | -------------------- |
| 选中某 resolved 项         | 保持 `resolved`                                 | 该阶段跳过           |
| 未选中某 resolved 项       | 降级为 `pending`                                | 该阶段重新执行       |
| rejected 项                | 保持 `rejected`                                 | 永久跳过             |
| 用户选择「重新开始」       | 所有 resolved 降级为 pending，从阶段一重新开始  | 全部重新执行         |
| 用户全部选中所有 resolved  | 从第一个 pending 阶段继续                       | 正常推进             |

---

## 阶段完成时回写

> **每个阶段完成后，立即更新 `current_work_ask` 中对应字段的状态。**

| 阶段完成情况              | 回写值         |
| ------------------------- | -------------- |
| 阶段正常完成              | `resolved`     |
| 用户主动跳过该阶段        | `rejected`     |
| 阶段执行失败              | 保持 `pending` |

---

## 与已有跳过规则的关系

- 本「阶段恢复检查」是对 `skip_decisions` 和 `user_confirmation` 字段的**补充**，不是替代
- `current_work_ask` 是**用户确认维度**的阶段状态快照，用于跨会话恢复
- `skip_decisions` 和 `user_confirmation` 是**单次会话内**的决策记录
- 两者独立维护，互不覆盖
