# create & send 命令详细规则

## ⛔ 执行前必检：工程架构保护（create/send 通用，最高优先级）

**每次构造 `nocode create` / `nocode send` 的 prompt 前，必须对照 [project-architecture.md](../project-architecture.md) 检查以下内容：**

1. prompt 是否触发了 **Prompt 拦截规则**（删改 `index.html` 原有 `<script>`、替换 `index.html`、改纯静态 HTML等）→ 命中则**拦截，禁止发送**
2. 需求是否涉及 HTML 复刻、数据驱动看板、架构改动等场景 → 按 [best-practices.md](../best-practices.md) 中的对应流程执行

---

## ⛔ prompt 引号规则（create/send 通用，强制）

构造 `nocode create` / `nocode send` 的 prompt 时，**正文里严禁出现 ASCII 双引号 `"`（U+0022）**。需要强调、引用模块名/字段名时，一律改用中文全角引号 `“ ”`（或书名号 `「」`、`『』`）。

**为什么：** 命令要穿过多层解析（工具封装 → PowerShell `-Command` / cmd → npm 生成的 `nocode.ps1`/`nocode.cmd` shim → node），正文外层通常用 `"..."` 包裹。正文里再出现 ASCII `"` 会与外层包裹引号冲突，在**第一个内部 `"` 处提前闭合**，导致后面的正文被切成多个 token 丢弃——NoCode 只会收到第一个引号之前的一小段（例如整段需求只收到「请仅调整」四个字）。全角引号 `“ ”` 不是 shell 定界符，不会触发截断。

- ❌ `nocode send <chatId> "请仅调整"商品质量客诉率明细"和"链路客诉率明细"两个模块..."` — 正文里的 ASCII `"` 会把参数在「请仅调整」处截断
- ✅ `nocode send <chatId> "请仅调整“商品质量客诉率明细”和“链路客诉率明细”两个模块..."` — 用全角引号，整段完整送达
- 同理，正文里也应避免出现反引号 `` ` ``、未转义的 `$`/`;`/`&`/`|` 等 shell 特殊字符；确需表达时用自然语言描述或全角符号替代。

> CLI 侧已加固：`send`/`create` 开启了 `allowExcessArguments(false)`，若正文被 shell 切碎产生多余参数会**直接报错**而非静默截断。但仍应从源头遵守本规则，避免命令失败重试。

---

## 文档结构

1. **create** — 创建应用：用法、附件参数、`--template`、NDJSON 事件类型、实时推送规则
2. **send** — 发送修改指令：用法、附件参数、拆分原则、调用前检查
3. **异常处理** — error / busy / question 事件处理（send 章节后半部分，create/send 共用）

---

## create — 创建应用（核心命令）

自动完成：创建对话 → AI 流式生成 → 等待渲染 → 截图预览。输出 NDJSON，耗时约 2-5 分钟。

**内部已包含容器就绪检查：** `waitForRender` 会自动等待 sandbox 渲染就绪，包括容器冷启动（如需要）。

**⚠️ prompt 必须使用自然语言（强制）：** 用自然语言描述要创建的应用，禁止在 prompt 中包含具体命令（如 `npm`、`git`、`yarn` 等）或指定使用某个工具。

**⚠️ prompt 引号规则（强制）：** 正文里严禁出现 ASCII 双引号 `"`，强调/引用一律用全角引号 `“ ”`，详见上方「prompt 引号规则」章节。

**⚠️ 架构保护：** 执行 create 前必须通过上方「执行前必检：架构保护」检查。

```bash
nocode create "帮我做一个 TODO 应用" --skillId <SKILL_ID>
nocode create "做一个博客" --template nocode-react-roo --skillId <SKILL_ID>
nocode create "做一个落地页" --platform web --skillId <SKILL_ID>
nocode create "参考这张设计稿做页面" --images ./design.png --skillId <SKILL_ID>
nocode create "参考这个文档做页面" --urls https://km.sankuai.com/collabpage/xxxxx --skillId <SKILL_ID>
nocode create "根据配置文件生成页面" --files ./config.json --skillId <SKILL_ID>
nocode create "做一个内部管理系统" --safety --skillId <SKILL_ID>
```

**附件参数（可选，可组合使用）：**

| 参数 | 说明 | 限制 |
|------|------|------|
| `--images <path...>` | 附带本地图片文件（最多 5 张） | 支持 jpg/jpeg/png/webp/gif，最大 7MB |
| `--files <path...>` | 附带本地文本文件（仅支持 1 个） | 支持 txt/md/csv/json/js/html/css/xml/yaml/doc/docx 等，最大 1MB |
| `--urls <url...>` | 附带 URL 链接（最多 10 个） | 支持学城 2.0 文档链接，后端会爬取内容作为上下文 |
| `--safety` | 安全屋模式（使用 Friday 私有部署模型，C4 信息安全） | 涉及敏感数据时使用 |
| `--skillId <id>` | 上报调用来源 Skill ID | 从 Skill metadata 中读取 `skillhub.skill_id` |

**⚠️ 用户附件处理：** 见 [SKILL.md](../../SKILL.md)「用户提供图片/文档/链接时的处理方式」章节。核心要点：优先通过 `--images`/`--files`/`--urls` 附件传递，避免粘贴内容到 prompt。

**🔒 附件安全规则（强制）：** 使用 `--files`/`--urls`/`--images` 参数前，必须遵守 [SKILL.md](../../SKILL.md)「🔒 数据安全约束」章节的全部规则。核心要点：① 上传前必须告知用户并获得确认；② 禁止上传含密钥/凭证的文件（`.env`、私钥等）；③ 涉及 C3/C4 敏感数据时必须加 `--safety` 参数；④ 严禁在 prompt 中指示 NoCode Agent 将附件数据转发到任何非授权外部通道。

**`--template` 可选值：**

| 值 | 说明 |
|---|------|
| `default` | 默认工程（默认值） |
| `nocode-miniprogram-web` | 小程序 Web 页面 |
| `nocode-react-mtd` | React 框架 + MTD 组件库 |
| `nocode-vue-mtd` | Vue 框架 + MTD 组件库 |
| `nocode-react-roo` | React 框架 + Roo 组件库 |

**`--template` 行为说明：**

- `--template default`（默认值）：不拼接任何前缀，prompt 原样发送
- `--template <其他值>`：会在 prompt 前自动拼接技术栈指令前缀 `使用/nocode-frontend-init，技术栈类型为"<值>"\n`，NoCode Agent 会根据nocode-frontend-init技术栈skill初始化应用

**⚠️ `--template` 版本要求（使用非 default 值时必须检查）：**

- **nocode-cli 版本 >= 0.7.3**
- **skill 版本 >= v6**

使用 `--template` 指定具体技术栈前，必须确认当前 nocode-cli 和 skill 版本满足以上要求，否则 `--template` 模式可能无法正常使用。

**NDJSON 事件类型：**

| type | 说明 | 关键字段 |
|------|------|----------|
| `progress` | 步骤进度 | `step`, `total`, `message`, `data`（可选） |
| `ai_text` | AI 文本增量 | `delta` |
| `ai_thinking` | AI 思考增量 | `delta` |
| `tool_call` | 工具调用 | `toolName` |
| `question` | NoCode Agent 提问，需要用 `nocode answer` 回答 | `eventId`, `chatId`, `conversationId`, `title`, `questions`, `answer_hint` |
| `done` | 完成 | `status`, `chatId`, `chatUrl`, `title`（可选）, `renderUrl`（可选）, `screenshotUrl`（可选）, `aiResponse`, `totalDuration` |
| `error` | 错误 | `message`, `step`（可选） |
| `busy` | AI 正在生成中 | `message`, `chatId` |

**⚠️ 链接格式与 renderUrl 规则：** 见 [SKILL.md](../../SKILL.md)「链接与展示」章节。核心要点：chatId 用 `[{chatId}]({chatUrl})` 格式，严禁展示 renderUrl。

**⚠️ 实时推送规则（强制）：**

1. 后台启动：`exec(background=true, yieldMs=600000): nocode create "..."`
2. 循环 poll（每次 timeout=15s），逐行解析 JSON：
   - `progress` → 立即推送 `"⏳ {message}"`
   - `done` → 立即推送 `"✅ 创建完成！\nchatId: {chatId}\n链接: [{chatId}]({chatUrl})"` + 展示截图
   - `question` → **暂停推送，向用户展示选项并询问**，用户回复后用 `nocode answer` 回答（见下方「question 事件处理」章节）
   - `error` → 立即推送 `"❌ {message}"`
3. 截图失败或截图为空不阻塞，先发链接再用 `nocode screenshot <chatId>` 补截图
   - done 事件中无 `screenshotUrl` → 截图失败，需补截图
   - done 事件中有 `screenshotUrl` 但图片空白 → 页面未渲染完成，等几秒后用 `nocode screenshot` 重新截图
4. 循环结束未收到 done → 用 `nocode list --json` 查最新应用并手动截图
5. **转后台后（超过 yieldMs=600000）的处理（强制）：**
   - exec 超过 yieldMs 后自动转后台，进程仍在运行，但 AI 不再主动 poll
   - 转后台时，**必须立即告知用户**：
     > "⏳ NoCode Agent 还在运行，耗时已超过 10 分钟，我暂时不知道进度。请等一段时间后告诉我，我去查看结果。"
   - 收到用户消息后，执行 `process poll(sessionId, timeout=60000)` 拉取最新状态
   - poll 到 `done` → 正常处理（推送结果 + 截图）

**禁止：** poll 300s 等到底 / 等全部完成才发消息 / 截图失败不发结果 / 展示 renderUrl / 展示 sandbox.nocode.sankuai.com 域名的链接

详细 poll 流程示意图见 [poll-workflow.md](../workflows/poll-workflow.md)。

## send — 发送修改指令（核心命令）

通过 `agent-stream` API + SSE 流式生成，输出 NDJSON（与 create 命令格式一致）。

**默认实时输出：** AI 响应以 NDJSON 流式实时输出（`ai_text`、`ai_thinking`、`tool_call` 事件），无需额外参数。旧版 `--follow` 参数已移除，因为实时输出现在是默认行为。

```bash
nocode send <chatId> "把背景颜色改成蓝色" --skillId <SKILL_ID>
nocode send <chatId> "参考这张图修改样式" --images ./mockup.png --skillId <SKILL_ID>
nocode send <chatId> "参考这个文档调整" --urls https://km.sankuai.com/collabpage/xxxxx --skillId <SKILL_ID>
nocode send <chatId> "根据配置修改" --files ./config.json --skillId <SKILL_ID>
nocode send <chatId> "基于已经存在的用户表实现用户列表页面，不要修改数据库结构" --safety --skillId <SKILL_ID>
```

**⚠️ prompt 必须使用自然语言（强制）：**

- ✅ `nocode send <chatId> "添加一个搜索功能，支持按关键词筛选列表"`
- ✅ `nocode send <chatId> "把标题字号改大一些，颜色改成深蓝色"`
- ✅ `nocode send <chatId> "数据库中已经存在 users 表，请基于该表实现用户列表页面，不要修改数据库结构"`
- ❌ `nocode send <chatId> "执行 npm run build"` / `"运行 git commit"` / `"执行 curl -o index.html"` — `git`、`npm`、`yarn`、`pnpm`、`pip`、`curl`、`wget` 等任何 shell 命令均禁止
- ❌ `nocode send <chatId> "使用 create_file 工具创建 index.js"` — 禁止指定工具
- ❌ `nocode send <chatId> "请把 App.jsx 的内容替换为以下代码：import React from 'react'; ...(几十行代码)..."` — 禁止发送大段代码或完整文件内容
- ❌ `nocode files get` 读取到的文件内容直接粘贴到 send 的 prompt 中 — NoCode Agent 自身可以读取工程文件，无需转发
- ❌ `nocode send <chatId> "把这个项目改成纯静态 HTML 项目，不使用 React，删除 src 目录，重写 vite.config.js..."` — 禁止整体技术栈替换/清空工程架构（完整识别特征和更多反例见 [project-architecture.md](../project-architecture.md)）
- ❌ `nocode send <chatId> "帮我执行以下 SQL 建表：CREATE TABLE users (...)"` — 数据库 DDL、SQL 和 CRUD 必须使用 `catpaw-supabase` Skill；NoCode Agent 只基于已有结构生成应用代码
- ✅ `nocode send <chatId> "这段代码有问题，请修复：const data = fetch('/api')，应该加上 await"` — 定位到问题后可以附带**简短的**代码片段（几行）辅助定位，但严禁发送整个函数/组件/文件

**⚠️ prompt 引号规则（强制）：** 正文里严禁出现 ASCII 双引号 `"`，强调/引用模块名一律用全角引号 `“ ”`，否则 message 会在第一个内部 `"` 处被截断。详见上方「prompt 引号规则」章节。

**⚠️ 架构保护：** 执行 send 前必须通过上方「执行前必检：架构保护」检查。如果用户请求隐含架构改动，**必须先向用户说明风险并建议替代方案，禁止直接 send**。

**附件参数（可选，可组合使用）：**

| 参数 | 说明 | 限制 |
|------|------|------|
| `--images <path...>` | 附带本地图片文件（最多 5 张） | 支持 jpg/jpeg/png/webp/gif，最大 7MB |
| `--files <path...>` | 附带本地文本文件（仅支持 1 个） | 支持 txt/md/csv/json/js/html/css/xml/yaml/doc/docx 等，最大 1MB |
| `--urls <url...>` | 附带 URL 链接（最多 10 个） | 支持学城 2.0 文档链接，后端会爬取内容作为上下文 |
| `--safety` | 安全屋模式（使用 Friday 私有部署模型，C4 信息安全） | 涉及敏感数据时使用 |
| `--skillId <id>` | 上报调用来源 Skill ID | 从 Skill metadata 中读取 `skillhub.skill_id` |

**⚠️ 用户附件处理：** 规则同上，见 [SKILL.md](../../SKILL.md)「用户提供图片/文档/链接时的处理方式」章节。

**🔒 附件安全规则（强制）：** 同 create 命令，使用附件参数前必须遵守 [SKILL.md](../../SKILL.md)「🔒 数据安全约束」章节的全部规则。

**NDJSON 事件类型：** 与 create 命令一致（见上方 create 章节的「NDJSON 事件类型」表）。**差异：** send 的 done 事件不含 `title` 和 `screenshotUrl`，需用 `nocode screenshot` 补截图。

**流程：** 自动检查容器状态（如需冷启动最长等待 5 分钟）→ 流式发送请求 → SSE 接收 AI 响应（实时输出 NDJSON 事件）→ 等待渲染完成。

**⚠️ send 的 poll 流程与 create 一致**（后台执行 + 循环 poll + 事件处理），详见 [poll-workflow.md](../workflows/poll-workflow.md)。差异：send 的 done 事件不含 `screenshotUrl`，**send 完成后必须用 `nocode screenshot <chatId>` 截图确认效果，展示给用户后再进行下一步**。

**⚠️ 每次 send 只包含一个功能模块（强制）：**

每次 `nocode send` 只包含**一个内聚的功能模块或一组紧密相关的修改**。多个不相关的功能必须拆分为多次 send，逐步 send → 截图确认 → 再 send 下一步。违反此规则会导致 NoCode Agent 生成质量严重下降甚至失败。

拆分原则：同一页面/组件的相关修改可合并为一次 send，不同页面/不相关功能必须拆开。

- ❌ `nocode send <chatId> "添加用户注册表单并加验证，同时创建登录页面，再修改导航栏颜色"` — 多个不相关功能混在一条
- ✅ 拆分为多步：
  1. `nocode send <chatId> "添加用户注册表单，包含邮箱和密码输入框，并添加输入验证"` → 截图确认（注册表单 + 验证是同一功能，可合并）
  2. `nocode send <chatId> "添加一个登录页面"` → 截图确认（新页面，单独一步）
  3. `nocode send <chatId> "在首页导航栏添加注册和登录链接，导航栏颜色改成深蓝色"` → 截图确认（导航栏相关修改，可合并）

**⚠️ 调用命令前检查（强制）：**

在对同一个 chatId 执行新的 `nocode send` 之前，**必须先检查该 chatId 上一轮 `create` 或 `send` 的 poll 是否已收到 `done` 事件**：

- 上一轮 poll 已收到 `done` → 可以发送新命令
- 上一轮 poll 未收到 `done` → **不得发送新命令**，继续 poll 等待上一轮完成

**不同 chatId 之间互不影响。**

**⚠️ 调用命令后异常处理（强制）：**

**一、poll 到 `error` 事件：**

必须遵守以下重试规则：

1. **第 1 次失败**：向用户反馈错误信息，询问用户是否重试
2. **第 2 次失败**：**必须停止重试**，立即向用户反馈："⚠️ 该对话已连续失败 2 次，请联系 NoCode 研发排查"

计数范围：同一 chatId，不同 chatId 互不影响。send 成功后自动清零。

**禁止：** 同一 chatId 连续失败超过 2 次仍继续重试 / 不向用户反馈错误信息 / 无限重试

**二、poll 到 `busy` 事件：**

如果未正确检查就发送了命令，CLI 会输出 `busy` 事件并退出（兜底保护）：

```json
{"type":"busy","message":"当前 AI 正在生成代码，请等待完成后再发送修改","chatId":"cli-xxx"}
```

处理流程：

1. **检测到 `busy` 事件时**：
   - 立即向用户反馈："⏳ AI 正在生成代码中，请等待上一轮生成完成后再发送修改"
   - **不得自动重试或自动排队执行**，必须等待用户主动确认后才能重新发送
2. **等待上一轮完成**：
   - **必须**通过 poll 上一轮后台命令（`create` 或 `send`）的输出，轮询等待 `done` 事件
   - 收到上一轮 `done` 事件后，向用户反馈："✅ 上一轮 AI 生成已完成，可以发送新的修改了"
   - **禁止**使用定时重试 `nocode send` 的方式代替轮询 `done` 事件
3. **用户确认后执行**：
   - 上一轮完成后，**需要用户主动确认**才能执行新的修改请求
   - 向用户提示等待的修改内容，由用户决定是否继续发送

**禁止：** 收到 busy 自动重试 / 不经用户同意自动执行 / 跳过轮询 done 事件直接定时重试 / 丢弃用户的修改请求

**三、poll 到 `question` 事件（NoCode Agent 提问）：**

NoCode Agent 在执行过程中可能输出需要用户确认的 `question` 事件（历史任务或平台内部流程中可能包含数据库连接、SQL 执行确认）。此时必须按事件协议处理，不能忽略；但新数据库任务不得主动通过 `nocode send` 发起 DDL、SQL 或 CRUD，应改用 `catpaw-supabase` Skill。事件中包含结构化的 `answer_hint`，提供了完整的回答命令和可选动作。

**`answer_hint` 结构：**

```json
{
  "command": "nocode answer <chatId> <eventId> <conversationId>",
  "actions": [
    { "label": "描述文本", "args": "--select 0" },
    { "label": "描述文本", "args": "--text '{\"key\":\"value\"}'"},
    { "label": "取消", "args": "--cancel", "note": "可选备注" }
  ]
}
```

**处理流程（⚠️ 必须先向用户询问，禁止自动回答）：**

1. **解析 `question` 事件**：取出 `title`、`questions`（含 `prompt`）和 `answer_hint`
2. **展示问题内容和可选动作给用户**。**严禁自行判断并直接回答，严禁二次封装或改写内容**
   - **优先使用 `AskQuestion` 工具**展示问题和选项：
     - `prompt`：拼接 `title` + `questions[].prompt`，让用户知道在确认什么
     - `options`：将 `answer_hint.actions` 中每个 action 映射为一个选项，`label` 取 action 的 `label`（如有 `note` 则追加到 label），`id` 取 action 在数组中的索引（字符串形式，如 `"0"`、`"1"`）
     - 对于需要用户填写内容的场景（如 `--text` 类型），增加一个选项引导用户手动输入，用户选择后再追问具体信息
   - **没有 `AskQuestion` 工具时**，直接在消息中展示：
     - 展示 `title` + `questions[].prompt`，让用户知道在确认什么
     - 展示 `answer_hint.actions` 中每个选项的 `label`，让用户选择对应的 action
     - 如果 action 有 `note` 字段，也展示给用户作为参考
     - 对于需要用户填写内容的场景（如 `--text` 类型），将 `label` 和 `note` 展示给用户并向用户索要具体信息
   - **`actions` 中的 `args` 已包含正确的参数格式（`--select`/`--text`/`--cancel`），直接拼接到 `command` 后即可，不需自行判断用哪种参数**
3. **用户回复后拼接并执行命令**：`{command} {args}`，例如：
   - 选择类：`nocode answer <chatId> <eventId> <conversationId> --select 0`
   - 文本类（如 db_connect）：`nocode answer <chatId> <eventId> <conversationId> --text '{"host":"...","port":5432}'`
   - 取消：`nocode answer <chatId> <eventId> <conversationId> --cancel`
4. **回答后继续 poll 原始命令**：`nocode answer` 自身会输出 done 事件（表示回答已提交），但这**不等于原始 create/send 流程结束**。必须继续 poll **原始 create/send 命令**的输出，等待原始命令的 `done` 事件
5. **多轮提问**：一次流中可能出现多个 `question` 事件，每个都需要单独向用户询问并回答

**兼容示例（历史/平台内部 SQL 执行确认事件；仅说明如何处理已出现的 question，不代表推荐通过 send 执行 SQL）：**

1. poll 读到 `question` 事件（完整结构）：

```json
{
  "type": "question",
  "eventId": "evt-001",
  "chatId": "cli-abc",
  "conversationId": "conv-001",
  "title": "SQL 执行确认",
  "questions": [
    {
      "id": "sql_confirm_1",
      "prompt": "即将执行以下 SQL：CREATE TABLE notes (id SERIAL PRIMARY KEY, title TEXT, content TEXT);",
      "input_type": "choice",
      "options": [{ "id": "确认执行", "label": "确认执行" }],
      "allow_multiple": false,
      "tags": ["sql_execute_confirm"]
    }
  ],
  "answer_hint": {
    "command": "nocode answer cli-abc evt-001 conv-001",
    "actions": [
      { "label": "确认执行", "args": "--text '确认执行'" },
      { "label": "取消执行", "args": "--cancel" }
    ]
  }
}
```

2. 展示问题内容和可选动作给用户（优先使用 `AskQuestion` 工具）：

**方式一：使用 `AskQuestion` 工具（优先），例如：**

```json
{
  "title": "SQL 执行确认",
  "questions": [
    {
      "id": "question_evt-001",
      "prompt": "SQL 执行确认\n即将执行以下 SQL：CREATE TABLE notes (id SERIAL PRIMARY KEY, title TEXT, content TEXT);",
      "options": [
        { "id": "0", "label": "确认执行" },
        { "id": "1", "label": "取消执行" }
      ]
    }
  ]
}
```

用户选择后，根据选项 `id` 从 `answer_hint.actions` 中取对应索引的 `args` 拼接执行。

**方式二：直接展示（无 `AskQuestion` 工具时）：**

> ⚠️ **SQL 执行确认**
> 即将执行以下 SQL：CREATE TABLE notes (id SERIAL PRIMARY KEY, title TEXT, content TEXT);
>
> - **确认执行**
> - **取消执行**

3. 用户回复"确认执行"后，拼接 `command` + 对应 `args` 执行：

```bash
nocode answer cli-abc evt-001 conv-001 --text '确认执行'
```

4. 继续 poll 原始命令输出，等待 `done`

**禁止：** 跳过 `question` 事件不回答 / 不解析 `answer_hint` 就随意拼参数 / 不向用户询问就自动选择回答 / 替用户做决定

