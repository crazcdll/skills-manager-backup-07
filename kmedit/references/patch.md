# Parker + Pike API-only 增量编辑

`kmedit patch` 是 `collabpage` 的无浏览器结构化编辑链路。它不启动 Chrome/CDP，也不调用 CitadelMD/Markdown 全文转换：

1. 读取协作文档快照和快照之后的 `querystep`。
2. 用内网 `@it/parker` 的协作 schema 在本地重建 ProseMirror `EditorState`。
3. 把远端增量 step 顺序应用到本地 state；未知 step 或 schema 漂移一律停止。
4. 将结构化 operations 应用成一个原生 ProseMirror transaction。
5. 为 transaction 中的每个 step 加上官方协作元数据。
6. 建立 Pike WSS 长连接，登记当前文档的在线编辑态，通过协作 `/step` 提交增量。
7. 通过 `querystep` 逐字段读回校验，下线编辑态并关闭 Pike。

当前实现是“一次命令、一个文档、一个短生命周期 Pike session”。不会为每个文档常驻一条连接，也不会在不同文档之间复用 channel。

只读检查使用同一套重建逻辑：

```bash
kmedit inspect --doc-id <docId> --outline
kmedit inspect --doc-id <docId> --node-type data2chart --attrs
kmedit inspect --doc-id <docId> --snapshot-file /tmp/current.json
```

`inspect` 不连接 Pike、不登记在线编辑态、不要求编辑权限；导出的 JSON 已重放最新 tail，可与返回的
`currentStepVersion` 一起作为全文编辑基线。

## 支持的结构化 operations

### 精确文本替换

```json
{
  "op": "replace_text",
  "find": "唯一的旧文本",
  "replace": "新的文本",
  "target": { "nodeId": "可选的段落节点 ID" },
  "occurrence": 1
}
```

- `target` 可选；提供后只在该节点的子树内匹配。
- 不提供 `occurrence` 时必须唯一；`occurrence` 从 1 开始。
- 匹配不能跨 text node；替换保留原 text node 的 marks。
- 换段请使用节点级 `replace` / `insert`，不要在 `replace` 字符串里写换行。

### 节点插入、替换、删除

```json
[
  {
    "op": "insert",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "content": {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "新增段落" }]
    }
  },
  {
    "op": "replace",
    "target": { "nodeId": "paragraph-node-id" },
    "content": {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "替换后的整段" }]
    }
  },
  {
    "op": "delete",
    "target": { "nodeId": "obsolete-node-id" }
  }
]
```

- `insert.position` 支持 `before`、`after`、`inside_start`、`inside_end`，默认 `after`。
- `content` 支持单个 ProseMirror node JSON、node JSON 数组；字符串兼容形式会生成 paragraph。
- 新增的、schema 声明了 `nodeId` 的节点会自动生成稳定 ID。
- 同类型整节点 `replace` 在未显式提供 `nodeId` 时保留原目标的 `nodeId`。
- 所有内容都经过 Parker schema 校验；不允许插入 `doc` 节点。
- 显式 `nodeId` 只能是非空字符串或 `null`；`null` 按缺省处理并生成 ID。

### 节点属性

```json
{
  "op": "set_node_attrs",
  "target": { "nodeId": "paragraph-node-id" },
  "attrs": { "align": "center" }
}
```

属性采用 merge 语义。未知属性会失败，且不允许通过该接口修改稳定 `nodeId`。

### 富文本 marks

```json
[
  {
    "op": "add_mark",
    "target": { "nodeId": "paragraph-node-id" },
    "find": "需要加粗",
    "mark": { "type": "strong" }
  },
  {
    "op": "remove_mark",
    "target": { "nodeId": "paragraph-node-id" },
    "find": "取消颜色",
    "mark": { "type": "color", "attrs": { "color": "#f00" } }
  }
]
```

`remove_mark` 不带 `attrs` 时移除该范围内同类型的全部 mark；带 `attrs` 时只移除完全匹配的 mark。

### 表格语义

API-only 已与 CDP 的标准 `table` 命令对齐：

- `table_insert_row` / `table_delete_row`
- `table_insert_column` / `table_delete_column`
- `table_merge_cells` / `table_split_cell`
- `table_set_cell` / `table_delete`

```json
[
  {
    "op": "table_insert_row",
    "target": { "nodeId": "table-node-id" },
    "row": 0,
    "position": "after"
  },
  {
    "op": "table_set_cell",
    "target": { "nodeId": "table-node-id" },
    "row": 1,
    "col": 0,
    "content": "新内容"
  }
]
```

行列坐标从 0 开始，`target` 必须解析到标准 Parker `table`。新增行列中被复制出来的 row、cell、paragraph
会重新分配唯一 `nodeId`。只有一行/一列时不能用删除行列隐式删除整表，必须显式用 `table_delete`。
合并表格会优先选择未跨越目标边界的 cell 作为精确行列锚点；如果目标行/列完全被 `rowspan` / `colspan`
覆盖，API-only 会拒绝操作，调用方应先拆分对应合并单元格，避免 CDP 命令按合并矩形误改多行或多列。

### 与 CDP 同名的高阶命令

下列 CDP operation 可原样交给 `patch`，由 browserless 层物化为 Parker 原生节点/属性 step：

| operation | API-only 语义 |
| --- | --- |
| `paste` | 仅 `textPlain`；换行物化为多个 paragraph |
| `insert_image` | 下载/读取图片、调用官方 `uploadphoto`、插入同文档原生 `image` 节点 |
| `insert_attachment` | 下载/读取文件、调用官方文件上传、插入同文档原生 `attachment` 节点 |
| `insert_audio` / `insert_video` | 下载/读取媒体、调用官方 `uploadMedia`、插入同文档原生音视频节点 |
| `insert_html` / `edit_html` | 原生 `html` 宏节点插入/属性更新 |
| `insert_yuntu` | 原生 `open_iframe` 云图节点 |
| `insert_mermaid` | 通过官方附件 create/fileinfo/upload API 保存 source，再插入原生 `open_iframe` |
| `insert_plantuml` | 调用学城 PlantUML SVG 服务校验源码并读取固有尺寸，再插入保留 source 的原生 `plantuml` 节点；渲染失败则停止 |
| `insert_drawio` / `update_drawio` | 本地严格渲染 XML / `.drawio` / 可编辑 SVG，上传可编辑 SVG 后写入原生 `drawio`；未知 shape 默认失败，显式 `allowDegraded: true` 才允许降级 |
| `insert_minder` / `insert_minder_svg` | 本地布局并保留完整 minder JSON `content` 的 SVG，上传后写入原生 `minder` |
| `insert_data2chart` / `update_data2chart_config` / `update_data2chart_data` | 通过 Data2Chart 官方 chart/datasource/save-publish 生命周期物化，再写回原生 `data2chart` 节点 |

例如：

```json
[
  {
    "op": "insert_html",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "html": {
      "content": "<section>...</section>",
      "source": "agent"
    }
  },
  {
    "op": "insert_mermaid",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "mermaid": {
      "content": "flowchart LR\nA-->B",
      "mermaidConfig": { "layout": "preview" }
    }
  }
]
```

这些命令保留原 operation 名称出现在 `changes[].op` 中，便于调用方统一审计 CDP 与 Pike 结果。

资源 operation 使用明确类型，不能用通用 `insert` 伪造 Provider 节点：

```json
[
  {
    "op": "insert_image",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "image": {
      "path": "./logo.png",
      "alt": "项目 Logo",
      "width": 320
    }
  },
  {
    "op": "insert_attachment",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "attachment": {
      "path": "./report.pdf",
      "name": "完整报告",
      "expand": false
    }
  },
  {
    "op": "insert_audio",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "audio": { "path": "./meeting.mp3", "name": "会议录音" }
  },
  {
    "op": "insert_video",
    "target": { "nodeId": "anchor-node-id" },
    "position": "after",
    "video": { "path": "./demo.mp4", "name": "演示视频", "width": 960, "height": 540 }
  }
]
```

- 每个 payload 必须且只能提供 `path` 或 `url`；`url` 会先在本地下载，再上传到目标文档，绝不直接写成外链。
- 可用 `filename` 覆盖上传文件名、用 `mimeType` 显式补充无法从后缀推断的类型；图片/音频/视频会校验 MIME 前缀。
- `image` 还支持 `alt`、`width`、`height`、`border`、`isFullWidth`；附件支持 `name`、`align`、`expand`；音视频支持 `name`、`align`，视频另支持宽高。
- `before` / `after` 图片会放进原生 paragraph；`inside_start` / `inside_end` 用于在可接收 inline content 的目标内插入图片。
- 文件读取沿用 20 MiB 的单文件输入上限。`check` 只读取并校验文件、模拟资源地址，不上传；`patch` 才执行上传。
- 上传完成但 Pike 提交失败时，错误的 `orphanedResources` 会列出可能遗留的图片、附件或媒体资源，调用方不得自动重试。

## target 语义

优先使用稳定 `nodeId`：

```json
{ "nodeId": "node-id" }
```

没有 nodeId 时可使用 fallback：

```json
{
  "fallback": {
    "type": "paragraph",
    "textContains": "唯一锚点文本",
    "nth": 0
  }
}
```

- `fallback.nth` 从 0 开始。
- 未提供 `nth` 时 fallback 必须唯一。
- `nodeId` 未命中但同时提供 fallback 时会尝试 fallback。

## 适用边界

- 只支持 `collabpage`。
- 运行环境必须能从 `PATH` 找到 `node`；Pike Node SDK 在隔离子进程中运行，CLI 仍由 Bun 承载。
- API-only 支持通用 schema 节点 JSON、标准表格命令和上表列出的可安全物化命令，但不运行编辑器 DOM/UI extension。
- 低层兼容操作 `update_data2chart` 不能走 API-only，因为它只改 KM attrs、绕过 Provider 读回；请使用
  `update_data2chart_config` / `update_data2chart_data`。通用 `insert` / `replace` / `table_set_cell` 不能直接构造 `drawio`、`minder`、`data2chart`、
  `open_iframe`、`plantuml`、`html`、`image`、`audio`、`video`、`attachment` 等受管节点；
  `set_node_attrs` 也不能绕过对应高阶命令直接修改这些节点。
  这类输入返回 `browserless_capability_unavailable`，防止跳过 provider 字段和附件生命周期校验。
- 富文本/Markdown/custom/file paste、`copy_result`、`copy_refs` 必须走 CDP；API-only paste 只接受 `textPlain`。图片、附件和音视频应使用四个显式高阶 operation，而不是 file paste。
- DrawIO、Minder 的本地 renderer 以及 PlantUML 的学城 SVG renderer 与 KM 编辑传输是分离的：`render` 只生成 artifact，`check` 只读验证，
  `patch` 才上传、调用 provider 并提交 Pike step。所有运行均不启动 Chrome/CDP。
- DrawIO 未覆盖的 shape、无法读取的既有 DrawIO 源、Minder 未支持的模板或 XLSX 未归一化数据会失败并给出可选 CDP fallback；绝不伪造成普通图片或残缺节点。
- PlantUML 保留原生 source 节点，宽高来自同一源码的服务端 SVG `width`/`height` 或 `viewBox`；没有固定尺寸降级，语法、网络或不可测量 SVG 都会在提交前失败。
- 快照节点/mark、远端 step slice、输入内容和属性都按本地 Parker schema 严格校验。出现未知类型、未知属性、非法 content expression 或未知 step 时不提交。
- request、operation、target、fallback、node 和 mark JSON 的未知字段也会直接失败；例如把 `position` 拼成 `positon` 不会静默使用默认值。
- 多个 operations 在同一 transaction 中按顺序执行，后一个 operation 看到前一个 operation 产生的新 state。

## 执行

操作文件支持 JSON 数组，或带 `operations` 的对象：

```bash
kmedit patch --doc-id <docId> --ops-file ./ops.json
kmedit check --doc-id <docId> --ops-file ./ops.json
kmedit render --ops-file ./render-ops.json --output-dir ./artifacts
cat ./ops.json | kmedit patch --doc-id <docId>
```

需要强制乐观锁时传 `--expected-step-version <version>`。默认发生版本冲突会重新读取最新状态、重新定位、重新生成 transaction 并有限重试；指定版本后只要当前版本不同就直接失败。

`check` 是给 Agent 的只读预检，不是必须交给人看的预览：它加载当前 Parker state、验证 target、执行本地渲染并生成 step 计划，绝不创建附件、图表、Pike 连接或编辑态。`patch` 在真正写入前会重复关键预检。

成功结果必须同时满足：

- `ok: true`
- `transport: "pike"`
- `schema.profile: "parker-collab-1"`
- `readback.verified: true`
- `readback.verifiedStepCount == stepCount`
- Data2Chart 写入还要求 `readback.providers.data2chart[*].verified == true`
- `session.online: true`

`session.offline: false` 表示提交已经成功、但离线清理失败；保留成功结果并报告 warning。不要把 `realtime.updateReceived: false` 当成提交失败：当前连接不一定收到自己的广播，提交真实性以 `/step` 响应和 `querystep` 读回为准。

### 提交状态不确定

下面两类结果都必须视为“服务端可能已提交”，禁止原样自动重试：

- `code: "commit_unverified"`：`/step` 已成功但版本或 `querystep` 读回不一致时返回 `committed: true`；提交请求发生传输异常、无法判断服务端是否接收时返回 `committed: "unknown"`。
- `code: "runner_timeout"`：外层 CLI 总时限触发，返回 `commitStatus: "unknown"`。

两者都会带 `retrySafe: false`。调用方应先重新读取该文档的 snapshot 和全部 tail steps，确认目标变更及最新 step version，再决定是否生成一笔新的 transaction；不要复用旧 transaction、`trVersion` 或 `msgId`。

## 安全规则

- C4 文档必须先按学城 Skill 的 C4 确认流程向用户做一次性确认，得到明确同意后本次命令才可带 `--confirm-c4`。
- C4 以上禁止执行。
- 不要把 Pike channel、用户 token、Sign、Cookie 或 bootstrap 身份信息打印、保存到 ops 或写入文档。
- macOS 首次刷新 SSO 时可能弹出 Keychain 授权窗口；应让用户完成系统授权，不要绕过或导出凭证。
- `target_not_unique`、`text_not_unique`、`schema_mismatch`、未知远端 step 等安全错误必须停止；不要改用模糊匹配、猜位置或全文覆盖兜底。
