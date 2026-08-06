# kmedit Ops 速查

用于通用节点编辑、paste、表格和跨文档复制。具体 DrawIO、Data2Chart、HTML 宏、Minder/Yuntu 的细节见对应 reference。

## 支持的 op

- `replace`
- `insert`
- `delete`
- `paste`
- `insert_image`（仅 `kmedit patch`）
- `insert_attachment`（仅 `kmedit patch`）
- `insert_audio`（仅 `kmedit patch`）
- `insert_video`（仅 `kmedit patch`）
- `insert_drawio`
- `update_drawio`
- `insert_mermaid`
- `insert_plantuml`
- `insert_minder`
- `insert_minder_svg`
- `insert_yuntu`
- `insert_html`
- `edit_html`
- `insert_data2chart`
- `update_data2chart_config`
- `update_data2chart_data`
- `update_data2chart`
- `table_insert_row`
- `table_delete_row`
- `table_insert_column`
- `table_delete_column`
- `table_merge_cells`
- `table_split_cell`
- `table_set_cell`
- `table_delete`

API-only 图片定位插入使用 `kmedit patch` 的 `insert_image`。CDP 路径仍可用公开 CLI `kmedit insert-image`；四个新资源 operation 不属于 `kmedit browser-apply`。

DrawIO session runtime action 不是 `kmedit browser-apply` 的普通 `op`，需要直接传给 JS runtime：

- `drawio_session_start`
- `drawio_session_apply`
- `drawio_session_commit`
- `drawio_session_discard`

## Browserless / CDP 对齐

同一个 ops JSON 中，下列 operation 可直接改用 `kmedit patch`：

- 通用节点/文本/属性/mark：`replace_text`、`replace`、`insert`、`delete`、`set_node_attrs`、
  `add_mark`、`remove_mark`
- 全部标准 `table_*`
- `paste`，但只限 `clipboard.textPlain` 或 `source.type=payload` + `textPlain`
- `insert_image`、`insert_attachment`、`insert_audio`、`insert_video`：显式上传到目标文档后插入原生节点
- `insert_html`、`edit_html`、`insert_mermaid`、`insert_plantuml`、`insert_yuntu`
- `insert_drawio` / `update_drawio`：支持 XML、`.drawio`、可编辑 SVG 和本地 cell operations；未知 shape
  默认失败，只有显式 `allowDegraded: true` 才允许近似
- `insert_minder` / `insert_minder_svg`：支持本地语义布局或已有带 `content` 的可编辑 SVG
- 完整 Provider 生命周期的 `insert_data2chart`、`update_data2chart_config`、`update_data2chart_data`

下列模式仍必须使用 CDP `kmedit browser-apply`：富文本/Markdown/file/copy paste、跨文档 copy/paste、DrawIO
实时 session、低层兼容 `update_data2chart`，以及本地 renderer 明确报告不支持的图形语义。误送到 API-only 时会返回
`browserless_capability_unavailable`，不会静默降级。

通用 `insert` / `replace` / `table_set_cell` 只用于普通 Parker schema 节点，不能直接构造
`drawio`、`minder`、`data2chart`、`open_iframe`、`plantuml`、`html`、`image`、`audio`、
`video`、`attachment` 等受管节点；
`set_node_attrs` 也不能直接修改这些节点。请使用对应高阶 operation，让 browserless 层完成字段、上传和资产归属校验。

## 定位规则

`target` 支持：

- `nodeId`
- `fallback.type`
- `fallback.textContains`
- `fallback.nth`

优先使用 `target.nodeId`。fallback 文本容易重复，只能作为兜底；fallback 命中多个节点时必须指定 `nth`。

未知 `nodeId` 时，先用官方学城 Skill `citadel` 或 `km get <docId>` 理解上下文；再用 `kmedit inspect --find "<text>" --limit 5`、`--node-type <type>` 或 `--outline` 定向找候选节点。文档结构复杂或定向 inspect 不足时，用 `kmedit inspect --doc-id <docId> --snapshot-file /tmp/km_doc_<docId>.json` 导出已重放 tail 的当前 JSON tree，再用 `jq` 或 Node 短脚本筛出少量候选节点，不要把完整 JSON tree 塞进 Agent 上下文。

插入类 `position`：

- `before`
- `after`
- `inside_start`
- `inside_end`

`paste.source`：

- `type="payload"` + `clipboard`
- `type="copy_result"` + `result`
- `type="copy_refs"` + `sources`

跨学城文档复制时，优先使用 `source.type="copy_result"` 或 `copy_refs`，不要手写或拼接 `clipboard.textHtml`。`kmedit copy` 会从源文档采集编辑器原生剪贴板数据，`paste` 再按原生剪贴板内容写入目标文档；含图片内容粘贴后，用 `kmedit browser-inspect --force-refresh` 确认图片节点。
一个 copy result 中的多个 item 会按原顺序作为同一插入容器下的同级片段落地，不会沿用前一个片段内部的光标位置。

`paste.clipboard`：

- `textMarkdown`：按 Markdown 粘贴为正文节点。不要用 `![alt](url)` 作为图片插入方式；需要图片时先转成 `textHtml` 的 `<img src="...">`。
- `textHtml`：按浏览器 HTML 剪贴板粘贴为正文节点；适合公众号/网页全文富文本迁移。
- `textPlain`：纯文本兜底。
- `files`：可选，用于模拟剪贴板 File 项。PDF/DOCX 等 file-only 粘贴会生成 `attachment` 节点；期望生成附件时建议单独一次只带 `files` 的 paste。含图 HTML 粘贴通常不必提供 `files`；只要 `textHtml` 中的 `<img src="https://...">` 可被学城编辑器访问，编辑器会在粘贴时拉取并上传为 KM 图片节点。

## 表格规则

- `target` 必须是表格节点本身，不是单元格或行。
- 只支持标准 `table`，不支持 `xtable`。
- 编辑单元格内容时，优先 `table_set_cell`；需要更细粒度控制时再 `replace` 具体单元格内部段落节点，不要替换整张表。
- 行列坐标从 0 开始。目标行/列完全被 `rowspan` / `colspan` 覆盖时，先拆分合并单元格再增删，
  避免命令把合并矩形当成多行或多列范围。

## 最小示例

最小 `paste`：

```json
{
  "operations": [
    {
      "op": "paste",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "clipboard": {
        "textMarkdown": "## markdown block\n\n- item A\n- item B"
      }
    }
  ]
}
```

含图片 HTML 直粘：

```json
{
  "operations": [
    {
      "op": "paste",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "clipboard": {
        "textHtml": "<p>正文</p><p><img src=\"https://<image-host>/<image-path>\"></p>",
        "textPlain": "正文"
      }
    }
  ]
}
```

上面这种不需要 `files`；粘贴后用 `kmedit browser-inspect --force-refresh` 确认图片节点。

附件 file-only 粘贴：

```json
{
  "operations": [
    {
      "op": "paste",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "clipboard": {
        "files": [
          {
            "path": "/tmp/example.pdf",
            "name": "example.pdf",
            "mimeType": "application/pdf"
          }
        ]
      }
    }
  ]
}
```

PDF/DOCX 等附件使用 file-only paste。若同时需要说明文字，先/后再做一次文本 paste，避免附件粘贴被 HTML 文本路径干扰。

PlantUML：

```json
{
  "operations": [
    {
      "op": "insert_plantuml",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "plantuml": {
        "content": "@startuml\nAlice -> Bob: hello\n@enduml"
      }
    }
  ]
}
```

Yuntu：

```json
{
  "operations": [
    {
      "op": "insert_yuntu",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "yuntu": {
        "url": "https://yuntu.sankuai.com/v3/dashboard/<dashboardId>/widget/<widgetId>/view?type=ref"
      }
    }
  ]
}
```

HTML 宏插入：

```json
{
  "operations": [
    {
      "op": "insert_html",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "html": {
        "content": "<style>.demo{font-family:sans-serif}</style><div class=\"demo\">Demo</div><script>console.log('ready')</script>",
        "source": "km-interactive-demo"
      }
    }
  ]
}
```

HTML 宏更新：

```json
{
  "operations": [
    {
      "op": "edit_html",
      "target": { "nodeId": "html_node" },
      "html": {
        "content": "<style>.demo{font-family:sans-serif}</style><div class=\"demo\">Updated</div>"
      }
    }
  ]
}
```

表格插入行：

```json
{
  "operations": [
    {
      "op": "table_insert_row",
      "target": { "nodeId": "table_node_id" },
      "row": 2,
      "position": "after"
    }
  ]
}
```
