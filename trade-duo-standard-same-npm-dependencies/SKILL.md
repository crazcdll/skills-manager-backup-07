---
name: trade-duo-standard-same-npm-dependencies
description: 交易 DUO 框架标准化 npm 依赖三端一致性改造（iOS/安卓/鸿蒙）。1、npm 标准版本以 k-hub 酒旅 npm 三端一致性改造知识库为准；**不**通过 Citadel/浏览器等读取学城页面。2、将三端兼容依赖写入 dependencies.json，仅鸿蒙兼容的保留在 ohDependencies.json。步骤 2～4 更新 npm 时仅当知识库标准版本（semver）严格大于当前版本才写入。3、componentsMap 同步与降级阻断见步骤 4。4、步骤 01 **必须**配置 k-hub；未配置则输出配置方法并**终止全流程**，配好后重新发起。
---

# 交易 DUO 框架标准化 npm 依赖三端一致性改造（iOS/安卓/鸿蒙）

## 📋 工作流描述

1、**标准版本**以 **k-hub 知识库**（酒旅 npm 三端一致性改造相关文档）为唯一依据。**本流程不**使用 Citadel、内网浏览器自动化或其它方式拉取 [学城 KM](https://km.sankuai.com/collabpage/2747476284) 页面内容作为版本来源；若需与学城人工核对，由用户在流程外自行打开。2、将三端兼容依赖写入 **`dependencies.json`**，仅鸿蒙侧保留的写入 **`ohDependencies.json`**（上述两份 JSON 为本流程要修改的主清单）。**步骤 2～4 中凡涉及将清单或 `componentsMap` 中的 npm 版本改为「知识库/步骤 1 对照表中的标准化版本」时，仅当该标准化版本按 semver 严格大于当前条目已有版本时才执行更新**；若标准版本小于或等于当前版本，则保持当前版本不变并在变更说明中注明跳过原因。3、若工程存在 **`componentsMap.json`**，且其中物料对应的 npm 包在步骤 2/3 中发生了版本变化，则在步骤 4 中**再次校验**清单目标版本相对当前 `npmVersion` 是否为**升级**后再同步 **`npmVersion`** 及含版本号的资源 URL；若判定为**降级风险**，须向用户**重点提示**并**阻断 commit**（见步骤 4 中 `block-commit.flag` 与 changelist 约定）。4、减少分端差异，避免 Android/iOS 依赖版本过低导致底层走非标桥。

### 标准版本来源与待修改文件

- **k-hub 知识库（权威主线）**：通过 **k-hub MCP** 查询《标准化公共依赖版本-整合版》及各业务《【境外】/【交通】/【住宿】/【景点】/【交易】/【民宿】标准化依赖》等文档。多文档版本冲突时：**该工程所属业务的文档 > 公共依赖文档 > 其他业务文档**。
- **项目侧原材料（梳理用，与步骤 01 一致）**：工程的 **`package.json`**、**`oh-package.json`**；与 **k-hub** 查询结果交叉核对。
- **本流程要修改的目标文件**：工程中的 **`dependencies.json`** 与 **`ohDependencies.json`**（数组结构，每项一般含 `name`、`version`、`type`、`url` 等字段，以仓库中实际文件为准）。
- **Skill 内 `trade-duo-standard-same-npm-dependencies/data/`**：提供 JSON **结构示例**（`dependencies.json`、`ohDependencies.json`、`componentsMap.json`），便于对齐字段含义；**不以 `data/` 下快照为版本权威**。

第 1 步通过 **k-hub** 查询知识库，并结合 **`package.json` / `oh-package.json`** 与上述两份待修改清单，生成 `.temp/trade-duo-standard-same-npm-dependencies/file/` 下的对照表，供后续步骤使用。

### 前置条件：k-hub MCP（强制）

步骤 01 **必须**通过 **k-hub**（知识库 MCP）查询酒旅 npm 三端一致性改造相关文档；**执行前须在本机 Cursor 中配置并连通该 MCP Server**。未配置、不可用或鉴权失败时：**不得**继续步骤 2～6；须按下文向用户给出配置说明并**终止当前流程**，待用户配置完成后**重新发起**本 skill 全流程。

在 Cursor 的 MCP 配置（用户级或项目级，以你环境为准，常见为 **Settings → MCP** 或 **`~/.cursor/mcp.json`** / **`.cursor/mcp.json`**）的 `mcpServers` 中增加 **`k-hub`** 项，例如：

```json
{
  "mcpServers": {
    "k-hub": {
      "url": "https://block.sankuai.com/mcp/api/knowledge-hub-mcp?kbInfo=435@0.0.0&useRag=true&userToken=d60f7b23-d52e-4cba-9262-d74ad6e2ea2d"
    }
  }
}
```

保存后**重载 MCP 或重启 Cursor**，确认 `k-hub` 已连接成功。

**说明**：`userToken` 若与个人账号绑定，请替换为你本人有效 token；团队内请勿将他人 token 写入公共仓库。若官方更新接入方式，以内部文档为准，上述 `url` 可与管理员核对。

**执行方（Agent）在未检测到 k-hub 或调用失败时**：不得伪造知识库查询结果；须向用户**原样给出**本节 JSON 配置说明（含 `mcpServers` 与 `k-hub` 的 `url`），并提示在 Cursor MCP 中添加上述项、保存并重载后**重新发起本流程**；在 `${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}`（若可写）或对话中注明 **「k-hub MCP 未就绪，trade-duo-standard-same-npm-dependencies 已终止，未执行步骤 2～6」**；**立即结束本 skill，不继续后续步骤**。

## 🚀 流程自动执行指南

在 **k-hub 已就绪** 的前提下，总共需要执行 **6** 个步骤，请一次性无中断地完成全部节点；每个节点开始前需要查看对应的 step 文档（标注了 @stepName），然后立即执行该节点并继续下一步，直到所有节点完成。

执行过程中不得停下来等待用户确认或输入，除非节点文档明确要求澄清信息。

**例外**：若步骤 01 在开头判定 k-hub 不可用，**终止全流程**，不执行步骤 2～6。

### ⚙️ 执行要点

1. 查看对应的 step 文档获取详细指令
2. 根据 step 文档中的指令完整执行任务
3. 输出所需的产物文件
4. 确认完成后继续下一步

### 📝 步骤清单

#### 第 1 步: 梳理 dependencies.json 与 ohDependencies.json 中依赖的基本情况

- **描述**: 确认各个依赖 npm 的包名、作用信息、版本号、各端依赖情况、配置位置
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/01-梳理dependencies-json与ohDependencies-json中依赖的基本情况.md
- **后续步骤**: 执行第 2 步 (更新 ohDependencies.json)

#### 第 2 步: 更新 ohDependencies.json

- **描述**: 遍历 `ohDependencies.json` 中的条目，将三端兼容的依赖迁出，将仅兼容鸿蒙的依赖对齐标准版本；**写入标准版本时仅当标准版本（semver）严格大于当前版本才更新**（迁出时若标准不高于当前则保留当前版本写入 `dependencies.json`）。
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/02-更新ohDependencies-json.md
- **后续步骤**: 执行第 3 步 (更新 dependencies.json)

#### 第 3 步: 更新 dependencies.json

- **描述**: `dependencies.json` 中应对齐知识库标准版本；**仅当标准版本（semver）严格大于当前 `version` 时才改写**。
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/03-更新dependencies-json.md
- **后续步骤**: 执行第 4 步 (更新 componentsMap.json)

#### 第 4 步: 更新 componentsMap.json

- **描述**: 若工程存在 `componentsMap.json`，仅针对步骤 2/3 已变更的 npm：**再次校验**相对 `npmVersion` 为升级而非降级后再同步；若检出降级风险则**重点提示用户核查且本流程不生成 commit**。
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/04-更新componentsMap-json.md
- **后续步骤**: 执行第 5 步 (double check 与重复依赖检测)

#### 第 5 步: double check 与重复依赖检测

- **描述**: 检查 `dependencies.json` 与 `ohDependencies.json` 的改动是否一致、完整。
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/05-double-check与重复依赖检测.md
- **后续步骤**: 执行第 6 步 (提示)

#### 第 6 步: 提示

- **描述**: 提示用户需要重点关注的内容
- **Step**: @trade-duo-standard-same-npm-dependencies/steps/06-提示.md
- **后续步骤**: 流程完成

## ⚠️ 执行规则

**顺序执行**: 必须按照步骤顺序从 1 到 6 依次执行每一步

**查看 Step**: 每一步开始前都要查看对应的 step 文档（使用 @ 引用）

**执行指令**: 根据 step 文档中的内容完整执行任务

**一次跑完**: 从第一步开始自动连续执行到最后一步，中途不得停顿或等待额外指示

**条件分支处理**: 对于带有条件判断的节点，根据条件判断结果选择对应的分支执行

**循环处理**: 对于循环节点，需要在进入条件满足时反复执行循环体，直到满足退出条件

**错误处理**: 如果某一步执行失败，停止流程并报告错误信息

**k-hub MCP**：步骤 01 调用 k-hub 前须确认已配置（见上文「前置条件：k-hub MCP」）。若当前环境无 k-hub 工具、调用失败或鉴权失败，按该节向用户输出配置说明，不得编造知识库内容，**并终止全流程**；**不得**改用 Citadel/浏览器读取学城或其它方式替代 k-hub 继续执行 trade-duo-standard-same-npm-dependencies。
