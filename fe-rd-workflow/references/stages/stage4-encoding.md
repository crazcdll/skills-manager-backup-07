# Stage 4：物料组件开发和协议开发

> **目标**：按照技术方案和任务清单，完成物料组件开发、协议开发和业务逻辑实现。
> **阻塞级别**：🔴阻塞 — 物料组件和协议开发问题要在当前阶段修复。

## 入场门禁（必须逐条输出确认，否则 MUST_NOT 继续）
- [ ] 已输出 Stage 3 → Stage 4 交接检查点摘要
- [ ] 已判断需求类型：{A直接开发 / B完整流程 / P发布 / T测试}，判断依据：{...}
- [ ] 已输出「物料组件和协议开发 Skill 声明」
- [ ] 已读取 `dev-tasks.md`，将其中每个开发任务导入 `workflow-context.runtime.stage4_tasks[]`，逐条设置 `id` / `desc` / `type`(material|protocol|logic) / `status=pending` / `artifact`。导入的任务数量必须与 Stage 3 交接摘要中声明的任务数量一致，否则 MUST_NOT 继续。

## 输入

- 技术方案文档：`.duo/{demand_description}/docs/tech-design.md`
- 开发任务文档：`.duo/{demand_description}/docs/dev-tasks.md`
- **Flow 测试用例（TDD 驱动输入）**：`.duo/{demand_description}/ui-test/flows/`（Stage 3 Step 3.4 产出；不存在时按常规方式开发）
- 物料组件开发依赖的 skill 路径：`max-material-dev`
- 页面协议开发依赖的 skill 路径：`duo-protocol`
- 前端代码编写规范 skill `fe-ai-review`

## TDD 开发约束

> **内循环约束：本阶段不执行任何自动化测试。** Flow 用例在这里的角色是“可执行的验收标准”，用于驱动和约束编码，而不是跑测试。

`.duo/{demand_description}/ui-test/flows/` 存在时，按以下方式使用：

1. **开发前读用例**：开始编码前先读取与当前任务相关的 Flow 用例，明确“做完后页面应该长什么样”。
2. **按用例的校验点编码**：用例中的每个「校验」项都是一个实现目标（应出现的文案、状态、字段、层级结构）。
3. **开发后逐条自查**：完成一个任务后，对照用例逐条确认实现情况（阅读代码 / 本地渲染确认），**不要求跑自动化**。
4. **用例与实现不一致时**：先判断是实现遗漏还是用例写错。实现遗漏则补实现；用例写错则更新 `ui-test/flows/` 对应文件并在交付时说明原因。
5. **三态分类处理**：`manual-review` 类用例不要求代码层满足，仅作为 Stage 5 人工确认项。

用例不存在（Stage 3 Step 3.4 被跳过）时，本节不适用，按常规方式依据技术方案与任务清单开发。

---

## 过程

按照先开发物料组件再开发页面协议，顺序不可以改变。

### Step 4.1：物料组件开发与发布

严格按以下步骤执行，缺一不可：
- 1. 开始物料组件开发之前先阅读`max-material-dev/SKILL.md`，禁止用 summary / 历史上下文替代 read 操作，未完成 read 前 MUST_NOT 开始任何物料组件开发动作
- 2. **输出「物料组件开发 Skill 声明」**，列出已读取的 skill 路径
- 3. 在进行代码开发之前必须先阅读代码规范 skill `fe-ai-review`
  - 阅读通用前端编码规范 `{fe-ai-review}/references/rule/base/general-rules.md`
  - 如果是 MRN 技术栈、则阅读规范 `{fe-ai-review}/references/context/mrn-context.md`
  - 如果是 MAX 技术栈、则阅读规范 `{fe-ai-review}/references/context/max-context.md`

#### Step 4.1.1 物料组件开发
- 遵循`max-material-dev`的完整规范进行开发，禁止自行进行物料组件开发，需要覆盖所有的开发任务，不可以跳过开发任务。
- 物料组件的验证也在当前阶段完成，遵循`max-material-dev`规范。
- **任务级回写**：每完成一个物料类任务（`stage4_tasks[].type=material`），立即将其 `status` 回写为 `done` 并填写实际 `artifact` 路径；确需跳过时须将 `status` 置为 `skipped` 并填写 `skip_reason`，MUST_NOT 静默跳过。

#### Step 4.1.2 物料组件发布

**条件**：
- 1）当物料组件为新增必须发布。
- 2）当物料组件描述协议description.json 修改时，必须发布。
- 3）其他情况为可选，用户自行判断是否发布，物料组件开发完成需要提醒用户是否执行发布。

**发布操作步骤**（严格按序执行，缺一不可）：
1. 物料组件的`package.json`版本号更新（遵循semver规范）
2. 读取`max-material-dev`的发布规范
3. 执行发布：`duo publish-procode -y`
4. **校验发布结果**：确认命令回显包含成功标识，且发布版本号与 step 1 更新后的版本号一致
5. **失败处理**：发布失败时将错误记录到 `workflow-context.errors[]`，并使用 `AskQuestion` 暂停，让用户选择「重试发布 / 跳过发布 / 中止流程」

> ⚠️ `duo publish-procode` 是影响线上物料市场的副作用操作。未确认发布成功（step 4 校验通过）前，MUST_NOT 将 `stage4.1` 标记为 completed。

**依赖 cli**：
- `duo-cli`：`duo publish-procode -y` 命令（缺失时暂停，提示用户安装`npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com`）

### Step 4.2：协议开发

协议开发完全遵循`duo-protocol`的完整规范进行开发，禁止自行页面协议开发实现,需要覆盖所有的开发任务，不可以跳过开发任务。

严格按以下步骤执行，缺一不可：
- 1. 开始页面协议开发之前先阅读`duo-protocol/SKILL.md`，禁止用 summary / 历史上下文替代 read 操作，未完成 read 前 MUST_NOT 开始任何页面协议开发动作
- 2. **输出「协议开发 Skill 声明」**，列出已读取的 skill 路径
- 3. 进行协议开发之前阅读经验文档 `{fe-ai-review}/references/stack/duo-rules.md`
- 4. **任务级回写**：每完成一个协议类/业务逻辑类任务（`stage4_tasks[].type=protocol|logic`），立即将其 `status` 回写为 `done` 并填写实际 `artifact` 路径；确需跳过时须将 `status` 置为 `skipped` 并填写 `skip_reason`，MUST_NOT 静默跳过。

## 出场门禁（标记 `stage4` completed 前 MUST 逐条校验，任一未满足则 MUST_NOT 标记 completed）

- [ ] `workflow-context.runtime.stage4_tasks[]` 中每个任务的 `status` 均为 `done` 或 `skipped`（`skipped` 必须附 `skip_reason`），无 `pending` 遗留。
- [ ] 声明改动的产物实际存在 git 变更：执行 `git diff --name-only {base_branch}...HEAD`，其覆盖的路径应包含 `stage4_tasks[].artifact` 声明的模块，无声明但未改动的任务。
- [ ] 若涉及物料组件新增或 `description.json` 变更：已执行 Step 4.1.2 发布并通过发布结果校验（`stage4.1` 已标记 completed）。
- [ ] 本地构建/类型检查通过（若仓库存在 `build` / `tsc` 等脚本则执行，失败记录到 `errors[]` 并暂停修复）。

## 输出

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 物料组件源码 | `material/packages/*/src/` | 新增/修改的组件 |
| DUO 协议文件 | `protocol/` | 页面配置协议 |
| 业务逻辑代码 | `src/` | 页面/组件逻辑 |
| 用例修订（如有） | `.duo/{demand_description}/ui-test/flows/` | 开发中发现用例写错时的修正，需说明原因 |
| 更新状态 | workflow-context | Stage 4 完成 |

> 交接 Stage 5 时说明：Flow 用例中哪些校验点已实现、哪些因客观原因未实现、哪些用例被修订过。

---

