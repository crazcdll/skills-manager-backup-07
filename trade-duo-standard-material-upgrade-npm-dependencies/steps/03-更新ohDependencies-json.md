---
name: 更新ohDependencies.json
description: 若 oh 非空，逐条用步骤 1 目标清单匹配；有则迁到 dependencies 并删 oh；无则提示用户自找三端版本；最后汇总
---

## 目标

在 **第 2 步** 已写回 **`dependencies.json`** 后，根据 **`ohDependencies.json` 是否仍有数据** 做迁出与提示：

1. 若 **无数据**（空数组或文件不存在/视为空）：记录「`ohDependencies.json` 无需处理」，进入汇总后结束本步。  
2. 若 **有数据**：对 **每一条** 用 **步骤 1** 的 **目标版本清单**（${{inputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/target-versions.md}}）做 **`name` 全等** 查询，分两类处理（见下）。  
3. 处理完 **整个** `ohDependencies.json` 后，**必须** 向用户输出 **修改结果汇总**（见「汇总输出」），并写入 ${{outputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/result/changelist.md}}。

**不再沿用** 旧版「与 same-npm 步骤 2 同构的 semver 在 oh 内升版」**主线**；本步**核心**是：**能进目标表的一律迁入 `dependencies.json` 并从 `oh` 删除**；**进不了目标表的**只**提示**、不替你猜版本。

---

## 实施源材料

- **第 1 步**：`target-versions.md`（`name` → 目标 `Vstd` 的机器可读映射）  
- **待改**：`ohDependencies.json`、`dependencies.json`（迁入端）  
- **结构参考**：@trade-duo-standard-material-upgrade-npm-dependencies/data/ohDependencies.json、同目录 `dependencies.json`

---

## 处理规则

### 名称匹配

- 只接受 **`name` 全等**（与 `target-versions.md` 或解析出的包名行），**禁止** 模糊匹配。

### 情况 A：在目标清单中能找到 `name`（有 `Vstd`）

- **从 `ohDependencies.json` 删除**该条。  
- **在 `dependencies.json` 中落地该依赖**：  
  - 若 **已有** 同名 `name`：**不要** 再「新增」重复条目；将已有条目的 **`version`（及含版本路径的 `url`）** 与 **`Vstd` 对齐**（与第 2 步预发/精确号规则一致），**然后** 再从 oh 删该条。  
  - 若 **尚无** 该 `name`：**新增** 一条，字段与仓库内已有条目 **同构**（通常含 `name`、`version`、`type`、`url`）：
  - `version`：取 **目标清单** 的 **`Vstd`**。  
  - `type`：可沿用本条在 oh 上的 `type`；无则与同类依赖一致（如常见 `util`），不得虚构业务含义。  
  - `url`：若 oh 行上原有 `url`，将路径中的 **旧版本段** 替换为 **`Vstd`** 对应片段；若无法安全替换，按仓库内 **同包名/同 CDN 基路径** 的其它条目拼出 `.../包路径/Vstd/...`；仍无法确定时 **写入摘要与 changelist 标「需人工补 URL」**，禁止编造不存在域名。  
- **联动包**：`@mtfe/msi` 与 `@mtfe/msi-mrn` **同版本**（与步骤 1 / 内建表一致）；从 oh 迁出时若两条都在，**成对**处理。

### 情况 B：在目标清单中 **没有** 对应 `name`

- **不要** 自动在 `dependencies.json` 里**编造**三端版本、**不要** 为「清 oh」而随意删除。  
- **保留** 该条在 **`ohDependencies.json`**（不删除）。  
- 在对话与 **汇总** 中**明确提示用户**需 **自助排查**：为该依赖查找 **适配上 Android / iOS / 鸿蒙** 的目标版本，并与 **2738858921 文档 / 团队规范** 对齐后再手动迁移或补全目标表后重跑。  
- 可生成「**待处理列表**」块列出：`name`、当前 `version`、说明「未出现在步骤 1 目标清单」。

---

## 操作顺序（SOP）

1. 读取 `ohDependencies.json`；若数组**为空**，跳至「汇总输出」并写 changelist 一笔。  
2. 从 `target-versions.md` 建立 **`name` → `Vstd`** 索引。  
3. 遍历 oh 中**每一**条，按上节 **A / B** 执行写库。  
4. 写回合法 JSON 到工程内**约定路径**的 `ohDependencies.json` 与 `dependencies.json`。  
5. 执行 **汇总输出**；更新 ${{outputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/result/changelist.md}}。

---

## 汇总输出（本步结束必须给出）

在对话与/或 `changelist` 中至少包含 **三类一块**（无则写「无」）：

| 类别 | 内容 |
|------|------|
| **已迁入** | 包名、从 oh 删除、`Vstd`、在 dep 为「新增」或「仅更新/仅删重」的说明 |
| **需用户自助** | 包名、当前 `version`、原因（**目标清单中无此包**）与建议动作（自找三端版本与文档后处理） |
| **未动** | 若因异常跳过某条，说明原因 |

**一句话结论**：本步对 `ohDependencies.json` 处理完毕；剩余 oh 中条目均为 **B 类（清单无包名）** 待用户自助，或**空**。

---

## 工作边界

- **不** 修改 `componentsMap.json`。  
- **不** 在 **情况 B** 中自动从 oh 删条（避免丢失「仅知鸿蒙侧」的尚未对齐信息，除非用户另有约定）。  
- 与第 2 步、第 1 步冲突时，以 **目标表 `Vstd`** 与 **非降级** 原则与第 2 步**对齐**；若 `dependencies` 中已有更高版本，**不降级** 为 `Vstd`，在汇总与 changelist 说明。

---

*完成本步后，继续第 4 步：@trade-duo-standard-material-upgrade-npm-dependencies/steps/04-清单依赖检查.md*
