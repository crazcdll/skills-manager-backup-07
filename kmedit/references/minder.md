# Minder 脑图指南

用于 `kmedit` 的学城原生脑图节点。Minder 适合脑图、思维导图、知识结构、任务拆解、树状目录、组织结构和流程清单；不要把它和 Yuntu 运维看板混在同一个使用场景里。

## 什么时候使用

- 用户要求插入脑图、思维导图、mind map、Minder。
- 用户要把主题、知识点、方案、任务、组织结构做成树状结构。
- 用户提供层级列表、目录、JSON 树，希望在 KM 中以可视化脑图呈现。
- 已有合法 minder SVG，需要作为 Minder 节点导入。

不适用：

- 运维监控、实时指标、SRE 大盘、业务观测看板：使用 `insert_yuntu`，读 `references/yuntu.md`。
- 流程图、架构图、泳道图：优先 DrawIO。
- Mermaid / PlantUML 源码：使用对应原生节点。

## 入口选择

- 语义化脑图：优先 `insert_minder`。
- 已有合法 minder SVG：使用 `insert_minder_svg`。

`insert_minder` 的 `content` 可以是 KM minder JSON 字符串，支持在顶层写入 `template` 和 `theme`：

```json
{
  "root": {
    "data": { "text": "项目计划" },
    "children": [
      { "data": { "text": "需求" }, "children": [] },
      { "data": { "text": "研发" }, "children": [] }
    ]
  },
  "template": "right",
  "theme": "fresh-blue"
}
```

## 原生渲染与连接准备

`insert_minder` 通过 Minder converter 的原生引擎渲染，再通过 KM API 上传和提交。`render`、`check` 和 `patch` 接收 `--cdp-url`，也可设置 `LOCAL_CDP_URL`。

按当前环境的浏览器说明获取可供程序连接的完整 CDP 地址。优先使用任务提供的地址；宿主提供管理命令时，先查看帮助，再查询当前会话的连接信息。动态端口由管理方返回。用 `minder-converter doctor --probe --cdp-url "$LOCAL_CDP_URL"` 验证后再转换。

```bash
kmedit render --ops-file ops.json --output-dir ./artifacts --cdp-url "$LOCAL_CDP_URL"
kmedit check --doc-id <docId> --ops-file ops.json --cdp-url "$LOCAL_CDP_URL"
kmedit patch --doc-id <docId> --ops-file ops.json --cdp-url "$LOCAL_CDP_URL"
```

模板支持 `default`、`right`、`structure`、`filetree`、`fish-bone`、`tianpan`。常用组合是 `right/fresh-blue`、`fish-bone/fish`、`tianpan/tianpan`；完整主题列表见 converter `doctor`。

缺省使用 `default/fresh-blue`。完整 JSON 的备注、链接、优先级、资源标签及折叠状态随模型保留；图片节点会返回 `unsupported_feature`，需要资源嵌入能力后再转换。渲染在上传前完成，预览校验与提交复用同一份产物。

已有合法 SVG 使用 `insert_minder_svg`，保留原始文件字节和可编辑模型。最终检查页面预览并在脑图编辑器重开确认。
