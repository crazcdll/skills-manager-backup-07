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

## 布局与主题

API-only 本地 renderer 支持的 `template`：

- `default`：默认左右展开脑图
- `right`：全部向右展开，适合流程/清单
- `filetree`：文件树结构
- `structure`：组织结构/自上而下结构

`fish-bone`、`tianpan` 等专用布局继续走 CDP runtime；API-only 会明确失败，不会把它们错误画成普通脑图。

常用 `theme`：

- `fresh-blue`：默认清爽蓝色，优先使用
- `fresh-green`：绿色主题
- `fresh-purple`：紫色主题
- `classic`：经典主题
- `snow`：浅色雪景主题
- `fish`：适合鱼骨图
- `wire`：黑底线框风格

## Gotchas

- `template` 控制布局预设，`theme` 控制颜色/样式；不要把内部 layout 名称当成 `template` 使用。
- `fish-bone` 建议搭配 `theme: "fish"`；`tianpan` 可搭配 `theme: "tianpan"`，但二者当前需要 CDP runtime。
- 如果不指定，renderer 默认使用 `template: "default"` 和 `theme: "fresh-blue"`。
- `patch` 的 `insert_minder` 使用本地 renderer，不依赖页面 `provider.serverUrl`，并在 SVG `content` 中保留完整 JSON 语义；不支持的模板应失败并走显式 CDP fallback。
- 不要把 Minder SVG 当普通图片插入；需要保留脑图语义时使用 `insert_minder_svg`。
