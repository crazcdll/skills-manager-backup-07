# Stage 4：物料组件开发和协议开发

> **目标**：按照技术方案和任务清单，完成物料组件开发、协议开发和业务逻辑实现。
> **阻塞级别**：🔴阻塞 — 物料组件和协议开发问题要在当前阶段修复。

## 入场门禁（必须逐条输出确认，否则 MUST_NOT 继续）
- [ ] 已输出 Stage 3 → Stage 4 交接检查点摘要
- [ ] 已判断需求类型：{A直接开发 / B完整流程 / P发布 / T测试}，判断依据：{...}
- [ ] 已输出「物料组件和协议开发 Skill 声明」

---

## 输入

- 技术方案文档：`.duo/{demand_description}/docs/tech-design.md`
- 开发任务文档：`.duo/{demand_description}/docs/dev-tasks.md`
- 物料组件开发依赖的 skill 路径：`max-material-dev`
- 页面协议开发依赖的 skill 路径：`duo-protocol`

---

## 过程

按照先开发物料组件再开发页面协议，顺序不可以改变。

### Step 4.1：物料组件开发与发布

严格按以下步骤执行，缺一不可：
- 1. 开始物料组件开发之前先阅读`max-material-dev/SKILL.md`，禁止用 summary / 历史上下文替代 read 操作，未完成 read 前 MUST_NOT 开始任何物料组件开发动作
- 2. **输出「物料组件开发 Skill 声明」**，列出已读取的 skill 路径

#### Step 4.1.1 物料组件开发
- 遵循`max-material-dev`的完整规范进行开发，禁止自行进行物料组件开发，需要覆盖所有的开发任务，不可以跳过开发任务。
- 物料组件的验证也在当前阶段完成，遵循`max-material-dev`规范。

#### Step 4.1.2 物料组件发布

**条件**：
- 1）当物料组件为新增必须发布。
- 2）当物料组件描述协议description.json 修改时，必须发布。
- 3）其他情况为可选，用户自行判断是否发布，物料组件开发完成需要提醒用户是否执行发布。

**发布操作步骤**：
1. 物料组件的`package.json`版本号更新（遵循semver规范）
3. 读取`max-material-dev`的发布规范
3. 执行发布：`duo publish-procode -y`

**依赖 cli**：
- `duo-cli`：`duo publish-procode -y` 命令（缺失时暂停，提示用户安装`npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com`）

### Step 4.2：协议开发

协议开发完全遵循`duo-protocol`的完整规范进行开发，禁止自行页面协议开发实现,需要覆盖所有的开发任务，不可以跳过开发任务。

严格按以下步骤执行，缺一不可：
- 1. 开始页面协议开发之前先阅读`duo-protocol/SKILL.md`，禁止用 summary / 历史上下文替代 read 操作，未完成 read 前 MUST_NOT 开始任何页面协议开发动作
- 2. **输出「协议开发 Skill 声明」**，列出已读取的 skill 路径

---

## 输出

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 物料组件源码 | `material/packages/*/src/` | 新增/修改的组件 |
| DUO 协议文件 | `protocol/` | 页面配置协议 |
| 业务逻辑代码 | `src/` | 页面/组件逻辑 |
| 更新状态 | workflow-context | Stage 4 完成 |

---

