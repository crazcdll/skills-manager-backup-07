# DrawIO 使用指南

用于 `kmedit` 的 DrawIO 插入、一次性更新和实时编辑。不要把 DrawIO 降级成普通 SVG 图片；学城里的 DrawIO 节点需要保存可编辑语义。

## 选择入口

- 新插入 DrawIO：`insert_drawio`。
- 一次性改完已有 DrawIO：`update_drawio`。
- 用户要求“边改边看”“多次局部调整”“先预览，最后保存”：使用 DrawIO session runtime。

## 关键 Gotchas

- 不要用多次 `update_drawio` 反复上传保存实时编辑；使用 `drawio_session_start` + 多次 `drawio_session_apply` + 一次 `drawio_session_commit`。
- `drawio_session_apply` 只更新 iframe draft；如果 `persistence.uploadCount` 或 `persistence.saveCount` 非 0，说明链路用错。
- session 开始后不要 `forceRefresh`，也不要换 tab；必须复用返回的 `binding.targetId` 和稳定 `sessionId`。
- 更新已有 DrawIO 时优先用 `target.nodeId` 绑定具体 drawio 节点；fallback 必须唯一。
- 已有节点只传 `target.nodeId` 即可；`check` / `patch` 会优先读取节点内联 XML，缺失时通过节点的 KM
  attachment URL 只读恢复可编辑 SVG/XML。只有附件不可访问或不含可编辑 `mxfile` 时才需要显式补充原文件。
- API-only 一次性编辑可直接传 `.drawio` / XML / 可编辑 SVG：本地 renderer 会生成带 `mxfile content` 的 SVG，再由官方文件上传接口落成原生节点；无需 Chrome/CDP。
- 本地 renderer 不认识的第三方 shape 默认会失败。只有明确接受视觉降级时才传 `allowDegraded: true`；不要把 raw XML 当普通 `.svg` 上传。
- DrawIO XML 操作后使用 `expectedCellIds` 校验关键 cell，避免保存空图、旧图或未命中的操作结果。

## 实时编辑流程

1. `kmedit browser-inspect --doc-id <docId> --node-type drawio --limit 20`，记录返回的 `binding.targetId`，并从 `inspect.matches.nodes` 找到目标 `drawio` 节点的 `nodeId`。
2. 调用 `drawio_session_start`，传入 `target.nodeId`、稳定 `sessionId`、`targetId`。如果是新 XML 草稿，可以传 `drawio.xml` / `drawio.path`；编辑已有图通常只传 `target`。
3. 多次调用 `drawio_session_apply`，传同一个 `targetId` 和 `sessionId`，用 `drawio.operations` 更新 cell。每次 apply 的 `persistence.uploadCount` 和 `persistence.saveCount` 都必须是 `0`。
4. 满意后调用 `drawio_session_commit`，传 `expectedCellIds`，让 runtime 导出当前 iframe draft、上传 SVG、回写节点并保存。
5. 中途放弃时调用 `drawio_session_discard`。

DrawIO session 目前走底层 JS runtime stdin JSON：

```bash
cd scripts/meituan-local-km-js
bun run src/main.ts < ./drawio-session-start.json
```

## XML Cell 操作

- `add_cell` / `append_cell`：新增 `mxCell`，需要 `id`，可传 `value`、`style`、`parent`、`geometry`。
- `update_cell`：修改已有 cell 的 `value`、`style`、`source`、`target`、`geometry` 等。
- `delete_cell`：删除 cell；默认连带删除连接到该 cell 的边，可用 `deleteEdges: false` 覆盖。
- 边使用 `edge: true`、`source`、`target`，通常配 `geometry: { "relative": true }`。

## Session 示例

`drawio_session_start`：

```json
{
  "action": "drawio_session_start",
  "docId": "2759083105",
  "targetId": "<inspect.binding.targetId>",
  "sessionId": "drawio-live-001",
  "target": { "nodeId": "<drawio_node_id>" },
  "exportPreview": true,
  "visible": false
}
```

`drawio_session_apply`：

```json
{
  "action": "drawio_session_apply",
  "docId": "2759083105",
  "targetId": "<same_targetId>",
  "sessionId": "drawio-live-001",
  "exportPreview": true,
  "drawio": {
    "operations": [
      {
        "op": "add_cell",
        "id": "risk_review",
        "value": "风险复核",
        "style": "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        "geometry": { "x": 320, "y": 240, "width": 160, "height": 56 }
      }
    ],
    "expectedCellIds": ["risk_review"]
  }
}
```

`drawio_session_commit`：

```json
{
  "action": "drawio_session_commit",
  "docId": "2759083105",
  "targetId": "<same_targetId>",
  "sessionId": "drawio-live-001",
  "target": { "nodeId": "<drawio_node_id>" },
  "discard": true,
  "drawio": {
    "filename": "drawio-live-001.svg",
    "expectedCellIds": ["risk_review"]
  }
}
```

## 一次性更新示例

一次性更新已有 DrawIO 优先走 API-only；实时 session 仍使用 CDP：

```json
{
  "operations": [
    {
      "op": "update_drawio",
      "target": { "nodeId": "<drawio_node_id>" },
      "drawio": {
        "operations": [
          { "op": "update_cell", "id": "risk_review", "value": "风险复核完成" }
        ],
        "expectedCellIds": ["risk_review"]
      }
    }
  ]
}
```

执行前可用 `kmedit check --doc-id <docId> --ops-file ./ops.json` 做无写入预检；确认后用 `kmedit patch`。
