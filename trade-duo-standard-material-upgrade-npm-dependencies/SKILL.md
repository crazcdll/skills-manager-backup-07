---
name: trade-duo-standard-material-upgrade-npm-dependencies
description: 交易 DUO 物料仓库 NPM 新架构目标依赖升级：dependencies.json、ohDependencies.json；学城 2738858921（Citadel，禁止 web_fetch），兜底见本 skill data/fallback-target-versions.md；第 4 步检查清单中是否仍有 @gfe/babel-plugin-react-add-name。
---

# 交易 DUO 物料仓库 NPM 依赖（新架构）升级

## 工作流

面向 **物料仓库**：将 **`dependencies.json`**、**`ohDependencies.json`** 按 **学城** [新架构组件/API依赖文档](https://km.sankuai.com/collabpage/2738858921)（`contentId` **2738858921**）目标版本对齐。**不改 `componentsMap.json`**；`data/` 下 JSON 仅作结构示例。

- **第 1 步** 用 **`oa-skills citadel getMarkdown --contentId 2738858921`** 拉正文；**失败** 时用 **`data/fallback-target-versions.md`**，并在 changelist 写明。  
- **第 2 步** 骨架可对照 **@trade-duo-standard-same-npm-dependencies/steps/03-更新dependencies-json.md**（**版本来源** 为本 skill 第 1 步的 `target-versions.md`）。  
- **第 3 步** **oh 有则按目标表迁入 dep/删 oh**；目标表**无**该 `name` 则提示用户**自助**定三端版本；**不** 与 same-npm 步骤 2 同构。  
- **不跑** same-npm 的 `componentsMap` 与 **double check** 专步。  
- **第 4 步** 检查 **两份清单**中是否仍有 **`@gfe/babel-plugin-react-add-name`**。  
- **第 5 步** 收尾与**最终汇报**须含第 4 步结论；不提前在仅完成第 3 步时宣称全流程结束。

## 使用提示

- **调用本 skill 前，用户必须提供 MIS 号。** 该 MIS 用于学城鉴权与拉取 2738858921。
- **若启动本 skill 时未提供 MIS 号：必须立即暂停流程**，不要继续第 1 步；直接提示用户：`请先提供 MIS 号，收到后再继续拉取学城文档。`

## 前置

第 1 步**必须** 使用 Citadel + 用户提供的 MIS 拉取学城正文；失败时才用 **`data/fallback-target-versions.md`**。可将降级说明写入 `.temp/trade-duo-standard-material-upgrade-npm-dependencies/result/changelist.md`（若可写），**不伪造**学城数据。

## 待改文件

| 文件 | 说明 |
|------|------|
| `dependencies.json` | 通用/三端侧 |
| `ohDependencies.json` | 仅鸿蒙保留项 |

## 能力边界

- **本 skill**：清单 JSON 升级、第 4 步清单依赖扫描、**第 5 步** 提示。  
- **不** 改 `yarn.lock`、不 `yarn install`、不维护 `resolutions`、不查 `yarn` 残锁。  
- **不** 检查 `package.json`、babel 配置或源码环境变量。  
- 根工程**还要**对锁与 Node 做完整工程化升级，由**团队其它流程/文档**处理，**不在**本步骤内展开。  
- `componentsMap` 见 **@trade-duo-standard-same-npm-dependencies/steps/04-更新componentsMap-json.md** 或第 5 步。

## 执行

**第 1～5 步** 顺序；**一次跑完** 至第 5 步。

| # | 内容 | Step 文件 |
|---|------|-----------|
| 1 | Citadel 目标表 / 降级 | `steps/01-通过citadel获取新架构目标版本清单.md` |
| 2 | 写 `dependencies.json` | `steps/02-更新dependencies-json.md` |
| 3 | oh 迁出 / 自助 | `steps/03-更新ohDependencies-json.md` |
| 4 | 清单依赖检查 | `steps/04-清单依赖检查.md` |
| 5 | 提示与汇报 | `steps/05-提示.md` |

## 执行规则

- 版本以 **学城 2738858921** 为首选，**内建表** 仅兜底。  
- 与 same-npm：仅第 2 步**骨架**可对齐其 step 3；**第 3 步** 为本 skill 专有多迁出逻辑。  
- **最终输出**（第 5 步对用户的结项汇报）**必须使用 Markdown 表格**，不要改成普通列表或散文。  
- 遇错**停**并报，**不**编假版本。
