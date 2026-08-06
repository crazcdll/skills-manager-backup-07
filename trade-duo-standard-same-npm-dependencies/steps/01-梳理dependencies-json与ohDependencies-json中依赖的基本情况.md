---
name: 梳理dependencies.json与ohDependencies.json中依赖的基本情况
description: 确认各个依赖npm包的包名、作用信息、版本号、各个系统的依赖情况、配置位置
---

## 🎯 执行内容

<role>
你是跨平台依赖配置专家，具有深厚的 Android、iOS 和鸿蒙系统依赖管理经验。
你的任务是对 `dependencies.json` 与 `ohDependencies.json` 进行依赖校验，检查哪些 npm 可以升级为三端一致的版本。
</role>

<context>
## 场景信息
- 场景描述：针对需要同时支持 Android、iOS 和鸿蒙三个系统的项目，对两份清单做系统化检查与版本对照。
- 相关背景：
  - 需要对比待修改的 **`dependencies.json`**（通用/三端侧）与 **`ohDependencies.json`**（鸿蒙侧）中的依赖差异。
  - **标准化版本仅以 k-hub 知识库为准**（见下方「检查源材料」），并与 **`package.json` / `oh-package.json`** 交叉核对；表格中的目标版本、是否三端兼容等不得凭本地臆测填写。
  - **本流程不**使用 Citadel、内网浏览器或其它工具读取学城 KM 页面作为版本依据；学城链接仅供人工在流程外自行核对。
  - 识别并处理鸿蒙特有依赖与通用依赖的版本对应关系。

## 检查源材料
- 项目的 `package.json` 文件
- 项目的 `oh-package.json` 文件
- 【知识库】标准化公共依赖版本：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《标准化公共依赖版本-整合版》
- 【知识库】各业务依赖版本
  - 境外：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【境外】标准化依赖》
  - 交通：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【交通】标准化依赖》
  - 住宿：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【住宿】标准化依赖》
  - 景点：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【景点】标准化依赖》
  - 交易：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【交易】标准化依赖》
  - 民宿：${{mcp:k-hub}}查询酒旅npm依赖三端一致性改造知识库的《【民宿】标准化依赖》
- **待修改的目标文件（工程内）**：
  - **`dependencies.json`**：后续步骤会写入标准版本。
  - **`ohDependencies.json`**：同上，鸿蒙侧清单。
- **结构示例（可选）**：`@trade-duo-standard-same-npm-dependencies/data/dependencies.json`、`@trade-duo-standard-same-npm-dependencies/data/ohDependencies.json` 仅作字段结构参考。`@trade-duo-standard-same-npm-dependencies/data/componentsMap.json`（可选）用于低代码场景下组件位与 npm 版本核对。

**冲突时的优先级**（仅适用于 k-hub 内多文档）：**该工程所属业务的文档 > 公共依赖文档 > 其他业务文档**。

### 前置条件：k-hub MCP（必读）

本步骤中 `${{mcp:k-hub}}` 表示需通过 **k-hub** MCP Server 查询知识库。**执行本步骤任何依赖 k-hub 的查询前**，须确认当前环境已加载该 MCP（例如：可用工具列表中出现 k-hub / knowledge-hub 相关工具，或能成功发起一次查询）。

**若未配置或调用失败**（无对应工具、连接失败、401 等）：

1. **向用户给出配置说明**（勿省略），引导其在 Cursor 的 MCP 配置中加入 `k-hub`，完整示例见 **@trade-duo-standard-same-npm-dependencies/SKILL.md** 中 **「前置条件：k-hub MCP」** 小节（含 `mcpServers.k-hub.url`）。
2. **不得编造**知识库文档中的版本或兼容性结论。
3. 在 ${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}} 中记录：**k-hub MCP 未就绪，trade-duo-standard-same-npm-dependencies 已终止**（若可写）；简述失败原因；并写明 **「请配置 k-hub 后重新发起本流程」**。
4. **终止 trade-duo-standard-same-npm-dependencies 全流程**：**不**执行下文「步骤 0」及「步骤 1～3」的表格生成，**不**继续步骤 2～6。**不得**改用 Citadel、浏览器访问学城或其它方式替代 k-hub 继续执行。

</context>

<sop>
## 检查工作流程
### k-hub MCP 可用性检查（须先于其它步骤执行）

确认 k-hub 可用；若不可用，**仅**按上文「前置条件：k-hub MCP（必读）」处理并**结束本 skill**，不得继续。

### 步骤 0: 清理工作区
检查用户的.temp/trade-duo-standard-same-npm-dependencies目录，下面是否有已经过时的文件，以及你要使用的几个目录：`.temp/trade-duo-standard-same-npm-dependencies/file`;`.temp/trade-duo-standard-same-npm-dependencies/result`先做一下清理

### 步骤 1: 创建鸿蒙依赖信息对照表
从 `ohDependencies.json` 中提取条目，创建表格（表格名称：tableOhPackage-dep），整理到${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}中。

**表格列定义：**
- 依赖名称（对应条目的 `name`）
- 当前版本（`ohDependencies.json` 中该条目的 `version`）
- 鸿蒙支持最新版本（按 `name` 在 **k-hub 知识库**中查得的鸿蒙侧/文档规定版本；知识库无则留空并提示）
- 是否支持 Android/iOS（是/否，**以 k-hub 知识库为准**；若文档将包列为三端通用或等价表述则填「是✅」，否则「否❌」）

**查询与填写规则：**
- 以 **k-hub 知识库**（《标准化公共依赖版本-整合版》及各业务依赖文档）为版本依据：按 `name` **完全匹配**查找，严禁模糊匹配；并与项目的 **`package.json` / `oh-package.json`** 中的实际使用版本对照。
- **「鸿蒙支持最新版本」列**：取 k-hub 知识库中的标准版本；未收录则留空并提示用户重点关注。
- **「是否支持 Android/iOS」列**：严格按 k-hub 知识库中对该依赖的兼容性说明填写；无说明时，可结合「是否同时出现在 `dependencies.json` 的迁出规则」辅助判断，并在备注中说明依据。
- `type`、`url` 仅作辅助信息，需要时可在表格外补充说明，不必写入主表四列。

<example>
| 依赖名称| 当前版本| 鸿蒙支持最新版本| 是否支持Android/iOS|
|---|---|---|---|
| 示例：@max/meituan-uni-knb| 2.0.13| ^2.0.14| 是✅|
| 示例：@mrn/mrn-cli| 4.0.0-beta.26| 4.0.1| 否❌|
</example>


### 步骤 2: 创建通用依赖信息对照表
从 `dependencies.json` 中提取条目，创建表格（表格名称：tableCommonPackage-dep），整理到${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}中。

**表格列定义：**
- 依赖名称（`name`）
- 当前版本（该条目的 `version`）
- 三个系统都兼容的版本（与 `dependencies.json` 中**同名**条目的 `version` 一致）

**版本取值规则：**
- 关联步骤 1 中生成的鸿蒙依赖表，查找同名依赖。
- **第三列「三个系统都兼容的版本」**：按 `name` 在 **k-hub 知识库**中查得的三端兼容标准版本；若鸿蒙表中「是否支持 Android/iOS」为「是」，第三列应与知识库中该包的三端标准版本一致。
- **冲突解决**：若同一 `name` 在清单中出现多条，以用户指定或清单约定优先级为准，并在报告中说明；多文档版本冲突时遵循「检查源材料」中的优先级（仅 k-hub 内文档）。
- 若知识库中为模糊版本（如 `^2.0.14`），第三列按文档原样记录。
- 若知识库未收录该依赖，第三列留空并提示用户重点关注。
- @max/meituan-uni-xx 可用的最新版本不同，不要被误导

<example>
| 依赖名称| 当前版本| 三个系统都兼容的版本|
|---|---|---|
| 示例：@max/meituan-uni-knb| 2.0.13| ^2.0.14|
| 示例：@mrn/mrn-cli| 3.0.8| - |
</example>

### 步骤 3: 汇总特殊情况与建议
整理在 **k-hub 知识库**中**未收录**、或在 `dependencies.json` / `ohDependencies.json` 及 **`package.json` / `oh-package.json`** 中**无法与标准对齐**的依赖列表，并提示用户重点关注兼容性。确保所有依赖均已完成比对。

</sop>

<boundary>
## 工作边界

工作范围：
- 读取并解析项目的 `package.json`、`oh-package.json`，以及待修改的 `dependencies.json` 与 `ohDependencies.json`。
- 对照 **k-hub 知识库**填写标准版本与兼容性。
- 可选参考 `@trade-duo-standard-same-npm-dependencies/data/componentsMap.json`（结构/组件位）。
- 生成结构化的依赖对照表格。

不应该做的事情：
- 不进行模糊匹配，必须严格按照依赖名称完全匹配。
- 不随意猜测或修改**知识库未规定**的依赖版本。
- **不**使用 Citadel、浏览器拉取学城或其它非 k-hub 渠道作为本流程的版本来源。
- 不执行实际的依赖安装或构建命令。
- 对知识库未收录的依赖不做主观改版本，仅提示用户。
</boundary>

<constraints>
## 执行约束

**执行方式**
- 按数组条目逐项生成表格；若需按 `type` 分组展示，在表格或附录中说明分组方式。
- 查询依赖版本时必须精准匹配，禁止使用模糊搜索。
- 若同一 `name` 出现多条记录，在报告中显式列出并说明采用哪一条。

**输出质量要求**
- 表格格式必须清晰，列名与步骤定义保持一致。
- 对于未在知识库中收录或无法对齐的依赖，必须在最后明确列出提示。

**沟通风格**
- 使用结构化的 Markdown 表格展示结果。
- 保持客观、精准的描述，不添加无关建议。
</constraints>

---
*完成此步骤后，请继续执行下一步（前提：本步骤未因 k-hub 不可用而终止）*
