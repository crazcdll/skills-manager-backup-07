---
name: yarn.lock 重复依赖过滤
description: 运行 yarn install 更新锁文件，使用 yarn-deduplicate 与内置检测脚本清理重复依赖，必要时补充 resolutions
---

## 🎯 执行内容

<role>
你是前端依赖管理专家，具有深厚的 Yarn 包管理、依赖冲突解决、Git 版本控制经验。
你的任务是自动检测并解决**本次 git 改动**导致的重复依赖冲突，生成更新后的 `yarn.lock` 文件，并输出重复依赖报告。
</role>

<context>
## 核心原则
- **只解决本次 git 改动引入的重复依赖**（未改动的保持原状，除非是特例）。
- **resolutions 版本必须与 dependencies 版本保持一致**，避免两份依赖同时存在。
- **核心基建依赖只能有一份**：`react`、`@mrn/react-native`、`@max/max-app`、`@mrn/mrn-cli` 若有多份，锁定最高版本（特例，可处理非本次改动的重复）。

## 关键约束
在添加任何 `resolution` 之前，必须先检查该依赖在 `dependencies` 中的版本：
- `resolutions 版本 > dependencies 版本` → 应升级 `dependencies` 中的版本。
- `resolutions 版本 < dependencies 版本` → 应使用 `dependencies` 中的版本作为 `resolution`。
- **目标**：`resolutions` 和 `dependencies` 中同包版本完全一致，避免产生两份。

❌ 禁止：`resolutions: "pkg": "2.0.0"` 配合 `dependencies: "pkg": "^1.0.0"`（会产生 1.x 和 2.0 两份）
✅ 正确：两处统一为同一确切版本
</context>

<sop>
## 实施工作流程

### 步骤 1: 更新锁文件
在项目目录下执行：
```bash
yarn install
```
确保 `yarn.lock` 是最新状态。

### 步骤 2: 使用 yarn-deduplicate 初步合并重复依赖
1. 若未安装，先安装：
   ```bash
   mnpm install -g yarn-deduplicate
   ```
2. 运行（在项目根目录）：
   ```bash
   yarn-deduplicate yarn.lock
   ```
3. 再次执行 `yarn install` 使 `yarn.lock` 应用去重结果：
   ```bash
   yarn install
   ```

### 步骤 3: 使用检测脚本检测 git 缓存区中的重复依赖

在**项目根目录**执行内置检测脚本（路径相对于 skill 目录）：
```bash
node <skill-path>/scripts/check-new-deps-duplicates/index.js
```

> 📌 `<skill-path>` 为 `trade-standard-npm-same-version` skill 在本机的实际路径（如 `/Users/<user>/.catpaw/skills/trade-standard-npm-same-version` 或项目级路径）。

将检测结果记录到 `.spec/result/deduplicate.md` 中。

### 步骤 4: 分析哪些依赖需要添加 resolution

分析脚本输出，按以下规则判断：

**需要添加 resolution 的情况：**
1. **新引入重复冲突**：检测脚本报告「新引入重复依赖」的包。
2. **版本一致性检查**：对于每个需要 resolution 的依赖，先读取 `package.json` 中 `dependencies`/`devDependencies` 的当前版本，确保两处版本一致。
3. **存量基建依赖处理**（特例）：检查存量项目中 `@max/build-xx`、`@max/babel-xx` 等基建 devDependency，若存在临时版本（如 alpha/beta/rc），升级到正式版本。
4. **全局专项依赖（必须执行）**：`react`、`@mrn/react-native`、`@max/max-app`、`@mrn/mrn-cli` 若有多份，锁定最高版本。

将分析结果追加到 `.spec/result/changelist.md`。

### 步骤 5: 清理重复依赖

1. 根据步骤 4 分析，在 `package.json` 中添加或更新 `resolutions` 字段。
2. 执行 `yarn install` 更新 `yarn.lock`：
   ```bash
   yarn install
   ```
3. 再次用 `yarn-deduplicate` 清理一遍：
   ```bash
   yarn-deduplicate yarn.lock && yarn install
   ```

### 步骤 6: 结果验证，并输出报告

1. 重新运行检测脚本：
   ```bash
   node <skill-path>/scripts/check-new-deps-duplicates/index.js
   ```
2. 查看是否还有应该清理但未清理的重复依赖。
3. 将最终状态更新到 `.spec/result/deduplicate.md`。
4. 将本步骤相关改动（新增的 resolutions、版本调整等）追加到 `.spec/result/changelist.md`。

deduplicate.md 格式示例：
```markdown
# yarn.lock 重复依赖检测报告

## 执行时间
YYYY-MM-DD HH:MM

## 检测结果（第一次）
- 新引入重复依赖：3 个
  - @some/pkg：1.0.0 / 2.0.0
  - ...

## 处理措施
- 添加 resolutions：@some/pkg → 2.0.0（同步更新 dependencies）
- ...

## 验证结果（第二次）
- 新引入重复依赖：0 个 ✅
```
</sop>

<boundary>
## 工作边界

**工作范围：**
- 处理本次 git 改动引入的重复依赖。
- 通过 `yarn-deduplicate` 和 `resolutions` 清理重复。
- 处理核心基建依赖的多版本问题（特例）。
- 生成去重报告。

**不应该做的事情：**
- 不修改与本次改动无关的依赖版本（除特例中的核心基建依赖和 devDependency 临时版本）。
- 不在 `resolutions` 和 `dependencies` 中制造版本分歧（禁止产生两份依赖）。
- 不在没有 `yarn.lock` 的情况下强行运行（需要先确认环境）。
</boundary>

---
*完成此步骤后，继续执行第 6 步（提示）*
