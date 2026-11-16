# D2C 编码流程参考

> 本文档是 explore-design-tree-ingee skill 的扩展参考。当用户要求基于设计稿数据编写代码时，按此流程执行。
> explore-design-tree-ingee 核心职责仍是数据提取，编码是可选的下游消费。

## 核心原则

**零自由发挥**：子 agent 是翻译机器，把数据翻译成代码，不允许有任何创作空间。

- 所有样式数值（尺寸、颜色、间距、圆角）必须来自数据文件，禁止凭经验猜
- 所有图标/装饰元素必须查 CDN 资源表，有切图就用切图，没有才用组件画
- 文本内容必须来自 extract_leaves 输出，不能自己编
- 不确定的地方写 `// TODO: 待确认`，不要自己填
- **编码规范必须遵守 max-preflight skill**（`~/.openclaw/skills/max-preflight/SKILL.md`），主 session 需将规范要点内联到 task 中传给子 agent

## 编码铁律

1. **先规划再编码**：拿到 JSON 后先看截图 → 读 `_ready.json` → 划分模块 → 确认切图。禁止跳过规划直接写代码
2. **逐模块实现**：每个模块走 `inspect_node → 编码 → 截图对比设计稿 → 修复` 循环。禁止一次性实现整个页面
3. **每个模块必须 Diff**：写完一个模块就截图对比，发现偏差立刻修复。禁止跳过 Diff 进入下一个模块
4. **数据驱动**：所有 CSS 值必须来自 `inspect_node` 输出，禁止凭记忆猜测任何数值

## 编码规则

### 数据驱动
- 每个 CSS 值必须来自 `inspect_node` / `extract_leaves` 输出，禁止凭记忆猜测
- 同构模块的第一个走完整 inspect；其余只提取差异字段（textContent、图片路径）

### 文本逐字保留
- `textContent` 必须原样使用，**禁止改写、缩略、替换分隔符或标点**
- Unicode 字符（中文引号 `""`、竖线 `|`、特殊空格）不得替换为 ASCII 近似字符

### 元素数量对齐
- 编码前先数 JSON 中目标模块的直接 `children` 数量
- 实现后的 DOM 元素数必须与 JSON **一一对应**，不增不减

### 布局方向校验
- 父节点 `style.display === 'flex'` 时：
  - 无 `flexDirection` 或值为 `'row'` → 子元素**横排**
  - `flexDirection: 'column'` → 子元素**竖排**
- **禁止**将横排设计实现为竖排
- flex 子节点不会有 `left`/`top`，若有 `flexGrow`/`alignSelf` 须保留

### 编码数据源（关键！禁止信息损耗）
- **编码时必须直接从语义 JSON 取值**：通过 `inspect_node` / `extract_leaves` 获取节点完整 style
- **中间文档（ANALYSIS.md 等）仅用于模块划分和规划**，不可作为编码的样式数据源
- **正确流程**：语义 JSON → 规划模块划分 → 逐模块 `inspect_node` 取原始 style → 编码

### 大页面多 Agent 并行编码
- **数据量大时可开多个子 agent**：每个子 agent 负责一个模块，直接从语义 JSON inspect 对应节点编码
- **主 agent 职责**：规划模块划分 → 分配模块根 nodeId 给各子 agent → 整合输出
- **子 agent 职责**：拿到 nodeId + 语义 JSON 路径 → `inspect_node` 取完整 style → 编码该模块的 tsx + scss
- **关键**：每个子 agent 都直接读原始 JSON，不经过中间翻译层，无信息损耗

## 流程

### Step 1: 主 session 提取设计稿数据（explore-design-tree-ingee 职责）

```bash
# 下载画板数据
python scripts/analyze/fetch_skeleton.py <imageId>

# 提取所有 CDN 切图资源
python -c "
import json
with open('<semantic.json>') as f:
    data = json.load(f)
# 递归找所有 _exportSrc 节点 → 输出 CDN_ASSETS.json
"

# 逐模块 inspect 获取精确样式
python scripts/analyze/inspect_node.py <json> <nodeId> --compact

# 提取叶子节点文本
python scripts/analyze/extract_leaves.py <json> <nodeId> --compact
```

产出物：
- `_ready.json` — 画板元信息
- `CDN_ASSETS.json` — 所有切图资源清单（nodeId → URL → 名称 → 用途）
- `STRUCTURE.md` — 页面骨架结构（树、模块划分）
- 各模块 inspect 数据

### Step 2: 主 session 做决策（不可委托子 agent）

| 决策项 | 说明 |
|--------|------|
| 组件选型 | 每个节点用 LImage/LinearGradient/Text/View？ |
| CDN vs 组件 | 有 `_exportSrc` 的节点用切图，没有的用组件实现 |
| 背景实现方式 | LImage 包裹子元素做背景图 |
| 编码规范选择 | max-preflight / 其他技术栈规范 |

产出物：
- 组件选型决策表
- 编码规范摘要（内联到 task，不依赖子 agent 自己读 skill）
- 实战样式补丁（读取 `references/ingee-d2c-style-rules.md`，内联到 task）

### Step 3: 按模块拆分多 agent 并行开发

#### 3.1 拆分策略
- 按页面模块拆分，每个子 agent 负责 1-2 个模块
- 推荐 3-4 个 agent 并行（视模块数量）
- 独立模块之间无依赖，可完全并行

#### 3.2 子 agent 的 task 模板

```
## 核心规则
- **所有样式值必须从 inspect_node 原始数据提取**，禁止凭经验猜测
- 查不到数据 → 写 TODO 注释，不要自己替代

## 你的工具
- 设计稿 JSON 路径
- inspect_node.py 命令
- extract_leaves.py 命令

## 你负责的模块根节点
| 模块 | 根节点 ID | 说明 |
（只给根节点 ID，让子 agent 自己递归查子节点）

## 工作流程
1. 对根节点跑 inspect_node，递归查所有子节点直到拿全样式
2. 根据原始数据写 TSX + SCSS

## CDN 切图
（本模块涉及的切图资源清单）

## 编码规范摘要
（完整内联，不能只给 skill 路径）

## 实战样式补丁
（读取 `references/ingee-d2c-style-rules.md` 并内联到此处，这些规则优先级高于 max-preflight 中的通用规则）

## 硬约束
- 必须按 inspect_node 数据编码，禁止凭感觉补
- 有 CDN 切图的必须用 LImage + source={{ uri }}
- 查不到/不确定的写 TODO，不要自作主张替代
- inspect_node 只输出 style，CDN 信息在上面的切图表里

## 输出
写到指定文件路径（part-x.tsx + part-x.scss）
```

#### 3.3 关键原则

| ✅ 正确做法 | ❌ 错误做法 |
|------------|-----------|
| 只给模块根节点 ID | 给精确叶子 nodeId 列表（会漏） |
| 让子 agent 自己递归 inspect | 主 agent 整理好样式数据喂给子 agent（会错） |
| 编码规范完整内联到 task | 只给 skill 路径让子 agent 自己读 |
| CDN 切图表内联到 task | 让子 agent 自己去查 _exportSrc |

#### 3.4 拼装

所有子 agent 完成后，主 session 负责：
1. 读取所有 part-x.tsx / part-x.scss
2. 统一 import 头、mock 数据、组件导出
3. 拼装为 index.tsx + index.module.scss
4. 修正不一致的 API 用法（如 `src=` → `source={{ uri }}`）

### Step 4: 主 session 审查 + 修补

#### 4.1 规范合规检查
用 grep 批量验证：
- [ ] 无 `gap:` 属性
- [ ] 无 CSS `linear-gradient`（应用 LinearGradient 组件）
- [ ] 无 `border:` 简写（必须拆分 border-width/color/style）
- [ ] 无 `white-space`（RN 不支持）
- [ ] 无 `height: 100%`
- [ ] 无动态 className（只允许静态字符串字面量）
- [ ] 无 `import React`
- [ ] 所有容器有 `display: flex`
- [ ] LImage 用 `source={{ uri: '...' }}` 格式
- [ ] line-height ≥ font-size × 1.3
- [ ] border-radius 多值需拆为四角

#### 4.2 像素级样式审查（必做！）
**目的**：验证代码中的数值与设计稿 inspect_node 原始数据一致。

**执行方法**：
1. 对每个模块根节点跑 `inspect_node`，提取关键样式值（font-size、line-height、width、height、padding、margin、border-radius、color）
2. 用 Python/正则从 SCSS 文件中提取对应 class 的同名属性值
3. 逐条对比，列出不一致项
4. 修复所有不一致

**重点检查项**（上次出错最多的）：
- font-size / line-height（容易被概括错）
- border-radius（容易写小）
- padding（容易写小）
- width（容易遗漏）
- border（容易遗漏）

**脚本模板**：
```python
import re
checks = [
    ('描述', 'class-name', 'expected-property: expected-value'),
    ...
]
for label, cls, expected in checks:
    pattern = r'\.' + re.escape(cls) + r'\s*\{([^}]+)\}'
    m = re.search(pattern, content)
    if m and expected in m.group(1):
        print(f'  ✅ {label}')
    else:
        print(f'  ❌ {label}')
```

#### 4.3 其他
- [ ] 所有 CDN 资源是否正确使用
- [ ] 有无遗漏的 TODO

## 注意事项

### inspect_node 的局限性

`inspect_node.py` 只输出 `style`、`children`、`tag` 等结构信息，**不输出以下元数据**：
- `_exportSrc` — CDN 切图 URL
- `_exportHint` — 导出类型（slice/icon）
- `_exportReason` — 导出原因
- `_mgType` — 节点类型（INSTANCE/PEN 等）
- `_autoTag` — 自动标签（icon 等）

因此子 agent 如果只用 inspect_node，**无法得知哪些节点有切图**。必须由主 session 提前提取 `_exportSrc` 并传递。

### 子 agent 的边界

| 子 agent 可以做 | 子 agent 不能做 |
|----------------|----------------|
| 按数据和决策表写代码 | 决定用什么方案实现 |
| 按规范写样式 | 自己去读 skill 文件做判断 |
| 遇到不确定写 TODO | 猜测/自作主张替代 |
| 读取落盘的数据文件 | 自己分析设计稿做决策 |

### 编码规范（强制）

写代码**必须**遵守 `max-preflight` skill 规范（`~/.openclaw/skills/max-preflight/SKILL.md`）。

主 session 派发 task 时，必须将 max-preflight 的关键规则内联到 task 文本中（不能只给路径让子 agent 自己去读），至少包括：
- Import 规范（`@max/max` 不是 react）
- 单位规范（rpx）
- border 拆分、无 gap、无 CSS 渐变
- line-height 对照表
- className 静态字符串
- LImage 用法（source + inline style）
- LinearGradient 方向对照
- SCSS 扁平选择器 + 显式 display:flex

### 与其他 skill 的关系

```
explore-design-tree-ingee       → 数据提取（结构、样式、CDN 资源表）
max-preflight   → 编码规范（Max/MRN 技术栈）— 必须遵守
max-kb-mcp      → 组件文档查询（如果知识库可用）
本文档           → 串联以上，定义编码流程
```
