---
name: citadel
description: "学城 km/wiki/km.sankuai.com 文档官方工具，凡涉及学城文档操作，优先使用本skill，而不是web_fetch或browser-agent(会造成脏数据)操作学城。激活方式：遇到任何 km.sankuai.com 链接或提到学城/文档/collabpage/contentId/parentId/pageId/知识库/km/wiki/流程图/Drawio/划词评论/历史版本/恢复文档/数据图表/密级/知识广场时优先激活。支持读取文档内容和相关信息、读取模板内容、文档目录和子文档列表，创建/编辑/删除/复制/移动学城文档、从模板创建、恢复已删除文档、设置密级、搜索学城文档，查询最近编辑/浏览/收到的/被@的/评论过的文档列表，查询/添加/回复/删除划词评论和全文评论，盘点/授权/修改/移除/继承权限，读取/下载附件，读取/生成/插入流程图，获取知识广场文章，查询/还原历史版本，读取/新建/编辑数据图表。"

metadata:
  skillhub.creator: "rui.zou"
  skillhub.updater: "rui.zou"
  skillhub.version: "V47"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3367"
  skillhub.high_sensitive: "true"
---

# 学城（km/wiki/citadel/km.sankuai.com）文档操作和管理

通过 CLI 操作学城文档的完整能力：读取文档内容与元信息、读取模板内容、查看文档目录与子文档列表；创建、编辑、删除、复制、移动文档，支持从模板创建、恢复已删除文档、设置文档密级；搜索学城文档；查询最近编辑/浏览/收到的/被@的/评论过的文档列表；查询、添加、回复、删除划词评论与全文评论；盘点、授权、修改、移除、继承文档权限；读取与下载附件；读取、生成、插入流程图；获取知识广场文章；查询与还原历史版本；读取、新建、编辑数据图表。认证自动处理。

## Node.js 版本检查

执行 citadel skill 时会自动检查 Node.js 版本是否符合要求（>= 18.0.0）。如果版本过低，系统会：

1. **自动检测并安装 nvm**（如未安装）
2. **通过 nvm 自动安装并切换到 Node.js 18 或更高版本**
3. **重新执行命令**，使用新的 Node.js 版本

**无需手动干预，版本升级完全自动化。** ✨

## CLI 可用性检查

每次 skill 激活时或首次执行命令前，先检查 `oa-skills` 是否存在；不存在时再执行安装。

```bash
node -e "const cp=require('child_process'); const probe=process.platform==='win32'?'where oa-skills':'command -v oa-skills'; try{cp.execSync(probe,{stdio:'ignore',shell:true})}catch{cp.execSync('npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com',{stdio:'inherit',shell:true})}"
```

**此步骤必须执行一次，否则新环境中可能不存在 CLI 命令导致运行失败。**

## 用户偏好记忆

citadel skill 在用户本地维护一个独立的记忆文件，用于跨会话保留用户习惯。记忆文件的格式规范和建议场景见 [references/user-memory.md](references/user-memory.md)。

**记忆文件路径**：`~/.cache/oa-skills/citadel-memory.md`

### 读取

每次 skill 激活时执行：

```bash
node -e "const fs=require('fs'),os=require('os'),path=require('path');const f=path.join(os.homedir(),'.cache','oa-skills','citadel-memory.md');try{process.stdout.write(fs.readFileSync(f,'utf8'))}catch{}"
```

- 若文件存在：将内容加载到上下文，后续操作按需查阅对应章节。
- 若文件不存在：按无偏好状态继续执行，**不要主动创建**，等到用户首次触发写入时再创建。

### 写入

当用户说出以下任意触发词时，执行记忆写入：

**写入触发词（以下任意一类均触发）**：
- 记住偏好：「记住这个」「以后都这样」「记住我的习惯」「记住我的偏好」「记下来」「下次自动...」
- 记住位置：「以后都放这里」「记住这个目录」「默认创建在 XXX 下」
- 记住模板：「记住这个模板」「这个模板叫做 XX」「以后用 XX 模板」
- 记住密级：「以后默认设为 CX」「记住我通常用 CX」「默认密级是 CX」
- 清除偏好：「取消默认」「清除记忆」「忘掉这个」「不用记住了」「删除 XX 模板」

**写入流程**：

1. 若文件不存在，先按 [references/user-memory.md](references/user-memory.md) 中的"初始模板"创建文件（目录不存在时自动创建）：
   ```bash
   node -e "const fs=require('fs'),os=require('os'),path=require('path');const d=path.join(os.homedir(),'.cache','oa-skills');fs.mkdirSync(d,{recursive:true})"
   ```
   然后用 AI 将初始模板内容写入 `~/.cache/oa-skills/citadel-memory.md`（实际路径见 Node.js 的 `os.homedir()` 返回值）。
2. 用 AI 编辑 `~/.cache/oa-skills/citadel-memory.md` 中对应章节，写入格式参照 [references/user-memory.md](references/user-memory.md) 中对应场景的格式说明。
3. 只修改目标章节，其他章节保持不变。
4. 写入完成后告知用户："已记住你的偏好，下次操作时自动应用。"

### 使用

记忆文件加载后，执行相关操作时按需查阅对应章节：

- **创建文档，用户未指定位置时**：查阅 `## 创建文档默认位置`，有值则询问用户是否沿用。
- **用户说"用我的[别名]模板"时**：查阅 `## 常用文档模板`，匹配别名后直接使用对应 templateId。
- **`createDocument` 成功后的收尾**：查阅 `## 文档默认密级`，有值则询问用户是否设置密级。

## URL → ID 提取规则

用户给 学城（km） 链接时直接提取，不要追问：

- 文档链接：
  - `km.sankuai.com/collabpage/1234567890` → `--contentId 1234567890`
  - `km.sankuai.com/page/1234567890` → `--contentId 1234567890`
- 模板中心链接（用于从模板创建/读取模板内容）：
  - `km.sankuai.com/template-center/1234567890` → `--templateId 1234567890`
  - `km.sankuai.com/template-center/1234567890?isRelease=1` → `--templateId 1234567890`（忽略 query 参数）
- 用户直接给纯数字字符串 → 直接作为对应 ID

模板链接 `templateId` 提取规则（必须遵守）：

1. 若链接形如 `km.sankuai.com/template-center/<数字ID>`（可带 query/hash），提取 `<数字ID>` 作为 `templateId`。
2. 若用户直接给纯数字字符串，直接作为 `templateId`。
3. 只有在以上规则都无法提取时，才追问 `templateId`。

## 意图路由

### 优先级规则（必须遵守）

1. 用户意图是"创建/新建/生成/复制文档"时，优先走 `createDocument`，不要因为出现 km 链接就先 `getSimpleMarkdown`。
2. 在创建意图里，链接只用于提取 ID：
   - 目标目录链接（`collabpage/<id>` / `page/<id>`）→ `--parentId <id>`
   - 模板中心链接（`template-center/<id>`）→ `--templateId <id>`
   - 来源文档链接（`collabpage/<id>` / `page/<id>`）→ `--copyFrom <id>`
3. 用户意图是"查看模板内容"时，执行 `getTemplateSimpleMarkdown`，不要走 `getSimpleMarkdown`。
   - 但如果用户意图是"基于模板修改内容再创建文档"（如"按模板改好内容后创建"、"基于模板填写后生成"），应使用 `getTemplateXml` 获取完整 XML，AI 修改后通过 `createDocument --file` 创建；不要用 `getTemplateSimpleMarkdown`（简化版会丢失 nodeId 等关键信息）。
4. 只有用户明确要求"阅读/查看/总结文档内容"且目标是文档正文时，才执行 `getSimpleMarkdown`。
5. **群权限管理**：如果是在大象群里创建文档，创建后需要执行两步授权：
- 为当前群授予浏览权限：`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --xm-group-ids <群ID> --perm "仅浏览"`
- 为群助理的管理员（mis）授予管理权限：`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --person <管理员mis> --perm "可管理"`
6. **创建后的授权收尾**：每次 `createDocument` 成功后，必须询问用户："文档已创建，是否需要为特定人员/群组授权？"；若当前场景是大象群，则自动执行两步授权；若是单聊或其他场景，则询问用户是否需要授权，按需执行。


### 读取学城文档 markdown（仅在阅读/总结意图下）

```bash
getSimpleMarkdown --contentId <id>
```

> **说明**：`getSimpleMarkdown` 为当前推荐命令，输出简化版 Markdown，token 消耗更低，适合阅读和总结。
> 命令**仅供阅读**，不可直接用于创建或更新文档。

### 获取模板内容 / 模板列表

```bash
# 仅阅读/理解模板结构
getTemplateSimpleMarkdown --templateId <id>

# 基于模板修改内容再创建文档（完整 XML，保留 nodeId，可编辑后通过 createDocument --file 创建）
getTemplateXml --templateId <id>
```

> 📖 完整说明（查看公共、个人、分享给我的模板列表、从模板创建、复制文档）见 [references/templates.md](references/templates.md)

### 总结学城文档

执行 [references/doc-summary.md](references/doc-summary.md) 文件里的具体步骤，输出总结结果。

### 查看当前学城文档的子文档、文档结构和内容、parentId 下的文档目录

```bash
getChildContent --contentId <id>
```

### 创建/新建学城文档

> 🛑 **强制门禁：创建文档前必须完整读取 reference 文件**
>
> 在生成 XML 内容 **之前**，**必须完整读取**以下文件：
> 1. **[references/doc-xml-syntax.md](references/doc-xml-syntax.md)** — 完整 XML 语法参考、节点示例、自检清单
> 2. **[references/doc-create.md](references/doc-create.md)** — 创建文档详细步骤
>
> **禁止**仅凭以下方式推断格式规则：
> - ❌ 对话记忆或历史经验（规则可能已更新）
> - ❌ 本文件（SKILL.md）的摘要性描述（本文件只做路由指引，完整规则在 reference 中）
>
> 只有完整读取上述 reference 文件后，才能开始生成 XML 内容。

> ⚠️ **创建文档前的内容格式要求**（必读）：
> 1. **优先使用富文本原生节点**：用 `<p>`、`<h1>`～`<h6>`、`<ul>`、`<ol>`、`<table>` 等标准节点表达内容，**禁止使用 `<km-markdown>` 写入文档内容**——这样做不仅失去划词评论、选区编辑等学城完整能力，还更容易出错。
> 2. **普通 Markdown 文件（`.md`）可直接用 `--file` 传入**，系统自动转为富文本。
> 3. **根标签只能是 `<km-doc>`**，禁止使用 `<doc>`、`<document>`、`<body>` 等任何其他标签
> 4. **`<km-title>` 必须是第一个子节点，有且只有一个**
> 5. **禁止使用 `<div>`、`<section>`、`<thead>`、`<tbody>` 等 HTML 布局标签**（会被静默丢弃）
> 6. 详见 [references/doc-xml-syntax.md](references/doc-xml-syntax.md) 末尾的「AI 生成前的自检清单」

> ⚠️ **位置默认规则（必须遵守）**：
> - 用户**未明确指定**创建位置（未给 `--parentId` 或 `--spaceId`）时，**一律不加这两个参数**，由系统自动创建在当前用户个人空间根目录。
> - **禁止**从上下文中自动猜测或沿用任何文档 ID 作为 `--parentId`。只有用户明确说"在 XXX 文档下创建"或"创建为 XXX 的子文档"时，才传 `--parentId`。

> 📝 **内容传递方式（优先使用文件方式）**：
> - **文档内容较多时（超过几段正文），必须优先将内容写入本地文件，再通过 `--file` 参数传入**，避免在命令行中直接输出大段内容导致 AI 输出过大。
> - 只有内容极短（单行标题、简短说明等）且用户无额外需求时，才可直接用 `--content` 参数内联传入。

```bash
# 【推荐】将文档内容写入本地文件后创建
createDocument --title <标题> --file /tmp/new-doc.xml

# 创建为指定文档的子文档（用户明确指定了父文档时）
createDocument --title <标题> --file /tmp/new-doc.xml --parentId <父文档id>

# 仅适用于内容极短的场景
createDocument --title <标题> --content <内容>
```

**⚠️ 群权限提醒**：如果是在大象群里创建文档，创建后需要执行以下**两步授权**：

```bash
# 第一步：为大象群授予浏览权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/返回的contentId" \
  --xm-group-ids "群ID" \
  --perm "仅浏览"

# 第二步：为群助理的管理员（mis）授予管理权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/返回的contentId" \
  --person "管理员mis" \
  --perm "可管理"
```

> 📖 创建子文档、授权收尾、多维表格内嵌详见 [references/doc-create.md](references/doc-create.md)

### 学城权限管理与空间管理员管理

执行 [references/permission-management.md](references/permission-management.md) 里的具体步骤。统一使用 `oa-skills citadel` 下的权限管理子命令处理以下场景：

- 盘点空间或目录权限：`audit`
- 批量授权、改权、移权：`grant` / `modify` / `revoke`
- 移除或恢复权限继承：`inherit`
- 盘点离职员工文档：`audit-resigned`
- 批量转移所有者：`transfer-owner`
- 一键清空权限：`clear-perm`
- 批量设置链接分享权限：`share-perm`
- 增加或移除空间管理员：`space-admin`

### 编辑学城文档/更新学城文档内容/插入新内容到学城文档

执行 [references/doc-update.md](references/doc-update.md) 文件里的具体步骤，进行安全的文档更新，**禁止直接操作修改 JSON 数据以及通过 GUI 方式进行编辑操作**。

> 🛑 **强制门禁：每次编辑前必须完整读取 reference 文件**
>
> 在执行 `getDocumentXml` 拉取 XML **之后**、动手编辑 XML **之前**，**必须完整读取**以下两个文件：
> 1. **[references/doc-update.md](references/doc-update.md)** — 编辑工作流、注意事项、结构约束速查
> 2. **[references/doc-xml-syntax.md](references/doc-xml-syntax.md)** — 完整 XML 语法参考、节点示例、自检清单
>
> **禁止**仅凭以下方式推断格式规则：
> - ❌ 对话记忆或历史经验（规则可能已更新）
> - ❌ 原文档 XML 中已有的属性值（如已有表格的 `responsive="false"` 是历史遗留，不代表新建表格也要沿用）
> - ❌ 本文件（SKILL.md）的摘要性描述（本文件只做路由指引，完整规则在 reference 中）
>
> 只有完整读取上述两个 reference 文件后，才能开始编辑 XML。

> ⚠️ **编辑前的内容格式要求**（每次修改 XML 文件后、执行 `updateDocumentByXml` 前必须自检）：
> 1. **新增内容优先使用富文本原生节点**：用 `<p>`、`<h1>`～`<h6>`、`<ul>`、`<ol>`、`<table>` 等标准节点表达内容，**禁止使用 `<km-markdown>` 写入文档内容**——这会导致划词评论、选区编辑等能力失效。
> 2. **保留原有根标签 `<km-doc>`**，不要改写为任何其他形式
> 3. **保留原有 `<km-title>` 节点，位置不变**；只修改内容，不要删除或移位
> 4. **不要引入 `<div>`、`<section>`、`<thead>`、`<tbody>` 等禁止标签**
> 5. **不要新造不存在于规范的 `km-*` 标签**（如 `<km-heading>`、`<km-paragraph>`、`<km-code-block>`）
> 6. 详见 [references/doc-xml-syntax.md](references/doc-xml-syntax.md) 末尾的「AI 生成前的自检清单」

> **所有内容编辑统一走 XML 路径，必须使用本地文件传入，禁止在命令行内联大段内容**：
>
> ```bash
> # 第一步：获取文档 XML，保存到本地文件
> oa-skills citadel getDocumentXml --contentId <id> --output /tmp/doc.xml
>
> # 第二步：AI 编辑本地 /tmp/doc.xml 文件（语法见 references/doc-xml-syntax.md）
>
> # 第三步：通过文件回传（--file 方式，禁止内联传入内容）
> oa-skills citadel updateDocumentByXml --contentId <id> --file /tmp/doc.xml --step-version <stepVersion>
> ```
> 处理编辑请求时，必须严格遵守以下通用原则：
> - **每次编辑必须重新拉取最新内容**：每一轮编辑请求都必须重新执行获取命令，**禁止基于对话记忆或上一次拉取的内容直接发起覆盖写入**。用户在 AI 两次编辑之间可能手动修改了文档，若 AI 以"记忆中的旧内容"为基础写回，会覆盖用户手动编辑的内容，造成数据丢失。
> - **先读后改**：必须先获取文档内容，禁止在未读取原文的情况下凭空生成整篇文档内容覆盖回传
> - **最小改动**：只修改用户明确要求的那几处；无关节点、属性、顺序、样式一律保持原样
> - **不要做格式化重写**：禁止把整篇内容"重新整理""统一格式""批量改写"为另一种等价写法
> - **保留所有已有节点的 nodeId**：已有节点的 `nodeId` 属性必须保留；新增节点可省略
> - **如果用户只是补充/替换一小段**，优先在原位置做局部修改，不要整段重写

**输出**：返回编辑文档的链接，提醒用户需要刷新当前页面才能看到更新内容。

### 修改文档标题

**必须同时做两件事**：
1. 修改 `<km-title>` 内的文字
2. `updateDocumentByXml` 时传 `--title "新标题"`

```xml
<!-- 修改 km-title 节点 -->
<km-title nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">新的文档标题</km-title>
```

```bash
oa-skills citadel updateDocumentByXml --contentId <id> --file doc.xml --title "新的文档标题"
```

### 将 AI 生成的内容（图片、附件）或本地文件（包括视频、音频）插入到学城文档

执行 [references/doc-insert.md](references/doc-insert.md) 文件里的具体步骤，将 AI 生成的图片、本地文件、本地视频或本地音频安全插入到指定学城文档。

- **插入图片**：**严禁直接将非学城图片 URL 插入文档**，必须先调用 `uploadImageToDocument` 上传，再将返回的图片 XML 节点插入文档。
- **插入附件**：**严禁将非学城附件 URL 直接写入文档**，必须先调用 `uploadAttachmentToDocument` 上传（仅限 PDF/Word/Excel/ZIP 等非媒体文件，**视频和音频禁止用此命令**）。
- **插入视频**：必须先调用 `uploadVideoToDocument` 上传，再将返回的视频 XML 节点插入文档。
- **插入音频**：必须先调用 `uploadAudioToDocument` 上传，再将返回的音频 XML 节点插入文档。
- **插入 WPS Excel 嵌入节点**：使用 `createWpsExcelInDocument --contentId <id>` 创建，详见 [references/doc-update.md](references/doc-update.md)，非用户指定不使用WPS。

- **插入内嵌多维表格**：详见 [references/doc-create.md](references/doc-create.md)。

### 从模板创建 / 复制 / 删除 / 恢复 / 移动文档

```bash
createDocument --title <标题> --templateId <id>   # 从模板创建
createDocument --title <标题> --copyFrom <id>      # 复制文档
deleteDocument --contentId <id>                    # 删除
restoreDocument --contentId <id>                   # 恢复已删除
moveDocument --contentId <id> --newParentId <id>   # 移动到其他文档下
moveDocument --contentId <id> --newSpaceId <id>    # 移动到空间根目录
```

> 📖 模板/复制详细说明见 [references/templates.md](references/templates.md)

### 设置文档密级

```bash
setSecretLevel --contentId <id> --secret-level <2|3|4>
# 2=C2内部公开，3=C3内部敏感，4=C4内部机密
```

### 搜索学城文档

```bash
searchContent --keyword <关键词>
```

> 📖 分页、按空间/目录搜索等完整参数见 [references/search.md](references/search.md)

### 获取/查看最近文档列表

```bash
getLatestEdit --limit 10          # 最近编辑
getRecentlyViewed --pageSize 10   # 最近浏览
getReceivedDocs --limit 10        # 收到的文档
getMentionedDocs --limit 10       # 被@的文档
getCommentedDocs --limit 10       # 评论过的文档
```

### 评论相关

```bash
# 获取评论
getDiscussionComments --contentId <id>   # 划词评论
getFullTextComments --contentId <id>     # 全文评论
getAllComments --contentId <id>          # 全部评论

# 新增全文评论（每篇文档每次 AI 会话最多调用 1 次，禁止批量循环）
addFullTextComment --contentId <id> --text "评论内容"
addFullTextComment --contentId <id> --text "回复内容" --parentCommentId <评论ID>
```

> 添加划词评论，回复已有划词评论的完整步骤见 [references/discussion-comment.md](references/discussion-comment.md)
> 📖 删除评论（高风险，需用户确认）的完整步骤见 [references/discussion-comment.md](references/discussion-comment.md)

### 获取文档统计信息和元信息

```bash
getDocumentStats --contentId <id>     # 浏览量、评论数、创作时长等
getDocumentMetaInfo --contentId <id>  # 父文档ID、标题、创建者、所有者等
getSpaceIdByMis --targetMis <mis>     # 根据 MIS 号获取个人空间 ID
getSpaceRootDocs --spaceId <id>       # 获取空间根目录文档列表
```

### 获取学城知识广场文章列表

```bash
getKnowledgeSquareArticles           # 推荐列表（默认）
getKnowledgeSquareArticles --type 3  # 最新列表
getKnowledgeSquareArticles --type 2  # 关注列表
getKnowledgeSquareArticles --limit 20
```

### 查看/还原文档历史版本

```bash
oa-skills citadel getDocumentVersions --contentId <id>
oa-skills citadel getDocumentVersionXml --contentId <id> --stepVersion <stepVersion> --output /tmp/restore.xml
oa-skills citadel updateDocumentByXml --contentId <id> --file /tmp/restore.xml
```

> 📖 详细说明见 [references/doc-versions.md](references/doc-versions.md)

### 列出 CLI 支持的命令

```bash
listTools
```

> 完整参数说明、示例和输出格式见 [references/cli-reference.md](references/cli-reference.md)

### 下载或读取学城文档附件

**学城文档附件一律通过文枢 skill 处理，禁止直接下载。** 完整流程见 [references/doc-view.md](references/doc-view.md) 中"场景 A：下载"和"场景 B：读取内容"章节。

### 数据图表

```bash
# 读取图表数据
getChartData --contentId <文档ID> --chartId <chartId>

# 新建图表（详细步骤见 references/chart-insert.md）
oa-skills citadel createAndInsertChart \
  --contentId <文档ID> --title "图表标题" --type line --data-file /tmp/chart-data.json

# 编辑图表数据
oa-skills citadel updateChartData --contentId <文档ID> --chartId <chartId> --data-file /tmp/new-data.json

# 编辑图表配置（类型/标题）
oa-skills citadel updateChartConfig --contentId <文档ID> --chartId <chartId> --type bar
```

> 📖 完整说明（参数、图表类型、混合图、备份回滚）见 [references/chart-insert.md](references/chart-insert.md)

### 获取学城 Drawio 流程图内容

```bash
oa-skills citadel fetchDrawio --drawioUrl "<src 属性的 URL>"
# 大型流程图保存到本地
oa-skills citadel fetchDrawio --drawioUrl "<url>" --save /tmp/km-drawio.svg
```

### 生成并插入 AI draw.io 流程图到学城文档

执行 [references/generate-drawio.md](references/generate-drawio.md) 文件里的具体步骤，由 AI 生成 draw.io 流程图并插入到指定学城文档。

```bash
oa-skills citadel uploadDrawioToDocument --contentId <文档ID> --file /tmp/diagram.xml
```

## 约束

- 所有文档内容编辑统一走 XML 路径：`getDocumentXml` → 修改 → `updateDocumentByXml`
- **`getSimpleMarkdown` 仅供阅读和总结，禁止用其返回内容直接创建文档（createDocument --content）或更新文档（updateDocumentByXml）**，会丢失合并表格、宏节点、nodeId 等关键信息，导致文档损坏
- 缺少关键参数时只追问必要字段（contentId / templateId / keyword / title），不给笼统报错
- 用户给了 km 链接时按 URL 规则直接提取 ID（contentId / parentId / templateId / copyFrom）执行，不要反复确认
- **创建文档时，若用户未明确指定父文档或空间，禁止从上下文中自动沿用任何文档 ID 作为 `--parentId`**；默认不传 `--parentId` / `--spaceId`，由系统创建在个人空间根目录
- **创建/编辑文档内容时，必须使用 `--file` 参数传入本地文件，禁止将大段内容直接内联在命令行参数里**；只有内容极短（单行、几个词）时才允许内联；文档内容应先写入临时文件（如 `/tmp/new-doc.xml`），再执行 `createDocument --file` / `updateDocumentByXml --file` 命令；编辑时先用 `--output` 保存到本地文件，AI 修改后再用 `--file` 回传
- **创建或编辑文档时，禁止使用 `<km-markdown>` 写入文档内容**；应使用 `<p>`、`<h1>`～`<h6>`、`<ul>`/`<ol>`（内含 `<li><p>...</p></li>`）、`<table>`、`<pre><code>` 等富文本原生节点，这样才能支持划词评论、选区编辑等学城完整能力；普通 Markdown 内容推荐直接以 `.md` 文件通过 `--file` 传入，系统自动转为富文本
- **在大象群里创建文档后，必须执行两步授权**：① 为当前群授予浏览权限（`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --xm-group-ids <群ID> --perm "仅浏览"`）；② 为群助理的管理员（mis）授予管理权限（`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --person <管理员mis> --perm "可管理"`）；两步缺一不可
- **每次 `createDocument` 成功后，必须做授权收尾判断**：先询问用户"文档已创建，是否需要为特定人员/群组授权？"；如果场景是大象群，直接执行两步授权；如果是单聊或其他场景，询问用户是否需要授权并按需执行
- 在"复制模板/按模板创建"场景，禁止先 `getSimpleMarkdown` 再 `createDocument --content`；优先 `--copyFrom`（尤其学城文档2.0）
- 在"查看模板内容"场景，优先 `getTemplateSimpleMarkdown`，不要调用 `getSimpleMarkdown`；在"基于模板修改内容后创建文档"场景，使用 `getTemplateXml`，不要用简化版（会丢失 nodeId 等关键信息）
- `getRecentlyViewed` 用 `--pageNo`（从 1 开始），其他命令用 `--offset`（从 0 开始）
- **插入图片到文档时，严禁直接将非学城图片 URL 插入文档**；必须先调用 `uploadImageToDocument` 将图片上传到目标文档，再将返回的图片 XML 节点插入文档
- **插入附件到文档时，严禁将非学城附件 URL 直接写入文档**；必须先调用 `uploadAttachmentToDocument` 将本地文件上传到目标文档，再将返回的附件 XML 节点插入文档。**`uploadAttachmentToDocument` 仅限 PDF、Word、Excel、ZIP 等非媒体文件；视频必须用 `uploadVideoToDocument`，音频必须用 `uploadAudioToDocument`，绝对不可混用**
- **插入视频到文档时，严禁将非学城视频 URL 直接写入文档**；必须先调用 `uploadVideoToDocument` 将本地视频上传到目标文档，再将返回的视频 XML 节点插入文档
- **插入音频到文档时，严禁将非学城音频 URL 直接写入文档**；必须先调用 `uploadAudioToDocument` 将本地音频上传到目标文档，再将返回的音频 XML 节点插入文档
- **插入 WPS Excel 嵌入节点时，严禁复用图片/附件/视频/音频上传接口的 ID 来构造 `<km-open-iframe type="wpsExcel">`**；必须先调用 `createWpsExcelInDocument` 获取专用 `attachmentId`，再通过 `getDocumentXml` → 插入 `openIframeXml` → `updateDocumentByXml` 将节点写入文档；AI 不能直接编辑 WPS Excel 内部的表格数据
- **插入内嵌多维表格时，如果是在学城文档内新建表格，不需要先创建多维表格文档**；直接使用 `createTable --contentId <文档ID>` 即可。若是复制到学城文档再插入，固定使用 `copyTable --targetType 3`。然后使用 `getDocumentXml` + `updateDocumentByXml` 将多维表格节点插入文档（XML 用 `<km-xtable xtableId="<tableId>" />`），不要直接伪造表格数据节点；新增节点时 `nodeId` 可省略，已有值保留
- **严禁把其他文档中的 `<km-xtable>` 节点直接复制到当前文档，严禁手写/伪造 xtableId**：多维表格权限与文档绑定，未关联到当前文档的表格在文档中会加载失败。必须先用 `copyTable --sourceTableId <源表ID> --targetParentId <当前文档ID> --targetType 3` 复制出关联到当前文档的新表，用返回的新 tableId 插入；`updateDocumentByXml` / `updateDocumentByMd` 会对新增的 xtableId 做两阶段校验：不存在/已删除/无权限的表格 ID 在写入前直接拒绝；写入后自动审计归属，未关联到本文档的（跨文档引用）会报带 `[XTABLE_AUDIT_FAILED_POST_WRITE]` 标记的错误并要求用 `copyTable` 复制新表替换节点，收到该标记时文档已被写入、禁止原样重试（重试会静默误报成功），必须按报错指引修复。**同一张表格在同一文档中只应嵌入一次**：本次编辑新增的重复 `<km-xtable>`（同一 xtableId 出现 ≥2 次）会在写入前被拒绝，需在文档多处展示相同数据时用 `copyTable` 复制新表。创建文档时初始内容不允许包含 `<km-xtable>`（新文档尚无 ID，表格不可能已关联到它），必须先创建文档再按上述流程插入
- **生成或编辑文档内容时，文档标题节点必须是文档的第一个节点，有且只有一个**（XML 路径为 `<km-title>`）；标题节点与 `heading`（正文中的章节标题样式）完全不同，不可混用
- **编辑复杂表格时，优先在原格式内做局部修改，不要把表格还原或重写成 JSON**（XML 路径直接改 `<tr>`/`<td>`/`<th>` 内容）
- **`addFullTextComment` / `addDiscussionComment` / `replyDiscussionComment` 频次限制**：每次 AI 会话、每篇文档最多调用 1 次，禁止批量循环调用
- **`deleteFullTextComment` / `deleteDiscussionComment` 高风险限制**：不可撤销，必须先展示评论内容、获得用户明确确认后再执行；单次只能删除一条，详见 [references/discussion-comment.md](references/discussion-comment.md)
- **新建图表时，chartXml 不会自动插入文档**：`createAndInsertChart` 返回 `chartXml` 后，AI 必须额外执行 `getDocumentXml` → 插入节点 → `updateDocumentByXml` 三步
- **编辑图表数据时，`source-id` 无需手动传入**，命令内部自动获取；`updateChartConfig` 只改图表类型/标题，不涉及数据变更

## 暂不支持

以下能力当前 **不可用**，不要伪造执行结果：

- 若用户要求"复制后再填充内容"，先按 `--copyFrom` 创建，再说明当前不支持自动编辑已创建文档。
- 替代方案：先用 `getSimpleMarkdown` 阅读文档内容，再对指定部分用 `getDocumentXml` + `updateDocumentByXml` 编辑。

## 认证

根据运行环境选择合适的策略，优先 SSO 无感登录。Token 自动缓存。

认证失败 → `oa-skills citadel --clear-cache` 后重试
- 如需强制走 CIBA 认证，可额外添加 `--force-ciba`（仅在认证异常时兜底使用，正常不需要添加）

## 验证

执行完成后确认：

1. 命令退出码为 0
2. 读取类：返回了文档内容/列表
3. 创建类：返回了新文档 contentId 和链接
4. 给用户简明结论（标题、ID、数量），而非原始数据
