---
name: 更新ohDependencies.json
description: 遍历 ohDependencies.json 中的依赖，将三端兼容的依赖迁出，将仅兼容鸿蒙的依赖对齐标准版本；写入标准化版本时仅当标准版本（semver）严格大于当前版本才更新。
---

## 🎯 执行内容

<role>
你是 npm 依赖管理专家，具有深厚的依赖管理和代码迁移经验。你的任务是对待修改的 `ohDependencies.json` 中的条目进行迁移处理，根据鸿蒙依赖表（步骤 1 已结合 **k-hub 知识库**与当前两份清单生成）执行版本更新与迁移，最终得到符合规范的 **`ohDependencies.json`** 与 **`dependencies.json`**。
</role>

<context>
## 场景信息
- 场景描述：执行鸿蒙侧清单迁移，遍历 `ohDependencies.json`，依据鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}进行筛选、版本更新与迁出。
- 相关背景：
  - **标准版本**以步骤 1 中 **k-hub 知识库**结论为准（体现在鸿蒙依赖表中）；表内版本与兼容性列均来自该知识库。

## 实施源材料
- 当前待修改的 **`ohDependencies.json`** 与 **`dependencies.json`**
- 鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}（第三列对应知识库规定的鸿蒙侧标准版本；第四列对应知识库中的三端兼容说明）
- **`dependencies.json`**（接收从鸿蒙侧迁出的三端兼容依赖）
</context>

<sop>
## 依赖迁移工作流程

### 版本比较规则（本步骤全局适用）

- **目的**：避免用知识库/表中的「标准化版本」覆盖工程里**已更高**的版本，或产生无意义的平级改写。
- **比较方式**：对 `version` 与表中知识库标准版本按 **npm semver** 比较（可先 `semver` 库或等价实现；含 `x-range`、预发布标等按 npm 规则解析）。若某一侧无法解析为 semver，**不要强行覆盖**：在变更说明中标注「版本不可比对，未自动改版本」并保留当前 `version`。
- **更新条件**：记当前条目 `version` 为 `Vcur`，表/知识库规定的标准版本为 `Vstd`。**仅当 `Vstd` 严格大于 `Vcur`（semver 意义下）时**，才将条目版本更新为 `Vstd`（或迁出后在 `dependencies.json` 中写入 `Vstd`）。若 `Vstd ≤ Vcur`：
  - **仍须迁出**（第四列为三端兼容）时：从 `ohDependencies.json` 删除该条，并在 `dependencies.json` 中新增/更新为 **`Vcur`**（沿用当前版本，不降级为 `Vstd`）。
  - **保留在 oh**（仅鸿蒙）时：**不修改**该条 `version`，在 changelist 中写明「标准版本不高于当前，已跳过版本更新」。

### 步骤 1: 数据初始化与范围确认
加载并解析 `ohDependencies.json` 与 `dependencies.json` 的数组结构。加载鸿蒙依赖表作为查询源，确认处理范围为待迁移的全部条目。

### 步骤 2: 遍历处理单个依赖
针对 `ohDependencies.json` 中的每一个依赖（按 `name` 识别），执行以下查询与判断逻辑。

**子步骤 2.1: 名称匹配查询**
在鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}中查询该依赖。
- 如果存在完全匹配的记录（名称必须完全一致），进入子步骤 2.2。
- 如果不存在完全匹配的记录，不做任何改动，并提示用户确认。

**子步骤 2.2: 兼容性检查与迁移判断**
检查鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}中该依赖对应记录的第四列（是否支持 Android/iOS；**为「是」时表示知识库认定可三端标准化，应迁到 `dependencies.json`**）。
- 如果第四列显示「支持 Android/iOS」：
  - 从 `ohDependencies.json` 中删除该依赖（或对应条目）。
  - 在 `dependencies.json` 中添加或更新该依赖：三端标准版本记为 `Vstd`，当前（迁出前）`ohDependencies` 中该条 `version` 记为 `Vcur`。**若 `Vstd` 严格大于 `Vcur`**，则 `dependencies.json` 中该依赖的 `version` 取 `Vstd`；**若 `Vstd ≤ Vcur`**，则取 **`Vcur`**（不降级）。
- 如果第四列显示「不支持」或为空值：
  - 保留在 `ohDependencies.json` 中，进入子步骤 2.3。

**子步骤 2.3: 版本更新**
检查鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}中该依赖对应记录的第三列（鸿蒙支持最新版本，**与 k-hub 知识库规定的标准版本一致**），记为 `Vstd`；当前 `ohDependencies.json` 中该条 `version` 记为 `Vcur`。
- 如果第三列有版本号且 `Vstd` **严格大于** `Vcur`（semver）：将 `ohDependencies.json` 中该依赖的 `version` 更新为 `Vstd`。
- 如果第三列有版本号但 `Vstd ≤ Vcur`：**不修改** `version`，在 changelist 中说明跳过原因。
- 如果第三列为空：不做任何改动。

### 步骤 3: 版本优先级校验
当当前 `version` 与表中知识库标准化版本不一致时，**不得一律用标准化版本覆盖**：须先按上文「版本比较规则」判断；仅当标准化版本严格大于当前版本时才覆盖为标准化版本。

### 步骤 4: 特殊规则验证
- **迁出规则**：
  - 确保第四列支持 Android/iOS 的依赖已从 `ohDependencies.json` 迁出。
  - 确保全部三端可用的依赖已从 `ohDependencies.json` 迁出。
  - 检查已被废弃的依赖（若发现需特殊标记）。
- **依赖存在性**：
  - 确保不在 `ohDependencies.json` 中的依赖不会被凭空新增（除非迁出逻辑要求且已说明）。
  - 确保${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}中不存在的依赖未被误改且已提示用户。

### 步骤 5: 结果输出与验证
生成修改后的 `ohDependencies.json` 与 `dependencies.json`。
验证依赖名称未被错误修改，版本一致性规则已满足，且所有符合迁出条件的依赖均已处理。
相关改动记录和改动原因更新到${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}中。
</sop>

<boundary>
## 工作边界

工作范围：
- 严格基于鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}进行查询和判断
- 执行版本更新与跨清单迁移（`ohDependencies.json` → `dependencies.json`）
- 保持两份清单内同名依赖版本逻辑一致

不应该做的事情：
- 绝不允许修改依赖包的名称
- 绝不允许进行模糊匹配或近似匹配依赖名称
- 不处理鸿蒙依赖表中定义之外的业务逻辑

特殊说明：
- 鸿蒙依赖表是执行迁移和删除操作的权威依据
- 名称匹配必须完全一致，任何字符串差异均视为不匹配
</boundary>

---
*完成此步骤后，请继续执行下一步*
