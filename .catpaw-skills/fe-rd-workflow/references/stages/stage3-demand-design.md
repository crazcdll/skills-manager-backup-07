# Stage 3：需求分析与技术方案设计

> **目标**：基于 PRD/视觉稿/用户描述，完成需求分析和技术方案设计，一次性输出需求分析文档 + 技术方案文档。
> **阻塞级别**：🟡 半阻塞 — 完成后必须等待用户确认才能进入下一阶段。

Agent MUST 严格按以下顺序执行，缺一不可：

```
Step 1: 完整阅读本文件              ← 不得只读目录
  ↓
Step 2: 按 3.1 → 3.5 逐条执行     ← 严格按本文档命令，不得凭记忆推断
  ↓
Step 3: 输出「阶段三需求分析与技术方案设计执行确认单」    ← 见文档末尾模板
  ↓
Step 4: 全部 PASS 后才可进入后续阶段
```

**读取承诺**：执行前 Agent 必须先输出：

```
📖 我已完整读取 referemces/stages/stage3-demand-design.md，将严格按 Step 3.1 → Step 3.5 顺序执行，
   每一步完成后勾选对应检查项，并在最后输出「阶段三需求分析与技术方案设计执行确认单」。
```
---

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| PRD 链接 | 用户输入 | 产品需求文档（KM/ONES） |
| 视觉稿链接 | 用户输入（可选） | Ingee/Figma 设计稿 |
| 接口文档 | 用户输入（可选） | 后端 API 文档 |
| 用户补充说明 | 对话上下文 | 用户对需求的额外解释 |
| 现有代码库 | 项目目录 | 当前实现参考 |
| workflow-context | Stage 2 输出 | 项目上下文信息 |

---

## 过程

按照如下步骤完成需求分析和技术方案设计，不可以跳过：

### Step 3.1：需求规格

- Step 3.1.1：读取 `design-spec/SKILL.md`
- Step 3.1.2：使用 `design-spec skill` 生成 `.duo/{demand_description}/docs/demand-spec.md`
- Step 3.1.3：完成需求规格后，**必须使用 `AskQuestion` 工具暂停并等待用户确认**：
```
AskQuestion({
  title: "需求规格确认",
  questions: [
    {
      id: "demand_accuracy",
      prompt: "需求理解是否准确？\n",
      options: [
        { id: "yes", label: "确认，继续技术设计" },
        { id: "no", label: "修改后重新生成" },
        { id: "supplement", label: "补充更多需求" },
        { id: "skip", label: "跳过此阶段" }
      ]
    }
  ]
})
```

根据用户选择执行对应动作：

| 用户选择 | 动作 |
|----------|------|
| `yes`（确认，继续技术设计） | 写入 `workflow-context.local_docs.demand-spec.status = completed`，进入 Step 3.2 |
| `no`（修改后重新生成） | 根据用户反馈修改文档，重新生成后再次确认 |
| `supplement`（补充更多需求） | 收集补充内容，更新文档后再次确认 |
| `skip`（跳过此阶段） | 写入 `workflow-context.stage3.1.status = skipped`，直接进入 Stage 3.2 |


### Step 3.2: 技术方案

- Step 3.2.1：读取 `design-spec/SKILL.md`
- Step 3.2.2：读取`.duo/{demand_description}/docs/demand-spec.md`
- Step 3.2.3：使用 `design-spec skill` 生成 `.duo/{demand_description}/docs/tech-design.md`

#### Step 3.2.4：技术方案评审（`ai-tr`，可选）

> **依赖 Skill（可选）**：`ai-tr`（技术方案三维评审：文码一致性 / 完备性 / 架构合理性；有学城链接时支持问题划线评论回落到方案原文）。
> **定位**：在技术方案产出后、任务拆解前做一次证据驱动的方案评审，把 P0-P2 问题在进入编码前消化掉。
> **缺失或跳过不阻断流程**，但 MUST 在 Step 3.5 确认单中记录「未评审 + 原因」。

**跳过条件**（满足任一即跳过，需记录原因）：

- `ai-tr` skill 不可用
- `docs/tech-design.md` 不存在或内容为空
- 用户明确表示本次不需要方案评审

> **无学城文档不构成跳过条件**：没有学城链接时降级为「本地文件模式」——评审照常执行，只是不产出划线评论。

**步骤 1：判定评审模式**（按顺序取第一个可用项）

| 模式 | 触发条件 | 能力 |
|------|----------|------|
| **学城模式（全量）** | 用户提供技术方案学城链接；或方案已同步学城（`km_only` / `dual_write` 下已上传）；或按 `km_only` / `dual_write` 策略用 `oa-skills citadel createMarkdownDocument` 把 `docs/tech-design.md` 上传到 `input.km_parent_id` 后拿到链接 | 评审报告上传学城 + 问题划线评论回落方案原文 |
| **本地模式（降级）** | 无学城链接（`local_only` 或用户不愿上传） | 直接以 `docs/tech-design.md` 为评审输入；**不做划线评论** |

> 本地模式下禁止为「凑划线」而擅自上传学城；仅在用户明确同意时才升为学城模式。

**步骤 2：委托 `ai-tr` 执行评审**，以自然语言传达：

- **评审输入**：技术方案学城链接（学城模式）或 `docs/tech-design.md` 本地路径（本地模式）
- **评审维度**：默认三维全跑
- **报告位置**：学城模式 → 报告 parentId `input.km_parent_id`；本地模式 → `docs/tech-design-review.md`
- **评论范围**：学城模式默认 D/C/R 的 P0-P2；本地模式明确告知「**不做划线评论**」，问题定位到「章节标题/表格 + 行号」写入报告
- **关联材料**：`docs/demand-spec.md`（PRD 需求点母表）、`input.prd_link`、`input.api_link`、涉及仓库与分支（`outputs.branch.feature`，未建分支时以 master 为基线）
- **明确告知**：当前处于研发流程 Stage 3.2，只需评审报告（+ 学城模式下划线评论），**不改代码**

**步骤 3：结果处理**（依据 `ai-tr` 报告的综合评级）

| 综合评级 | 后续行为 |
|----------|----------|
| 🟢 绿 | 记录报告位置，进入 Step 3.2.5 |
| 🟡 黄 | 列出待确认项 `AskQuestion`；把 P0/P1 结论回写 `tech-design.md`（有实质修改时可重评一次），进入 Step 3.2.5 |
| 🔴 红 | 返回 Step 3.2.3 修订技术方案后重评一次；仍为红 → `AskQuestion` 由用户决定「带风险继续 / 终止流程」 |

**产物**：

- 本地模式（任何情况都必须有）：`.duo/{demand_description}/docs/tech-design-review.md`（综合评级、P0-P2 问题清单及「章节/行号」定位、未评审项及原因）
- 学城模式（额外）：学城评审报告链接 + 划线评论条数

> 评审信息只落在 `tech-design-review.md` 与 Step 3.5 确认单中，**不新增 `workflow-context.json` 字段**。

#### Step 3.2.5：用户确认

完成技术方案后，**必须使用 `AskQuestion` 工具暂停并等待用户确认**：
```
AskQuestion({
  title: "技术方案确认",
  questions: [
    {
      id: "design_accuracy",
      prompt: "技术方案是否合理？",
      options: [
        { id: "yes", label: "确认，继续任务拆解" },
        { id: "no", label: "修改后重新生成" },
        { id: "supplement", label: "补充更多" },
        { id: "skip", label: "跳过此阶段" }
      ]
    }
  ]
})
```

根据用户选择执行对应动作：

| 用户选择 | 动作 |
|----------|------|
| `yes`（确认，继续任务拆解） | 写入 `workflow-context.local_docs.tech-design.status = completed`，进入 Step 3.3 |
| `no`（修改后重新生成） | 根据用户反馈修改文档，重新生成后再次确认 |
| `supplement`（补充更多需求） | 收集补充内容，更新文档后再次确认 |
| `skip`（跳过此阶段） | 写入 `workflow-context.stage3.2.status = skipped`，直接进入 Stage 3.3 |

### Step 3.3：任务拆解

- Step 3.3.1：读取 `design-spec/SKILL.md`，并直接进入Step 3。
- Step 3.3.2：读取`.duo/{demand_description}/docs/tech-design.md`
- Step 3.3.3：使用 `design-spec skill` 生成 `.duo/{demand_description}/docs/dev-tasks.md`

### Step 3.4：Flow 测试用例生成（TDD 驱动）

> **内循环约束：本步骤只生成用例，不执行任何自动化测试。** 用例的作用是作为可执行的验收标准，先写清楚“做完应该长什么样”，再照着它编码（Stage 4）、照着它自查（Stage 5）。

**依赖 Skill（可选）**：载入 `ai-auto-ui-test` skill，按 **内循环（Flow 用例生成）** 执行。缺失时跳过本步骤，Stage 4 按常规方式编码，Stage 5 仅依据验收标准自查。

**跳过条件**（满足任一即可跳过，需记录原因）：

- 本次需求不涉及页面可视层（如纯协议字段调整、纯工具函数）
- 用户明确表示不需要 TDD 用例

**委托方式**：以自然语言传达以下信息：

- **需求文档**：`.duo/{demand_description}/docs/demand-spec.md`
- **技术方案**：`.duo/{demand_description}/docs/tech-design.md`
- **变更范围**：`.duo/{demand_description}/docs/dev-tasks.md` 中涉及页面与组件的任务
- **产物目录**：`.duo/{demand_description}/ui-test/`
- **明确告知**：当前处于内循环，只生成用例，不执行测试、不申请设备

**产物**：

```
.duo/{demand_description}/ui-test/
├── flows/
│   └── flow-{NN}-{场景简称}.md    # 每个场景一个 Flow 用例
└── flow-index.md                  # 用例索引：场景清单 + 三态分类 + 覆盖的验收点
```

**完成标准**：

- [ ] `ui-test/flows/` 下至少有 1 个 Flow 用例文件
- [ ] 每个用例标注了三态分类（deterministic / data-dependent / manual-review）
- [ ] `flow-index.md` 说明了哪些验收点**未被用例覆盖**

> `ui-test/flows/` 已存在时不重新生成，除非用户明确要求更新用例。

### Step 3.5：执行确认单输出

> **这是离开阶段三、进入阶段四的唯一凭证。未输出 = 未完成阶段三。**

```
📋 需求分析与技术方案设计执行确认单
═══════════════════════════════════════════════════════════
- 需求规格说明：.duo/{demand_description}/docs/demand-spec.md
- 技术方案设计：.duo/{demand_description}/docs/tech-design.md
- 技术方案评审：{综合评级 + 报告位置（学城链接 / 本地 tech-design-review.md，标注是否含划线评论） | 未评审：{原因}}
- 任务清单详情：.duo/{demand_description}/docs/dev-tasks.md
- Flow 测试用例：.duo/{demand_description}/ui-test/flows/（共 {N} 个场景；跳过时写“未生成：{原因}”）

当前阶段已完成，下一阶段进入Stage4：物料组件和页面协议开发（将以 Flow 用例作为 TDD 驱动输入）。
```

- 当需求分析和技术方案设计完成后，**必须使用 `AskQuestion` 工具暂停并等待用户确认**：

```
AskQuestion({
  title: "需求分析和方案设计是否已完成",
  questions: [
    {
      id: "demand_design",
      prompt: "需求分析和方案设计是否已完成？",
      options: [
        { id: "yes", label: "确认，继续下一步" },
        { id: "no", label: "修改后重新生成" },
        { id: "supplement", label: "补充更多" },
        { id: "skip", label: "跳过此阶段" }
      ]
    }
  ]
})
```

根据用户选择执行对应动作：

| 用户选择 | 动作 |
|----------|------|
| `yes`（确认，继续下一步） | 写入 `workflow-context.local_docs.dev-tasks.status = completed`、`workflow-context.runtime.stages.stage3.status = completed`，进入 Step 4 |
| `no`（修改后重新生成） | 根据用户反馈修改文档，重新生成后再次确认 |
| `supplement`（补充更多需求） | 收集补充内容，更新文档后再次确认 |
| `skip`（跳过此阶段） | 写入 `workflow-context.stage3.status = skipped`，直接进入 Stage 4 |


---

## 异常处理

| 场景 | 处理方式 |
|------|----------|
| PRD 链接无效 | 提示用户提供正确链接或直接粘贴需求内容 |
| 视觉稿无法解析 | 跳过视觉稿分析，基于文字描述继续 |
| 复杂度边界模糊 | 向用户确认，推荐保守评级（偏高一级） |
| 接口文档缺失 | 基于需求分析推断接口，标注「待确认」 |
| 现有代码不熟悉 | 通过 codebase_search 了解现有实现 |
| 技术选型有争议 | 向用户呈现选项对比，由用户决定 |
| `ai-auto-ui-test` 未安装 | 跳过 Step 3.4，在确认单中记录；Stage 4/5 不依赖 Flow 用例也可正常执行 |
| `ai-tr` 未安装 | 跳过 Step 3.2.4，在确认单中记录；后续阶段不依赖方案评审结果 |
| 技术方案无学城链接 | 降级为本地文件模式：以 `docs/tech-design.md` 为评审输入，报告落本地，**不做划线评论**、不上传学城；仅用户明确同意时才上传 |
| `ai-tr` 评审判定为红且重评仍为红 | 不擅自进入 Stage 4，`AskQuestion` 由用户决定「带风险继续 / 终止流程」 |
| 验收标准过于笼统、无法写用例 | 返回 Step 3.1 补充验收标准，而不是凭空编造用例 |

---

