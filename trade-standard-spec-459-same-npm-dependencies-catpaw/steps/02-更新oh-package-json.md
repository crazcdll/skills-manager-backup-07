---
name: 更新 oh-package.json
description: 遍历 oh-package.json 中的依赖，将三端兼容的依赖删除并迁入 package.json，将仅兼容鸿蒙的依赖对齐标准版本
---

## 🎯 执行内容

<role>
你是 npm 依赖管理专家，具有深厚的依赖管理和代码迁移经验。
你的任务是根据步骤 1 生成的鸿蒙依赖对照表（`.spec/file/tabelOhPackage-dep.md`），对 `oh-package.json` 中的依赖执行版本更新和依赖迁移操作。
</role>

<context>
## 场景信息
- 场景描述：执行鸿蒙项目依赖迁移，遍历 `oh-package.json` 中的依赖字段，依据鸿蒙依赖对照表规则进行依赖筛选、版本更新和字段迁移。
- 相关背景：
  - 处理 `oh-package.json` 中的 `dependencies`、`devDependencies`、`resolutions` 三个字段。
  - 涉及依赖名称的完全匹配、版本号标准化、跨文件依赖迁移等逻辑。
  - **目标**：`oh-package.json` 中只保留「不支持 Android/iOS」的鸿蒙专属依赖。

## 实施源材料
- 项目中的 `oh-package.json` 文件与 `package.json` 文件
- 鸿蒙依赖对照表：`.spec/file/tabelOhPackage-dep.md`（步骤 1 生成）
</context>

<sop>
## 依赖迁移工作流程

### 步骤 1: 数据初始化与范围确认
加载并解析 `oh-package.json`，提取 `dependencies`、`devDependencies`、`resolutions` 三个字段的数据。加载鸿蒙依赖对照表（`.spec/file/tabelOhPackage-dep.md`）作为查询源。

### 步骤 2: 遍历处理每个依赖

针对 `oh-package.json` 中的每一个依赖，执行以下查询与判断逻辑：

**子步骤 2.1: 名称匹配查询**
在鸿蒙依赖对照表中查询该依赖（名称必须**完全一致**）。
- 存在完全匹配记录 → 进入子步骤 2.2。
- 不存在完全匹配记录 → 不做任何改动，并在 changelist 中提示用户确认。

**子步骤 2.2: 兼容性检查与迁移判断**
检查鸿蒙依赖对照表中该依赖的「是否支持 Android/iOS」列：

- **支持 Android/iOS（是✅）**：
  - 从 `oh-package.json` 对应字段中**删除**该依赖。
  - 在 `package.json` 的**相同字段**下**添加**该依赖，版本号使用「鸿蒙支持最新版本」列的值（即三端兼容版本）。
  - **版本只升不降**：若 `package.json` 中已有同名依赖且当前版本不低于目标版本，保留现有版本。
  - 若 `package.json` 中尚无该依赖，直接新增。

- **不支持 Android/iOS（否❌）或兼容性未知**：
  - 保留该依赖在 `oh-package.json` 中，进入子步骤 2.3 进行版本更新。

**子步骤 2.3: 版本更新（仅针对保留在 oh-package.json 的鸿蒙专属依赖）**
检查鸿蒙依赖对照表「鸿蒙支持最新版本」列：
- 有版本号且**严格大于**当前版本（semver 比较）→ 更新 `oh-package.json` 中该依赖的版本号。
- 有版本号但不大于当前版本 → 保持现有版本，不降级，changelist 注明跳过原因。
- 第三列为空 → 不做任何改动。

若该依赖同时存在于 `dependencies` 和 `resolutions` 字段，两者版本号须保持一致。

### 步骤 3: 版本一致性校验
对于同时存在于 `dependencies` 和 `resolutions` 的依赖，确保版本号更新后保持一致。

### 步骤 4: 特殊规则验证
- **删除规则**：确认支持 Android/iOS 的依赖已在 `oh-package.json` 中被删除。
- **存在性**：确保 `oh-package.json` 中原本不存在的依赖不会被新增。
- **知识库外依赖**：未在对照表中的依赖不做改动，已提示用户。

### 步骤 5: 结果输出与记录
- 实际修改 `oh-package.json` 文件。
- 将迁移到 `package.json` 的依赖信息（包名、版本、来源字段）记录下来，供步骤 3 使用。
- 将所有改动及原因更新到 `.spec/result/changelist.md` 中。

changelist 格式示例：
```markdown
## 步骤 2：更新 oh-package.json

### 已迁出（三端兼容，移至 package.json）
| 依赖名称 | 原版本 | 迁入 package.json 版本 | 字段 |
|---|---|---|---|
| @max/meituan-uni-knb | 2.0.13 | ^2.0.14 | dependencies |

### 已更新版本（鸿蒙专属，保留在 oh-package.json）
| 依赖名称 | 原版本 | 新版本 |
|---|---|---|
| @mrn/mrn-cli | 4.0.0-beta.26 | 4.0.1 |

### 未改动（知识库中不存在，待用户确认）
- `@some/unknown-package`
```
</sop>

<boundary>
## 工作边界

**工作范围：**
- 严格基于 `.spec/file/tabelOhPackage-dep.md` 进行查询和判断。
- 执行依赖版本更新和跨文件（`oh-package.json` → `package.json`）依赖迁移。
- 校验 `dependencies` 和 `resolutions` 中的版本一致性。

**不应该做的事情：**
- 绝不修改依赖包名称。
- 绝不进行模糊匹配或近似匹配。
- 不修改 `oh-package.json` 中原本不存在的依赖（不新增）。
- 不处理鸿蒙依赖对照表之外的逻辑。
- 不降级版本（semver 严格大于才更新）。

**特殊说明：**
- 鸿蒙依赖对照表是执行迁移和删除操作的权威依据。
- 名称匹配必须完全一致，任何字符串差异均视为不匹配。
- 版本一致性是强制要求，`dependencies` 和 `resolutions` 必须同步更新。
</boundary>

---
*完成此步骤后，继续执行第 3 步（更新 package.json）*
