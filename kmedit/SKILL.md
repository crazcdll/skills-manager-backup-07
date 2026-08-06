---
name: kmedit
description: 当用户要对学城/KM/WIKI 协作文档做编辑器原生结构化操作时使用，包括 Mermaid/PlantUML/Minder/Yuntu/Data2Chart/table/paste/copy/html宏、km-html 宏、插入 HTML、HTML 看板、图片定位插入、已有 DrawIO 更新或 DrawIO 实时会话等节点级编辑；Vega 图表/图表组、HTML slides、dashboard、DrawIO 生成/转换先路由到专门 skill。

metadata:
  skillhub.creator: "pingxumeng"
  skillhub.updater: "pingxumeng"
  skillhub.version: "V19"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4621"
  skillhub.high_sensitive: "false"
---

# kmedit

`kmedit` 是学城协作文档的编辑器工具。精确文本、通用节点/属性/mark、标准表格、图片、附件、音视频、
HTML、Mermaid、PlantUML、Yuntu、DrawIO、Minder 和 Data2Chart 可以走 Parker + Pike API-only 增量提交；需要实时专属编辑器
session、跨文档复制或富剪贴板语义时走 CDP。整篇正文改写、整篇 Markdown 更新优先走官方学城
Skill `citadel`。

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
| 精确文本、通用节点 JSON、表格、图片、附件、音视频、HTML、Mermaid、PlantUML、Yuntu、DrawIO、Minder、Data2Chart | `kmedit patch` | 读 `references/patch.md`；本地上传/渲染/物化 + Parker state + Pike WSS，无浏览器、无全文转换。 |
| 整篇正文改写、跨区域批量改动、章节重排 | `kmedit full` | 读 `references/full-edit.md`；提交完整 ProseMirror JSON，运行时按 nodeId diff 成增量 step，必须带 `--step-version`。 |
| CitadelMD 原地更新（1.0 文档等 `kmedit full` 不适用的场景） | 官方 `oa-skills citadel` | 读 `references/CITADELMD_IN_PLACE_EDIT.md`；这是全文覆盖更新，不走 `kmedit browser-apply`。 |

## 适用场景

- 在指定段落前后插入 DrawIO、Mermaid、PlantUML、Minder、Yuntu、Data2Chart、HTML 宏、图片或表格。
- 对已有正文中唯一、明确的小范围文本做 API-only 增量替换。
- 用原生 ProseMirror JSON 插入、替换、删除节点，或修改节点属性与 marks。
- 编辑已有 DrawIO、Data2Chart、HTML 宏、表格结构。
- 把 markdown/html 转为学城原生正文节点。
- 跨文档复制原生节点，例如表格、图片、DrawIO、Mermaid、PlantUML、Minder。
- 需要用 `nodeId`、锚点位置或编辑器 schema 精确控制插入位置。

不负责：

- 不能用精确文本或明确节点 JSON 表达的段落改写、润色、翻译、续写。
- 读取、搜索、创建、移动、删除、恢复文档。
- 静态图片、附件、视频、音频的普通插入，除非必须指定编辑器节点位置。
- 可以安全通过整篇 CitadelMD 更新完成的任务。

## Installation

```bash
NPM_CONFIG_REGISTRY=http://r.npm.sankuai.com bun add -g @waimai/meituan-local-km-cli
NPM_CONFIG_REGISTRY=http://r.npm.sankuai.com bun update -g @waimai/meituan-local-km-cli --latest
kmedit --version
```

## 前置条件

- `kmedit --version` 能正常输出版本。
- 目标文档最终落地 URL 必须是 `https://km.sankuai.com/collabpage/<docId>`；如果仍是 `/page/<docId>`，回退到官方学城 Skill `citadel`。
- 不要只根据用户给出的 URL 文本判断，必要时打开/检查最终落地 URL。

## 工作流

1. 判断是否真的需要 `kmedit`；精确文本和通用结构化节点可用 `patch`，其他普通正文优先官方学城 Skill `citadel`，图表/HTML 先按上面的路由表选择专门 skill。
2. 确认目标是 `collabpage`。
3. 优先使用 `km get <docId>` 或官方学城 Skill `citadel` 读取正文语义；需要精确协作版本、最新 tail
   或完整 ProseMirror JSON 基线时用 `kmedit inspect`。只有需要 CDP 编辑器状态和 tab binding 时才用
   `kmedit browser-inspect`。
4. 需要 schema 时运行 `kmedit schema`。
5. 按内容类型只阅读对应 reference：
   - HTML 宏：`references/insert-html.md`
   - Data2Chart：`references/data2chart.md`
   - DrawIO 与实时编辑：`references/drawio.md`
   - Minder 脑图：`references/minder.md`
   - Yuntu 运维看板：`references/yuntu.md`
   - Parker + Pike API-only 结构化编辑：`references/patch.md`
   - CitadelMD 原地编辑：`references/CITADELMD_IN_PLACE_EDIT.md`
   - 通用 ops、paste、table、copy：`references/ops.md`
6. 按所选链路生成 `ops.json`，执行 `kmedit patch ...` 或 `kmedit browser-apply ...`。
7. 成功后检查命令的增量读回结果；CDP 节点操作再按风险决定是否用 `inspect --force-refresh` 验证。

## 锚点定位与 inspect

- `kmedit inspect --doc-id <docId>` 是精确状态入口：它把周期性 snapshot 与其后的全部
  collaboration tail step 重放成当前 Parker 文档，返回 `snapshotStepVersion`、`currentStepVersion` 和节点统计。
- 定向查找支持 `--find`、可重复的 `--node-type`、`--node-id`、`--outline`、`--limit` 和显式 `--attrs`。
- 全文 JSON 基线使用
  `kmedit inspect --doc-id <docId> --snapshot-file /tmp/km_doc_<docId>.json`；该文件已经包含最新 tail，
  可直接作为 `kmedit full` 的本地编辑基线。不要把只含周期检查点的旧 JSON 当作当前协作状态。
- `kmedit browser-inspect --doc-id <docId>` 返回 CDP 编辑器状态、tab binding、schema 和节点采样；仅在
  `inspect` 无法覆盖的浏览器运行时语义下使用。
- 需要正文上下文时，优先用官方学城 Skill `citadel` 或 `km get <docId>`。
- 需要精确锚点时，先从标题、段落原文、表格附近文本缩小范围，再用定向 `inspect` 确认候选节点和 schema：`--find "<text>"`、`--node-type <type>`、`--outline`、`--limit <n>`。
- 采样不足或文档结构复杂时，用 `inspect --snapshot-file` 导出精确当前 JSON tree，用 `jq` 或脚本
  在本地查找目标文本、节点类型和 `attrs.nodeId`；只把筛选后的少量 `{type,nodeId,text}` 回填到上下文。
- `inspect` 默认保持轻量、定向验证；只有显式 `--snapshot-file` 才导出完整 JSON tree，不把完整树输出到 Agent 上下文。

## 能力速览

- `insert_drawio` / `update_drawio`：插入或一次性更新 DrawIO。
- DrawIO session runtime：`drawio_session_start` / `drawio_session_apply` / `drawio_session_commit` / `drawio_session_discard`。
- `insert_mermaid` / `insert_plantuml`：插入原生 Mermaid / PlantUML。
- `insert_minder` / `insert_minder_svg`：插入语义脑图或已有 minder SVG。
- `insert_yuntu`：插入云图 iframe 节点。
- `insert_html` / `edit_html`：插入或更新学城编辑器原生 HTML 宏。
- `insert_image` / `insert_attachment` / `insert_audio` / `insert_video`：上传本地文件或 URL 内容并插入目标文档的原生资源节点。
- `kmedit insert-image` CLI：把官方 `km upload-image` 已上传得到的 KM 图片 URL 通过 CDP 插到指定锚点；旧的预上传图片路径仍可用。
- `insert_data2chart` / `update_data2chart_config` / `update_data2chart_data`：创建或更新原生数据图表。
- `paste`：把 markdown / html / copy 结果转换为学城原生节点；`textHtml` 里带 `<img src="https://...">` 时，编辑器可直接拉取图片并上传为 KM 图片节点。
- `replace` / `insert` / `delete`：节点级结构化编辑。
- `table_*`：表格行列、合并、拆分、删除等语义操作。
- `copy` + `paste.source`：跨文档复制原生节点。

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
kmedit insert-html --help
kmedit edit-html --help
kmedit insert-image --help
kmedit check --help
kmedit render --help
kmedit patch --help
kmedit browser-inspect --help
kmedit browser-apply --help
kmedit browser-start --help
```

HTML 宏文件入口优先用于上层工具复用：

```bash
kmedit insert-html \
  --doc-id <docId> \
  --tab-target-id <targetId> \
  --target-node-id <anchorNodeId> \
  --content-file ./fragment.html \
  --source <source>

kmedit edit-html \
  --doc-id <docId> \
  --tab-target-id <targetId> \
  --target-node-id <htmlNodeId> \
  --content-file ./fragment.html \
  --source <source>
```

`kmedit browser-apply` 支持文件和标准输入：

```bash
kmedit browser-apply --doc-id <docId> --ops-file ./ops.json
cat ./ops.json | kmedit browser-apply --doc-id <docId>
kmedit browser-apply --doc-id <docId> --ops-file - < ./ops.json
```

`kmedit check` 是只读的 Agent 预检，并不要求人工预览；`kmedit render` 只产生 artifact，其中 PlantUML 会调用学城 SVG 渲染服务但不读写文档；`kmedit patch` 使用相同的文件/标准输入形式。除通用 `replace_text`、`insert`、`replace`、`delete`、
`set_node_attrs`、marks 外，还接受全部标准 `table_*`、纯文本 `paste`、`insert_image` / `insert_attachment` /
`insert_audio` / `insert_video`、`insert_html` / `edit_html`、
`insert_mermaid`、`insert_plantuml`、`insert_yuntu`、DrawIO、Minder 和全部 Data2Chart 命令：

```bash
kmedit patch --doc-id <docId> --ops-file ./structured-ops.json
cat ./structured-ops.json | kmedit patch --doc-id <docId>
```

## 关键 Gotchas

- `patch` 支持四个显式资源上传 operation、纯文本 paste 和标准 `table_*`；通用富文本/Markdown/file paste、跨文档 copy/paste 继续走 CDP。
- `insert_drawio` / `update_drawio`、`insert_minder` 和 Data2Chart create/config/data 均可走 API-only；本地 renderer / provider materializer 与 Pike 编辑传输分离。DrawIO 未支持 shape、Minder 未支持模板和 XLSX 未归一化数据会失败，不会静默降级。
- Data2Chart 的 `check` 与 `patch` 使用同一份最终配置计算；`patch` 在提交 Pike step 前还会
  读取 Provider 的生效 config/source 并校验，成功结果见 `readback.providers.data2chart`。
- `insert_plantuml` 会在 Pike 会话前调用学城 PlantUML SVG 服务校验源码并读取实际尺寸；失败直接停止，不使用固定宽高兜底。
- 不要把 DrawIO / Mermaid / PlantUML / Minder / Yuntu / Data2Chart 降级成普通图片、iframe 文本或代码块。
- 不要因为文件后缀是 `.svg` 就自动按普通图片处理；Mermaid/DrawIO/Minder 产物可能需要保留原生语义。
- 学城编辑器 HTML 宏不是正文结构；目标是可编辑正文时用 `paste`，目标是宏节点时才用 `insert_html` / `edit_html`。
- 插入 HTML 宏前必须先按内容类型路由到 `km-slides`、`km-html-dashboard`、`km-vega`、`km-infographic`；DrawIO 生成/转换先路由到 `kmdrawio`；都不匹配才直接使用通用 HTML 宏。
- HTML 宏源码只插入可信、自生成或用户明确认可的内容；不要引用 `file://`、localhost、未上传图片、CDN JS 或远程运行时。
- 网页/公众号等富文本整段迁移优先用 `paste` + `clipboard.textHtml`，保留 HTML 中的 `<img src="https://...">`；学城编辑器会按真实粘贴链路把可访问的远程图片上传为 KM 图片节点。
- 不要依赖纯 `clipboard.textMarkdown` 中的 Markdown 图片语法 `![alt](url)` 来插入图片；需要图片时，先把 Markdown 图片转为 HTML `<img src="https://...">`，再用 `clipboard.textHtml` 粘贴。
- `paste.clipboard.files` 用于 CDP 模拟剪贴板 File 项；它不是含图 HTML 粘贴的必需字段。API-only 精确资源插入使用 `patch` 的四个 `insert_*` operation，这四个 operation 不属于 `kmedit browser-apply`。
- 跨学城文档复制统一优先用 `copy_result` / `copy_refs`。
- 连续多次 `insert + after` 到同一锚点时，结果顺序会反转。
- 尾部插入不能落到 `footnote_list` 后面，应插在脚注区之前。
- 表格操作的 `target` 必须是表格节点本身，不是单元格或行；标准 `table` 和 `xtable` 不同。
- CitadelMD 原地编辑是官方 CLI 全文覆盖流程，不是 `kmedit browser-apply` 节点操作；不要把 `km get` 或 `getSimpleMarkdown` 的输出拿去回写。
- `kmedit full` 只接受完整 ProseMirror JSON；`--step-version` 必填。冲突后要基于新版本重新生成目标文档，不能只换版本号重投旧内容，否则会静默还原他人改动。
- `kmedit full` 无法新建 XTable、Data2Chart 等托管资源，也不接受跨文档附件；先用专用命令创建再引用其 ID。

## 快速判断

- `logo.svg` 作为封面插图：`patch` + `insert_image`；如果它实际是 DrawIO/Minder/Mermaid 资产，必须改走对应原生 operation。
- 公众号/网页全文富文本迁移，且图片 URL 可被编辑器访问：`paste` + `clipboard.textHtml`。
- 学城文档间复制：`copy_result` / `copy_refs`。
- Markdown 文本里有图片：不要只传 `textMarkdown`，先转为 HTML `<img src="...">` 后用 `clipboard.textHtml`。
- PDF/DOCX 等附件且要求无浏览器精确定位：`patch` + `insert_attachment`；需要真实剪贴板转换语义时才用 CDP `paste.clipboard.files`。
- 音频或视频且要求无浏览器精确定位：`patch` + `insert_audio` / `insert_video`。
- 找 `nodeId`：先 `citadel` / `km get` 理解上下文；用 `inspect` 定向查找或导出精确当前 JSON；
  `browser-inspect` 仅在需要浏览器编辑器状态时使用。
- 整篇正文改写、标题修改、CitadelMD 原地更新：`references/CITADELMD_IN_PLACE_EDIT.md`。
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
