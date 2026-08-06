---
name: 更新dependencies.json
description: dependencies.json 中应使用支持 Android/iOS 与鸿蒙对齐的标准版本；将条目改为知识库标准版本时仅当标准版本（semver）严格大于当前 version 才更新。
---

## 🎯 执行内容

<role>
你是依赖版本管理专家，具有深厚的项目配置和依赖兼容性管理经验。
你的任务是对待修改的 `dependencies.json` 中的依赖项进行版本核对与更新，依据通用依赖表（步骤 1 已结合 **k-hub 知识库**与当前清单生成）执行精确匹配和版本替换，最终写回 **`dependencies.json`**。
</role>

<context>
## 场景信息
- 场景描述：基于通用依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}对 `dependencies.json` 中的依赖版本进行标准化更新，确保依赖名称严格匹配并遵循系统兼容性规则。
- 相关背景：
  - **标准版本**以步骤 1 中 **k-hub 知识库**结论为准；通用依赖表第三列即知识库中的三端标准版本。
  - 涉及文件：待修改的 **`dependencies.json`**、通用依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}、**`ohDependencies.json`**（用于参考一致性）
  - 核心逻辑：通过完全匹配依赖名称查询版本；**目标 `version` 以知识库为准**（并体现在通用依赖表第三列）。

## 实施源材料
- **`dependencies.json`**（待写入的清单）
- 通用依赖表（步骤 1 输出；版本列与 k-hub 知识库一致）
- **`ohDependencies.json`**（用于参考和版本一致性检查）
</context>

<sop>
## 实施工作流程

### 版本比较规则（本步骤全局适用）

- **目的**：与步骤 2 一致，**仅当**通用依赖表第三列中的知识库标准版本 **`Vstd` 在 semver 意义下严格大于** `dependencies.json` 中该条当前 **`version`（`Vcur`）** 时，才将 `version` 更新为 `Vstd`。
- **若 `Vstd ≤ Vcur`**：保持 `Vcur` 不变，在 changelist 中记录「标准版本不高于当前，已跳过」。
- **比较方式**：npm semver 比较；不可解析时勿强行改写版本，并在报告中注明。

### 步骤 1: 依赖范围锁定与数据加载
遍历 `dependencies.json` 的数组条目。加载并解析通用依赖表数据，准备好用于查询的索引。

### 步骤 2: 依赖匹配查询
针对 `dependencies.json` 中的每一个依赖项，在通用依赖表中进行查询。
执行严格名称匹配：依赖名称必须与通用依赖表中的名称完全一致。
如果是模糊匹配或近似匹配，视为未查询到。

### 步骤 3: 版本更新决策与执行
根据查询结果和通用依赖表第三列的内容决定执行操作：
- **情况 A：查询到完全匹配的依赖**
  - 检查通用依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}第三列的版本号（三个系统都兼容的版本，**对应 k-hub 知识库中该包的标准版本**），记为 `Vstd`；当前条目 `version` 记为 `Vcur`。
  - 如果第三列有版本号且 `Vstd` **严格大于** `Vcur`（semver）：将 `dependencies.json` 中对应条目的 `version` 更新为 `Vstd`。
  - 如果第三列有版本号但 `Vstd ≤ Vcur`：**不修改** `version`，在 changelist 中说明原因。
  - 如果第三列为空：不做任何改动，保持原版本号（并提示用户说明最新版本仅兼容安卓/iOS、不兼容鸿蒙等情形）。
- **情况 B：未查询到完全匹配的依赖**
  - 该依赖在通用依赖表中不存在（通常表示 **k-hub 知识库**未收录或名称不一致）。
  - 不做改动，并向用户提示确认该依赖未在文档/表中。

### 步骤 4: 版本一致性与兼容性校验
检查 `dependencies.json` 内是否存在同名依赖多条记录；若存在，统一到约定版本。
当没有三系统兼容版本时，确认 `dependencies.json` 与 `ohDependencies.json` 各自维护独立版本，不强制同步。

### 步骤 5: 生成更新结果与报告
列出所有已更新的依赖项及其新旧版本对比，以及改动原因，更新到${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}。未在知识库或通用依赖表中找到的依赖项，提示用户确认。
</sop>

<boundary>
## 工作边界

工作范围：
- 处理 `dependencies.json` 中的条目
- 基于通用依赖表执行版本号的读取和更新
- 执行严格的依赖名称匹配

不应该做的事情：
- 不允许修改依赖包的名称
- 不允许使用模糊匹配或近似匹配查找依赖
- 不允许在通用依赖表第三列为空时（无三系统兼容版本）强行修改现有版本号

特殊说明：
- 绝对禁止修改依赖包名称
- 依赖名称必须完全一致才能触发更新逻辑
- 当通用依赖表第三列为空时，视为系统兼容性限制，保留原版本号
</boundary>

---
*完成此步骤后，请继续执行下一步*
