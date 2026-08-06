# Ingee 设计稿数据格式说明

## 原始数据结构（MCP 返回）

```json
{
  "imageId": "1349286",
  "width": 828,
  "height": 921,
  "imagePath": "https://s3plus-img.meituan.net/...",
  "image_urls": [
    {"name": "xxx@1.5x", "format": "png", "url": "https://p0.meituan.net/..."}
  ],
  "trees": [{...}]  // 或 layersTree: {...}
}
```

## 节点字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `objectId` | string | 唯一标识，如 "16:0968" |
| `objectName` | string | 节点名称 |
| `objectType` | string | 类型：FRAME/GROUP/TEXT/RECTANGLE/ELLIPSE/LINE/PEN/VECTOR/STAR/POLYGON/BOOLEAN_OPERATION |
| `rect` | object | `{x, y, width, height, relativeX, relativeY}` |
| `css` | string[] | CSS 字符串数组，如 `["display: flex;", "color: #111;"]` |
| `content` | string | 文本内容（仅 TEXT 类型） |
| `children` | array | 子节点 |
| `isVisible` | bool | 是否可见（默认 true） |

## 节点类型 → HTML Tag 映射

| objectType | tag |
|------------|-----|
| FRAME / GROUP / COMPONENT / INSTANCE / SECTION / SLICE | `div` |
| TEXT | `span` |
| RECTANGLE / ELLIPSE | `div` |
| LINE | `hr` |
| PEN / VECTOR / STAR / POLYGON / BOOLEAN_OPERATION | `svg` |

## CSS 解析规则

CSS 数组中的每一条为一个字符串：
- 标准属性：`"color: #111111;"` → `{"color": "#111111"}`
- 注释行：`"// 自动布局"` → 跳过
- 复合值：`"background: linear-gradient(118deg, #FFE74D 0%, #FFDD00 100%);"` → 完整保留
- 复合边框：`"border: 1px solid #FF77004C;"` → 完整保留

解析后 key 会转为 camelCase（`font-size` → `fontSize`）。

## 归一化后新增字段

| 字段 | 说明 |
|------|------|
| `_mgType` | 原始 objectType 保留 |
| `_exportHint` | 自动检测的切图标记 |
| `_exportReason` | 切图原因（designer_marked/svg_node/svg_majority_group） |
| `_autoTag` | 自动分类（icon/deco/dynamic/statusbar） |
| `_sizing` | Flex 容器尺寸策略 `{w: "hug"|"fixed", h: "hug"|"fixed"}` |
| `_layoutSummary` | Flex 布局描述 |
| `_meta` | 设计稿元信息（imageId, imagePath, imageUrls） |

## 与 IMD 格式的区别

| 特性 | IMD | Ingee |
|------|-----|-------|
| CSS 格式 | style 对象 `{key: value}` | css 字符串数组 `["key: value;"]` |
| 文本字段 | `textContent` | `content` |
| 位置信息 | `style.left/top` | `rect.{x, y}` |
| 切图导出 | 需要下载 + 上传 CDN | `image_urls` 直接含 CDN 链接 |
| 语义标注 | 服务端自动生成 | 归一化时自动检测 |
| 数据获取 | Supabase Storage | MCP HTTP 调用 |
| 响应格式 | 单树根节点 | 含 meta 的包裹对象 |
