---
name: duo-feature-development-workflow
description: 当需要在酒店提单页或类似 DUO/MRN 合并仓中完整推进业务需求开发时使用，尤其是涉及 PRD/技术方案/UI/AppMock 读取、协议和物料改造、进度文档、Token 统计、验证与提交的场景。
---

# DUO 需求开发工作流

## 概览

这个 Skill 用来把一个 DUO/MRN 业务需求从资料输入推进到实现交付。它沉淀自酒店提单页“会员免费定向升房”需求：先读需求和资料，再做开发方案，然后修改 `protocol` 与 `material`，最后完成验证、进度记录和提交。

这是流程型 Skill，不是某个具体业务的接口说明。使用时始终以个人全局指令、当前仓库的 `AGENTS.md`、目录级 `AGENTS.md`、最新 PRD、前端技术方案、UI 稿、AppMock 数据和现有代码为准。

## 适用场景

当用户提出以下需求时使用：

- 端到端开发 DUO/MRN 页面功能或修复 Bug；
- 开发前需要读取 PRD、学城文档、Ingee UI 稿、AppMock 数据；
- 需要修改 DUO 协议、Groovy 数据源、生命周期逻辑或 ProCode 物料；
- 需要持续维护进度文档、AI 工具记录、Token 用量或语音输入记录；
- 需要把一次需求开发过程抽象成可复用的标准流程。

不适用于纯命令问答、单纯代码审查、无关后端开发，或非 DUO 前端应用；除非用户明确要求复用这套流程。

## 开始前必须做

1. 读取个人全局指令和当前仓库根 `AGENTS.md`，确认个人信息、仓库规则和长期知识。个人 MIS 等身份信息只从全局指令或环境变量读取，不写入仓库级文档。
2. 根据改动目录读取目录级 `AGENTS.md`；如果仓库把某个需求的文档收敛到 `docs/<需求目录>`，优先读取该目录下的 `AGENTS.md`。改 `protocol/` 前遵循协议规则，改 `material/` 前读 `material/AGENTS.md`，调试 `duo-builder/` 前读 `duo-builder/AGENTS.md`。
3. 确认 turn-log hooks 会记录每轮原始输入；语音归档文档放在当前需求目录的 `voice-prompt/*.md`，每天收工或关键节点批量补齐，不为每句话单独生成提交。
4. 执行 `git status --short`，识别已有改动，不能回滚用户或他人改动。
5. 如果用户点名某个 Skill，或任务明显匹配某个 Skill，先读取对应 Skill。
6. 判断本轮是代码开发、文档更新、资料调研、方案调整，还是验证收尾。

## 仓库心智模型

| 区域 | 作用 | 处理原则 |
|---|---|---|
| `protocol` | DUO 协议源文件，包含页面结构、节点 props、展示规则、接口入参、生命周期逻辑 | 涉及节点展示、接口参数、Groovy 逻辑时优先修改 |
| `material/packages` | ProCode 物料源码 | 涉及 UI、交互、组件状态、props/events 时优先修改 |
| `duo-builder` | 本地调试和出码入口 | 查找并运行本地调试命令 |
| `src` | 出码结果 | 只用于排查，不把它当源码修改 |
| `docs/<需求目录>/superpowers` | Superpowers 计划、规格和流程复盘 | 与工作流本身强相关的产物放这里 |
| `docs/<需求目录>/progress` | 需求进度、工具、Token、费用、对话日志 | 功能、Bug、联调、测试或需求变更后同步更新 |
| `docs/<需求目录>/agent-reference.md` | 长项目事实、链接、当前需求细节和低频参考 | 按需读取，不放进根 `AGENTS.md` |
| `docs/<需求目录>/voice-prompt` | 用户语音输入归档 | 每天收工或关键节点批量更新，确保不遗漏 |

Node 版本约定：

- 项目开发、运行、调试使用 Node 16。
- Skills、学城、Ingee、内部工具优先使用 Node 24，除非工具自身另有要求。
- 本机有 NVM 时直接切换版本。

## 工具索引

需要具体工具用途、命令口径或失败兜底路线时，读取 [references/tool-map.md](references/tool-map.md)。

核心工具：

| 工具 / Skill | 用途 |
|---|---|
| `citadel` / `oa-skills citadel` | 读取学城 PRD、前端技术方案和引用文档 |
| `explore-design-tree-ingee` | 下载 Ingee 局部画板、预览图和语义 JSON |
| `ingee-flex` / `duo ingee-fetch` | 获取更细的 Ingee DSL、裁切图或尺寸信息 |
| `appmock-all` | 理解和读取 AppMock 配置、接口数据 |
| CatDesk 浏览器路线 | ciba/SSO 直连失败时读取 AppMock 原始 JSON |
| `duo-protocol` | 理解和修改 DUO 协议 |
| Superpowers `writing-plans` | 大改动前产出开发方案 |
| Superpowers `verification-before-completion` | 完成前做验证确认 |
| Superpowers `writing-skills` | 创建或修改 Skill 时校准触发条件和结构 |
| 前端代码审查 Skill | 大范围改动后进行代码审查，可在 `trade-code-reviewer`、`hotel-frontend-code-review`、Superpowers reviewer、拼写检查之间选择 |
| Codex hooks / turn-log | 每轮只记录原始 JSONL；每天收工生成摘要版和完整版 Markdown 总结 |
| CodexBar / Codex sqlite | 记录 Token、费用、缓存 token 和缓存命中率快照 |
| `trade-commit-message` | 基于暂存区 diff 生成中文 Conventional Commit 并提交 |
| `git` | 用中文提交说明提交代码和文档 |

## 工作流

### 1. 输入记录与可追溯性

1. 依赖 turn-log hooks 先记录每轮原始 prompt；每天收工或关键节点再把用户输入归档到当前需求目录的 `voice-prompt/prd.md`、`voice-prompt/bug.md` 或 `voice-prompt/else.md`。
2. 只把长期稳定且团队共享的项目知识或协作规则写入仓库 `AGENTS.md`；个人 MIS、个人偏好放到个人全局指令或环境变量。
3. 大体积下载物和临时产物放到忽略目录，例如 `.temp`。
4. 在当前需求目录的 `progress` 下创建或更新需求进度、工具、Token 和对话日志文档；中间轮次只保留原始日志，阅读版总结和人工维护文档在每天收工统一生成。
5. 用户要求统计 Token 时，在阶段结束或每天收工前更新 Token 用量文档。

### 2. 收集需求资料

优先读一手资料，不靠记忆：

1. PRD：用 `citadel` 或 `oa-skills citadel` 读取学城文档。
2. 前端技术方案：每次用户说有更新时都重新读取最新版。
3. UI：拉取用户给的 Ingee 图层，区分最终稿、参考稿和过期稿。
4. AppMock：拉取相关 mock，重点看 `bizReq`、`bizRes` 和 DUO 转换后的 `data`。
5. 现有代码：用 `rg` 搜索并阅读附近实现后再决定落点。

资料可能变化时，必须重新读取，不要沿用旧总结。

### 3. 编写或更新开发方案

较大的需求需要在当前需求目录的 `superpowers/plans` 下维护方案。方案至少映射：

- 业务修改点；
- 需要修改的协议文件和大概节点 / 数据源位置；
- 需要修改的物料包和组件文件；
- 请求和响应字段；
- UI 状态、交互和异常态；
- 验证方式；
- 未决问题和 mock 缺口。

用户更新接口结构、UI 规则或交互逻辑后，要同步更新方案。

如果需要补充设计取舍或 Superpowers brainstorming 产物，放到当前需求目录的 `superpowers/specs`。普通需求进度不要放到 `superpowers`。

### 4. 实现策略

按现有架构推进：

1. 先改协议：新增 props、展示规则、接口入参或生命周期逻辑。
2. 再改物料类型定义。
3. 再实现物料 UI 和交互。
4. 如果新增物料 props/events，同步更新 `description.json`。
5. 只有排查出码结果时才查看 `src`，不要直接改 `src`。

DUO / Groovy 注意事项：

- 使用 `a?.b?.c` 这类逐级安全访问。
- 避免 DUO 表达式中不稳定的 Groovy 写法。
- `PAYLOAD` 只用于本次 update/submit 的临时入参；submit 应尽量从稳定 node/data-source 状态组装。
- 明确区分 preview、update、submit 的入参差异。

物料注意事项：

- 遵循当前包的导入、样式和组件组织方式。
- 同时考虑 Web、MRN、小程序等端差异。
- 后端下发的颜色、图片、文案不要写死。
- 新增 props 时同步 TypeScript 类型和低代码描述。
- 优先复用现有弹层、气泡、Toast、checkbox、置灰样式等能力。

进入执行前要把“是否适合拆 subagents/并行 Agent”当作检查点，而不是强制拆分。默认主会话 checklist 推进；只有任务边界清晰、上下文耦合低、并行收益明显，并且用户明确授权时才拆分。耦合高、需求仍在变化或共享核心上下文较多时，说明原因后继续主会话执行。

### 5. 验证

至少执行：

1. `git diff --check`。
2. 解析改动过的 JSON，例如 `description.json`。
3. 如果项目支持，对改动 TS/TSX 文件跑定向 lint 或类型检查。
4. 只把生成后的 `src` 当排查辅助。
5. 能启动本地环境时，用 Node 16 跑 `duo-builder` 下的调试命令。
6. 如果 MRN 必须依赖真机或 DUO 平台，最终说明哪些内容还没端上验证，需要用户协助。

只有静态检查时，不要声称已经完整端上测试。

### 6. 进度、工具和 Token 记录

发生实质进展后：

- 关键提交、阶段结束或每天收工时更新需求进度文档，写清阶段、commit、变更范围和验证结果；普通中间轮次不单独提交进度文档。
- 引入新的 Skill、MCP、插件、Agent 或工具类型时，记录到 AI 工具文档；可在当天收工时批量补齐。
- Codex hooks 产出的 JSONL turn-log 用于记录每轮耗时；后续阶段耗时统计优先使用 turn-log 字段，而不是人工估算。`targeted-room-upgrade-turn-log.md` 摘要版和 `targeted-room-upgrade-turn-log-full.md` 完整版只在收工时通过 `python .codex/hooks/turn_time_logger.py DailySummary` 生成。
- 更新 Token 文档：
  - 关键提交或 Bug 修复后补阶段快照；
  - 每天收工前补当天汇总；
  - 主线程用 Codex state 的累计差值；
  - 记录 cache input token 和缓存命中率；
  - CodexBar 当日成本作为本机全量估算费用。
- 收工总结要全面、可核验，覆盖当天做过的功能、Bug、联调、测试、提交、截图、工具、Token、风险和下一步；中间记录保持轻量。

### 6.5 代码审查

完成主要功能、准备交给用户或同事看之前，优先做一次代码审查。可选工具：

- `trade-code-reviewer`：交易前端、DUO、MRN/MAX、Groovy 协议和物料综合审查，优先推荐。
- `hotel-frontend-code-review`：酒店前端本地 Git diff 审查，适合 PR 前自查报告。
- Superpowers `requesting-code-review`：用户授权时可用独立 reviewer 视角审查。
- `branch-spell-check`：拼写、大小写和术语检查，作为辅助检查。

审查结论要记录到进度文档；如果发现问题，进入 Bug 修复记录和验证闭环。

### 7. 提交纪律

提交前：

1. 查看 `git status --short`。
2. 只暂存与当前任务相关的文件。
3. 不暂存无关用户改动。
4. 用户已授权时，可以自动 `git add` 本轮自己修改的相关文件。
5. 暂存后优先使用 `trade-commit-message` Skill：只基于 `git diff --cached` 生成中文 Conventional Commit message 并执行提交。
6. commit message 不能只写 subject；正文必须包含 `变更文件：` 和 `变更内容：`，分别说明文件清单和核心改动点。
7. 用户已授权源码和非源码变更在完成验证后都可直接提交，但提交前仍要检查 diff，只暂存本轮相关文件。
8. 修改历史 commit message 属于重写历史；必须先确认范围、push 状态和风险，再选择安全方式处理；重写后的每个提交也要补齐 `变更文件：` 和 `变更内容：`。

建议提交分组：

- 知识沉淀 / 文档记录单独提交；
- 源码功能实现单独提交；
- 进度、Token、工具记录这类收尾文档可单独提交。

## AppMock 模式

AppMock 直连失败时：

1. 先参考 `appmock-all` Skill。
2. 读取 mock 配置优先用：
   `https://appmock.sankuai.com/appmockapi/mock/getMockConfigByMockId?mockId=<id>`
3. 如果 SSO、ciba、npm、MOA 失败，改用已登录浏览器会话读取。
4. 提取 `data.response`，它通常是业务响应 JSON 字符串。
5. 大型原始结果保存到忽略目录 `.temp`，不要直接提交。
6. 区分三段数据：
   - `bizReq`：DUO 组装的后端请求；
   - `bizRes`：后端响应结构；
   - `data`：DUO 转换后的页面 / 组件数据。

## Ingee 模式

处理 UI 链接时：

1. 先判断链接是最终稿、参考稿还是过期占位。
2. 用 `explore-design-tree-ingee` 拉局部图层、预览图和语义信息。
3. 需要详细 DSL、尺寸或图片 URL 时，再用 `ingee-flex` / `duo ingee-fetch`。
4. 根据项目约定把设计稿 px 转成代码尺寸。
5. 后端下发的颜色、图片、文字当作数据处理，不写死为常量。

## 交付前清单

最终回复前确认：

- 用户输入已由 hooks 原始日志记录；如果是收工或关键节点，当前需求目录的 `voice-prompt` 已批量归档。
- 相关文档已在关键节点或收工时更新；中间轮次不强制生成总结文档。
- 有源码改动时已验证。
- 本轮改变项目状态时已更新进度 / Token。
- 需要代码审查时已列出工具或完成审查。
- 已检查 `git status --short`。
- 需要提交的内容已提交。
- 最终回复说明改了什么、文件位置、commit id 和验证边界。

## 常见错误

- 改生成目录 `src`，而不是改 `protocol` 或 `material`。
- 新增物料 props 后忘记更新 `description.json`。
- 把 AppMock 的 `data` 当作后端原始响应。
- 用户说技术方案更新后仍沿用旧字段。
- 把后端下发的颜色、图片、文案写死。
- 把个人 MIS 等个性化信息写进会合入 master 的仓库级文档。
- 在脏工作区误提交用户无关改动。
- 收工只更新进度，忘记语音记录、工具记录、turn-log 摘要版/完整版 Markdown 或 Token 记录。
- 没有真机或 DUO 平台验证，却说 MRN 已完整验证。
