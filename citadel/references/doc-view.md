# 理解学城文档内容（getSimpleMarkdown 阅读指南）

通过 `getSimpleMarkdown` 获取的文档内容为简化版 Markdown，专供阅读和总结使用。各类节点已转换为标准或接近标准的 Markdown 格式，按以下方式理解。

## 文字与结构

- **文档标题**：转换为 `# 标题` （H1），位于正文最前面
- **章节标题**：`## 章节` 到 `###### 章节`（H2～H6），代表文档层级结构（由于 H1 已被文档标题占用，正文中 heading level 1 输出为 H2，以此类推）
- **普通段落、列表、引用、代码块**：与标准 Markdown 含义相同
- **折叠块**：输出为 blockquote 形式，标题行带 📂 图标，后续内容同样缩进为 blockquote：
  ```
  > **📂 折叠块（默认展开）：折叠标题**
  > 折叠内容…
  ```
  `（默认展开）` 或 `（默认折叠）` 表示初始展开状态；**两部分内容都要读取，不能只看标题**
- **提示框**：输出为 blockquote 形式，图标和前缀表明类型：
  - `> **ℹ️ 信息：标题**` → info 类型
  - `> **⚠️ 警示：标题**` → note 类型
  - `> **❗ 注意：标题**` → warning 类型
  - `> **💡 提示：标题**` → tip 类型

## 图片

- 标准图片语法：`![描述](url)` 或 `![描述](url) (宽×高)`
  - `alt` 文字（方括号内）是图片的描述/名称，如有应在理解时参考
  - 图片 URL 来自学城存储，通常形如 `https://km.sankuai.com/api/file/cdn/...`
  - 当文档中出现图片时，需告知用户该图片的描述文字和位置，说明"文档在此处包含一张图片：[描述]"
  - 若需要理解图片内容（如截图、图表），**不可直接通过 fetch/curl 下载**——学城图片有鉴权保护，必须通过以下 CLI 命令获取：
    - **小图片（≤ 4MB）**：返回 base64，直接用于视觉识别
      ```
      oa-skills citadel fetchImage --imageUrl "<图片URL>"
      ```
      返回 JSON 中的 `dataUri` 字段（`data:<mimeType>;base64,...`）可直接用于视觉识别。图片超过 1MB 时命令会提示建议使用 `--save`。
    - **大图片（> 4MB）或为节省 token**：保存到本地后读取
      ```
      oa-skills citadel fetchImage --imageUrl "<图片URL>" --save /tmp/km-image.png
      ```
      此时命令返回 `savedTo` 字段（本地文件绝对路径）和 `deleteAfterUse: true`。超过 4MB 时命令会强制要求使用 `--save`。
      > ⚠️ **安全强制要求**：命令输出中 `deleteAfterUse: true` 表示该文件含学城敏感数据。**读取并识别图片内容后，必须立即执行删除**：
      > ```
      > rm -f "<savedTo 路径>"
      > ```
      > 禁止跳过删除步骤，禁止将文件留在本地磁盘。

## 媒体与附件

媒体和附件节点均输出为 blockquote 形式，包含文件名和 URL：

- **音频**：`> 🎵 **音频附件**：[文件名](url)` — 关注文件名理解内容，说明文档包含音频文件
- **视频**：`> 🎬 **视频附件**：[文件名](url)` — 关注文件名理解内容，说明文档包含视频文件
- **附件**：`> 📎 **附件**（大小）：[文件名](url)` — 关注文件名和大小；若需要下载或读取附件内容，分别参考以下两个独立场景

---

### 场景 A：下载学城文档附件

用户需要将附件文件保存到本地时，执行以下步骤。

> 🚫 **绝对禁止路径**：禁止通过任何方式（fetch、curl、浏览器自动化等）直接尝试下载学城附件。**必须且只能通过文枢 skill 处理所有附件下载请求。**

#### 步骤 A-1：提取附件 fileId

找到文档中的附件节点：

```
> 📎 **附件**（大小）：[文件名](https://km.sankuai.com/api/file/cdn/<contentId>/<fileId>?contentType=0)
```

从 URL 中提取 `fileId`：URL 形如 `.../cdn/<contentId>/<fileId>?...`，其中**`?` 前最后一段数字**即为 `fileId`。

#### 步骤 A-2：查询文枢安全下载策略

```
oa-skills citadel fetchAttachment --fileId "<fileId>"
```

命令返回 JSON，关注以下字段：
- `wenshuUrl`：文枢安全下载链接（形如 `cryptbox://...` 或 `https://cryptbox.sankuai.com/...`），**下一步必须用此链接**
- `checkResult`：校验结果（`"PASS"` 表示可下载）
- `executionWay`：执行方式（`"WENSHU"` 表示需要文枢处理）

> ⚠️ 若 `checkResult` 不为 `"PASS"` 或接口报错，**立即停止**，告知用户当前账号无权下载该附件。

#### 步骤 A-3：通过文枢 skill 下载文件

将 `wenshuUrl` 传入文枢 skill 执行下载：

1. 优先调用 `wenshu-tools` skill，传入 `wenshuUrl`
2. 若 `wenshu-tools` 不可用，尝试 `wenshu-catdesk-tools` skill
3. 若两个 skill 均不可用，**停止所有下载尝试**，提示用户：
   > "该附件需要通过文枢 skill 才能下载。请访问 https://friday.sankuai.com/skills/skills-market 先安装 `wenshu-tools` 或 `wenshu-catdesk-tools` skill 后再试。"

文枢 skill 成功后会将文件保存到本地，并返回本地文件路径。

---

### 场景 B：读取学城文档附件内容

用户需要 AI 解析附件文字内容（如 PDF 正文、Word 内容等）时，在完成场景 A 的下载后继续执行以下步骤。

#### 步骤 B-1：完成附件下载

按场景 A 的步骤 A-1 → A-2 → A-3 完成下载，取得文枢 skill 返回的本地文件路径（如 `/tmp/filename.pdf`）。

#### 步骤 B-2：根据文件类型解析内容

- **PDF 文件**（`.pdf`）：调用 `pdf` skill 读取内容，传入本地文件路径
- **Word 文件**（`.docx`）：调用 `docx` skill 读取内容
- **Excel/表格文件**（`.xlsx`、`.csv`）：调用 `xlsx` skill 读取内容
- **其他文本类文件**（`.txt`、`.md`、代码文件等）：直接用 `read_file` 工具读取本地文件路径

> 若无对应 skill 且文件为不可直接读取的二进制格式，告知用户"暂无法解析该格式，文件已保存至 `<本地路径>`，请手动打开"。

#### 步骤 B-3：清理本地临时文件

读取并处理完文件内容后，**必须立即删除本地临时文件**：

```bash
rm -f "<步骤 B-1 返回的本地文件路径>"
```

> ⚠️ **安全强制要求**：学城附件属于内部敏感数据，禁止将临时文件长期留存在本地磁盘。即使步骤 B-2 解析失败，也必须执行清理。

## 图表与特殊组件

图表和特殊组件均输出为 blockquote 占位形式：

- **PlantUML 图表**：以代码块形式输出，内部是 PlantUML 语法，需要解读图表描述的流程/架构/关系：
  ````
  ```PlantUML
  图表内容…
  ```
  ````
- **Drawio 流程图**：`> 📊 **流程图（Drawio）**：<url>` — `url` 为流程图源文件地址，可通过以下命令获取流程图完整数据：
  ```
  oa-skills citadel fetchDrawio --drawioUrl "<url>"
  ```
  命令返回 `mxGraphXml`（流程图完整结构数据，理解和修改流程图均应基于此字段）和 `svgContent`（原始 SVG 文本，可作补充参考）
- **脑图（Minder）**：`> 🧠 **脑图（Minder）**：<url>` — 无法直接读取内容，告知用户"文档在此处包含一张思维导图"
- **甘特图**：`> 📅 **甘特图**（id: ...）` — 无法读取详情，告知用户"文档在此处包含一张甘特图"
- **数据图表**：`> 📈 **数据图表**（chartId: <chartId>）` — 可获取图表的完整表格数据，详见下方"数据图表"章节
- **数学公式（块级）**：`$$\n公式\n$$` — 理解其数学含义并用自然语言描述
- **数学公式（行内）**：`$公式$` — 同上，尝试用自然语言描述

## 表格

- **标准 Markdown 表格**（`| 列1 | 列2 |` 格式）：直接读取
- **含合并单元格的表格**：输出顶部会有 `⚠️ 此表格含合并单元格，以下为简化显示` 警告，colspan/rowspan 合并信息已丢失，相关单元格内容平铺展示；若需完整合并结构，使用 `getDocumentXml` 查看
- **嵌套表格 / 单元格内宏节点（折叠块、提示框、媒体等）**：嵌入内容会被压缩为单行文本，文字内容可理解，但层级和格式结构丢失；若需完整层级结构，使用 `getDocumentXml` 查看

## 行内元素

- **提及用户**：输出为 `@用户名`，直接读取 @ 后的名称
- **日期引用**：输出为 `YYYY-MM-DD`（带时间时为 `YYYY-MM-DD HH:MM`）
- **状态标签**：输出为图标 + 文字，例如 `✅ 已完成`、`⚠️ 进行中`、`❌ 已取消`
- **链接**：输出为标准 Markdown `[文字](url)`，读取链接文字及目标 URL
- **表情**：输出为 `:name:` 格式，根据名称理解表情含义
- **行内数学公式**：`$公式$`，尝试用自然语言描述含义
- **行内代码**：反引号包裹的代码片段
- **加粗/斜体/删除线/下划线**：标准 Markdown 格式，直接理解
- **颜色/背景色/字体样式**：样式属性已被忽略，只保留内部文字

## 占位与系统节点

以下节点输出为简短的 blockquote 占位说明，直接按说明理解即可：

- `> 📑 **文档目录**`：自动生成的目录组件，跳过即可
- `> 🌳 **文档目录树**`：展示子文档结构，说明"文档在此处包含子文档目录"
- `> 📋 **多维表格**（id: ...）`：嵌入的多维表格引用，告知用户"文档在此处嵌入了多维表格"
- `> 🔄 **空间更新卡片**`：空间动态卡片，跳过即可
- `> 📌 **附录区域**`：附录标记，如后续有脚注内容可说明
- `> ⚠️ **不支持的宏节点（...）**`：不支持的宏，跳过，不需要提及
- `> 🔗 **嵌入内容**：<url>` / `> 🔗 **链接卡片**：[标题](url)` / `> 🃏 **嵌入卡片**：<url>`：嵌入的外部内容，告知用户"文档在此处嵌入了外部内容"
- **脚注**：输出在文末分隔线后，格式为列表，如有内容可说明
- `> 🎙️ **听写 block**（blockId: ...）`：会议录音转写 block，**内容已自动内联展示**（`getSimpleMarkdown` 会自动获取并替换为实际转写稿和笔记）；若用户希望**单独获取**某个听写 block 的内容，参见下方"听写 Block"章节
- `> 🔗 **同步 block**（blockId: ...）`：非听写类型的同步 block，内容无法自动展开，告知用户"文档在此处包含一个同步 block"

---

## 听写 Block（转写稿与笔记）

学城文档中的听写 block（`sync_block`，blockType=1）包含会议录音转写稿和手动笔记。`getSimpleMarkdown` 会**自动内联**获取并展示这些内容，无需额外操作。

若需要**单独读取**某个听写 block 的转写稿和笔记（例如用户指定了 blockId，或需要二次处理转写内容），使用以下命令：

```
oa-skills citadel getBlockTranscript --contentId "<文档ID>" --blockId "<blockId>"
```

参数说明：
- `--contentId`：包含该听写 block 的文档 ID（从文档 URL 提取，如 `km.sankuai.com/collabpage/<contentId>`）
- `--blockId`：听写 block 的 ID（从简化 Markdown 占位行 `blockId: <id>` 中提取）

命令输出格式（非 `--raw` 模式）：

```
转写稿
说话人1：喂，听到吗？
说话人1：可以，因为我也说不上嘛，要不投个屏吧……
说话人2：好的，稍等一下。

笔记
这里是手动记录的笔记内容。
```

- **转写稿**：按发言顺序列出每条语句，格式为 `说话人X：文字内容`；若任务尚未完成或无转写内容，输出 `（无转写内容或任务尚未完成）`
- **笔记**：会议中手动添加的文字笔记；若无笔记，此部分不输出

使用 `--raw` 可获取原始 JSON，包含完整的转写片段列表（`info.textContent`）和笔记结构（`info.textNote`），适合需要精细处理的场景（如按时间轴筛选、提取特定说话人发言等）。

---

## 数据图表

学城文档中的数据图表在 `getSimpleMarkdown` 输出中表示为：

```
> 📈 **数据图表**（chartId: <chartId>）
```

若需要读取图表的具体数据，使用以下命令：

```
oa-skills citadel getChartData --contentId "<文档ID>" --chartId "<图表ID>"
```

参数说明：
- `--contentId`：包含该数据图表的文档 ID（从文档 URL 提取，如 `km.sankuai.com/collabpage/<contentId>`）
- `--chartId`：图表 ID（从简化 Markdown 占位行 `chartId: <chartId>` 中提取）

### 命令返回结构

**`chartData`（数据部分，所有图表类型结构统一）**

- `chartData.head`：列头定义数组，每项包含：
  - `name`：列名（如 `"日期"`、`"项目A"`）
  - `alias`：别名（可能为 `null`）
  - `key`：内部唯一 key（与 `config.label.dataConfig` 中的 key 对应，用于确定各列的角色）
  - `type`：列类型（`1` = 文本/日期维度列，`3` = 数值列）
- `chartData.body`：数据行二维数组，每行按 `head` 顺序依次存放各列的值，例如 `[["2019-10-01", 434, 534], ...]`
- `chartData.count`：总行数

**`config`（图表配置部分）**

- `config.type`：图表类型，**可以是字符串或字符串数组**：
  - 字符串（单一类型）：`"bar"` 柱状图、`"line"` 折线图、`"area"` 面积图、`"stack"` 堆叠图、`"rotatingBar"` 条形图（横向）、`"pie"` 饼图、`"ring"` 环图、`"funnel"` 漏斗图、`"nightingale"` 南丁格尔图
  - 数组（混合图表，每个元素对应一个数值系列的子类型）：如 `["line", "bar"]` 折线+柱状混合图、`["line", "scatter"]` 折线+散点混合图
- `config.label.dataConfig.dimension`：维度（分类）字段配置，`values` 中的 key 对应 `head` 中 `type=1` 的分类列
- `config.label.dataConfig.number`：数值系列配置，`values` 中的 key 对应 `head` 中 `type=3` 的数值列；混合图表中每个 `dataSource[i].settings.chartType` 指定该系列的子图表类型
- `config.title.text`：图表标题（未设置时为 `"Untitled chart"`）

使用 `--raw` 可获取完整 JSON（含完整 config 配置），适合需要深入分析图表结构的场景。

### 如何解读不同类型图表的数据

**有轴图表（`bar`、`line`、`area`、`stack`、`rotatingBar`、混合图）**：
- `dimension`（分类维度列）→ X 轴标签（如日期、类别名称）
- `number`（数值列，可多列）→ 各系列 Y 轴数据
- `body` 中每行 = 一个 X 轴刻度点上各系列的值

**无轴图表（`pie`、`ring`、`nightingale`、`funnel`）**：
- 数据格式与有轴图表完全相同，无需特殊处理
- `dimension`（分类维度列）→ 扇区/分段的标签名
- `number`（数值列）→ 扇区/分段的大小值；多个数值列对应多组数据系列
- `body` 中每行 = 一个分类的各系列值

### 读取数据图表的完整流程

1. 通过 `getSimpleMarkdown` 获取文档内容，找到 `> 📈 **数据图表**（chartId: <chartId>）` 占位行
2. 从文档 URL 提取 `contentId`，从占位行提取 `chartId`
3. 调用 `getChartData --contentId <contentId> --chartId <chartId>`
4. 先读 `config.type` 判断图表类型（注意可能是数组）
5. 通过 `chartData.head` 与 `config.label.dataConfig` 的 key 对应关系，确认哪列是维度、哪列是各数值系列
6. 读取 `chartData.body` 获取具体数值
7. 向用户描述：图表类型、分类维度（列名/值）、各数值系列（列名/值），以及数据的整体趋势或分布情况
