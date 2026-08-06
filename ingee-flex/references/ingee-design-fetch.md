# Ingee 视觉稿数据获取规则

## CLI 命令

使用 `duo ingee-fetch` 读取 Ingee 视觉稿 DSL 数据：

```bash
# 读取完整视觉稿数据
duo ingee-fetch -b <artboard_id>
# 读取视觉稿中指定图层的数据
duo ingee-fetch -b <artboard_id> -n <node_id>
```
| 参数 | 别名 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `--artboard` | `-b` | string | 是 | 视觉稿 ID |
| `--node-id` | `-n` | string | 否 | 图层节点 ID，不填时获取完整视觉稿数据 |

## 参数提取规则

链接示例：`https://ingee.meituan.com/#/artboard/1315894/pos_n?action=developer&layerId=2%3A071775&domId=773`

- `artboard_id`（传给 `-b`）：`#/artboard/` 后到下一个 `/` 之间的数字 → `1315894`
- `node_id`（传给 `-n`）：`layerId` 参数 URL 解码后的值 → `2:071775`

**特殊情况**：
- 链接中**无 `layerId`** 但用户口述了 node_id 或相近表达 → 使用用户提供的值
- 链接中**无 `layerId`** 且用户未提供 → 不传 `-n`，获取整个画板数据

## 返回字段语义

**顶层字段**：`artboardId`、`width`/`height`（画板尺寸 px）、`nodeId`、`layersTree`（图层树）、`imageUrl`（节点裁切图 URL）

**节点字段（LayerInfo）**：`objectID`（唯一标识）、`name`、`type`（`group`/`shape`/`text`/`slice`）、`rect.x`/`rect.y`/`rect.width`/`rect.height`、`color['color-hex']`、`color['css-rgba']`、`fontSize`、`fontFace`、`fontWeight`、`lineHeight`、`letterSpacing`、`opacity`、`content`（文本内容）、`radius`、`children`

## 尺寸换算规则

查看顶层 `width` 字段：
- `width: 750` → 2 倍图，需 ÷ 2（最常见）
- `width: 375` → 1 倍图，无需换算
- `width: 1125` → 3 倍图，需 ÷ 3

换算公式：`代码尺寸 = 视觉稿尺寸 × (开发基准宽度 / 视觉稿基准宽度)`

需要换算的属性：`rect` 尺寸、`width`/`height`/`padding`/`margin`、`border-width`/`border-radius`、`font-size`/`line-height`/`letter-spacing`/`text-indent`、`gap`/`top`/`right`/`bottom`/`left`、`box-shadow` 偏移值

不需要换算：颜色（`#FFFFFF`、`rgba()`）、百分比（`100%`）、透明度（`0`-`1`）、无单位值（`flex: 1`、`font-weight: 500`）

## 执行要求

### 强制执行

- 必须通过 `duo ingee-fetch` 获取数据，不得仅凭链接主观猜测结构
- `-n` 的值必须对 URL 中的 `layerId` 进行 URL 解码后使用
- 链接中无 `layerId` 时，须检查用户是否口述了 node_id 之类

### 禁止执行

- 禁止不调用 `duo ingee-fetch` 直接推断视觉稿结构
- 禁止直接使用 URL 中的编码值（如 `2%3A071775`）未解码
