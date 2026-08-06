# 物料 ID 配置错误总结

以下错误是在实际生成协议过程中遇到的，请避免类似问题：

## 1. ❌ 错误：物料版本 ID（`id`）与版本号（`npmVersion`）不匹配

**错误现象**：协议解析时报错 `物料id：xx不存在`

**错误原因**：同一物料的不同版本有不同的版本 ID（`id`），不能随意编造或复用其他版本的 `id`。

**错误示例**：

```json
"37": {
  "id": "134",
  "materialType": "proCode",
  "type": "component",
  "npm": "@max/leez-card",
  "npmVersion": "2.3.39",
  "web": [...]
}
```

> ❌ `id: "134"` 是 `@max/leez-button` 的版本 ID，错误地用到了 `@max/leez-card`

**正确写法**：从 `materials.json` 中查找该物料对应版本的 `id`

> ✅ key `"37"` 是物料 ID（materialId），`id: "135"` 是 `@max/leez-card@2.3.39` 对应的版本 ID

```json
"37": {
  "id": "135",
  "materialType": "proCode",
  "type": "component",
  "npm": "@max/leez-card",
  "npmVersion": "2.3.39",
  "web": [...]
}
```

## 2. ❌ 错误：使用不存在的物料

**错误原因**：不是所有 npm 包都在 DUO 资产平台上有对应的物料配置。

**常见不存在的物料**（截至 2026 年 3 月）：

- `@max/leez-navigation-bar` - 不在 `materials.json` 中
- `@hfe/max-view` - 不在 `materials.json` 中
- `@hfe/max-textinput` - 不在 `materials.json` 中
- `@max/leez-style-util` - 不在 `materials.json` 中
- `@max/leez-toast` - 不在 `materials.json` 中

**解决方案**：使用 `duo yooz-*` CLI 或 MCP 工具查询或者`materials.json` 中存在的物料替代，或联系物料负责人添加。

## 3. ✅ 正确：从 CLI/MCP 查询或者`materials.json` 查询物料版本 ID

**查询方法**：

1. 使用 `duo yooz-*` CLI（优先）或 MCP 工具查询，或在`materials.json` 中搜索物料的 npm 包名
2. 找到该物料对应的 `materialId`（作为 `componentsMap` 的 key）
3. 在 `versions` 数组中找到目标版本
4. 使用该版本的 `id` 作为 `componentsMap` 中的 `id` 字段

**示例**：查询 `@max/leez-card@2.3.39`

`materials.json` 中的结构（其中 `id: 135` 对应版本 `2.3.39`）：

```json
{
  "materialId": 37,
  "npm": "@max/leez-card",
  "label": "Leez卡片容器",
  "versions": [
    { "id": 6709, "version": "2.5.58" },
    { "id": 135, "version": "2.3.39" }
  ]
}
```

**对应的 componentsMap 配置**：

> 版本 `2.3.39` 对应的 `id` 为 `135`，从上方 `materials.json` 查询得到

```json
"37": {
  "id": "135",
  "materialType": "proCode",
  "type": "component",
  "npm": "@max/leez-card",
  "npmVersion": "2.3.39",
  "web": ["https://s3plus-bj02.sankuai.com/yooz-assets/material/@max/leez-card/2.3.39/index.js"]
}
```

## 4. ✅ 正确：常用物料版本 ID 对照表

| npm 包名 | materialId | 版本号 | 版本 ID (id) |
| --- | --- | --- | --- |
| `@max/leez-button` | 36 | 2.3.39 | 134 |
| `@max/leez-card` | 37 | 2.3.39 | 135 |
| `@max/leez-text` | 38 | 2.3.39 | 136 |
| `@max/leez-tip` | 39 | 2.3.39 | 137 |
| `@max/leez-icon` | - | - | 不在 materials.json 中 |
| `@meishi/common-layout-top-bottom` | 7 | 2.1.5-scroll-beta.6 | 22000 |
| `@meishi/common-duo-lifecycle` | 13 | 1.1.1-lifecycle-check.1 | 19422 |
| `@meishi/common-event-nav` | 90 | 2.1.5-hotel.0 | 19702 |

>⚠️ **重要**：版本 ID 会随着版本更新而变化，使用前请务必通过 `duo yooz-*` CLI / MCP 查询或者在`materials.json` 中核实。

## 5. 🔴 危险信号检测（Agent 自检清单）

> **⚠️ 历史踩坑（2026-04-16）**：Agent 在写入 componentsMap 时将 materialId 写成 `600`（实际应为 `1332`），版本 id 也错误。根因是 Agent 跳过了物料查询步骤，凭记忆/猜测填写了 ID。以下危险信号用于 Agent 在执行过程中自我检测。

### 5.1 危险信号列表

| # | 危险信号 | 风险等级 | 含义 | 处置 |
|---|---------|---------|------|------|
| 1 | 准备写 materialId 但说不出确切来源 | 🔴致命 | 正在编造ID | **立即停止 → 调用 MCP** |
| 2 | "我记得是这个 ID"、"大概是 xxx" | 🔴致命 | 记忆不可靠 | **立即停止 → 调用 MCP** |
| 3 | 从旧协议文件/其他页面复制 ID 未重新查询 | 🟡高 | 版本可能已变 | **立即停止 → 调用 MCP验证** |
| 4 | 从非 MCP / 非 materials.json 的来源获取 ID | 🔴致命 | 来源不合法 | **立即停止 → 仅使用合法来源** |
| 5 | 觉得"查 MCP 太麻烦了，直接写吧" | 🔴致命 | 偷懒倾向 = 错误源头 | **强制自己调用 MCP** |
| 6 | 写入 componentsMap 时没有注释标注来源 | 🟡高 | 无法追溯 | **补充来源注释** |

### 5.2 强制查询流程（Step 3.6.0）

在写入 componentsMap **之前**，MUST 按以下流程执行：

```
1. 列出待查物料（npm 包名 + 目标版本）
   ↓
2. 调用 CLI/MCP 工具查询（按优先级）
   ├─ **CLI 优先**：`duo yooz-read-detail -n "<包名>"` 或 `duo yooz-getby-packagename -p "<包名>"`
   └─ **MCP 降级**：`mcp_tool_duo_ai_mcp_server_read_yooz_material_detail(names=[包名])` 或 `mcp_tool_duo_ai_mcp_server_get_material_by_package_name(packageNames=[包名])`
   ↓
3. CLI 和 MCP 均失功？→ 降级到 references/materials.json
   ↓
4. 输出查询结果表给用户确认
   ↓
5. 用户确认后 → 写入 componentsMap（附来源注释）
```

### 5.3 合法数据来源（仅限以下两种）

| 优先级 | 数据来源 | 工具/文件 | 说明 |
|--------|---------|----------|------|
| P0（首选） | `duo yooz-*` CLI 工具 | `duo yooz-read-detail` / `duo yooz-getby-packagename` | 实时查询 YOOZ 资产平台，输出 JSON 到 stdout |
| P1（降级） | MCP 工具 | `mcp_tool_duo_ai_mcp_server_read_yooz_material_detail` / `get_material_by_package_name` | CLI 失败时降级使用 |
| P2（备选） | `references/materials.json` | 本地静态文件 | CLI 和 MCP 查询均失败时的离线备选 |

**任何其他来源（记忆、猜测、旧文件复制、AI训练数据）均为非法。**

### 5.4 写入规范（带来源标注）

❌ 错误：无来源标注，无法验证

```json
"600": {
  "id": "1234",
  "npm": "@meishi/some-comp",
  "npmVersion": "1.0.0"
}
```

✅ 正确：带来源标注，可追溯（来源信息写在代码块外部，不写入 JSON）

> 来源: MCP查询 @meishi/some-comp@1.0.0 → materialId=1332, id=5678, 2026-04-16T15:30:00

```json
"1332": {
  "id": "5678",
  "materialType": "proCode",
  "type": "component",
  "npm": "@meishi/some-comp",
  "npmVersion": "1.0.0",
  "web": ["https://s3plus-bj02.sankuai.com/yooz-assets/material/@meishi/some-comp/1.0.0/index.js"]
}
```
