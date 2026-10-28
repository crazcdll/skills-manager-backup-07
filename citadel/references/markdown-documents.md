# 原生 MD 文档（type=7）

适用于 `/md/<contentId>`、`/md/<contentId>.md`，或 `getDocumentMetaInfo` 返回 `type: 7` 的文档。编辑等需要区分类型的操作，只有数字 ID、类型不明时先查元信息；正文阅读由 `getSimpleMarkdown` 自动识别类型。

本文件是 MD 命令与操作流程的事实源。原生 Markdown 直接用于读取、创建和全文覆盖。`createDocument --file xxx.md` 创建原有 2.0 文档，不能替代下列原生 MD 命令。

## 使用前

执行 `oa-skills citadel --help`，确认包含 `getSimpleMarkdown`、`getMarkdownDocument`、`createMarkdownDocument`、`updateMarkdownDocument`。旧版 CLI 缺少所需命令或 MD 支持时停止，说明需要更新 CLI；不能改用 2.0 写入命令。Skill ZIP 只有说明文档，不包含 CLI 运行时代码。

读取或还原历史版本时，还须确认 CLI 包含 `getMarkdownDocumentVersion`；缺少时停止，不用当前正文代替历史正文。

测试环境所有命令使用相同的 `--env test --swimlane <泳道名>`。不传 `--env` 时共享 runner 可能沿用本地配置或环境变量，无配置时客户端使用生产地址；测试时必须明确指定 `test`（生产枚举为 `product`）。泳道参数仅负责请求路由，不会部署服务或验证目标服务版本。

## 读取正文（阅读和总结）

```bash
oa-skills citadel getSimpleMarkdown --contentId <id> --output /tmp/md-read.md
```

阅读和总结统一使用 `getSimpleMarkdown`。命令按实际文档类型自动分流，MD 通过原生转换器输出 Markdown，不转 XML。`--output` 保存 Markdown 正文（含文档标题），文档信息输出到 stderr；不指定输出文件时正文输出到 stdout。`--raw` 返回 `{ contentId, title, content }`，不返回编辑所需的 `stepVersion`。

阅读结果不作为编辑基线。需要修改正文或标题时，重新执行下述 `getMarkdownDocument`，同时取得最新正文和对应版本。

### 编辑前读取正文和版本

```bash
oa-skills citadel getMarkdownDocument --contentId <id> --output /tmp/md-doc.md
```

文件保存纯 Markdown（含文档标题）；标准输出返回 JSON，包含 `contentId`、`stepVersion`、`url`、`output`。`--raw` 返回包括 `markdown` 在内的完整 JSON，同时仍会写入 `--output` 文件。不指定输出文件或 `--raw` 时，正文写入 stdout，版本写入 stderr。

CLI 使用 `GET /api/docs/recent/safeRoom/{contentId}` 读取快照，保留个人认证、服务端权限及安全屋密级校验，分页补齐至本次读取确定的 Step 版本；调用现有 MD 服务合并后，再由 Nest `jsontomarkdown` 输出 Markdown。整个读取过程不写入文档或保存快照，不依赖浏览器 `.md` 导出登录态。主服务须已部署安全屋入口的 MD 类型适配。

Step 缺失、版本不连续、合并部分失败或转换失败均直接报错，不返回旧快照。转换后再次检查最新版本；期间发生变化则失败，重新读取。不得把旧文件与新版本号拼接后覆盖。接口拒绝访问或返回错误时停止，不切换其他入口重试。

当前正文和历史正文都受安全屋入口保护。达到服务端配置的保护密级（默认 C4）时，须由平台提供有效且已开启安全屋的 Token；CLI 复用 `DAXIANG_SAFE_ROOM_TOKEN` 透传，不能自行开启安全屋。普通登录成功不代表安全屋已开启。收到安全屋提示时停止，不回退普通 recent 或 `.md` 导出；编辑和新增划词评论也会在读取基线受阻后停止写入。

### 通用读取入口

- `getDocumentJson --contentId <id> --raw` 会按实际类型读取。MD 返回 `docVersion: "md"`、完整 `body` JSON 及与正文对应的 `stepVersion`；JSON 用于诊断和节点定位，Agent 不应手写 JSON 回传。
- `getSimpleMarkdown` 是正文阅读和总结的统一入口；保留的 `getMarkdown` 命令同样能识别 MD，并用原生转换器输出 Markdown。编辑前使用 `getMarkdownDocument`，一次取得最新正文和对应版本。
- `getDocumentXml` 对 MD 明确报错，不会尝试按 2.0 转换。

### 权限与目录搜索

权限命令的 `--url` 和搜索的 `--parent-urls` 支持 `/md/<id>`、`/md/<id>.md`，可带 query/hash。沿用 [权限管理](permission-management.md) 的用户授权与备份规则，目录目标仍可能递归影响子文档，操作前确认范围。

```bash
oa-skills citadel audit --url https://km.sankuai.com/md/<id> --raw
oa-skills citadel searchContent --keyword "关键词" --parent-urls https://km.sankuai.com/md/<id> --raw
```

权限报告将 `type=7` 显示为 MD 文档；权限报告和搜索结果中的 MD 链接使用 `/md/`，测试时保留客户端配置的环境与泳道。链接不会自动切换 CLI 环境，测试操作仍须显式传入 `--env test --swimlane <泳道名>`。搜索参数不合法时，在认证和请求前非零退出。

## 创建

```bash
oa-skills citadel createMarkdownDocument --title "MD 测试文档" --file /tmp/new-md.md --parentId <父文档ID>
```

- 创建 `type=7` 文档，成功返回 `contentId`、`title`、`/md/<id>` 链接。
- 非零 `--parentId` 与 `--spaceId` 不同时使用。指定 `--spaceId` 表示空间根目录；两者都不传则为当前用户个人空间根目录。不得自动沿用上下文中的父文档 ID。
- `--file` 必填、内容须为 UTF-8；允许空文件。`--title` 必须是非空单行标题。
- 文件开头的普通一级标题按文档标题解析，`--title` 覆盖该标题；正文首个章节推荐使用 `##`。格式化一级标题仍保留在正文。
- CLI 调用现有原生 MD codec 后，以该 Schema 的 JSON 创建；Agent 只需提供 Markdown，不应手写 JSON 或 XML。
- **不支持 MD 模板创建**，不接受 `--templateId` / `--copyFrom`。
- 只使用当前 MD Schema 支持的内容。不要插入 2.0 的 XML 宏或猜测不支持的组件语法。图片按下方流程先上传；创建/正文更新会校验图片域名、CDN 路径和文档归属。

## 编辑：读取后全文覆盖

1. 先用 `getMarkdownDocument --contentId <id> --output /tmp/md-doc.md` 读取，保存 Markdown、`stepVersion` 和一份修改前的本地备份。
2. 按用户意图修改文件，保留未要求修改的内容。
3. 使用此次读取返回的版本更新：

```bash
oa-skills citadel updateMarkdownDocument --contentId <id> --step-version <读取返回的版本> --file /tmp/md-doc.md
```

4. 用 `getSimpleMarkdown` 回读并确认标题和目标内容。比较语义即可，服务端可能规范化 Markdown 空白和格式。

其他编辑方式：

```bash
# 只改标题，保留正文
oa-skills citadel updateMarkdownDocument --contentId <id> --step-version <版本> --title "新标题"

# --file 可与 --title 同时提供；显式标题优先
```

空文件表示清空正文，必须有用户明确的清空意图。划词评论锚点可能随全文覆盖丢失，这是已确认的行为，不做锚点保留或重建。

### 保存回执和停止条件

- 保存前以当前版本比较规范 Markdown 与标题，比较期间版本变化即停止。标题和正文无变化时不调用保存接口、不新增 Step，返回 `{ contentId, unchanged: true, stepVersion, message }`；`stepVersion` 是核对时的当前版本。此回执不表示已经保存，也不承诺快照已持久化；现有节点属性和评论锚点保持原样。
- 正常回执包含 `contentId`、`savedStepVersion`、`snapshotSaved`。
- `snapshotSaved: false`：**Step 已提交成功**，仅快照待生成；保留回执中的提示，再读取核对，禁止重复提交。
- 版本冲突：命令非零退出。重新读取并重新合并修改，不可直接换新版本号重发旧文件。
- 权限不足、文档不存在/类型错误、Schema 不支持：停止写入并说明原因。
- 请求超时、网络中断、无有效回执：结果可能已经落库，先读取确认；创建失败时先检查目标目录。CLI 不自动重试创建或更新。
- 标题读取/保存仍以服务端结果为准；不要把成功退出等同于浏览器已同步刷新。

## 历史版本读取与还原

沿用 2.0 的“读取历史内容，再全文覆盖”流程。版本列表复用 `getDocumentVersions`，MD 历史内容使用原生 Markdown 命令，不调用 XML 转换或网页 recovery 保存接口。

```bash
# 选择目标历史版本，取 stepVersion 字段，不是 version 字段
oa-skills citadel getDocumentVersions --contentId <id>

# 获取精确历史 Markdown，文件与当前正文备份使用不同路径
oa-skills citadel getMarkdownDocumentVersion --contentId <id> --stepVersion <历史版本> --output /tmp/restore.md
```

输出约定与 `getMarkdownDocument` 一致：文件保存 Markdown；指定 `--output` 时标准输出返回 `contentId`、`stepVersion`、`url`、`output`；`--raw` 返回 `{ contentId, markdown, stepVersion, url }`，同时仍会写入 `--output` 文件。不指定输出文件或 `--raw` 时，正文输出到 stdout，版本输出到 stderr。

历史标题以该版本快照正文中的标题为准；版本列表的 `title` 通常是时间标签，不能当作文档标题。不要用当前文档标题替换历史标题，缺少目标标题时先与用户确认。

还原时按以下顺序操作：

1. 展示目标版本的时间、编辑者和历史正文，取得用户对目标版本及覆盖当前内容的确认。
2. 用 `getMarkdownDocument` 读取当前正文和 `stepVersion`，保存独立的本地备份：

```bash
oa-skills citadel getMarkdownDocument --contentId <id> --output /tmp/current-before-restore.md
```

3. 以这次**当前正文读取**返回的版本执行覆盖：

```bash
oa-skills citadel updateMarkdownDocument --contentId <id> --step-version <当前读取的版本> --file /tmp/restore.md
```

4. 用 `getSimpleMarkdown` 回读，核对目标标题和正文语义。服务端可能规范化空白和格式，不要求 Markdown 字节一致。

- 历史 `stepVersion` 用于选择历史内容，当前 `--step-version` 用于防止覆盖并发编辑，两者不能混用。
- 历史接口返回的实际版本不等于请求版本、正文缺失或转换失败时直接失败。不得回退最新正文、相邻版本或旧快照后声称已读取目标历史版本。
- 只支持完整的原生 MD JSON 历史快照；旧 HTML 快照明确报错，不按当前正文或其他格式替代。
- 当前版本冲突时停止，重新读取并说明新增编辑，再确认是否仍需还原；不能只换一个新版本号提交之前的文件。
- 还原复用全文覆盖的保存回执和停止条件，包括 Step 已提交但快照待生成时禁止重复提交。
- Markdown 覆盖会重建节点身份，旧 `nodeId`、`quote` 和划词评论锚点不保证原样还原；这是已确认的全文覆盖行为。

## 图片上传、清洗与跨文档迁移

复用 2.0 的“先上传、再写入”机制。校验针对原生 `image` 节点，覆盖表格、列表和链接内图片；引用式 Markdown 图片由原生 codec 解析后同样校验。普通超链接、代码示例和 Raw HTML 宏中的 HTML/CSS/脚本资源不在本次图片清洗范围。

### 在已有 MD 文档插入图片

```bash
# 本地图片；远程来源也可传 --imageUrl <图片URL>
oa-skills citadel uploadImageToDocument --contentId <目标文档ID> --image /tmp/image.png --alt "图片说明" --raw

# 来源已经是另一篇学城文档的图片时，用该命令迁移权限归属
oa-skills citadel copyImageToDocument --contentId <目标文档ID> --imageUrl <来源学城CDN链接> --raw
```

1. 上传/复制成功后使用返回的 **`nativeMarkdown`**，它是标准 Markdown 图片片段；`imageXml` 用于 2.0。
2. 通过 `getMarkdownDocument` 读取目标正文和版本，在指定位置插入片段，再用 `updateMarkdownDocument --step-version <版本>` 保存。
3. 已有图片只迁移 URL，保留原 `alt`、`title` 和链接等上下文。上传或复制本身不会把图片插入正文。

保存校验仅接受当前环境的 HTTPS 学城 CDN 链接：生产为 `km.sankuai.com`，测试为 `km.it.test.sankuai.com`，路径为 `/api/file/cdn/<contentId>/<fileId>`。测试命令均需带 `--env test --swimlane <泳道>`。外部域名、相对地址、data/blob、本地路径、上传临时 URL，以及更新时属于其他文档的图片都会被拒绝；不会在保存时自动下载外链，也不能删除用户图片后继续提交。

### 新建含图片的 MD 文档

- **本地/外部图片**：先用空文件创建 MD 文档取得 ID，再上传图片到这个 ID，最后按编辑流程写入完整正文。不要先把外链放入创建文件。
- **文件已经引用同环境的学城 CDN 图片**：`createMarkdownDocument` 会先创建仅含标题的文档，复用图片复制接口将资源迁移到新 ID，最后带版本保护保存完整正文。相同来源 URL 只迁移一次，图片描述、标题及嵌套结构保留。
- **中途失败**：错误会包含已经创建的文档 ID/链接。先回读该文档，再继续上传或编辑；不要重复创建。新文档发生其他编辑时停止自动填入正文；图片迁移或保存失败时可能保留空正文及已上传图片，不自动删除文档或资源。

## 复制整篇文档

复用现有复制命令，来源为 MD 时由服务端保留 `type=7`，无需先读取 Markdown 再创建：

```bash
oa-skills citadel createDocument --title "副本标题" --copyFrom <源文档ID> --parentId <目标目录ID>
```

- CLI 写入前检查来源类型、删除状态和阅读权限；成功返回副本的 `/md/<id>` 链接，测试环境保留泳道。来源 ID 和创建位置必须由用户意图确定，不猜测。
- 新版主服务的 MD 复制直接清洗原生 JSON，保留图片描述、图片标题、链接内图片、表格对齐及其他已有 Schema 的内容与属性。图片复用资源迁移服务，归属副本文档，相同来源 URL 只迁移一次。
- 使用完整源正文；未合并 Step 缺失、乱序、部分合成失败或读取期间版本变化时停止，不能用不完整正文创建副本。
- 副本使用指定标题；原划词评论锚点会清除，不复制评论记录。Raw HTML 内的 HTML/CSS/脚本资源继续按已确认范围排除图片迁移。
- 创建后读取 `getDocumentMetaInfo` 核对 type=7、标题和位置，用 `getSimpleMarkdown` 核对正文与图片；需要诊断内容属性时读取 `getDocumentJson`，不要手写 JSON 回传。
- 请求超时或返回复制提示时，先查目标目录确认结果，不自动重试。副本编辑使用 `getMarkdownDocument` + `updateMarkdownDocument`，沿用创建后的权限收尾规则。

本能力需要部署包含 MD 原生 JSON 复制修复的主服务；旧后端仍可能丢失属性，不能仅凭复制接口返回成功宣称内容完整。实际部署和验收状态另行记录。

## 评论

全文评论沿用 `getFullTextComments`、`addFullTextComment` 和 `deleteFullTextComment`；新增及回复返回实际评论 ID。回执缺少有效 ID 时可能已提交，先回查列表，不重复发布。

划词评论沿用 `getDiscussionComments`、`addDiscussionComment`、`replyDiscussionComment` 和 `deleteDiscussionComment`：

1. 用 `getDocumentJson --contentId <id> --raw` 读取完整原生 JSON、当前 `stepVersion`，选取目标节点的 `attrs.nodeId`。这里仅查看 JSON，不手写 JSON 回传。
2. 使用同一次读取的节点 ID 和版本：

```bash
oa-skills citadel addDiscussionComment --contentId <id> --nodeId <节点ID> --stepVersion <本次版本> --text "评论正文" --raw
```

3. 用 `getDiscussionComments` 回查引用及正式 `discussionId`、`commentId`、`quoteId`；回复、删除使用这些正式字段，不能用创建请求的临时 ID。

定位按当前 MD Schema 和完整 Step 合并后的正文计算。版本已变、Step 不完整、节点不存在或重复、目标不含可添加 quote 的非空文字时，不提交锚点或评论。支持整节点引用，不新增字符区间参数；图片、纯 mention、空节点等特殊锚点不走此命令。

锚点 Step 与评论创建是两次写入：锚点回执不明确时停止；锚点已保存而评论未完成确认时，错误包含 quoteId 和保存版本。先回读正文并查询评论，勿重跑整个添加命令。Markdown 全文覆盖后旧锚点可能丢失，不迁移或重建；列表沿用 2.0 的有效 quote/nodeId、特殊锚点及新评论判定。

评论内容、回复参数、每会话每文档条数限制，以及删除前用户确认和不可撤销规则，统一见 [划词及全文评论说明](discussion-comment.md)。删除文档授权不等于删除其已有评论的授权。

## 不支持的组件

当前 MD Schema 不支持附件、Drawio、音视频、WPS Excel 和数据图表组件。对应上传、创建与修改命令会先读取目标类型，确认是 MD 时直接报错，不创建或修改资源。类型未知、元信息请求失败或目标已删除时同样停止。原生图片继续按上方上传、清洗与迁移流程执行；不要用 2.0 组件 XML 或 Raw HTML 绕过限制。

## 删除

复用 `deleteDocument --contentId <id>`。先核对标题、ID 与用户删除意图，禁止批量或猜测目标。成功后用 `getDocumentMetaInfo --contentId <id> --raw` 确认 `deleted: true`；原生 MD 读取应失败。删除只针对明确指定的测试文档或用户已授权的文档。

已实现 MD 读、建、改、删、图片清洗上传、通用 JSON 读取、划词评论及组件写前检查，以及权限和搜索的 MD 链接入口。MD 历史还原和整篇复制按上述工作流执行，实际验收和发布状态另行记录。删除后其他已打开页面的自动刷新，还依赖主服务和协同服务的 MD 删除广播适配部署及实际长连接验收。MD 模板不支持；链接入口支持不代表所有跨账号、跨空间权限场景均已验收。
