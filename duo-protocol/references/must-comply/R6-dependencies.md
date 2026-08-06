# 依赖声明与物料注册表 dependencies.json + componentsMap.json

> 对应执行步骤：Step 3.6

## 目录

- [一、dependencies（依赖声明）](#一dependencies依赖声明)
- [二、componentsMap（物料注册表）](#二componentsmap物料注册表)
- [三、物料 ID 获取规则（MUST）](#三物料-id-获取规则must)
- [四、URL 路径规则](#四url-路径规则)
- [五、注意事项](#五注意事项)

## 一、dependencies（依赖声明）

列出页面用到的所有 npm 物料，运行前预加载。

```json
[
  {
    "name": "@hfe/max-button",
    "version": "4.0.4",
    "type": "component",
    "url": "https://s3plus-bj02.sankuai.com/yooz-assets/material/@hfe/max-button/4.0.4/index.js"
  },
  {
    "name": "@meishi/common-duo-lifecycle",
    "version": "1.1.0",
    "type": "logic",
    "url": "https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/1.1.0/index.js"
  }
]
```

## 二、componentsMap（物料注册表）

key 为页面内 materialId（字符串数字），每种组件只注册一次。

### proCode 组件

```json
"37": {
  "id": "135",
  "materialType": "proCode",
  "type": "component",
  "npm": "@max/leez-card",
  "npmVersion": "2.3.39",
  "web": [
    "https://s3plus-bj02.sankuai.com/yooz-assets/material/@max/leez-card/2.3.39/index.js"
  ]
}
```

### proCode 逻辑库

```json
"13": {
  "id": "19422",
  "materialType": "proCode",
  "type": "logic",
  "npm": "@meishi/common-duo-lifecycle",
  "npmVersion": "1.1.0",
  "web": [
    "https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/1.1.0/index.js"
  ]
}
```

### lowCode 组件

```json
"6073": {
  "id": "12345",
  "materialType": "lowCode",
  "type": "component",
  "name": "nav-bar"
}
```

## 三、物料 ID 获取规则（MUST）

| 规则 | 说明 |
|------|------|
| MUST | materialId 和版本 id 通过 `duo yooz-*` CLI（优先）/ MCP 工具查询或从 `materials.json` 获取 |
| MUST_NOT | 自行编造任何 materialId 或 id |
| MUST | 查询不到时，从 `materials.json` 备选；仍无则不使用该物料 |
| MUST | 物料版本 ID（`id`）与版本号（`npmVersion`）必须匹配 |

**获取优先级**：
1. `duo yooz-*` CLI 查询（优先）
2. MCP 工具查询（CLI 失败时降级）
3. 从 `references/materials.json` 复制
3. 均无法获取 → 不使用该物料

## 四、URL 路径规则

| type | CDN 路径 |
|------|---------|
| `component` | `https://s3plus-bj02.sankuai.com/yooz-assets/material/{name}/{version}/index.js` |
| `logic` | `https://s3plus-bj02.sankuai.com/yooz-assets/logic/{name}/{version}/index.js` |

> ⚠️ logic 类型必须使用 `/logic/` 路径，不能使用 `/material/` 路径。

## 五、注意事项

1. 所有 proCode 组件/逻辑库必须在 dependencies 和 componentsMap 中声明
2. lowCode 组件不需要在 dependencies 中声明，也没有 `web` URL
3. 所有 resource 都需要包含 `"buildConfig": null`
4. logics 标配 `common-duo-lifecycle` + `common-event-nav`
5. `nodeId` 每个节点实例全局唯一，推荐用 7 位数字
