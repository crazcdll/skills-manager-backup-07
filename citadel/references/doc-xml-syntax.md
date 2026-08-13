# CitadelXML 格式语法参考

CitadelXML 是学城文档的 XML 编辑格式，用于在 AI 编辑场景下使用，具有以下优势：

- 使用标准 HTML 标签（`p`, `h1-h6`, `ul`, `ol`, `table`），AI 预训练知识直接适用
- 使用 `km-` 前缀的扩展标签（`km-collapse`, `km-note`）表达学城专属宏
- XML 嵌套结构直观，更方便AI进行编辑
- 完整保留 `nodeId` 等关键属性，确保回传后文档结构完全还原

## 获取与回传流程

```bash
# 第一步：获取文档 XML（同时获取 stepVersion 用于并发保护）
oa-skills citadel getDocumentXml --contentId <id> --output doc.xml

# 第二步：由 AI 编辑 doc.xml 文件

# 第三步：回传更新文档
oa-skills citadel updateDocumentByXml --contentId <id> --file doc.xml

# 可选：同时更新文档标题
oa-skills citadel updateDocumentByXml --contentId <id> --file doc.xml --title "新标题"

# 可选：并发保护（传入 getDocumentXml 返回的 stepVersion）
oa-skills citadel updateDocumentByXml --contentId <id> --file doc.xml --step-version 42
```

## 根节点

整个文档以 `<km-doc>` 为根节点：

```xml
<km-doc>
  <km-title nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">文档标题</km-title>
  <h1 nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">第一章</h1>
  <p nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">段落内容</p>
</km-doc>
```

## 编辑规则（必须遵守）

### 基本原则

1. **每次编辑必须重新拉取**：禁止基于对话记忆中的旧内容直接发起覆盖写入
2. **先读后改**：必须先 `getDocumentXml`，禁止凭空生成整篇文档内容覆盖回传
3. **最小改动**：只修改用户明确要求的那几处；无关节点、属性、顺序一律保持原样
4. **保留 nodeId**：所有已有节点的 `nodeId` 属性必须保留；新增节点可省略 `nodeId`（系统自动生成）
5. **不做格式化重写**：禁止把整篇内容"重新整理"为另一种等价写法

### 文档标题

- `<km-title>` 必须是 `<km-doc>` 的**第一个子节点**，有且只有一个
- 修改文档标题时，需同时修改 `<km-title>` 内容 AND 在 `updateDocumentByXml` 传 `--title` 参数

```xml
<km-title nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">我的文档标题</km-title>
```

## 块级节点

### 段落

```xml
<p nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">普通段落内容</p>

<!-- 带对齐和缩进 -->
<p nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" align="center" indent="1">居中缩进段落</p>
```

### 标题（h1-h6）

```xml
<h1 nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">一级标题</h1>
<h2 nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">二级标题</h2>
<h3 nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">三级标题</h3>
```

### 列表

```xml
<!-- 无序列表 -->
<ul nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <li nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">
    <p nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">列表项内容</p>
  </li>
  <li nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">
    <p nodeId="e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b">另一个列表项</p>
  </li>
</ul>

<!-- 有序列表 -->
<ol nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <li nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">
    <p nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">第一项</p>
  </li>
</ol>

<!-- 任务列表：必须在 <ul> 上写 data-task-list="true"，在 <li> 上写 data-checked -->
<!-- ⚠️ 禁止使用 <km-task-list> 或 <km-task-item> 等非标准形式 -->
<ul data-task-list="true" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <li data-checked="false" nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">
    <p nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">未完成任务</p>
  </li>
  <li data-checked="true" nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">
    <p nodeId="e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b">已完成任务</p>
  </li>
</ul>
```

### 引用块

```xml
<blockquote nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <p nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">引用内容</p>
</blockquote>
```

### 代码块

> ⚠️ **必须使用 `<pre><code>` 格式**，禁止写成 `<km-code-block>` 或 `<code-block>` 等其他形式。

```xml
<!-- language / title / theme 均不能省略，必须显式写出 -->
<pre language="TypeScript" title="代码块" theme="xq-light" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"><code>const hello = "world";
console.log(hello);</code></pre>

<!-- 自定义标题示例 -->
<pre language="Python" title="示例代码" theme="xq-light" nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"><code>print("hello")</code></pre>
```

> **`code_block` 属性约束**：
> - `language` **不能为 `null`**，未指定时必须使用字符串 `"Plain Text"`
> - `theme` **不能为 `null`**，未指定时必须使用字符串 `"xq-light"`
> - `title` 必须是一行纯文本，不能包含换行符；未指定时使用 `"代码块"`
> - ⚠️ **`language` 大小写必须严格匹配**，例如必须写 `"Mermaid"` 而非 `"mermaid"`，`"Plain Text"` 而非 `"plain text"`，`"JavaScript"` 而非 `"javascript"`
> - 支持的 `language` 枚举值（共 40 种）：
>   `Plain Text`、`JavaScript`、`Java`、`JSON`、`Shell`、`HTML`、`PlantUML`、`Mermaid`、
>   `C`、`C++`、`C#`、`CSS`、`Dart`、`Elm`、`Go`、`Groovy`、`HTTP`、`JSX`、`Kotlin`、
>   `LaTeX`、`Lua`、`Markdown`、`Nginx`、`Objective-C`、`Perl`、`PHP`、`PowerShell`、
>   `Python`、`R`、`Ruby`、`Sass`、`Scala`、`SQL`、`Stylus`、`TypeScript`、`Swift`、
>   `Vue.js Component`、`XML`、`YAML`、`Mindmap`

### 分割线

```xml
<hr nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 表格

⚠️ **编辑表格时，禁止修改 `colspan` / `rowspan` / `colwidth` / `textAlign` / `verticalAlign` / `bgColor` / `color` / `numCell` 等结构属性**，除非用户明确要求改布局。

**新建表格规则**：
- 默认使用 `responsive="true"`（自适应宽度），不要使用 `responsive="false"`（固定宽度）。
- 新建表格的单元格（`<th>`/`<td>`）**不要指定 `colwidth` 属性**，学城会根据内容自动计算列宽。
- 只有在复制或编辑已有固定宽度表格时，才保留原有的 `colwidth` 值。
- **新建表格时，普通单元格（`<th>`/`<td>`）不需要写 `numCell` 属性**，转换器会将无 `numCell` 属性的单元格还原为普通格（`numCell: null`）。

```xml
<!-- 新建自适应宽度表格（推荐，不指定 colwidth，普通格无需写 numCell） -->
<table borderWidth="1" responsive="true" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <tr nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">
    <th nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">列标题1</th>
    <th nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">列标题2</th>
  </tr>
  <tr nodeId="e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b">
    <td nodeId="f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c">单元格1</td>
    <td nodeId="a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d">单元格2</td>
  </tr>
</table>

<!-- 带合并单元格的新建表格 -->
<table borderWidth="1" responsive="true" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <tr nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">
    <td colspan="2" nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">跨两列的单元格</td>
  </tr>
  <tr nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">
    <td nodeId="e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b">普通单元格</td>
    <td nodeId="f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c">普通单元格</td>
  </tr>
</table>
```

### numCell 属性说明

`numCell` 只有一种有效值需要 AI 主动写出：
- **不写 `numCell` 属性**（或任何非 `"true"` 的值）：普通单元格，转换器还原为 `numCell: null`，这是默认状态
- **`numCell="true"`**：**自动行号列**标记。带此属性的列会由学城自动显示递增序号（1, 2, 3...），单元格内容保持空 `<p />`

> ⚠️ **`numCell="true"` 只允许出现在表格的第一列**（每行的第一个 `<td>`）。在其他列写 `numCell="true"` 是错误用法。

> ⚠️ `numCell="0"` 等数字值会被转换器解析为 `null`（普通格），与不写等价，没有特殊意义。

> ⚠️ 自动行号列的识别方式：如果**第一列**的所有数据行 `<td>` 都带有 `numCell="true"`，则该列是自动行号列。

### 新增行时保留结构属性

编辑已有表格、新增行时，**必须检查同列其他行的结构属性并继承**：
- 如果同列已有行的 `<td>` 带有 `numCell="true"`，新增行的对应列也必须带 `numCell="true"`
- 如果同列已有行的 `<td>` 带有 `colwidth="[50]"`，新增行的对应列也必须带相同 `colwidth`
- 新增行号列单元格内容保持空：`<p />`

示例：为带行号列的表格新增一行：

```xml
<!-- 已有行（行号列 + 数据列） -->
<tr nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <td colwidth="[50]" numCell="true" nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"><p /></td>
  <td colwidth="[120]" nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f"><p>数据</p></td>
</tr>

<!-- 新增行（继承同列属性） -->
<tr>
  <td colwidth="[50]" numCell="true"><p /></td>
  <td colwidth="[120]"><p>新数据</p></td>
</tr>
```

### 新增列时的规则

新增列时，对齐已有行的结构：
- 表头行 `<tr>` 中加 `<th>`（带 `colwidth`）
- 所有数据行 `<tr>` 中加 `<td>`（带相同 `colwidth`）
- 不要遗漏任何行

## 学城扩展节点（km- 前缀）

### 折叠块（collapse）

```xml
<km-collapse active="true" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" titleNodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e" contentNodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">
  <km-title>折叠标题</km-title>
  <km-content>
    <p nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">折叠内容段落</p>
  </km-content>
</km-collapse>
```

### 提示块（note）

`type` 可选值：`info`（信息，蓝色）/ `note`（警示，黄色）/ `warning`（注意，红色）/ `tip`（提示，绿色）

```xml
<km-note type="warning" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" titleNodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e" contentNodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">
  <km-title>注意</km-title>
  <km-content>
    <p nodeId="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a">这是一条警告信息</p>
  </km-content>
</km-note>
```

### 图片

```xml
<img src="https://km.sankuai.com/api/file/cdn/xxx" name="图片名称" width="800" height="600" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

⚠️ **禁止直接填写非学城图片 URL**。必须先调用 `uploadImageToDocument` 上传，再使用返回的 URL。

### 附件

```xml
<km-attachment src="https://km.sankuai.com/api/file/cdn/xxx" name="文件名.pdf" size="12345" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 视频

```xml
<km-video src="https://km.sankuai.com/api/file/cdn/xxx" name="视频名称.mp4" width="640" height="480" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 音频

```xml
<km-audio src="https://km.sankuai.com/api/file/cdn/xxx" name="音频名称.mp3" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### Draw.io 流程图

```xml
<km-drawio src="https://km.sankuai.com/api/file/cdn/xxx?contentType=0" width="800" height="600" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 思维导图（minder）

```xml
<km-minder src="https://km.sankuai.com/api/file/cdn/xxx" width="800" height="600" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### LaTeX 数学公式

```xml
<!-- 块级公式：必须使用 <km-latex>，禁止写成 <km-latex-block> -->
<km-latex nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">E = mc^2</km-latex>

<!-- 行内公式（在段落内使用） -->
<p nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"><km-latex-inline nodeId="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f">E = mc^2</km-latex-inline></p>
```

### Markdown 嵌入块

> ⚠️ **内容必须用 `<![CDATA[...]]>` 包裹**，否则 Markdown 中的特殊字符（如 `<`、`>`、`&`）会导致 XML 解析错误。

```xml
<km-markdown nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"><![CDATA[
## 标题

这里是 Markdown 内容
]]></km-markdown>
```

### HTML 嵌入块

> ⚠️ **内容必须用 `<![CDATA[...]]>` 包裹**，否则 HTML 标签会被当作 XML 元素解析，导致内容丢失。

```xml
<km-html nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"><![CDATA[
<div style="color:red">自定义 HTML</div>
]]></km-html>
```

### PlantUML 图表

> ⚠️ **内容必须用 `<![CDATA[...]]>` 包裹**，否则 PlantUML 语法中的特殊字符会导致 XML 解析错误。

```xml
<km-plantuml width="400" height="300" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"><![CDATA[
@startuml
A -> B : 消息
@enduml
]]></km-plantuml>
```

### 目录（catalog）

```xml
<km-catalog style="none" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 内嵌多维表格（xtable）

```xml
<km-xtable xtableId="12345" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />
```

### 开放链接卡片（open_link / open_card）

```xml
<!-- open_link：带预览的链接卡片（行内），href 属性不能省略 -->
<km-open-link href="https://tt.sankuai.com/ticket/detail?id=339562956" type="TT" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" />

<!-- open_card：仅展示已有节点的完整保留格式，不要据此新建 -->
<km-open-card url="https://example.com/card/456" width="552" height="300" type="已有应用类型" align="center" refId="已有引用ID" nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e" />
```

> ⚠️ **`open_link` 的属性名必须是 `href`**（与学城服务端 schema 一致），不能写成 `url`。学城服务端不识别 `open_link` 的 `url` 属性，若误写为 `url`，服务端会将 `href` 判定为空，静默丢弃整个节点。转换器已做兼容归一化（`url` → `href`），但 AI 生成 XML 时应直接使用 `href`。
>
> ⚠️ **`open_card` 的属性名是 `url`**（与 `open_link` 不同，`open_card` 服务端 schema 确实用 `url`）。
>
> ⚠️ **`href`/`url` 不能为空或 `null`**：为空的 `<km-open-link>` / `<km-open-card>` 节点会在前端渲染时崩溃。转换器已对原文中 `href`/`url` 均为空的旧节点做自动丢弃处理；AI 编辑时**不得**新增或保留 `href`/`url` 为空的此类节点。

#### ⚠️ `open_card` 仅允许保留编辑，AI 不应自行创建

`open_card` 的 `type` 是编辑器配置的应用类型，`refId` 通常由引用注册接口生成，不能根据 URL 猜测。AI 直接使用 `type="doc"` 等自造值创建卡片不等价于编辑器原生创建流程，可能导致保存后属性失效或前端渲染异常。

- **禁止凭空新建 `<km-open-card>`**。指向学城文档时使用 `<a href="..." autoUpdate="true">文档标题</a>`；其他 URL 使用普通 `<a>` 链接。
- 编辑已有 `<km-open-card>` 时，必须保留 `url`、`width`、`height`、`type`、`align`、`refId`、`nodeId`；除非用户明确要求修改链接地址，否则不得修改 `url`，也不得清空、猜测或重建 `type`/`refId`。
- 若旧节点的 `url` 为空，转换器会在输出时丢弃该无效节点，避免前端渲染崩溃。

#### ⚠️ `type` 属性：仅用于保留编辑，AI 不应在创建新 `open_link` 时凭空填写

`open_link` 的 `type`（如 `TT`、`ones`、`DevTools`）**不是 AI 可以推断或枚举的固定值**。学城前端会先加载后端配置的链接识别规则，再根据 `href` 在前端匹配得到对应的 `type`。

区分两种场景：

- **创建新链接（文档中原本没有这个 `open_link`）**：
  - AI **不知道准确 `type` 时，禁止使用 `<km-open-link>`**。
  - 应改用「链接」一节介绍的 `<a href="..." autoUpdate="true">`（见下文），优先使用 `autoUpdate="true"` 的学城链接语义，让系统按学城逻辑处理标题；如内容并非学城文档、也不需要自动获取标题，则使用不带 `autoUpdate` 的普通链接，并由 AI 自行填写合适的链接文字。
  - 仅当用户明确提供了 `type` 取值，或文档中已存在同域名的 `<km-open-link>` 节点可直接参考其 `type` 时，才允许新建 `<km-open-link>` 并沿用该 `type`。
- **编辑已存在的 `open_link` 节点**：
  - 必须原样保留该节点已有的 `href`、`type`、`nodeId`，除非用户明确要求修改链接地址。
  - **不得**因为不确定 `type` 的含义就清空、猜测或"顺手修正"已有 `type` 值；也不得将已有 `open_link` 节点降级改写为普通 `<a>` 链接。

### @提及用户（@人）

```xml
<!-- 只需提供 uid（即 mis 账号），系统会自动查询并补全 name 和 empId -->
<km-mention uid="zhangsan" />

<!-- 若已知真实姓名也可直接填写，系统不会覆盖已有的 name -->
<km-mention name="张三" uid="zhangsan" empId="1234567" />
```

> ℹ️ **`uid` 字段填写用户的 mis 账号**（如 `zhangsan`）即可。
> 系统在保存文档时会自动通过 mis 查询真实姓名和 empId 并回填，无需 AI 手动填写这两个字段。
> 若 `name` 已有非空且非 mis 的值，则保持原值不变。

### 时间

```xml
<km-time date="1747036800000" />
<!-- 显示时间（精确到时分） -->
<km-time date="1747036800000" showTime="true" />
```

### 状态标签

```xml
<km-status pattern="default" color="blue" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">进行中</km-status>
```

### Emoji

```xml
<km-emoji name="thumbsup" />
```

## 行内样式

### 基本格式

```xml
<strong>粗体</strong>
<em>斜体</em>
<u>下划线</u>
<del>删除线</del>
<code>行内代码</code>
<sub>下标</sub>
<sup>上标</sup>
```

### 颜色和字号

```xml
<!-- 文字颜色（推荐写法） -->
<span color="#ff0000">红色文字</span>

<!-- 背景颜色（推荐写法） -->
<span bg="#ffff00">黄色背景</span>

<!-- 字号（推荐写法） -->
<span font-size="18">大字号文字</span>
```

> **兼容写法**：系统同时支持 HTML 标准 `style` 属性，以下写法会被自动解析为对应 mark：
>
> ```xml
> <!-- style 兼容写法（与推荐写法等价） -->
> <span style="color: #ff0000">红色文字</span>
> <span style="background-color: #ffff00">黄色背景</span>
> <span style="font-size: 18px">大字号文字</span>
>
> <!-- 也可在一个 style 中写多个属性（自动拆分为多层 mark） -->
> <span style="color: #ff0000; background-color: #ffff00; font-size: 18px">组合样式</span>
> ```
>
> 推荐优先使用 `color`、`bg`、`font-size` 写法，更简洁。`style` 写法作为兼容方案，便于 AI 生成时直接沿用 HTML 习惯。

### 组合样式

**关键规则：每个 `<span>` 只能携带一个样式属性（`color`、`bg`、`font-size` 三选一）。多种样式必须用多层 `<span>` 嵌套，语义标签（`<strong>`、`<em>`、`<u>` 等）可与 `<span>` 混合嵌套。**

```xml
<!-- ✓ 正确：粗体 + 红色文字（语义标签在外，span 在内）-->
<strong><span color="#ff0000">粗体红色文字</span></strong>

<!-- ✓ 正确：粗体 + 斜体 + 黄色背景 -->
<strong><em><span bg="#ffff00">粗斜体黄背景</span></em></strong>

<!-- ✓ 正确：字号 + 颜色（两层 span，外大内色）-->
<span font-size="20"><span color="#0000ff">大号蓝色文字</span></span>

<!-- ✓ 正确：字号 + 颜色 + 背景色（三层 span）-->
<span font-size="20"><span color="#0000ff"><span bg="#ffff00">大号蓝字黄背景</span></span></span>

<!-- ✓ 正确：粗体 + 下划线 + 红色 -->
<strong><u><span color="#ff0000">粗体下划线红色</span></u></strong>
```

**⚠️ 错误写法（只会识别第一个属性，其余被丢弃）：**

```xml
<!-- ✗ 错误：单个 span 不能同时写多个样式属性 -->
<span color="#ff0000" font-size="20">混合属性</span>
<!-- 实际效果：只应用 color，font-size 被忽略 -->

<!-- ✗ 错误：单个 span 不能同时写 color 和 bg -->
<span color="#ff0000" bg="#ffff00">颜色和背景</span>
<!-- 实际效果：只应用 color，bg 被忽略 -->
```

### 链接

```xml
<!-- 普通链接：纯链接，不自动获取任何数据，链接文字由 AI 自行填写 -->
<a href="https://example.com">链接文字</a>

<!-- 学城文档链接：加 autoUpdate="true" 后，系统会自动拉取该学城文档的最新标题并回填展示文字 -->
<a href="https://km.sankuai.com/collabpage/123" autoUpdate="true" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">学城文档链接</a>
```

> ℹ️ **`autoUpdate="true"` 用于学城文档链接**：当 `href` 指向 `km.sankuai.com` 的学城文档时，加上 `autoUpdate="true"` 可让系统自动获取并同步该文档的最新标题，无需 AI 手动维护链接文字。
>
> ℹ️ **AI 创建指向三方系统（TT/ones/代码仓库等）的新链接时，优先用这里的普通 `<a>` 链接**，由 AI 自行填写恰当的链接文字，**不要**尝试用 `<km-open-link>` 卡片形式（原因见上文「开放链接卡片」一节中 `type` 属性的说明）。

### 换行

```xml
段落内换行使用 <br /> 标签
```

## 常见编辑场景示例

### 在指定位置插入新段落

找到目标位置，在相邻节点之间插入（新增节点可省略 `nodeId`）：

```xml
<!-- 在 h2 标题后插入新段落 -->
<h2 nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">现有标题</h2>
<p>新增的段落内容（无需 nodeId，系统自动生成）</p>
<p nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">原有的下一段</p>
```

### 修改段落内容

保留 `nodeId`，只修改文本内容：

```xml
<!-- 修改前 -->
<p nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">旧内容</p>

<!-- 修改后 -->
<p nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">新内容</p>
```

### 在表格单元格中添加内容

只修改目标单元格内容，保留所有结构属性（**包括 `numCell`，不要删除**）：

```xml
<td colspan="1" rowspan="1" textAlign="" verticalAlign="" bgColor="" color="" nodeId="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d">
  <p nodeId="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e">修改后的单元格内容</p>
</td>
```

## 后端 Schema 约束（JSON 结构规则）

学城后端在接收文档时会进行严格的 Schema 校验。生成或编辑文档时必须遵守以下规则，否则提交会报错。

### 支持的节点类型

后端仅接受以下节点类型，**任何其他类型均会导致校验失败**：

| 分类 | 支持的类型 |
| --- | --- |
| 文档根节点 | `doc` |
| 块级节点 | `paragraph`, `heading`, `blockquote`, `code_block`, `horizontal_rule` |
| 列表 | `bullet_list`, `ordered_list`, `task_list`, `list_item`, `task_item` |
| 表格 | `table`, `table_row`, `table_cell`, `table_header` |
| 媒体 | `image`, `audio`, `video`, `attachment` |
| 折叠/提示 | `collapse`, `collapse_title`, `collapse_content`, `note`, `note_title`, `note_content` |
| 代码/公式 | `latex_block`, `markdown`, `html` |
| 嵌入内容 | `catalog`, `spaceupdate`, `page_tree`, `gantt`, `data2chart`, `calendar`, `plantuml`, `drawio`, `minder`, `xtable` |
| 卡片/链接 | `open_iframe`, `open_link`, `open_card` |
| 其他块级 | `appendix`, `not_support`, `control`, `doc_list_view`, `title`, `footnote_list`, `footnote_list_item` |
| 行内节点 | `text`, `hard_break`, `mention`, `link`, `time`, `status`, `emoji`, `latex_inline`, `footnote` |

### 支持的 Mark 类型

| mark 类型 | 说明 | 必填 attrs |
| --- | --- | --- |
| `strong` | 加粗 | 无 |
| `em` | 斜体 | 无 |
| `underline` | 下划线 | 无 |
| `strikethrough` | 删除线 | 无 |
| `code` | 行内代码 | 无 |
| `color` | 文字颜色 | `color`（颜色值） |
| `backgroundcolor` | 背景色 | `color`（颜色值） |
| `font` | 字体大小 | `dataSize`（整数，px） |
| `sub` | 下标 | 无 |
| `sup` | 上标 | 无 |
| `quote` | 划词评论引用 | `quoteId`（字符串） |

### doc 根节点的 title 约束

`doc` 根节点对 `title` 有严格的位置和数量约束：

| 约束 | 说明 |
| --- | --- |
| **第一个子节点必须是 `title`** | `doc.content[0]` 必须是 `title` 节点，不能是 `heading`、`paragraph` 等 |
| **有且只有一个 `title`** | `title` 不能出现多次 |
| **`title` 之后至少有一个内容节点** | `title` 后面必须跟 `paragraph`、`heading` 等内容节点 |

> ❌ **常见错误**：用 `<h1>` / `heading` 代替 `<km-title>` 作为文档第一个节点。  
> `heading` 是正文内的标题样式（如章节标题），`title` 是文档元数据标题，**两者完全不同**，不能混用。

### content 数量约束

以下节点类型要求 `content` 不为空（AT_LEAST_ONE），否则后端会报错：

- `doc`：文档根节点，必须有至少一个子节点
- `bullet_list`、`ordered_list`、`task_list`：列表不能为空
- `blockquote`：引用块不能为空
- `collapse_content`：折叠块内容不能为空
- `note_content`：提示框内容不能为空
- `footnote_list`、`footnote_list_item`：注释列表不能为空

### 子节点类型约束

| 父节点 | 允许的子节点类型 |
| --- | --- |
| `table` | 只能是 `table_row` |
| `table_row` | 只能是 `table_cell` 或 `table_header` |
| `bullet_list`、`ordered_list` | 只能是 `list_item` |
| `task_list` | 只能是 `task_item` |
| `collapse` | 必须包含 `collapse_title` 和 `collapse_content` |
| `note` | 必须包含 `note_title` 和 `note_content` |
| `footnote_list` | 只能是 `footnote_list_item` |
| `footnote_list_item` | 只能包含 `<p>`（至少一个，可以有多个）；每个 `<p>` 内**禁止插入图片**，其他 inline 节点不限 |

### text 节点规则

- `text` 节点**必须**包含 `text` 字段（字符串）
- `text` 节点**不应**包含 `content` 字段

## 注意事项

1. **仅支持 2.0 文档**：`getDocumentXml` / `updateDocumentByXml` 不支持学城 1.0 旧版文档（HTML 存储）；若文档是 1.0 格式，请改用 `getDocumentCitadelMd` / `updateDocumentByMd`
2. **nodeId 保留规则**：已有节点的 `nodeId` 必须保留；新增节点省略 `nodeId` 即可（系统自动分配）
3. **不要修改结构属性**：除非用户明确要求，禁止修改表格的 `colspan` / `rowspan` / `colwidth` / `numCell` 等布局属性；编辑已有单元格时必须保留原有 `numCell` 值
4. **表格行列号保护规则**：编辑带行号/列号的表格时——(1) **识别行号列**：第一列 `<td>` 全部带 `numCell="true"` 且内容为空 → 这是自动行号列；(2) **新增行**：继承行号列的 `numCell="true"` + `colwidth`；(3) **新增列**：每一行（含表头和数据行）都要加对应的 `<th>`/`<td>`；(4) **删除行**：行号会自动重排，无需手动调整；(5) **`numCell="true"` 只允许在第一列**，禁止在其他列使用
5. **附件类资源必须先上传**：图片、附件、视频、音频必须先通过对应的 `upload*ToDocument` 命令上传，不能直接填写外部 URL
6. **CDATA 内容不转义**：`km-markdown` / `km-html` / `km-plantuml` 节点内的内容使用 `<![CDATA[...]]>` 包裹，不需要 XML 转义
7. **新建表格普通单元格无需写 `numCell`**：转换器对无 `numCell` 属性的 `<th>`/`<td>` 自动还原为普通格（`numCell: null`）；只有**第一列**的自动行号列才需要显式写 `numCell="true"`，其他列禁止使用

## AI 生成前的自检清单

**每次生成或修改 CitadelXML 后，在调用 CLI 之前，必须逐项确认：**

### ❶ 根标签检查（最高频错误）

| ❌ 错误写法 | ✅ 正确写法 |
| --- | --- |
| `<?xml version="1.0"?>\n<km-citadel-xml>...` | `<km-doc>...` |
| `<km-citadel-xml>...</km-citadel-xml>` | `<km-doc>...</km-doc>` |
| `<km-document>...</km-document>` | `<km-doc>...</km-doc>` |
| `<document>...</document>` | `<km-doc>...</km-doc>` |
| `<html><body>...</body></html>` | `<km-doc>...</km-doc>` |
| `<?xml ...?>` 前缀 + 任何根标签 | 直接以 `<km-doc>` 开头，禁止加 XML 声明头 |

> ⚠️ **CitadelXML 的根标签只有 `<km-doc>`，不接受任何其他形式**，包括带 XML 声明头的变体。

### ❷ km-title 约束检查

- [ ] `<km-title>` 是 `<km-doc>` 的**第一个**子节点
- [ ] 有且只有**一个** `<km-title>`
- [ ] `<km-title>` 里只有纯文本，没有嵌套 `<h1>` 或其他块级标签

### ❸ 禁止使用的标签

以下标签在 CitadelXML 中均不合法，使用后对应内容**静默丢失**：

| ❌ 禁止使用 | ✅ 替代方案 |
| --- | --- |
| `<div>` | `<p>`（段落）或对应块级标签 |
| `<section>`, `<article>`, `<main>` | 直接用 `<h2>`/`<h3>` 划分章节 |
| `<thead>`, `<tbody>`, `<tfoot>` | 直接在 `<table>` 下写 `<tr>`，不需要包裹层 |
| `<details>`, `<summary>` | `<km-collapse>` 折叠块 |
| `<km-paragraph>` | `<p>` |
| `<km-heading>` | `<h1>`/`<h2>`/`<h3>` 等 |
| `<km-code-block>` | `<pre language="Plain Text"><code>...</code></pre>` |
| `<km-list>`, `<km-list-item>` | `<ul>`/`<ol>` + `<li>` |
| `<km-table>` | `<table>` |
| `<mark>` | `<span bg="#ffff00">` |
| `<figure>`, `<figcaption>` | 直接 `<img>`，说明文字放 `<p>` |

### ❹ CDATA 包裹检查

- [ ] `<km-markdown>` 内容已用 `<![CDATA[...]]>` 包裹
- [ ] `<km-html>` 内容已用 `<![CDATA[...]]>` 包裹
- [ ] `<km-plantuml>` 内容已用 `<![CDATA[...]]>` 包裹

### ❺ 标签名拼写检查

- [ ] 所有 `km-` 前缀标签拼写正确（参考本文档各节示例）
- [ ] 没有造出任何本文档中未出现的新 `km-` 标签
- [ ] 代码块用 `<pre language="..."><code>...</code></pre>`，`language` 大小写严格匹配枚举值

### ❻ 新建表格单元格检查

- [ ] 新建表格使用 `responsive="true"`，不指定 `colwidth`
- [ ] 普通单元格（`<th>`/`<td>`）**未**错误地写 `numCell="true"`（该值只有**第一列**的行号列才写，其他列禁止使用）

### ❼ 已有表格行列操作检查

- [ ] 新增行时，已检查**第一列**其他行是否有 `numCell="true"`（行号列），若有则新行第一列必须继承 `numCell="true"` + `colwidth`，内容保持空 `<p />`；其余列不得写 `numCell="true"`
- [ ] 新增列时，已对所有行（含表头行和数据行）都添加了对应的 `<th>`/`<td>`，没有遗漏任何行
- [ ] 未擅自删除或修改已有单元格的 `numCell` 属性值
