---
name: 更新componentsMap.json
description: 对步骤 2/3 已变更的 npm 在 componentsMap 中再次校验升级为非降级后同步 npmVersion/URL；若检出降级风险则重点提示用户核查且本流程不生成 commit。
---

## 🎯 执行内容

<role>
你是低代码物料与依赖清单对齐专家。你的任务是在完成 **`dependencies.json`** 与 **`ohDependencies.json`** 的版本更新后，检查工程中的 **`componentsMap.json`**（若存在）：仅针对步骤 2/3 已变更的 npm，在写回前**再次校验**清单目标相对当前 `npmVersion` 为**升级**后再同步；若检出**降级风险**，须重点提示用户并阻断 commit，而非强行对齐。
</role>

<context>
## 场景信息
- **前置条件**：步骤 2、步骤 3 已写回 `ohDependencies.json`、`dependencies.json`；步骤 3 产出的变更说明见 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}（或根据 Git diff / 新旧版本对照表识别「包名 → 新版本」）。
- **目标文件**：工程根目录或约定路径下的 **`componentsMap.json`**（若仓库中不存在该文件，则本步骤跳过，无需创建）。
- **结构说明**：`componentsMap.json` 一般为「字符串 key → 对象」映射；每个对象常含 `npm`（包名）、`npmVersion`（版本号）、`web`（资源 URL 数组，路径中通常包含版本号片段）等字段，以实际文件为准。

## 对齐规则
- **版本来源**：以当前已生效的 **`dependencies.json`** 与 **`ohDependencies.json`** 中对应条目的 `version` 为准（同名包若在两份清单中仅出现一处，以出现处为准；若业务约定以其中一份为准，与步骤 2/3 保持一致）。
- **何时修改**：仅当某 npm 包名在 `componentsMap` 某条目的 `npm` 字段中出现，且该包在步骤 2/3 中 **`version` 相对流程开始前发生了变化**，才**考虑**更新该条目。
- **二次校验（升级 vs 降级）**：本步处理的包**仅限于**步骤 2/3 中 `version` 已发生变更的包（步骤 1 的变化集合）；这些包在步骤 2/3 已按「标准版本 > 当前清单版本才写入」做过**第一道校验**。在写回 `componentsMap` 前，再对照清单目标版本 `Vlist` 与物料侧当前 `npmVersion`（`Vcm`）做一次**第二道校验**：若将 `npmVersion` 从 `Vcm` 调整为 `Vlist`，须保证是 **semver 升级**（`Vlist` 严格大于 `Vcm`）才允许同步。若 **`Vlist` 严格小于 `Vcm`**，视为**相对物料映射存在降级风险**（清单与 componentsMap 或历史步骤不一致），**不得**修改该条 `npmVersion`/URL，须按下文「降级处理」向用户**重点提示**并**阻断本流程的 commit**。
- **可同步条件**：仅当 `Vlist` 严格大于 `Vcm` 时，更新 `npmVersion` 与 URL 中版本片段。若 `Vlist` 等于 `Vcm`：无需改 `componentsMap`，可在报告中一笔带过。
- **降级处理（强制）**：一旦在任一条目上判定 `Vlist < Vcm`（semver）：(1) 在 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}（或等价结果输出）顶部或独立小节用醒目标题（如 **【步骤 4 降级风险 · 禁止提交】**）列出：包名、`Vlist`、`Vcm`、建议核对清单与步骤 2/3 及物料来源；(2) **创建或更新**标记文件 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/block-commit.flag}}（内容可为 `downgrade-risk-in-step04` 或简短说明），供后续自动化识别；(3) **本流程内不要执行 `git commit`**，若后续步骤（如 duo 流程的提交节点）依赖「成功完成且无阻断标记」，须**跳过提交**直至用户人工处理并删除该标记文件或确认可提交。
- **修改内容**（在满足「`Vlist` 严格大于 `Vcm`」且未触发降级处理时）：
  1. 将条目的 **`npmVersion`** 更新为清单中的目标版本 `Vlist`。
  2. 若存在 **`web`**（或其它含版本号的 URL 字段），将 URL 中与旧版本对应的版本号片段替换为 `Vlist`，保持与 `dependencies.json` / `ohDependencies.json` 中同类 `url` 的拼接规则一致（例如 `.../material/<scope>/<name>/<version>/index.js`）。
- **未出现在清单中的包**：`componentsMap` 中出现但不在 `dependencies.json` 与 `ohDependencies.json` 中的 npm 包，本步骤不强行改版本（避免与清单外依赖冲突）；可在报告中备注「仅存在于 componentsMap」供人工确认。
</context>

<sop>
## 实施工作流程

### 步骤 1: 收集版本变化集合
从 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}、Git 工作区 diff，或步骤 3 汇总中，整理「包名 → 新 `version`」映射（仅包含在步骤 2/3 中实际发生变更的包）。

### 步骤 2: 定位 componentsMap.json
若工程不存在 **`componentsMap.json`**，记录「跳过」并进入步骤 5。

### 步骤 3: 再次校验（升级/降级）并同步
本步仅处理步骤 1 收集到的、**已在步骤 2/3 中变更过版本**的 npm 包；步骤 2/3 已对「知识库标准版本 vs 当时清单内版本」做过一次校验，此处针对 **`componentsMap` 与清单的交叉**再做一次。

对 `componentsMap.json` 中每一项，若其 `npm` 落在步骤 1 的变化集合中：
1. **读取**：`npmVersion` 记为 `Vcm`；从当前 **`dependencies.json` / `ohDependencies.json`** 取该包清单目标版本 `Vlist`（与上文「对齐规则」一致）。
2. **再次校验 semver 方向**：
   - 若 **`Vlist` 严格大于 `Vcm`**：认定为对物料映射的**升级同步**，允许将 **`npmVersion`** 更新为 `Vlist`，并按需替换 **`web`**（等）URL 中的版本片段。
   - 若 **`Vlist` 等于 `Vcm`**：无需修改该条目。
   - 若 **`Vlist` 严格小于 `Vcm`**：认定为**降级风险**（若强行与清单对齐会使物料版本低于当前映射）。**不要**修改该条目；立即执行上文「降级处理（强制）」：向用户**重点提示**（说明须核对清单、步骤 2/3 产出与 `componentsMap` 是否一致、是否存在手工改清单或表数据错误），并**不得**在本流程内生成 commit；写入 `block-commit.flag` 与 changelist 醒目标识。
3. **比较不可解析**：若 `Vlist` 或 `Vcm` 无法按 semver 可靠比较，**不要**擅自同步版本；记入 changelist 并请用户人工确认；若业务上可判定为降级倾向，同样适用「降级处理」中的用户提示与阻断提交策略（由执行方保守处理）。

### 步骤 4: 一致性自检
- 确认所有已修改条目的 `npmVersion` 与清单中该包的 `version` 一致。
- 确认 URL 中的版本片段与 `npmVersion` 一致（无遗漏替换）。

### 步骤 5: 记录结果
- 若有**成功同步**的条目，将摘要追加到 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}，列出：`npm`、旧 `npmVersion`、新 `npmVersion`、是否更新了 `web`。
- 若曾触发**降级处理**：changelist 中已含禁止提交说明；**确认未执行 commit**；若全流程有「仅当无 `block-commit.flag` 才提交」的约定，执行方须遵守。
</sop>

<boundary>
## 工作边界

- **应做**：仅同步「步骤 2/3 已变更版本且 componentsMap 中存在的包」；写回前完成**二次校验**（升级非降级）；保持 JSON 合法性与原有字段结构（不删除无关 key）。
- **不应做**：不因本步骤反向修改 `dependencies.json` / `ohDependencies.json`；不批量升级未在步骤 2/3 中涉及的包版本。
- **降级时**：**不得**生成 commit；**须**输出重点提示并写入 `block-commit.flag`（路径见上文「降级处理」）。
</boundary>

---
*完成此步骤后，请继续执行下一步*
