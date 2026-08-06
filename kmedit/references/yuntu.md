# Yuntu 运维看板指南

用于 `kmedit` 的云图/Yuntu iframe 节点。Yuntu 通常承接运维看板、监控看板、值班大盘、SRE 观测、业务指标观测 widget 等场景；不要把它和 Minder 脑图混在同一个 reference 里。

## 什么时候使用

- 用户要求在 KM 中嵌入云图 / Yuntu 看板或 widget。
- 用户要放入运维监控大盘、SRE 排障面板、业务观测看板、值班大盘。
- 用户给出 Yuntu 链接、dashboardId、widgetId，或要求生成 `km-ref` 链接后插入 KM。
- 用户要求调整已有 Yuntu 看板的筛选条件，例如日期、组织、版本、城市、业务线等。

不适用：

- 脑图、思维导图、知识结构、树状拆解：使用 `insert_minder`，读 `references/minder.md`。
- 一次性静态 KPI 快照报告：使用 `km-html-dashboard`。
- 单张可编辑数据图表：使用 Data2Chart。
- Vega/Vega-Lite 图表或图表组：使用 `km-vega`。

## 基本规则

`insert_yuntu` 接收云图 `km-ref` 链接。优先使用 `meituan-yuntu` Skill 生成链接，再通过 `insert_yuntu` 插入原生云图 iframe 节点。

更新云图展示数据时，通常修改链接里的 `config` 查询参数：

1. 使用 `meituan-yuntu` Skill 的 `km-ref` 生成基础链接，或从已有 `open_iframe` / Yuntu 节点的 `attrs.src` 取出链接。
2. 解析 URL query，找到 `config` 参数。
3. 对 `config` 做 URL decode，并按 JSON 解析。
4. 按用户要求修改 JSON 字段，例如 `start_date`、`end_date`、`orgId`、`majorVersions` 等；字段名以目标 widget filters 为准，必要时先用 `yuntu filters <widget_id>` 确认。
5. 将修改后的 JSON 重新序列化并 URL encode，替换回原链接的 `config` 参数。
6. 插入新云图时直接使用 `insert_yuntu`；更新已有云图时，优先删除旧 Yuntu 节点并在原位置插入修改后的链接。

示例：

```text
config URL decode 后：
{"start_date":"2026-04-16","end_date":"2026-04-23","orgId":"1949","majorVersions":"8"}
```

如果用户要求把时间范围改为 `2026-04-20` 到 `2026-04-24`，只改 JSON 中对应字段，再 URL encode 回 `config=...`。

## Gotchas

- 云图应使用 `insert_yuntu`，不要退化成普通文本链接、普通 iframe 文本或静态截图。
- 云图链接里的 `config` 是 URL 编码后的 JSON；先 decode、按 JSON 改字段、再 encode，不要手写破坏编码。
- 如果数据来自 Yuntu/数据后台且需要下钻、筛选或实时观测，不要做成静态 HTML dashboard。
- 运维/SRE/监控看板通常应该保留为 Yuntu 原生 iframe 节点，方便复用后台权限、筛选和实时数据。
