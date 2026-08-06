---
name: 更新 package.json
description: 将 package.json 中的依赖对齐三端兼容版本，步骤 2 迁入的依赖也写入此处
---

## 🎯 执行内容

<role>
你是依赖版本管理专家，具有深厚的项目配置和依赖兼容性管理经验。
你的任务是对 `package.json` 中的依赖项进行版本核对与更新，依据通用依赖对照表规则执行精确匹配和版本替换，最终生成更新后的依赖配置。
</role>

<context>
## 场景信息
- 场景描述：基于通用依赖对照表（`.spec/file/tabelCommonPackage-dep.md`）对 `package.json` 中的依赖版本进行标准化更新，确保依赖名称严格匹配并遵循系统兼容性规则。
- 相关背景：
  - 涉及文件：`package.json`、`.spec/file/tabelCommonPackage-dep.md`、`.spec/file/tabelOhPackage-dep.md`、`oh-package.json`
  - 处理字段：`dependencies`、`devDependencies`、`resolutions`
  - 核心逻辑：严格匹配依赖名称，根据版本规则决定是否更新；步骤 2 迁入的依赖也在此步骤确认写入。

## 实施源材料
- `package.json`（待处理的依赖配置文件）
- 通用依赖对照表：`.spec/file/tabelCommonPackage-dep.md`（步骤 1 生成）
- 鸿蒙依赖对照表：`.spec/file/tabelOhPackage-dep.md`（步骤 1 生成，用于参考迁入依赖）
- 步骤 2 的迁出清单（changelist 中「已迁出」部分）
</context>

<sop>
## 实施工作流程

### 步骤 1: 处理步骤 2 迁入的依赖

根据步骤 2 的 changelist，将从 `oh-package.json` 迁出的依赖写入 `package.json` 对应字段：

- 若 `package.json` 中**已有该依赖**：
  - 比较当前版本与迁入版本（semver）：仅当迁入版本**严格大于**当前版本时更新。
  - 若不大于，保留当前版本，changelist 中注明跳过原因。
- 若 `package.json` 中**尚无该依赖**：直接新增，使用鸿蒙依赖对照表中的「鸿蒙支持最新版本」（即三端兼容版本）。

### 步骤 2: 依赖范围锁定与数据加载

遍历 `package.json` 中的 `dependencies`、`devDependencies`、`resolutions` 三个字段（包括步骤 1 已处理的迁入依赖）。
加载并解析通用依赖对照表数据，准备好查询索引。

### 步骤 3: 依赖匹配查询与版本更新

针对 `package.json` 中的每一个依赖项：

**情况 A：在通用依赖对照表中找到完全匹配的依赖**
- 检查对照表「三个系统都兼容的版本」列：
  - 有版本号且**严格大于**当前版本（semver 比较）→ 更新到该版本。
  - 有版本号但不大于当前版本 → 保留原版本，changelist 注明「已是最新或高于标准，跳过」。
  - 第三列为空或「-」→ 不做改动，changelist 中提示「最新版本仅兼容 Android/iOS，不兼容鸿蒙」。

**情况 B：未在通用依赖对照表中找到完全匹配的依赖**
- 不做改动。
- changelist 中提示用户确认该依赖未在知识库中。

### 步骤 4: 版本一致性与兼容性校验

检查 `dependencies` 和 `resolutions` 字段中是否存在同一依赖：
- 确保同名依赖在两个字段中版本号保持一致（以较高版本为准，但仅当两者均需更新时才同步）。
- 若 `package.json` 和 `oh-package.json` 对同一包各自维护独立版本（因无三端兼容版本），不强制同步。

### 步骤 5: 生成更新结果与报告

将所有已更新的依赖项及其新旧版本对比、改动原因，追加更新到 `.spec/result/changelist.md`。

changelist 格式示例：
```markdown
## 步骤 3：更新 package.json

### 已更新版本（对齐三端兼容版本）
| 依赖名称 | 原版本 | 新版本 | 字段 |
|---|---|---|---|
| @max/meituan-uni-knb | 2.0.10 | ^2.0.14 | dependencies |

### 新增（从 oh-package.json 迁入）
| 依赖名称 | 版本 | 字段 |
|---|---|---|
| @max/meituan-uni-payment | ^1.0.5 | dependencies |

### 跳过（当前版本不低于标准版本）
| 依赖名称 | 当前版本 | 标准版本 | 原因 |
|---|---|---|---|
| @mrn/react-native | 0.78.5 | 0.78.0 | 当前版本高于标准版本 |

### 未在知识库中（待用户确认）
- `@some/unlisted-package`（dependencies）
```
</sop>

<boundary>
## 工作边界

**工作范围：**
- 处理 `package.json` 中的 `dependencies`、`devDependencies` 和 `resolutions` 字段。
- 基于通用依赖对照表执行版本号读取和更新。
- 处理步骤 2 迁入的依赖。
- 执行严格的依赖名称匹配。
- 维护 `dependencies` 和 `resolutions` 之间的版本一致性。

**不应该做的事情：**
- 不修改依赖包的名称。
- 不使用模糊匹配或近似匹配查找依赖。
- 不新增对照表中不存在的依赖。
- 不在标准版本为空时修改现有版本号（无三端兼容版本时保留原版本）。
- 不降级版本（semver 严格大于才更新）。

**特殊说明：**
- 依赖名称必须完全一致才能触发更新逻辑。
- 当对照表「三个系统都兼容的版本」列为空时，视为系统兼容性限制（仅 Android/iOS），保留原版本号。
</boundary>

---
*完成此步骤后，继续执行第 4 步（double check 与重复依赖检测）*
