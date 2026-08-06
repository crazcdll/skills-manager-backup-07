# CLI 命令参考

完整参数说明，基于 `src/citadel/cli.ts` 实际实现。

## 通用选项

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--mis <mis>` | string | 从配置文件读取 | 用户 MIS 号，用于认证 |
| `--raw` | flag | false | 输出原始 JSON 到 stdout（默认输出人类可读格式到 stderr） |
| `--clear-cache` | flag | — | 清除认证缓存后退出，不需要指定命令 |
| `--force-ciba` | flag | false | 强制走 CIBA 认证（仅在认证异常时兜底使用，正常不需要添加） |

## getSimpleMarkdown

获取文档简化版 Markdown 内容（阅读/总结专用，低 token 消耗）。去除所有 `nodeId`、`dataDiffId` 等技术属性，学城专属宏保留语义提示，媒体/附件保留 URL。

> ⚠️ **该输出仅供阅读和总结，不可用于编辑文档**。如需编辑，请使用 `getDocumentXml`。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getSimpleMarkdown --contentId "2748397739"
```

**输出**：非 raw 模式下，文档标题/ID/长度输出到 stderr，简化版 Markdown 输出到 stdout（内容顶部包含不可用于编辑的警告）。

## getDocumentJson

获取文档的底层 JSON 内容。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getDocumentJson --contentId "1234567890"
```

**输出**：非 raw 模式下，文档标题/ID/长度输出到 stderr，JSON 正文输出到 stdout。

## listPersonalTemplates

获取协作文档模板列表，支持按类型查看"我创建的"、"分享给我的"或"公共模板"，并支持分页。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--type` | string | — | `personal` | 模板类型：`personal`=我创建的，`shared`=分享给我的，`public`=公共模板 |
| `--pageNo` | number | — | 1 | 页码（从 1 开始） |
| `--pageSize` | number | — | 16 | 每页数量 |

```bash
# 查看我创建的模板（默认）
oa-skills citadel listPersonalTemplates

# 查看分享给我的模板
oa-skills citadel listPersonalTemplates --type shared

# 查看公共模板
oa-skills citadel listPersonalTemplates --type public

# 分页
oa-skills citadel listPersonalTemplates --type public --pageNo 2 --pageSize 16

# 原始 JSON 输出
oa-skills citadel listPersonalTemplates --type personal --raw
```

**输出**：非 raw 模式下，模板总数/分页信息输出到 stderr，每条模板含 `templateId`、标题、创建者、修改者、创建时间、修改时间。raw 模式输出 `{ total, templates, pageNo, pageSize }` 的 JSON，`templates` 数组每项含完整模板字段。

> 获得 `templateId` 后可传给 `getTemplateSimpleMarkdown --templateId` 查看模板内容，或传给 `createDocument --templateId` 基于模板创建文档。

## getTemplateSimpleMarkdown

获取模板简化版 Markdown 内容（阅读/理解模板结构专用，低 token 消耗）。去除所有 `nodeId`、`dataDiffId` 等技术属性，学城专属宏保留语义提示，媒体/附件保留 URL。

> ⚠️ **该输出仅供阅读和理解模板结构，不可用于编辑文档**。如需基于模板创建文档，请使用 `createDocument --copyFrom` 或 `createDocument --templateId`。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--templateId` | string | ✅ | — | 模板 ID |

```bash
oa-skills citadel getTemplateSimpleMarkdown --templateId "2751442505"
```

**输出**：非 raw 模式下，模板ID输出到 stderr，简化版 Markdown 输出到 stdout（内容顶部包含不可用于编辑的警告）。

## getChildContent

获取子文档列表。自动查询文档所属 spaceId。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 父文档 ID |

```bash
oa-skills citadel getChildContent --contentId "2748397739"
```

**输出**：父文档标题、子文档列表（标题、ID、文档链接、类型、创建人、创建/修改时间、是否有子文档）。

> 当文档列表中含有 C4 级别的安全屋文档时，接口会返回非 C4 文档数据，同时输出中会附带 `warning` 字段，内容为：`当前数据返回不完整，请打开安全屋模式查看完整数据返回。原始提示：...`。如果 `warning` 存在，**必须将该警告展示给用户**。

## createDocument

创建学城文档。支持四种模式：直接内容、从文件读取、从模板创建、复制文档。

| 参数　　　　　 | 类型　 | 必填 | 默认值 | 说明　　　　　　　　　　　　　　　　　　　　　　　 |
| ----------------| --------| ------| --------| ----------------------------------------------------|
| `--title`　　　| string | ✅　　| —　　　| 文档标题　　　　　　　　　　　　　　　　　　　　　 |
| `--content`　　| string | 条件 | —　　　| 文档正文内容（支持 CitadelXML / 纯 Markdown） |
| `--file`　　　 | string | 条件 | —　　　| 从本地文件读取内容（优先于 `--content`，支持 `.xml` / `.md`） |
| `--templateId` | string | 条件 | —　　　| 从模板创建文档　　　　　　　　　　　　　　　　　　 |
| `--copyFrom`　 | string | 条件 | —　　　| 复制来源文档的 contentId　　　　　　　　　　　　　 |
| `--parentId`　 | string | —　　| —　　　| 父文档 ID（创建子文档时使用）　　　　　　　　　　　|
| `--spaceId`　　| string | —　　| —　　　| 目标空间 ID（不指定则使用个人空间）　　　　　　　　|

> `--content` / `--file` / `--templateId` / `--copyFrom` 至少提供一个。`--file` 优先级最高，会覆盖 `--content`。
>
> **内容格式自动识别**：`--content` / `--file` 支持多种格式，按以下顺序自动检测：
> 1. **CitadelXML**（以 `<km-doc` 或 `<doc` 开头）→ 通过 `citadelXmlToJson` 转换后提交（**推荐**）
> 2. **ProseMirror JSON**（合法 JSON 对象）→ 直接校验后提交
> 3. **普通 Markdown** → 通过转换后提交
>
> 模板来源是 `km.sankuai.com/collabpage/<id>` / `km.sankuai.com/page/<id>`（尤其学城文档2.0）时，优先使用 `--copyFrom <id>`，不要先读取内容后再通过 `--content` 重建。

```bash
# 根文档（CitadelXML 格式，推荐）
oa-skills citadel createDocument --title "方案" --file /tmp/new-doc.xml

# 根文档（纯文本内容）
oa-skills citadel createDocument --title "方案" --content "# 正文"

# 子文档
oa-skills citadel createDocument --title "子文档" --file /tmp/new-doc.xml --parentId "2748397739"

# 从文件（自动识别格式）
oa-skills citadel createDocument --title "文档" --file ./design.xml

# 指定空间
oa-skills citadel createDocument --title "文档" --content "# 正文" --spaceId "2506"

# 从模板
oa-skills citadel createDocument --title "周报" --templateId "template_123"

# 复制
oa-skills citadel createDocument --title "副本" --copyFrom "1234567890"

# 在目录下复制模板（推荐，保留 2.0 结构）
oa-skills citadel createDocument --title "测试文档" --copyFrom "2750769923" --parentId "2751336167"
```

**输出**：创建成功后一定要返回文档 ID 和文档链接，链接的拼接方式是`https://km.sankuai.com/collabpage/{pageId}`。

## getDocumentXml

获取文档的 CitadelXML 格式内容（**编辑场景推荐**，AI 理解更准确）。

CitadelXML 使用标准 HTML 标签（`<p>`、`<h1>`—`<h6>`、`<table>` 等）加 `km-` 前缀扩展标签表达学城专属宏，嵌套结构直观，AI 校验失败率更低。

> ⚠️ **仅支持 2.0 文档**（JSON 存储）。1.0 旧版文档格式不兼容，暂无 XML 编辑支持。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--output` | string | — | — | 将 CitadelXML 内容保存到本地文件路径（推荐，避免控制台截断） |

```bash
# 输出到控制台
oa-skills citadel getDocumentXml --contentId "1234567890"

# 保存到本地文件（推荐）
oa-skills citadel getDocumentXml --contentId "1234567890" --output doc.xml
```

**输出**：非 raw 模式下，文档标题/ID/CitadelXML 长度/stepVersion 输出到 stderr；若指定 `--output`，CitadelXML 内容写入该文件并输出保存路径；否则 CitadelXML 内容输出到 stdout。raw 模式输出包含 `{ contentId, title, xml, stepVersion }` 的 JSON。

> 此命令是文档 XML 编辑流程的第一步，返回的 `stepVersion` 应传给 `updateDocumentByXml --step-version` 以开启并发编辑保护。

## updateDocumentByXml

> ⚠️ **编辑文档内容的安全入口（CitadelXML 路径，推荐）。**
>
> 将 CitadelXML 格式内容转换回 ProseMirror JSON 后覆盖写入文档。
> 必须先通过 `getDocumentXml` 获取文档当前内容，修改后再回传。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `--contentId` | string | ✅ | 文档 ID |
| `--file` | string | 条件 | 从本地 `.xml` 文件读取内容（优先于 `--content`） |
| `--content` | string | 条件 | CitadelXML 格式的文档内容字符串 |
| `--title` | string | — | 同时更新文档标题（可选） |
| `--step-version` | number | — | 并发编辑保护版本号（从 `getDocumentXml` 返回的 `stepVersion` 获取，强烈建议传入） |

> `--file` 或 `--content` 至少提供一个。
>
> 传入 `--step-version` 后，执行前会检查文档当前版本是否一致；若中间有其他人修改了文档，则中断操作并报错，避免覆盖他人编辑。

```bash
# 第一步：获取文档 CitadelXML 内容（同时记录 stepVersion）
oa-skills citadel getDocumentXml --contentId "1234567890" --output doc.xml

# 第二步：编辑 doc.xml 文件（由 AI 修改内容）

# 第三步：回传更新（带并发保护）
oa-skills citadel updateDocumentByXml --contentId "1234567890" --file doc.xml --step-version <stepVersion>

# 同时更新标题
oa-skills citadel updateDocumentByXml --contentId "1234567890" --file doc.xml --title "新标题" --step-version <stepVersion>

# 不带并发保护（不推荐）
oa-skills citadel updateDocumentByXml --contentId "1234567890" --file doc.xml
```

**输出**：更新成功或失败的提示信息，以及文档链接（提醒用户刷新页面查看变更）。

## uploadImageToDocument

上传图片（本地文件或远程 URL）到指定学城文档，返回学城图片 URL 和可直接插入文档 XML 的图片节点。

> ⚠️ **严禁直接将非学城图片 URL 插入文档**。必须先调用此命令上传，再将返回的图片节点插入文档 XML。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 目标文档 ID（图片权限与文档绑定） |
| `--image` | string | ✅ | — | 本地图片路径或远程图片 URL（也可用 `--imageUrl`） |
| `--alt` | string | — | "图片" | 图片描述文字（alt 文本） |

```bash
# 上传本地图片
oa-skills citadel uploadImageToDocument --contentId "1234567890" --image "/path/to/image.png"

# 上传远程 URL 图片（AI 生成的图片等）
oa-skills citadel uploadImageToDocument --contentId "1234567890" --image "https://example.com/ai-image.png"

# 带描述文字
oa-skills citadel uploadImageToDocument --contentId "1234567890" --image "https://example.com/arch.png" --alt "架构图"
```

**输出**：学城图片 URL、图片尺寸（宽×高 px）、可直接插入文档的图片节点（`imageMd`）。

**完整插入流程**：

1. `uploadImageToDocument` 上传图片，获取图片节点
2. `getDocumentXml --contentId <id> --output doc.xml` 获取文档内容
3. 在 `doc.xml` 中插入图片节点
4. `updateDocumentByXml --contentId <id> --file doc.xml --step-version <stepVersion>` 回传

## uploadAttachmentToDocument

上传本地文件作为附件到指定学城文档，返回学城附件 URL 和可直接插入文档 XML 的附件节点。

> ⚠️ **严禁将非学城附件 URL 直接写入文档 XML**。必须先调用此命令上传，再将返回的附件节点插入文档 XML。
>
> **仅限非媒体文件（PDF、Word、Excel、ZIP 等）**。视频必须用 `uploadVideoToDocument`，音频必须用 `uploadAudioToDocument`，**绝对不可混用**，否则 URL 无法正确转换为 CDN 格式。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 目标文档 ID（附件权限与文档绑定） |
| `--file` | string | ✅ | — | 本地文件路径（仅限 PDF/Word/Excel/ZIP 等非媒体文件） |

```bash
oa-skills citadel uploadAttachmentToDocument --contentId "1234567890" --file "/path/to/report.pdf"
oa-skills citadel uploadAttachmentToDocument --contentId "1234567890" --file "/path/to/design.docx"
```

**输出**：学城附件 URL、附件 ID、下载直链、可直接插入文档的附件节点（`attachmentMd`）。

## uploadVideoToDocument

上传本地视频文件到指定学城文档，返回学城视频 CDN URL 和可直接插入文档 XML 的视频节点。

> ⚠️ **严禁将非学城视频 URL 直接写入文档 XML**。必须先调用此命令上传，再将返回的视频节点插入文档 XML。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 目标文档 ID（视频权限与文档绑定） |
| `--file` | string | ✅ | — | 本地视频文件路径 |
| `--size` | number | — | 自动检测 | 文件大小（字节），AI 预先获取后传入可加速上传 |

```bash
oa-skills citadel uploadVideoToDocument --contentId "1234567890" --file "/path/to/video.mp4"

# 指定文件大小（可选）
oa-skills citadel uploadVideoToDocument --contentId "1234567890" --file "/path/to/video.mp4" --size 52428800
```

**输出**：学城视频 CDN URL、视频附件 ID、转码任务 ID（jobId）、文件大小、可直接插入文档的视频节点（`videoMd`）。

## uploadAudioToDocument

上传本地音频文件到指定学城文档，返回学城音频 CDN URL 和可直接插入文档 XML 的音频节点。

> ⚠️ **严禁将非学城音频 URL 直接写入文档 XML**。必须先调用此命令上传，再将返回的音频节点插入文档 XML。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 目标文档 ID（音频权限与文档绑定） |
| `--file` | string | ✅ | — | 本地音频文件路径 |
| `--size` | number | — | 自动检测 | 文件大小（字节），AI 预先获取后传入可加速上传 |

```bash
oa-skills citadel uploadAudioToDocument --contentId "1234567890" --file "/path/to/audio.mp3"

# 指定文件大小（可选）
oa-skills citadel uploadAudioToDocument --contentId "1234567890" --file "/path/to/audio.mp3" --size 10485760
```

**输出**：学城音频 CDN URL、音频附件 ID、转码任务 ID（jobId）、文件大小、可直接插入文档的音频节点（`audioMd`）。

## deleteDocument

删除学城文档。仅文档所有者可以删除文档。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel deleteDocument --contentId "2748397739"
```

**输出**：删除成功或失败的提示信息，并明确告知用户删除了哪些文档，给出文档ID。并提示用户如果想撤销删除，可以跟我说撤销刚才删除的文档

## restoreDocument

撤销删除/恢复已删除的学城文档。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel restoreDocument --contentId "2748397739"
```

**输出**：恢复成功或失败的提示信息，如果撤销删除失败，给出文档ID。

## moveDocument

移动学城文档到新的父文档下。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 要移动的文档 ID |
| `--newParentId` | string | 条件 | — | 目标父文档 ID（移动到空间根目录时可不填） |
| `--newSpaceId` | string | 条件 | — | 目标空间 ID（移动到空间根目录时必填） |

```bash
oa-skills citadel moveDocument --contentId "2751172779" --newParentId "1440571964"
oa-skills citadel moveDocument --contentId "2751172779" --newSpaceId "23583"
```

**输出**：移动成功或失败的提示信息。并明确告知用户移动了哪些文档，给出文档ID。并提示用户如果想撤销移动，可以跟我说撤销刚才移动的文档

## setSecretLevel

设置学城文档密级。仅支持将密级设置为 C2、C3 或 C4。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--secret-level` | number | ✅ | — | 密级：`2`=C2（内部公开），`3`=C3（内部敏感），`4`=C4（内部机密） |

```bash
# 将文档设置为 C2 密级
oa-skills citadel setSecretLevel --contentId "2757266357" --secret-level 2

# 将文档设置为 C3 密级
oa-skills citadel setSecretLevel --contentId "2757266357" --secret-level 3

# 将文档设置为 C4 密级
oa-skills citadel setSecretLevel --contentId "2757266357" --secret-level 4
```

**输出**：设置成功后输出文档 ID、新密级标签和文档链接。

## getLatestEdit

获取最近编辑的文档列表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--offset` | number | — | 0 | 偏移量（从 0 开始） |
| `--limit` | number | — | 30 | 每页数量 |
| `--creator` | string | — | "" | 按创建者 MIS 过滤（空字符串表示当前用户） |

```bash
oa-skills citadel getLatestEdit
oa-skills citadel getLatestEdit --limit 10 --creator "zhangsan"
```

**输出**：文档标题、pageId、文档链接、文档类型（在线 WIKI/在线文档/学城文档2.0/多维表格）、修改时间、修改人。

> 当列表中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## getRecentlyViewed

获取最近浏览的文档列表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--pageNo` | number | — | 1 | 页码（从 1 开始） |
| `--pageSize` | number | — | 30 | 每页数量 |
| `--creator` | string | — | "" | 按创建者 MIS 过滤（空字符串表示当前用户） |

```bash
oa-skills citadel getRecentlyViewed
oa-skills citadel getRecentlyViewed --pageSize 10 --pageNo 2
```

**输出**：文档标题、pageId、文档链接、文档类型、浏览时间、作者。

> 当列表中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

> 注意：此命令用 `--pageNo`（从 1 开始），与其他命令的 `--offset`（从 0 开始）不同。

## getReceivedDocs

获取最近收到的文档列表（通过大象分享收到的）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--offset` | number | — | 0 | 偏移量（从 0 开始） |
| `--limit` | number | — | 30 | 每页数量 |

```bash
oa-skills citadel getReceivedDocs
oa-skills citadel getReceivedDocs --limit 10 --offset 30
```

**输出**：文档标题、contentId、文档链接、发送人、会话名（大象群名/个人名）、收到时间。

> 当列表中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## getDiscussionComments

获取文档划词评论（讨论列表）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--pageNo` | number | — | 1 | 页码（从 1 开始） |
| `--pageSize` | number | — | 100 | 每页评论数 |

```bash
oa-skills citadel getDiscussionComments --contentId "2746799101"
oa-skills citadel getDiscussionComments --contentId "2746799101" --pageNo 1 --pageSize 50
```

**输出**：每条评论的 commentId、创建人、引用文本、评论内容（原始 JSON doc 格式）、时间、解决状态、回复列表。

> 当文档含有 C4 级别内容时，接口返回可见的部分评论，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## getFullTextComments

获取文档全文评论。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--offset` | number | — | 0 | 偏移量（从 0 开始） |
| `--limit` | number | — | 10 | 每页评论数 |

```bash
oa-skills citadel getFullTextComments --contentId "2746799101"
oa-skills citadel getFullTextComments --contentId "2746799101" --offset 10 --limit 20
```

**输出**：每条评论的 commentId、创建人、评论内容（纯文本）、时间、回复列表。

> 当文档含有 C4 级别内容时，接口返回可见的部分评论，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## getAllComments

获取文档的所有评论（包含划词评论和全文评论）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getAllComments --contentId "2746799101"
```

**输出**：划词评论列表和全文评论列表。

## deleteFullTextComment

删除指定全文评论（单条）。

> ⚠️ **高风险操作**：删除不可撤销，**必须先 `getFullTextComments` 获取评论内容，向用户展示后获得明确确认再执行**。每次只能删除一条，禁止批量循环调用。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--commentId` | string | ✅ | — | 要删除的评论 ID（从 `getFullTextComments` 返回结果中获取） |

```bash
# 第一步：先获取评论列表，确认要删除的评论 ID 和内容
oa-skills citadel getFullTextComments --contentId "2755005703"

# 第二步：向用户展示评论内容并获得确认后，执行删除
oa-skills citadel deleteFullTextComment --contentId "2755005703" --commentId "234516644682"
```

**输出**：删除成功提示，并提醒用户删除操作不可撤销。

## deleteDiscussionComment

删除指定划词评论（或划词评论下的回复），单条操作。

> ⚠️ **高风险操作**：删除不可撤销，**必须先 `getDiscussionComments` 获取评论内容，向用户展示后获得明确确认再执行**。每次只能删除一条，禁止批量循环调用。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--discussionId` | string | ✅ | — | 划词评论的 discussion ID（对应 `getDiscussionComments` 返回的顶层 `commentId` 字段） |
| `--commentId` | string | ✅ | — | 要删除的具体评论 ID（删除主评论时与 `--discussionId` 相同；删除回复时填 `replies[].commentId`） |
| `--quoteId` | string | ✅ | — | 删除主评论时传空字符串 `""`；删除回复时传 `replies[].quoteId` |

```bash
# 第一步：先获取划词评论列表，确认 discussionId、commentId、quoteId
oa-skills citadel getDiscussionComments --contentId "2755005703"

# 第二步：向用户展示目标评论内容并获得确认后执行

# 删除划词评论主评论（quoteId 传空字符串）
oa-skills citadel deleteDiscussionComment \
  --contentId "2755005703" \
  --discussionId "2055228693043486770" \
  --commentId "2055228693068623933" \
  --quoteId ""

# 删除划词评论下的回复（quoteId 从 replies[].quoteId 获取）
oa-skills citadel deleteDiscussionComment \
  --contentId "2755005703" \
  --discussionId "2055228693043486770" \
  --commentId "2056571577902538821" \
  --quoteId "2755005703-node--94a9a6837b0d49fb8ec5b475d01181f3"
```

**输出**：删除成功提示，并提醒用户删除操作不可撤销。

**参数获取方式**：
- `discussionId` = `getDiscussionComments` 返回的顶层 `commentId`
- 删除主评论：`commentId` = `discussionId`，`quoteId` = `""`
- 删除回复：`commentId` = `replies[].commentId`（或同一字段），`quoteId` = `replies[].quoteId`

## getDocumentStats

获取文档的统计信息（浏览量、评论数、创作时长等）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getDocumentStats --contentId "2746799101"
```

**输出**：关注人数、收藏人数、浏览人数、浏览次数、评论数量、创作时长。

## getDocumentMetaInfo

获取文档元信息，包括父文档 ID、标题、创建者、所有者、创建时间、最后编辑时间等。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getDocumentMetaInfo --contentId "1982700288"
```

**输出**：文档标题、文档ID、创建者、所有者、最后编辑者、创建时间、最后编辑时间、所属空间ID、父文档ID（及父文档链接）。

**父文档权限说明**：若返回的 `parentId` 为 `0`，表示该文档位于空间根目录，或当前用户没有查看父文档的权限，此时无法获取父文档信息，应告知用户无父文档查看权限。

## getSpaceIdByMis

根据 MIS 号获取学城个人空间 ID。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--targetMis` | string | ✅ | — | 目标用户的 MIS 号 |

```bash
oa-skills citadel getSpaceIdByMis --targetMis "misId"
```

**输出**：用户的个人空间 ID。

## getSpaceRootDocs

获取空间根目录文档列表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--spaceId` | string | ✅ | — | 空间 ID |

```bash
oa-skills citadel getSpaceRootDocs --spaceId "23583"
```

**输出**：空间根目录文档列表，包含文档标题、文档ID、文档链接、文档类型、创建人以及创建时间。

> 当空间中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## audit

盘点指定空间、目录或单篇文档的权限，输出学城报告文档。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间、目录或文档 URL |
| `--secret-level` | number | — | — | 按文档密级过滤，范围 `0-5` |
| `--start-time` | string | — | — | 创建时间起始，格式 `YYYY-MM-DD` |
| `--end-time` | string | — | — | 创建时间截止，格式 `YYYY-MM-DD` |
| `--creators` | string | — | — | 按创建人 MIS 过滤，逗号分隔 |

```bash
oa-skills citadel audit --url "https://km.sankuai.com/collabpage/2750138424"
oa-skills citadel audit --url "https://km.sankuai.com/space/XOPEN" --secret-level 4
```

**输出**：学城报告文档链接。执行前要告知用户会创建报告文档。

## grant

批量授予显式权限。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间、目录或文档 URL |
| `--perm` | string | ✅ | — | 权限类型：`仅浏览` / `可浏览、评论` / `可编辑` / `可编辑、添加` / `可编辑、添加、删除` / `可管理` |
| `--person` | string | 条件 | — | 个人 MIS，逗号分隔 |
| `--dept` | string | 条件 | — | 部门全路径 |
| `--xm-group-ids` | string | 条件 | — | 大象群 ID，逗号分隔 |
| `--mails` | string | 条件 | — | 邮件组，逗号分隔 |
| `--app-ids` | string | 条件 | — | 应用 ID，逗号分隔 |
| `--account-types` | string | 条件 | — | 账号类型，逗号分隔 |
| `--org-roles` | string | — | — | 部门岗位族，逗号分隔 |
| `--contract-types` | string | — | `101` | 部门合同类型，逗号分隔 |
| `--country` | string | — | `CHN` | 部门国家，逗号分隔 |

> `--person` / `--dept` / `--xm-group-ids` / `--mails` / `--app-ids` / `--account-types` 六选一。

```bash
oa-skills citadel grant --url "https://km.sankuai.com/collabpage/2750138424" --person "lisi" --perm "可编辑"
oa-skills citadel grant --url "https://km.sankuai.com/collabpage/2750138424" --xm-group-ids "70411238253" --perm "仅浏览"
```

**输出**：成功/失败统计、备份文档链接；失败时附失败清单链接。

## modify

批量把目标对象已有的权限改成新权限。参数与 `grant` 基本一致，额外行为是:

- 只会修改“当前已经存在权限记录”的文档
- 没有命中权限记录的文档会计入 `skipped`

```bash
oa-skills citadel modify --url "https://km.sankuai.com/collabpage/2750138424" --person "lisi" --perm "可管理"
```

## revoke

批量移除目标对象已有的显式权限。目标参数与 `grant` 相同，但不需要 `--perm`。

```bash
oa-skills citadel revoke --url "https://km.sankuai.com/collabpage/2750138424" --person "lisi"
```

## inherit

移除或恢复文档权限继承。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 文档或目录 URL |
| `--action` | string | ✅ | — | `remove` 或 `restore` |
| `--keep-existing` | boolean | — | `true` | 恢复继承时是否保留已有显式权限 |

```bash
oa-skills citadel inherit --url "https://km.sankuai.com/collabpage/2750138424" --action remove
oa-skills citadel inherit --url "https://km.sankuai.com/collabpage/2750138424" --action restore --keep-existing false
```

## audit-resigned

盘点离职员工创建的文档，输出学城报告文档。过滤参数与 `audit` 一致。

```bash
oa-skills citadel audit-resigned --url "https://km.sankuai.com/space/XOPEN"
```

## transfer-owner

批量转移文档所有者。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间、目录或文档 URL |
| `--target-mis` | string | ✅ | — | 新所有者 MIS |
| `--secret-level` | number | — | — | 密级过滤 |
| `--start-time` | string | — | — | 创建时间起始 |
| `--end-time` | string | — | — | 创建时间截止 |
| `--creators` | string | — | — | 创建人过滤 |

```bash
oa-skills citadel transfer-owner --url "https://km.sankuai.com/space/XOPEN" --target-mis "lisi"
```

## clear-perm

一键清空显式权限，仅保留所有者和空间管理员，并尝试关闭链接分享权限。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间、目录或文档 URL |
| `--secret-level` | number | — | — | 密级过滤 |
| `--start-time` | string | — | — | 创建时间起始 |
| `--end-time` | string | — | — | 创建时间截止 |
| `--creators` | string | — | — | 创建人过滤 |

```bash
oa-skills citadel clear-perm --url "https://km.sankuai.com/collabpage/2750138424"
```

**输出**：成功/失败统计、备份文档链接。执行前必须明确提示高风险。

## share-perm

批量设置“获得链接的任何人”的访问权限。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间、目录或文档 URL |
| `--status` | number | ✅ | — | `0` 关闭，`1` 开启 |
| `--perm` | number | 条件 | `0` | 开启时必填，`0=可浏览、评论`，`1=可编辑`，`5=仅浏览` |

```bash
oa-skills citadel share-perm --url "https://km.sankuai.com/collabpage/2750138424" --status 1 --perm 5
oa-skills citadel share-perm --url "https://km.sankuai.com/collabpage/2750138424" --status 0
```

> 学城 1.0 文档不支持此命令，会自动跳过。

## space-admin

增加或移除空间管理员。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--url` | string | ✅ | — | 空间 URL，仅支持 `/space/...` |
| `--action` | string | ✅ | — | `add` 或 `remove` |
| `--person` | string | ✅ | — | 目标管理员 MIS，逗号分隔 |

```bash
oa-skills citadel space-admin --url "https://km.sankuai.com/space/XOPEN" --action add --person "lisi"
oa-skills citadel space-admin --url "https://km.sankuai.com/space/XOPEN" --action remove --person "lisi"
```

## getMentionedDocs

获取用户被@的文档列表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--offset` | number | — | 0 | 偏移量（从 0 开始） |
| `--limit` | number | — | 30 | 每页数量 |

```bash
oa-skills citadel getMentionedDocs
oa-skills citadel getMentionedDocs --limit 10 --offset 30
```

**输出**：文档标题、contentId、文档链接、最近被@时间、@次数。

> 当列表中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## getCommentedDocs

获取我评论过的文档列表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--offset` | number | — | 0 | 偏移量（从 0 开始） |
| `--limit` | number | — | 30 | 每页数量 |

```bash
oa-skills citadel getCommentedDocs
oa-skills citadel getCommentedDocs --limit 10 --offset 30
```

**输出**：文档标题、contentId、文档链接、最近评论时间、评论次数。

> 当列表中含有 C4 级别文档时，接口返回可见的部分数据，并附带 `warning` 字段提示数据不完整。如果 `warning` 存在，**必须将该警告展示给用户**。

## listTools

列出可用的 MCP 工具列表。无额外参数。

```bash
oa-skills citadel listTools
```

## getDocumentVersions

获取文档历史版本列表，按时间降序，最多返回 200 条，不支持翻页（防止频繁请求）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel getDocumentVersions --contentId "1234567890"
```

**输出**：历史版本列表，每条包含：版本号（`version`）、标题（`title`，如 "05月14日 09:16"）、协作步骤版本号（`stepVersion`，**获取版本内容时使用此字段**）、生成时间、编辑者列表（`name` + `mis`）、版本说明（`whatUpdate`）。

> `stepVersion` 与 `version` 是不同字段：`version` 是文档级整数递增版本号，`stepVersion` 是协作步骤级版本号，获取特定版本内容时**必须**使用 `stepVersion`。

## getDocumentVersionContent

获取指定历史版本的文档 JSON 内容（ProseMirror JSON 格式）。`stepVersion` 来自 `getDocumentVersions` 返回结果。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--stepVersion` | number | ✅ | — | 协作步骤版本号（从 `getDocumentVersions` 的 `stepVersion` 字段获取） |

```bash
oa-skills citadel getDocumentVersionContent --contentId "1234567890" --stepVersion 23
```

**输出**：非 raw 模式下，版本信息输出到 stderr，ProseMirror JSON 正文输出到 stdout。raw 模式输出 `{ contentId, versionTitle, stepVersion, version, body }` 的 JSON。

## getDocumentVersionXml

获取指定历史版本的文档 CitadelXML 内容，内部自动将历史版本 JSON 转换为 CitadelXML 格式。可直接传给 `updateDocumentByXml` 用于还原文档版本。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--stepVersion` | number | ✅ | — | 协作步骤版本号（从 `getDocumentVersions` 的 `stepVersion` 字段获取） |
| `--output` | string | — | — | 将 CitadelXML 内容保存到本地文件路径（推荐，内容较大时避免上下文过长） |

```bash
# 直接输出到 stdout
oa-skills citadel getDocumentVersionXml --contentId "1234567890" --stepVersion 23

# 保存到本地文件（推荐）
oa-skills citadel getDocumentVersionXml --contentId "1234567890" --stepVersion 23 --output /tmp/version-23.xml
```

**输出**：非 raw 模式下，版本信息（版本标题、CitadelXML 长度）输出到 stderr，并提示后续还原命令；若指定 `--output`，CitadelXML 写入该文件并输出保存路径；否则 CitadelXML 输出到 stdout。raw 模式输出 `{ contentId, versionTitle, stepVersion, version, xml }` 的 JSON。

**还原文档版本完整流程**：

```bash
# Step 1: 查看历史版本列表，找到目标版本的 stepVersion
oa-skills citadel getDocumentVersions --contentId "1234567890"

# Step 2: 获取该历史版本的 CitadelXML 并保存到本地
oa-skills citadel getDocumentVersionXml --contentId "1234567890" --stepVersion 23 --output /tmp/restore.xml

# Step 3: 使用保存的 XML 还原文档（覆写当前内容）
oa-skills citadel updateDocumentByXml --contentId "1234567890" --file /tmp/restore.xml
```

> ⚠️ 还原操作会覆盖文档当前内容，执行前应与用户确认目标版本（时间、编辑者）。
