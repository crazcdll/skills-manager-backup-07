---
name: kmedit
description: 当用户要对学城/KM/WIKI 协作文档做编辑器原生结构化操作时使用，包括 Mermaid/PlantUML/Minder/Yuntu/Data2Chart/table/paste/copy/html宏、km-html 宏、插入 HTML、HTML 看板、图片定位插入、已有 DrawIO 更新或 DrawIO 实时会话等节点级编辑；Vega 图表/图表组、HTML slides、dashboard、DrawIO 生成/转换先路由到专门 skill。

metadata:
  skillhub.creator: "pingxumeng"
  skillhub.updater: "pingxumeng"
  skillhub.version: "V26"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4621"
  skillhub.high_sensitive: "false"
---

# kmedit

`kmedit` 是学城协作文档的编辑器工具。精确文本、通用节点/属性/mark、标准表格、图片、附件、音视频、
HTML、Mermaid、PlantUML、Yuntu、DrawIO、Minder、Data2Chart、富文本/Markdown/file paste 和跨文档复制默认走
Parker + Pike API 增量提交；Minder 语义输入使用指定 CDP 浏览器原生渲染，再上传产物。DrawIO 多次编辑使用本地草稿会话；只有需要浏览器 iframe 实时交互或未知剪贴板格式时显式走 CDP。整篇正文改写使用 `kmedit full`：2.0 优先用带原生节点/评论保留标记的 Markdown，也支持 ProseMirror JSON；1.0 提交 HTML；

API-only 草稿、富文本复制/粘贴及共享语义校验要求 `kmedit >= 3.2.0`；首次使用先更新 CLI。Markdown 全文编辑要求 `kmedit >= 3.3.0`；使用前确认 `kmedit full --help` 包含 `--markdown-file`，旧版本需更新。

Minder 原生渲染及 `render/check/patch --cdp-url` 需要 `kmedit >= 3.4.0`。

原生表格列宽兼容性修复要求 `kmedit >= 3.4.3`；旧版本需更新，不能用 `colwidth: null` 表示自适应。

API-only patch 新表格默认自适应宽度要求 `kmedit >= 3.4.1`；显式 `responsive: false` 保留固定宽度，已有表格模式不自动改动。

## km-html 选路

| 目标 | 用法 | 是否需浏览器 |
| --- | --- | --- |
| 新建文档时插入 HTML 宏/信息图/看板 | `km create --file` 里写 <code>```km-html</code> | 否 |
| 改已有宏 / 精确节点定位插入 | `kmedit patch`（`insert_html` / `edit_html`） | 否；CDP 仍可用 |

如果用户是在“新建文档”阶段要 HTML 宏，先转 `meituan-local-km` 的 `km create --file`；本 skill 只负责已有文档里的精确插入或更新。

## 先路由

先判断用户要的“内容类型”，不要所有可视化都直接走 `insert_html`。

| 用户目标 | 首选 skill / 能力 | 说明 |
| --- | --- | --- |
| 翻页演示、PPT 风格、slides、故事化汇报 | `km-slides` | 识别用户口径 `km-slide` |
| KPI 看板、数据快照、周报月报、复盘 dashboard、多组件报告 | `km-html-dashboard` | 识别用户口径 `km-dashboard`；Vega 只作为预渲染资产嵌入。 |
| Vega/Vega-Lite 数据驱动图表、图表组、多图解读 | `km-vega` | 简单图默认 Canvas；复杂图默认 Vega Runtime；图片/SVG 仅作为用户指定或降级形态。 |
| Infographic、图文信息图 | `km-infographic` | 不要用通用 HTML 宏重写信息图规范。 |
| 原生可编辑数据图表 | `insert_data2chart` | 读 `references/data2chart.md`。 |
| 脑图、思维导图、知识结构、树状拆解 | `insert_minder` / `insert_minder_svg` | 读 `references/minder.md`。 |
| Yuntu 运维看板、监控看板、值班大盘、SRE/业务观测 widget | `insert_yuntu` | 读 `references/yuntu.md`。 |
| DrawIO 新图生成、Mermaid/CSV/XML 转 DrawIO | `kmdrawio` | 专门 skill 负责生成/转换，最终仍通过 `insert_drawio` 落地。 |
| 已有 DrawIO 更新或实时编辑 session | `kmedit` DrawIO 能力 | 读 `references/drawio.md`。 |
| Mermaid、PlantUML 等原生图形节点 | `insert_mermaid` / `insert_plantuml` | 不要降级成普通图片或 HTML。 |
| 通用交互、动画、自包含轻应用，且不匹配上面场景 | `insert_html` / `edit_html` | 读 `references/insert-html.md`。 |
| 精确文本、通用节点 JSON、表格、图片、附件、音视频、HTML、Mermaid、PlantUML、Yuntu、DrawIO、Minder、Data2Chart | `kmedit patch` | 读 `references/patch.md`；本地资源物化 + Parker state + Pike WSS；Minder 渲染传入 CDP 地址。 |
| 整篇正文改写、跨区域批量改动、章节重排 | `kmedit full` | 读 `references/full-edit.md`；优先 `inspect --markdown-file` → `full --markdown-file`，保留图形/附件/复杂表格/评论锚点；也支持 JSON，按 nodeId diff 成增量 step，必须带 `--step-version`。 |
| 1.0 文档正文编辑 | `kmedit full --html-file` | 读 `references/CITADELMD_IN_PLACE_EDIT.md`；导出原始 HTML，按 page version 保存并读回。 |
| 文档重命名（1.0 / 2.0） | `kmedit rename` | 保留正文，2.0 同步标题节点与元数据。 |

## 适用场景

- 在指定段落前后插入 DrawIO、Mermaid、PlantUML、Minder、Yuntu、Data2Chart、HTML 宏、图片或表格。
- 对已有正文中唯一、明确的小范围文本做 API-only 增量替换。
- 用原生 ProseMirror JSON 插入、替换、删除节点，或修改节点属性与 marks。
- 编辑已有 DrawIO、Data2Chart、HTML 宏、表格结构。
- 把 markdown/html 转为学城原生正文节点。
- 跨文档复制原生节点，例如表格、图片、DrawIO、Mermaid、PlantUML、Minder。
- 需要用 `nodeId`、锚点位置或编辑器 schema 精确控制插入位置。

不负责：

- 读取、搜索、创建、移动、删除、恢复文档。
- 静态图片、附件、视频、音频的普通插入，除非必须指定编辑器节点位置。

## Installation

```bash
NPM_CONFIG_REGISTRY=http://r.npm.sankuai.com bun add -g @waimai/meituan-local-km-cli
NPM_CONFIG_REGISTRY=http://r.npm.sankuai.com bun update -g @waimai/meituan-local-km-cli --latest
kmedit --version
```

## 前置条件

- `kmedit --version` 能正常输出版本。
- 支持 2.0 协作文档与 1.0 HTML 文档；先用 `kmedit inspect` 读取实际类型和版本，不只根据 URL 判断。
- 1.0 支持 inspect、full HTML 和 rename；Parker 节点操作仅适用于 2.0。

## 工作流

1. 判断是否真的需要 `kmedit`；精确文本和通用结构化节点可用 `patch`，整篇正文使用 `full`，图表/HTML 先按上面的路由表选择专门 skill。
2. 用 `inspect` 确认文档类型；1.0 返回 `docVersion: "1.0"` 和 `version`。
3. 优先使用 `km get <docId>` 读取正文语义；需要精确协作版本、最新 tail
   或完整 ProseMirror JSON 基线时用 `kmedit inspect`。只有需要 CDP 编辑器状态和 tab binding 时才用
   `kmedit browser-inspect`。
4. 需要 schema 时运行 `kmedit schema --nodes paragraph,table`（本地无网络）；加 `--doc-id` 查询文档 feature profile。默认 API，浏览器实际扩展 schema 使用 `--transport cdp`。
5. 按内容类型只阅读对应 reference：
   - HTML 宏：`references/insert-html.md`
   - Data2Chart：`references/data2chart.md`
   - DrawIO 与实时编辑：`references/drawio.md`
   - Minder 脑图：`references/minder.md`
   - Yuntu 运维看板：`references/yuntu.md`
   - Parker + Pike API-only 结构化编辑：`references/patch.md`
   - 2.0 Markdown / JSON 全文编辑：`references/full-edit.md`
   - 1.0 HTML 编辑：`references/CITADELMD_IN_PLACE_EDIT.md`
   - 通用 ops、paste、table、copy：`references/ops.md`
6. 精确编辑生成 `ops.json` 并执行 `patch`；全文编辑先 `inspect --markdown-file`，修改 Markdown 后 `full --markdown-file --step-version <n>`。显式 CDP 使用 `browser-apply`。
7. 成功后检查命令的增量读回结果。涉及新节点、资源粘贴或复制的 E2E，还要打开目标文档，确认正文编辑器初始化成功、目标节点实际显示；可用 `browser-inspect` 或浏览器检查。API 提交/读回成功只能证明保存，不能证明页面可加载；无法检查页面时明确标记“渲染未验证”。

## 锚点定位与 inspect

- `kmedit inspect --doc-id <docId>` 是精确状态入口：它把周期性 snapshot 与其后的全部
  collaboration tail step 重放成当前 Parker 文档，返回 `snapshotStepVersion`、`currentStepVersion` 和节点统计。
- 定向查找支持 `--find`、可重复的 `--node-type`、`--node-id`、`--outline`、`--limit` 和显式 `--attrs`。
- 全文改写优先 `kmedit inspect --doc-id <docId> --markdown-file /tmp/body.md`，修改普通 Markdown，保留需要的 keep 块，再 `full --markdown-file`。同次读取返回 `currentStepVersion` 与保留清单；带评论块整体保留，内部文字编辑用 patch。详见 `references/full-edit.md`。
- 全文 JSON 基线使用
  `kmedit inspect --doc-id <docId> --snapshot-file /tmp/km_doc_<docId>.json`；该文件已经包含最新 tail，
  可直接作为 `kmedit full` 的本地编辑基线。不要把只含周期检查点的旧 JSON 当作当前协作状态。
- `kmedit browser-inspect --doc-id <docId>` 返回 CDP 编辑器状态、tab binding、schema 和节点采样；仅在
  `inspect` 无法覆盖的浏览器运行时语义下使用。
- 需要正文上下文时，优先用`km get <docId>`。
- 需要精确锚点时，先从标题、段落原文、表格附近文本缩小范围，再用定向 `inspect` 确认候选节点和 schema：`--find "<text>"`、`--node-type <type>`、`--outline`、`--limit <n>`。
- 采样不足或文档结构复杂时，用 `inspect --snapshot-file` 导出精确当前 JSON tree，用 `jq` 或脚本
  在本地查找目标文本、节点类型和 `attrs.nodeId`；只把筛选后的少量 `{type,nodeId,text}` 回填到上下文。
- `inspect.writable: false` 表示该命令是只读入口，不代表协作步骤未保存；权限另看 `canEdit`，保存状态看版本和读回正文。
- `inspect` 默认保持轻量、定向验证；只有显式 `--snapshot-file` 才导出完整 JSON tree，不把完整树输出到 Agent 上下文。

## 能力速览

- `insert_drawio` / `update_drawio`：API-only 插入或一次性更新 DrawIO；kmedit >= 3.1.1 可原样上传 converter/桌面版生成的可编辑 SVG，含 XML 声明和 DOCTYPE，无需浏览器。
- API-only DrawIO 草稿：`kmedit drawio-session start/apply/commit/discard --session-file <path>`，apply 不上传、不保存，commit 绑定开始时的版本；详见 `references/api-only.md`。
- CDP iframe session runtime：`drawio_session_start` / `drawio_session_apply` / `drawio_session_commit` / `drawio_session_discard`。
- `insert_mermaid` / `insert_plantuml`：插入原生 Mermaid / PlantUML。
- `insert_minder` / `insert_minder_svg`：插入语义脑图或已有 minder SVG。
- `insert_yuntu`：插入云图 iframe 节点。
- `insert_html` / `edit_html`：插入或更新学城编辑器原生 HTML 宏。
- `insert_image` / `insert_attachment` / `insert_audio` / `insert_video`：上传本地文件或 URL 内容并插入目标文档的原生资源节点。
- `kmedit insert-image` CLI：默认 API，下载源图片并上传到目标文档后定位插入；`--transport cdp` 保留编辑器兼容路径。
- `insert_data2chart` / `update_data2chart_config` / `update_data2chart_data`：创建或更新原生数据图表。
- `paste`：API-only 解析 Markdown / HTML / 原生 copy 结果为学城正文；HTML 和 Markdown 图片、文件均通过目标文档上传生命周期落地。
- `replace` / `insert` / `delete`：节点级结构化编辑。
- `table_*`：表格行列、合并、拆分、删除等语义操作。
- `copy` + `paste.source`：API-only 跨文档复制，重建 nodeId，迁移附件和图形资源，重新创建 Mermaid/Data2Chart；`copy --output-file` 保存私有 JSON artifact。

## CLI 入口

```bash
kmedit --help
kmedit login --help
kmedit inspect --help
kmedit inspect --doc-id <docId> --outline --limit 20
kmedit inspect --doc-id <docId> --find "目标文本" --limit 5
kmedit inspect --doc-id <docId> --node-type drawio --limit 10
kmedit schema --help
kmedit copy --help
kmedit drawio-session --help
kmedit insert-html --help
kmedit edit-html --help
kmedit insert-image --help
kmedit check --help
kmedit render --help
kmedit full --help
kmedit patch --help
kmedit browser-inspect --help
kmedit browser-apply --help
kmedit browser-start --help
```

HTML 宏文件入口优先用于上层工具复用：

```bash
kmedit insert-html \
  --doc-id <docId> \
  --target-node-id <anchorNodeId> \
  --content-file ./fragment.html \
  --source <source>

kmedit edit-html \
  --doc-id <docId> \
  --target-node-id <htmlNodeId> \
  --content-file ./fragment.html \
  --source <source>
```

API-only 为默认入口，`kmedit patch` 支持文件和标准输入：

```bash
kmedit patch --doc-id <docId> --ops-file ./ops.json
cat ./ops.json | kmedit patch --doc-id <docId>
kmedit patch --doc-id <docId> --ops-file - < ./ops.json
```

`kmedit check` 是只读的 Agent 预检，并不要求人工预览；`kmedit render` 只产生 artifact，其中 PlantUML 会调用学城 SVG 渲染服务但不读写文档；`kmedit patch` 使用相同的文件/标准输入形式。除通用 `replace_text`、`insert`、`replace`、`delete`、
`set_node_attrs`、marks 外，还接受全部标准 `table_*`、富文本/Markdown/file/copy `paste`、`insert_image` / `insert_attachment` /
`insert_audio` / `insert_video`、`insert_html` / `edit_html`、
`insert_mermaid`、`insert_plantuml`、`insert_yuntu`、DrawIO、Minder 和全部 Data2Chart 命令：

```bash
kmedit patch --doc-id <docId> --ops-file ./structured-ops.json
cat ./structured-ops.json | kmedit patch --doc-id <docId>
```

## 关键 Gotchas

- API `schema` 同时返回字段类型、必填条件、枚举、范围和节点规则；生成原生 JSON 前定向查询相关节点。`check`、`patch`、`full` 和原生 paste 共享语义校验，错误中的 `path/expected/actual` 可直接用于修正输入，详见 `references/api-only.md`。历史异常未改动时允许编辑其他内容，不要通过换 nodeId 绕过校验。
- 默认 API：`inspect`、`schema`、`copy`、`check`、`patch`、HTML/图片快捷命令和本地 DrawIO 草稿。`schema`、`copy`、HTML/图片快捷命令用 `--transport cdp` 显式选择兼容路径。
- API-only paste 接受 HTML、Markdown、纯文本、文件和原生 copy capsule。未知 custom MIME 和 XTable/同步块等专属 Provider 节点会明确失败，不能通过通用节点 JSON 绕过生命周期。
- `insert_drawio` / `update_drawio`、`insert_minder` 和 Data2Chart create/config/data 均可走 API-only；本地 renderer / provider materializer 与 Pike 编辑传输分离。DrawIO 未支持 shape、Minder 未支持模板会失败，不会静默降级。
- Data2Chart 的 `check` 与 `patch` 使用同一份最终配置计算；`patch` 在提交 Pike step 前还会
  读取 Provider 的生效 config/source 并校验，成功结果见 `readback.providers.data2chart`。
- `insert_plantuml` 会在 Pike 会话前调用学城 PlantUML SVG 服务校验源码并读取实际尺寸；失败直接停止，不使用固定宽高兜底。
- 不要把 DrawIO / Mermaid / PlantUML / Minder / Yuntu / Data2Chart 降级成普通图片、iframe 文本或代码块。
- 不要因为文件后缀是 `.svg` 就自动按普通图片处理；Mermaid/DrawIO/Minder 产物可能需要保留原生语义。
- 学城编辑器 HTML 宏不是正文结构；目标是可编辑正文时用 `paste`，目标是宏节点时才用 `insert_html` / `edit_html`。
- 插入 HTML 宏前必须先按内容类型路由到 `km-slides`、`km-html-dashboard`、`km-vega`、`km-infographic`；DrawIO 生成/转换先路由到 `kmdrawio`；都不匹配才直接使用通用 HTML 宏。
- HTML 宏源码只插入可信、自生成或用户明确认可的内容；不要引用 `file://`、localhost、未上传图片、CDN JS 或远程运行时。
- 网页/公众号等富文本整段迁移优先用 `paste` + `clipboard.textHtml`，保留 HTML 中的 `<img src="https://...">`；API-only 会下载可访问的远程图片并上传到目标文档。
- `clipboard.textMarkdown` 支持图片语法 `![alt](url)`；图片须可下载。需要严格控制原生图形语义时使用对应专用 operation。
- API-only `paste.clipboard.files` 按 MIME 生成 image/audio/video/attachment；DrawIO/Minder 可编辑 SVG 使用专用 operation。显式 `insert_*` 可控制更多资源属性。
- 跨学城文档复制统一优先用 `copy_result` / `copy_refs`。
- 连续多次 `insert + after` 到同一锚点时，结果顺序会反转。
- 尾部插入不能落到 `footnote_list` 后面，应插在脚注区之前。
- 表格操作的 `target` 必须是表格节点本身，不是单元格或行；标准 `table` 和 `xtable` 不同。
- 原生表格即使 `responsive: true` 也必须使用正数 `colwidth` 数组，长度匹配 `colspan`；不要生成 `colwidth: null`。schema 接受空值不代表编辑器可渲染。表格写入后必须进入编辑模式确认初始化成功，不能只验证浏览模式或 API 读回。
- 1.0 HTML 必须基于 `inspect --snapshot-file` 导出的原始正文编辑；不要把 `km get` 的简化 Markdown 拿去回写。
- `kmedit full` 对 2.0 优先 `--markdown-file`（带保留标记），也接受完整 ProseMirror JSON；对 1.0 接受 `--html-file`。原生图形/附件/表格/评论块遗漏即报错；删除必须显式 `--drop-preserved-node`；`--step-version` 必填。冲突后要基于新版本重新生成目标文档，不能只换版本号重投旧内容，否则会静默还原他人改动。
- `kmedit full` 无法新建 XTable、Data2Chart 等托管资源，也不接受跨文档附件；先用专用命令创建再引用其 ID。

## 快速判断

- `logo.svg` 作为封面插图：`patch` + `insert_image`；如果它实际是 DrawIO/Minder/Mermaid 资产，必须改走对应原生 operation。
- 公众号/网页全文富文本迁移，且图片 URL 可被编辑器访问：`paste` + `clipboard.textHtml`。
- 学城文档间复制：`copy_result` / `copy_refs`。
- Markdown 文本里有图片：`patch` + `paste.clipboard.textMarkdown`，运行时上传到目标文档。
- PDF/DOCX 等附件且要求无浏览器精确定位：`patch` + `insert_attachment`；也可用 API-only `paste.clipboard.files`。
- 音频或视频且要求无浏览器精确定位：`patch` + `insert_audio` / `insert_video`。
- 找 `nodeId`：先 `km get` 理解上下文；用 `inspect` 定向查找或导出精确当前 JSON；
  `browser-inspect` 仅在需要浏览器编辑器状态时使用。
- 2.0 全文 Markdown 改写并保留原生复杂节点/评论：`references/full-edit.md`。
- 1.0 正文改写、标题修改：`references/CITADELMD_IN_PLACE_EDIT.md`。
- 精确文本或通用节点/属性/mark 编辑，且要求无浏览器增量提交：`references/patch.md`。
- DrawIO 新图、Mermaid/CSV/XML 转 DrawIO：`kmdrawio`。
- 已有 DrawIO 一次性更新或实时编辑：`references/drawio.md`。
- Mermaid 原生节点，需要保留 Mermaid source：`insert_mermaid`。
- 需要稳定首屏尺寸的 PlantUML：`insert_plantuml`。
- 脑图 / 思维导图：`insert_minder`；已有合法 minder SVG 才用 `insert_minder_svg`。
- Yuntu 运维看板 / 监控 widget：`insert_yuntu`。
- Vega/Vega-Lite 图表或图表组：`km-vega`。
- 快照 dashboard：`km-html-dashboard`。
- 翻页演示：`km-slides`。
- 数据未来要继续编辑：`insert_data2chart` / `update_data2chart_config` / `update_data2chart_data`。
