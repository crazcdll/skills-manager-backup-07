# 创建学城文档详细说明

## 内容传递格式自动识别

`createDocument` 的 `--file` / `--content` 参数自动识别以下格式，**优先使用原始 Markdown 文件传入**，无需转换为 XML：

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| 原生 Markdown | `.md` | 直接支持，内容按标准 Markdown 语法解析 |
| CitadelXML | `.xml` | 含 `<km-doc>` 根节点的学城扩展 XML |
| CitadelMD | `.citadelmd` | 含学城专属宏语法的 Markdown 变体 |
| ProseMirror JSON | `.json` | 文档底层 JSON |

## 场景一：用户已有 Markdown 文件（最常见，直接 --file 传入）

> ✅ **原生 Markdown（`.md`）文件可直接传给 `--file`**，系统会自动将 Markdown 转为学城文档格式。
> 不要把 MD 内容套进 `<km-markdown>` 再包成 XML——那样做反而更容易出错。

```bash
# 用户已有 /tmp/report.md，直接创建学城文档
oa-skills citadel createDocument --title "技术方案" --file /tmp/report.md --parentId <id>

# 无父文档时（创建到个人空间）
oa-skills citadel createDocument --title "技术方案" --file /tmp/report.md
```

## 场景二：内容极短，内联传入

```bash
# 少量内容可直接用 --content 内联（支持 Markdown）
oa-skills citadel createDocument --title "会议纪要" --content "# 主要结论\n- 下周启动" --parentId <id>
```

## 场景三：需要学城专属节点时，才使用 CitadelXML（富文本原生节点优先）

仅当文档需要折叠块、高亮提示框、脑图、draw.io 流程图等学城专属节点时，才需要 CitadelXML 格式。

> 🌟 **富文本原生节点是首选**：即使使用 CitadelXML，正文内容（段落、标题、列表、表格等）也应直接使用 `<p>`、`<h1>`～`<h6>`、`<ul>`、`<ol>`、`<table>` 等标准 HTML 节点来表达，**禁止使用 `<km-markdown>` 写入文档内容**。富文本原生节点才能支持学城的划词评论、选区编辑等完整能力。

> ⚠️ **使用 CitadelXML 时的合规要求**（违反会导致内容为空或数据丢失）：
> 1. **根标签只能是 `<km-doc>`**，禁止其他任何前缀
> 2. **`<km-title>` 必须是第一个子节点，有且只有一个**
> 3. **`<km-markdown>` / `<km-html>` / `<km-plantuml>` 内容必须用 `<![CDATA[...]]>` 包裹**
> 4. **禁止使用 `<div>`、`<section>`、`<thead>`、`<tbody>` 等 HTML 布局标签**（会被静默丢弃）
> 5. **禁止使用 `<km-markdown>` 写入文档内容**——这样不仅让文档失去划词评论、选区编辑等学城完整能力，还更容易引发解析错误
> 6. 详见 [doc-xml-syntax.md](doc-xml-syntax.md) 末尾的「AI 生成前的自检清单」

```bash
# 仅需学城专属节点时才用 XML 文件
oa-skills citadel createDocument --title "新文档" --file /tmp/new-doc.xml --parentId <id>
```

## 创建后的授权收尾

每次 `createDocument` 成功后，必须询问用户："文档已创建，是否需要为特定人员/群组授权？"

- **大象群**：自动执行两步授权（群浏览权限 + 管理员可管理权限）

```bash
# 第一步：为大象群授予浏览权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/<返回的contentId>" \
  --xm-group-ids "<群ID>" \
  --perm "仅浏览"

# 第二步：为群助理的管理员（mis）授予管理权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/<返回的contentId>" \
  --person "<管理员mis>" \
  --perm "可管理"
```

- **单聊/其他**：询问用户是否需要授权，按需执行

## 将多维表格内嵌到文档

当用户要求"在学城文档中插入/嵌入多维表格"时，按下面流程处理：

> 🚫 **归属红线（违反会被系统拦截）**：多维表格权限与文档绑定，只有**关联到当前文档**的表格才能内嵌。
>
> - **严禁**把其他文档 XML 里的 `<km-xtable>` 节点直接复制到当前文档——表格 x 归属于 A 文档时，把 x 的 ID 写进 B 文档会导致 B 的读者加载该表格失败
> - **严禁**手写、猜测或复用来历不明的 `xtableId`
> - 唯一合法来源：`createTable --contentId <当前文档ID>` 或 `copyTable --targetType 3 --targetParentId <当前文档ID>` 的返回值
> - **同一张表格在同一文档中只应嵌入一次**：编辑时不要复制已有 `<km-xtable>` 节点；本次编辑新增的重复嵌入会在写入前被拒绝。需要在文档多处展示相同数据时，用 `copyTable` 复制出新表分别嵌入
> - `updateDocumentByXml` / `updateDocumentByMd` 对本次**新增**的 xtableId 做两阶段校验：① 写入前，不存在/已删除/无权限的表格 ID（伪造 ID、他人无权限文档的表格）直接报错拒绝；② 写入后自动审计归属，未关联到本文档的（跨文档引用）报错并要求用 `copyTable` 复制新表替换节点——收到该报错时按报错指引修复，禁止原样重试。创建文档时初始内容包含 `<km-xtable>` 会直接报错（新文档尚无 ID，表格不可能已关联到它）

1. **先创建或复制多维表格**
   - 在现有学城文档内新建表格：调用 `oa-skills citadel-database createTable --contentId <目标文档ID> --tableTitle <表格名>`，其中 `contentId` 就是目标学城文档 ID，不需要先创建多维表格文档；返回值里的 `tableId` 仅用于后续数据读写
   - 复制已有数据表到目标学城文档：调用 `oa-skills citadel-database copyTable --sourceTableId <源表ID> --targetParentId <目标文档ID> --targetType 3`。内嵌到学城文档时固定使用 `type=3`，**插入文档的必须是返回的新 `tableId`，不是源表 ID**
2. **再走学城文档插入链路**
   - `getDocumentXml --contentId <目标文档ID> --output doc.xml`
   - 在目标位置插入 `<km-xtable xtableId="<tableId>" />`（新增节点时可不写 `nodeId`；若是编辑已有节点则保留原值）
   - `updateDocumentByXml --contentId <目标文档ID> --file doc.xml --step-version <stepVersion>`
3. **能力边界**
   - `citadel` 负责文档插入和内容更新
   - 多维表格的数据创建、复制、读写统一走 `oa-skills citadel-database`
   - `<km-xtable>` 是文档中的多维表格引用节点，不要把表格数据直接手写进文档
