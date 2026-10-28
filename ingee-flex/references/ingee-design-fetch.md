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

## 参数提取规则与前置校验（MUST，先于 CLI 调用执行）

链接示例：`https://ingee.meituan.com/#/artboard/1315894/pos_n?action=developer&layerId=2%3A071775&domId=773`

- `artboard_id`（传给 `-b`）：`#/artboard/` 后到下一个 `/` 之间的数字 → `1315894`
- `node_id`（传给 `-n`）：`layerId` 参数 URL 解码后的值 → `2:071775`

### 前置校验规则（MUST）

在执行 `duo ingee-fetch` 之前，必须先完成以下链接格式校验：

1. 链接必须匹配格式 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n`（`pos_n` 后可附带其他 query 参数，不影响校验），即：
   - 域名必须为 `ingee.meituan.com`
   - 路径中必须包含 `#/artboard/<artboard_id>/pos_n` 结构
2. `artboard_id` 必须存在，即 `#/artboard/` 与下一个 `/` 之间必须能解析出非空的数字/字符串
3. 只要链接格式不匹配上述结构，或 `artboard_id` 缺失/解析失败，**立即停止执行**，不得调用 `duo ingee-fetch`，也不得凭空猜测 `artboard_id`
4. 停止后向用户汇报链接错误，需明确指出问题，例如：
   > ⚠️ Ingee 视觉稿链接格式不正确：未能解析出 `artboard_id`。请提供格式为 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 的完整 Ingee 视觉稿链接后重试。
5. 校验通过后才可继续提取 `node_id` 并进入 CLI 调用

**特殊情况**：
- 链接中**无 `layerId`** → 不传 `-n`，获取整个画板数据；`node_id` **只能从链接的 `layerId` 参数解析获得**

### 项目级链接识别（MUST，单独校验点）

除上述格式校验外，还需专门识别**项目详情页链接**（而非单张视觉稿链接），典型形如：

```
https://ingee.meituan.com/#/detail/258568/default
```

- 该类链接路径结构为 `#/detail/<project_id>/default`（或类似 `/detail/` 开头的项目级路径），**不是** `#/artboard/<artboard_id>/pos_n` 单张视觉稿结构
- 项目详情页链接指向的是**包含多张视觉稿的项目集合**，无法从中确定唯一需要分析的一张或多张视觉稿
- 识别到此类链接（路径含 `#/detail/` 而非 `#/artboard/`）时，**视为校验不通过**，与「参数提取规则与前置校验」章节的判定结论一致：**立即停止执行**，不得调用 `duo ingee-fetch`，也不得尝试遍历/猜测项目下的某张视觉稿
- 停止后必须向用户提问澄清，明确说明链接类型问题，例如：
  > ⚠️ 检测到的链接 `https://ingee.meituan.com/#/detail/258568/default` 是 **Ingee 视觉稿项目链接**，其中包含多张视觉稿，无法确定需要分析的具体一张或多张。请打开该项目后，进入具体需要分析的视觉稿页面，复制格式为 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 的单张视觉稿链接后重试。
- 若需求文档中同时存在多个链接，需**逐一校验**，项目级链接与单张视觉稿链接分别识别，不得因文档中存在其他合法链接而忽略项目级链接的错误

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

- **必须先完成链接前置校验**（域名为 `ingee.meituan.com`、路径含 `#/artboard/<artboard_id>/pos_n`、`artboard_id` 非空），校验通过后才可执行 `duo ingee-fetch`
- 必须通过 `duo ingee-fetch` 获取数据，不得仅凭链接主观猜测结构
- `-n` 的值必须对 URL 中的 `layerId` 进行 URL 解码后使用，且只能来自链接本身的 `layerId`
- 链接中无 `layerId` 时，不传 `-n`，获取整个画板数据

### 禁止执行

- **禁止在链接格式不匹配或 `artboard_id` 缺失/解析失败时继续执行**，必须立即停止并汇报链接错误
- **禁止将项目详情页链接（`#/detail/<project_id>/default` 等）当作单张视觉稿链接处理**，也不得尝试猜测或遍历项目下的具体视觉稿，识别到此类链接必须立即停止并向用户提问澄清
- 禁止在 `artboard_id` 缺失时凭空猜测或使用默认值代替
- 禁止不调用 `duo ingee-fetch` 直接推断视觉稿结构
- 禁止直接使用 URL 中的编码值（如 `2%3A071775`）未解码
- **禁止接受任何非链接来源的 `node_id`**：`node_id` 必须且只能来自链接中 `layerId` 参数的解码结果
