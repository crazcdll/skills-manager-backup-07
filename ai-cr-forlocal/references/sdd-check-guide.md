# SDD 产物校验指南（Step 3A — 可选）

### Step 3A（SDD 校验）：SDD 产物校验（Spec-Code Alignment Check）

> **前提**：**始终执行**。有 spec 文件时做完备性 + 文码一致性检查；无 spec 文件时输出「本次变更未采用 SDD」。
> **纯前端路径**：若 Step 2 已委托 `fe-ai-review`，跳过整个 SDD 校验。
> **零额外 IO**：spec 文件已在 3C 加载，本步骤纯内存分析。
> **核心原则**：客观列出差异事实，不预设谁对谁错，由 Reviewer 自行判断。

#### SDD-1. 完备性检查

从 `changed_files` 推断涉及的功能模块，逐模块检查是否有对应 spec 文件：

- ✅ **完备**：有对应 spec 文件且覆盖本次变更涉及的核心设计点
- ⚠️ **简略**：有 spec 但缺少关键信息（需列出缺少哪些内容，如：缺少异常处理策略、缺少数据模型说明、缺少接口定义）
- ❌ **缺失**：涉及业务逻辑变更但无任何对应 spec 文件（`specs/`、`.mdp/context/`、`docs/superpowers/specs/` 均无，建议定为 **P2**）

**特殊情况**：变更仅涉及配置文件（.yml/.properties/.xml）、测试代码、纯重构（rename/move 无逻辑变更）→ 仍输出 SDD 结果，`has_spec: false` + `completeness: MISSING` + 备注「纯配置/测试/重构变更，无业务 spec 要求」

#### SDD-2. 文码一致性检查

将 3C 加载的 spec 内容与 diff 代码做双向比对，**仅在完备性为「完备」或「简略」时执行**：

- **正向**（spec → 代码）：spec 描述的关键设计决策（接口定义、数据模型、处理流程、异常策略、技术选型），代码实现是否符合
- **反向**（代码 → spec）：代码中新增的关键实现（新增 public 方法、新增异常分支、新增业务规则、新增外部依赖），spec 中是否有对应描述

定级：逻辑性不一致（方案/流程不同，可能误导后置环节）→ **P1**；新增关键逻辑未覆盖 → **P2**；命名/格式微差 → 忽略

#### SDD 结论（注入 Step 4 上下文，并作为文档 SDD 章节数据源）

```
[SDD_CHECK_RESULT]
has_spec: true | false
completeness: COMPLETE | PARTIAL(缺少: {异常处理策略/数据模型/接口定义等}) | MISSING
alignment_rate: {X}%  # 仅 has_spec=true 时输出
alignment_issues:     # 仅 has_spec=true 时输出，无问题则为空列表
  - [P1/P2] {spec文件} L{行号}：spec 描述「{spec描述}」，代码实现「{代码实现}」
suggestions:          # 仅 has_spec=true 时输出，简短1-2条
  - {待更新/待优化建议}
skipped: false | true（原因：仓库无 spec 目录 / 纯配置变更 / 纯前端）
[/SDD_CHECK_RESULT]
```

> ⚠️ **`has_spec=false` 时**：仅输出 `has_spec: false` + `completeness: MISSING`，不输出 alignment_issues / alignment_rate / suggestions。文档 SDD 章节写「本次变更未采用 SDD，无设计产物」。
> ⚠️ **`skipped=true` 时**：仅纯前端路径跳过（`fe-ai-review`），其余场景必输出 SDD 结果。
> ⚠️ **AI-SDLC 模式（`INVOKE_MODE=sdlc`）下**：`[SDD_CHECK_RESULT]` 仅供 Step 4 内部引用，不写入 SDLC JSON（格式约束不允许新增字段）。

---
