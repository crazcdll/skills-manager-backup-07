---
name: 更新dependencies.json
description: 按步骤 1 target-versions 写 dependencies.json，严格 name、semver 防降级、预发精确、url 随版本；骨架对齐 same-npm 的 03-更新dependencies
---

## 目标

在物料仓库中更新根目录（或工程约定路径）的 **`dependencies.json`**：将清单内每条 `name` 所对应的 **`version`（及含版本路径的 `url`）** 对齐 **步骤 1** 产出的 **MRN 新架构目标版本**（`${{inputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/target-versions.md}}` 中的映射）。

**流程骨架**与 **`trade-duo-standard-same-npm-dependencies` 的 @trade-duo-standard-same-npm-dependencies/steps/03-更新dependencies-json.md 一致**（范围锁定、严格包名匹配、按标准版本与当前版本做决策、一致性校验、落盘 changelist），但 **「标准版本」来源** 不是 k-hub 表，而是 **本 skill 步骤 1** 的 **Citadel/降级** 所确定的 **`target-versions.md`**。

- 对 **`dependencies.json` 数组** 按 `name` 与 `target-versions.md` 对照，判定需改、已达标、或不在表内。  
- **本步只** 改此 JSON，不**改** `package.json` 里 `resolutions`（有锁包需求见团队其它流程）。  
- **写回** `version` 及**含版本段** 的 `url`（见下「版本号写法」「步骤 3」）。

**联动与固定版本**（同步骤 1 / `data/fallback-target-versions.md`）：`@mtfe/msi` 与 `@mtfe/msi-mrn` **同版**；`react` / `react-redux` / `redux` 用**固定**目标，**不**用学城表去覆盖该三件套。

---

## 实施源材料

- **待改文件**：工程内 **`dependencies.json`**
- **目标版本表**：${{inputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/target-versions.md}}（**步骤 1 输出，唯一权威**）
- **只读参考**：`ohDependencies.json`（同仓库内版本分工与**交叉核对**用，**本步不修改** `ohDependencies.json`）
- **结构说明（可选）**：@trade-duo-standard-material-upgrade-npm-dependencies/data/dependencies.json 仅作字段结构参考

---

## 工作边界

与 @trade-duo-standard-same-npm-dependencies/steps/03-更新dependencies-json.md 相同的核心边界：

- **只改** `dependencies.json` 中允许与版本/资源相关字段；**不要改** 依赖 **`name`**
- **禁止** 模糊/近似匹配 `name`；只接受 **完全**
- 目标表中**无** `name`、或**文档/步骤 1 已排除**的条目：**不**为「凑目标」而改版本
- 若某条在目标表中**无有效 Vstd**（同「三端」流程里表第三列为空的情形）：**不**改 `version`，在 changelist 中说明

**补充（物料 + MRN）**：

- **禁止降级**：仅当对当前 `version` 作 npm semver 解析后，**目标 `Vstd` 严格高于** 当前**有效基线**（对 range 取满足约束的代表比较方式见下）时，将清单版本升到 `Vstd`；若已高于或不可判定为应升级，则**保持**并记录
- 若 `url` 存在且**无法**按规则安全替换版本段：在 changelist 中 **高亮** 并提示人工

---

## 实施工作流程

### 版本比较规则（与 same-npm 第 3 步「全局」一致、术语对齐 MRN 目标集）

- 记 `target-versions.md` 中解析出的**目标全量版本**为 `Vstd`，当前条目的 `version` 字段为 `Vstr`（可能为 `^` / `~` / 精确 / 预发）。
- **若 `Vstd` 有预发后缀**（如 `-test.`、`-beta.`）：`Vstd` 按 **完整精确串** 写入，预发按 npm semver 比较。  
- **升级条件**（在「`name` 在目标表且未在忽略列表中」的前提下）：  
  - 将 `Vstr` 与 `Vstd` 按 npm 比较，**Vstd 严格大于** 当前基线时升级；**禁止** 为「对齐目标表」而**降级** 已更高的版本。  
  - 若 **Vstd ≤ 当前有效版本**（不允许降级）：**不修改** `version`，changelist 中注明「不高于标准或已满足，已跳过」。
- **比较方式**：以 npm 语义/semver 为准；**不可解析**时勿强行改版本，changelist 说明「不可比或跳过」

### 版本号写法原则（`dependencies.json` 的 `version` 字符串）

- 若**原** `version` 为 `^x.y.z` 或 `~x.y.z`：升级后**保持**相同前缀，写成 `^Vstd` 或 `~Vstd` 的**规范形式**（以目标版本为基准）  
- 若**原**为**精确** `x.y.z`：升级后**精确**写 `Vstd`（预发时整个串精确）  
- 若**目标**为**预发**（含 `-test.`、`-beta.`、`-dev.`、`-alpha.` 等）：**必须** 写**精确** `Vstd`，**勿** 加 `^`。

**物料常见情况**：`version` 为无前缀精确串；则直接改为目标精确串（或 range，若与仓库历史一致且团队约定允许）。

### 步骤 1：依赖范围锁定与数据加载

- 读入**完整** `dependencies.json`（数组）  
- 从 ${{inputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/target-versions.md}} 建 **`name` → `Vstd`** 索引；合并步骤 1 中已声明的 **忽略/排除** 包名，不得纳入升级  
- 对 `@mtfe/msi-mrn` / `@mtfe/msi` 在索引中**强制同版本**（以 `msi-mrn` 所在行为准同步另一项）

### 步骤 2：逐条分类（需改 / 仅 lock 不在此处理 / 已达）

对数组中**每条**以 `name` 键：

- **A（需改）**：`name` 在目标表且**当前声明版本尚未对齐 Vstd**（在「非降级」规则下**应**升到 Vstd）  
- **B（本步不改 dependencies 内的 resolutions 语义）**：仅当工程单独维护 `resolutions` 时属「锁间接依赖」——**不**在 `dependencies.json` 里伪造条目；若你后续有专步改 `package.json` 的 `resolutions`，在 changelist 里可列待办  
- **C（已达）**：已对齐 Vstd 或**策略上保持更高版本**不降级

### 步骤 3：严格匹配与版本/URL 更新

对每条依赖，在目标索引中做 **name 全等** 查询：

- **情况 A：匹配且 `Vstd` 有效，且按上文规则应升级**  
  - 将 `version` 更新为目标写法。  
  - 若该条含 **`url`** 且为常见物料 CDN 形式（如路径中含 `/包名/版本号/` 或 `.../name/version/...`），将 **与旧 `version` 一致的那一段** 替换为 **新 `version` 的对应字符串**；若存在 **scoped 包** 多次编码，按仓库既有 URL 模式替换，避免破坏路径。  
- **情况 A'：`Vstd` 有值但 vstd 不比当前高（不降级）**  
  - **不**改 `version` / `url`，changelist 记原因。  
- **情况 B：目标表无此 `name`**  
  - **不**改，changelist 标「未在新架构表，保留」  
- **情况 C：目标表有 `name` 但 Vstd 为空或步骤 1 已标为不升级**  
  - **不**强改，同 same-npm 第三列为空时的处理

### 步骤 4：版本一致性与交叉核对

- 检查 `dependencies.json` 内 **同名** `name` 是否出现多条；若有，**统一** 到**同一** `Vstd` 策略（或标冲突人工处理）  
- 与 `ohDependencies.json` **对读**：若**同名**包在两处均有，**不**在本步从 dep 强删或强合（除非团队另有专步规则）；**仅**避免本文件内**自相矛盾**

### 步骤 5：落盘与 changelist

- 将修改后的 `dependencies.json` **写回** 工程内原路径（保持 JSON 风格与**合法**格式，键序可按团队约定；**禁止** 删除无关条目的注释若 JSON 不支持注释则略）  
- 更新 ${{outputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/result/changelist.md}}：含 **每个变更 name** 的**旧/新** `version`、**是否改 url**、**是否跳过/未匹配** 及原因

---

*完成本步后，继续本 skill 第 3 步：@trade-duo-standard-material-upgrade-npm-dependencies/steps/03-更新ohDependencies-json.md*
