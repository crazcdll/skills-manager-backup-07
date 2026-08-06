# AI 生成 draw.io 流程图并插入学城文档

## 概述

AI 可以根据用户描述，生成完整的 draw.io 流程图（mxGraph XML 格式），并通过 `uploadDrawioToDocument` 命令将其上传到学城文档，最终插入到指定位置。

整个流程分为四步：

1. **AI 生成 mxGraph XML**（唯一格式：纯 mxCell 列表，见下文）
2. **将 XML 写入本地临时文件**
3. **调用 `uploadDrawioToDocument` 上传**（自动包装 SVG + 上传到学城）
4. **插入到目标文档**（getDocumentXml → 插入 drawio 节点 → updateDocumentByXml）

---

## 开始前的判断

生成前先评估请求是否足够明确。若缺少关键信息，主动询问 1-3 个问题：

- **图表类型** — 使用哪个预设？（流程图、架构图、时序图、UML类图、ERD 或通用）
- **复杂度** — 大约几个节点/组件？是否有子流程或泳道？
- **样式偏好** — 使用内置样式（default/corporate/handdrawn）还是通用默认？

若请求已足够明确（如"帮我画一个用户注册流程图"），跳过询问直接生成。

**主动触发场景**（不需要用户明确要求"画图"）：
- 解释包含 3 个以上交互组件的系统
- 描述多步骤流程或决策树
- 对比两种架构或方案

---

## 样式预设

**样式预设**是一套命名配置，定义了颜色板、形状词汇、字体、连线风格。当预设激活时，它替代下文"默认样式属性参考"中的内置约定。

### 内置预设

#### default（通用默认）

清晰、对比度高，适合大多数场景：

| 角色 | fillColor | strokeColor | 用途 |
|------|-----------|-------------|------|
| 服务/步骤 | `#dae8fc` | `#6c8ebf` | 普通节点、服务 |
| 数据库/成功 | `#d5e8d4` | `#82b366` | 数据库、成功状态 |
| 队列/判断 | `#fff2cc` | `#d6b656` | 判断节点、队列 |
| 网关/API | `#ffe6cc` | `#d79b00` | 网关、API 节点 |
| 错误/告警 | `#f8cecc` | `#b85450` | 错误、失败路径 |
| 外部/中性 | `#f5f5f5` | `#666666` | 外部系统、说明节点 |
| 安全/认证 | `#e1d5e7` | `#9673a6` | 安全、认证相关 |

形状：service=`rounded=1`，database=`shape=cylinder3`，decision=`rhombus`
字体：Helvetica 12px；连线：`edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1`

#### corporate（企业正式风）

更柔和的配色，直角矩形，适合正式文档和汇报：

| 角色 | fillColor | strokeColor |
|------|-----------|-------------|
| 服务/步骤 | `#e3f2fd` | `#1565c0` |
| 数据库/成功 | `#e8f5e9` | `#2e7d32` |
| 队列/判断 | `#fff9c4` | `#f57c00` |
| 网关/API | `#fff3e0` | `#e65100` |
| 错误/告警 | `#ffebee` | `#c62828` |
| 外部/中性 | `#eceff1` | `#455a64` |
| 安全/认证 | `#f3e5f5` | `#6a1b9a` |

形状：service=`rounded=0`（直角矩形），字体：Arial 11px；虚线用于：optional、async 关系
连线：`edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1`

#### handdrawn（手绘草图风）

暖色调、轻描边，适合头脑风暴和原型设计：

| 角色 | fillColor | strokeColor |
|------|-----------|-------------|
| 服务/步骤 | `#ffe4b5` | `#b8651e` |
| 数据库/成功 | `#def0dc` | `#5c8a49` |
| 队列/判断 | `#fff4cc` | `#b8901a` |
| 网关/API | `#ffd9b3` | `#c25100` |
| 错误/告警 | `#ffcdbf` | `#a53d3d` |
| 外部/中性 | `#f5e6d3` | `#8b7355` |
| 安全/认证 | `#e6d7e8` | `#7b4397` |

形状：service=`rounded=1`，附加 `sketch=1;strokeWidth=2`（手绘质感）
连线：`edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1;orthogonalLoop=1;jettySize=auto;html=1`

### 预设识别规则

扫描用户消息，判断激活哪个预设：
- 用户明确说"使用 `corporate` 风格"、"手绘风"、"handdrawn"、"正式风格" → 激活对应预设
- 否则默认使用 **default** 预设

激活预设后，在第一行回复中注明：*"使用样式预设：`corporate`"*

---

## 第一步：AI 生成 mxGraph XML

`uploadDrawioToDocument` 接受**唯一输入格式**：**纯 `<mxCell>` 元素列表**。工具自动补充 `mxfile + mxGraphModel + root + id=0/1 根节点`，无需手动包装。

> ⚠️ **严禁**传入包含 `<mxfile>`、`<mxGraphModel>` 或 `<root>` 外层标签的 XML，这些结构由工具自动生成。

### mxCell XML 格式规则

**必须遵守的关键规则**：

1. **只生成 mxCell 元素**（不含 `<mxfile>`、`<mxGraphModel>`、`<root>` 包装标签，也不含 `id="0"` 和 `id="1"` 的根节点），工具自动添加外层结构
2. **所有 mxCell 必须是兄弟元素**，绝对不能将 mxCell 嵌套在另一个 mxCell 内部（XML 结构上是平铺的，层级关系通过 `parent` 属性表达）
3. **每个 mxCell 必须有唯一的 id**，从 `"2"` 开始递增
4. **所有节点和连线的 `parent` 属性均为 `"1"`**，即顶层父容器
5. **边（连线）的 source/target 属性**必须引用已存在的节点 id
6. **禁止在 XML 中包含注释**（`<!-- ... -->`），工具会自动去除但注释本身容易干扰 AI 生成正确 parent 关系
7. **特殊字符必须用 HTML 实体编码**：`<` → `&lt;`，`>` → `&gt;`，`&` → `&amp;`，`"` → `&quot;`

### 布局约束

- 从合理边距开始排布（如 x=40, y=40），保持元素紧凑分组
- 画布尺寸由工具根据 mxCell 坐标自动推算，无需手动指定
- 节点宽高：普通节点统一 **140×60px**，菱形判断节点建议 **140×80px**

### 节点（vertex）示例

```xml
<mxCell id="2" value="开始" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
  <mxGeometry x="340" y="40" width="140" height="60" as="geometry"/>
</mxCell>
```

### 连线（edge）示例

```xml
<mxCell id="5" style="edgeStyle=orthogonalEdgeStyle;exitX=0.5;exitY=1;entryX=0.5;entryY=0;endArrow=classic;" edge="1" parent="1" source="2" target="3">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

### 连线路由规则（重要！防止连线穿过节点）

> 以下规则供 AI 自身生成 XML 时遵守；美化提示词模板中的对应规则措辞更详细，面向下游 AI 传递。

**规则 1：必须明确指定 exitX、exitY、entryX、entryY**
- 每条连线必须在 style 中设置这 4 个属性
- 连接点选择自然方向，不要用角点（entryX=1,entryY=1 等角落位置）
- 上下流向：从底部出（exitY=1），从顶部入（entryY=0）
- 左右流向：从右侧出（exitX=1），从左侧入（entryX=0）

**规则 2：多条连线不能共用同一路径**
- 两个节点间有多条连线时，必须用不同的 exitY/entryY（如 0.3 和 0.7）
- 双向连线（A↔B）必须走对边：A→B exitY=0.3，B→A exitY=0.7

**规则 3：连线 label 必须错开，不得与其他 label 或节点文字重叠**
- 如果两条连线的中点距离 < 30px，必须用 exitY 或 waypoint 将路径偏移，使中点间距 ≥ 30px
- 连线 label 文字长度 **≤ 8 字**，超长截短，否则背景框会与相邻节点重叠

**规则 4：连线严禁穿过任何节点，必须绕行（添加 waypoint）**
- ⚠️ **最高优先级**：连线路径（包括每段折线的全程）不得经过任何节点的矩形 `[x, x+w] × [y, y+h]` 区域内
- 生成每条连线后，**立即用坐标数值逐段检验**是否与任何节点矩形相交——不得凭直觉跳过检查
- 如果有，必须添加 waypoint（通过 `<Array as="points"><mxPoint .../></Array>` 实现）绕行
- 绕行时给节点边界留 ≥ 30px 间隙；优先绕到整张图的最外侧空白区域（图左侧、右侧、上方、下方）

**带 waypoint 的连线示例**（绕过障碍物）：

```xml
<mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;exitX=0.5;exitY=1;entryX=0.5;entryY=0;endArrow=classic;" edge="1" parent="1" source="A" target="B">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="750" y="80"/>
      <mxPoint x="750" y="150"/>
    </Array>
  </mxGeometry>
</mxCell>
```

**规则 5：多连线分布到不同接入点**

当同一节点有 N 条连线接入同一侧时，将接入点均匀分布，防止线条堆叠：

| 接入侧 | 1 条 | 2 条 | 3 条 |
|--------|------|------|------|
| 底部（exitY=1） | exitX=0.5 | exitX=0.25 / 0.75 | exitX=0.2 / 0.5 / 0.8 |
| 右侧（exitX=1） | exitY=0.5 | exitY=0.25 / 0.75 | exitY=0.2 / 0.5 / 0.8 |

### 默认样式属性参考

> 当无样式预设激活时使用。若预设激活，以预设颜色为准。

- **节点圆角**：`rounded=1;whiteSpace=wrap;html=1;`
- **填充颜色**：`fillColor=#dae8fc;strokeColor=#6c8ebf;`
- **决策菱形**：`rhombus;whiteSpace=wrap;html=1;`
- **圆形**：`ellipse;whiteSpace=wrap;html=1;`
- **粗体文字**：`fontStyle=1;fontSize=14;`
- **连线样式**：`endArrow=classic;startArrow=none;curved=1;`

---

## 图表类型预设

根据用户请求的图表类型，选择对应的形状、样式和布局约定：

### 流程图（Flowchart）

标准业务流程、审批流、操作流程：

| 节点类型 | 形状 | style 参考 |
|---------|------|-----------|
| 开始/结束 | 椭圆 | `ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;` |
| 普通步骤 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;` |
| 判断分支 | 菱形 | `rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;` |
| 输入/输出 | 平行四边形 | `shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;` |
| 子流程 | 双边框矩形 | `rounded=0;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;` |
| 成功/完成 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#2E7D32;fontColor=#1B5E20;` |
| 失败/异常 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#FFEBEE;strokeColor=#C62828;fontColor=#B71C1C;` |
| 外部系统 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#F3E5F5;strokeColor=#6A1B9A;fontColor=#4A148C;` |

布局：TB（从上到下），垂直间距 200px，判断节点两侧分支向左右延伸再向下汇合。判断分支连线**必须标注"是"/"否"或具体条件文字**。

### 架构图（Architecture Diagram）

系统架构、微服务、数据流：

| 节点类型 | 形状 | style 参考 |
|---------|------|-----------|
| 层/分区 | 泳道容器 | `swimlane;startSize=30;fillColor=#dae8fc;strokeColor=#6c8ebf;` |
| 服务 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;` + 按层级配色 |
| 数据库 | 圆柱体 | `shape=cylinder3;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;` |
| 消息队列/总线 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;` |
| 网关/负载均衡 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;` |
| 外部系统 | 虚线矩形 | `rounded=1;dashed=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;` |

布局建议：≤4层用 TB，消息总线/Kafka 节点放在服务行**中央**（左侧服务用 `exitX=1`，右侧服务用 `exitX=0`，避免所有连线交叉）。

泳道容器示例（子节点坐标相对于容器）：
```xml
<mxCell id="tier1" value="Service Layer" style="swimlane;startSize=30;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
  <mxGeometry x="80" y="80" width="600" height="180" as="geometry"/>
</mxCell>
<mxCell id="svc1" value="User Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="tier1">
  <mxGeometry x="40" y="60" width="140" height="60" as="geometry"/>
</mxCell>
```

### 时序图（Sequence Diagram）

参与者交互、API 调用时序：

| 节点类型 | 形状 | style 参考 |
|---------|------|-----------|
| 参与者/生命线 | 生命线 | `shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;portConstraint=eastwest;` |
| 同步消息 | 实线箭头 | `html=1;verticalAlign=bottom;endArrow=block;` |
| 异步消息 | 虚线箭头 | `html=1;verticalAlign=bottom;endArrow=open;dashed=1;` |
| 返回消息 | 虚线灰色 | `html=1;verticalAlign=bottom;endArrow=open;dashed=1;strokeColor=#999999;` |

布局：LR（从左到右），参与者间距 200px，时间从上到下流动。

### UML 类图（UML Class Diagram）

类、接口、继承关系：

| 关系类型 | style 参考 |
|---------|-----------|
| 继承 | `endArrow=block;endFill=0;` |
| 实现接口 | `endArrow=block;endFill=0;dashed=1;` |
| 组合 | `endArrow=diamondThin;endFill=1;` |
| 聚合 | `endArrow=diamondThin;endFill=0;` |

类框：`swimlane;fontStyle=1;align=center;startSize=26;html=1;`（含标题/属性/方法三段）

### ERD（实体关系图）

数据模型、表关系：

| 元素 | style 参考 |
|------|-----------|
| 表（容器） | `shape=table;startSize=30;container=1;collapsible=1;childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;strokeColor=#6c8ebf;fillColor=#dae8fc;` |
| 列（行子元素） | `shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;fillColor=none;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontSize=12;` |
| 主键列 | 列 style 加 `fontStyle=1` 并加 `PK` 前缀 |
| 外键关系 | `dashed=1;endArrow=ERmandOne;startArrow=ERmandOne;` |

---

## 网格对齐布局规范

### 坐标对齐原则

**所有 x、y、width、height 值必须是 10 的倍数**（与 draw.io 默认网格对齐，便于后续手动编辑）：

```
✅ x=40, y=80, width=140, height=60
❌ x=43, y=77, width=135, height=58
```

### 间距规范（根据复杂度调整）

| 图表复杂度 | 节点数 | 水平间距 | 垂直间距 |
|-----------|--------|---------|---------|
| 简单 | ≤5 | 200px | 150px |
| 中等 | 6–10 | 280px | 200px |
| 复杂 | >10 | 350px | 250px |

### 走线通道

相邻两列/行之间必须预留 **≥ 120px** 的空白走线通道（两列节点左右边缘之间的空白，不是节点间距）：

```
列1节点 x=40~180 | 通道 x=180~300 | 列2节点 x=300~440 | 通道 x=440~560 | 列3节点 x=560~700
```

### 画布比例

- **横向图**（步骤多、左右流向）：选 **16:9**（如 960×540、1200×675）
- **竖向图**（层级深、上下流向）：选 **4:3**（如 800×600、960×720）
- 不确定方向时默认选 **4:3**
- 节点较多时，优先**多列网格布局**（如 3×4、4×3），而不是一列竖排到底
- 上下流向图超过 6 个节点时，将节点分为左右两列或多列并排

---

## 生成质量自检清单

生成 XML 后，输出前必须逐项检验（发现问题立即修改，**不得跳过**）：

1. ❌ 是否存在斜线（非水平/非垂直线段）？→ 全部改为正交折线
2. ❌ 是否有任意连线线段经过任意节点的矩形 `[x, x+w] × [y, y+h]` 区域？→ 用坐标数值验算，加 waypoint 绕到图外缘
3. ❌ 从同一节点出发是否有多条线走相同/相近路径（间距 < 15px）？→ 错开出口位置
4. ❌ 是否存在连线交叉？→ 重新规划布局或拆分子图
5. ❌ 内容较多时画布比例是否接近 1:1，或超出 4:3～16:9 的范围？→ 根据内容方向改为 4:3 或 16:9
6. ❌ 是否有多条连线的 label 落点距离 < 30px？→ 调整路径使中点错开
7. ❌ 连线 label 文字是否超过 8 字？→ 缩短文案
8. ❌ 坐标是否是 10 的倍数？→ 调整到最近的 10 倍数

---

## 美化流程图提示词模板

生成美观流程图时，可将以下提示词作为指令传给 AI，约束其输出质量：

````
请生成一个美观的 draw.io mxGraph XML 流程图，要求如下：

---

## 🔧 XML 结构规则（必须严格遵守）

1. **只输出纯 `<mxCell>` 元素列表**，不包含 `<mxfile>`、`<mxGraphModel>`、`<root>` 包装标签，也不含 `id="0"` 和 `id="1"` 的根节点
2. **所有 mxCell 必须是平级兄弟元素**，绝对不能将 mxCell 嵌套在另一个 mxCell 内部（层级关系通过 `parent` 属性表达）
3. **id 从 `"2"` 开始递增**，每个 mxCell 必须有唯一 id
4. **所有节点和连线的 `parent` 属性均为 `"1"`**
5. **禁止在 XML 中使用注释**（`<!-- ... -->`）
6. **特殊字符使用 HTML 实体**：`<` → `&lt;`，`>` → `&gt;`，`&` → `&amp;`
7. **坐标必须是 10 的倍数**，以便与 draw.io 网格对齐

---

## 📐 布局规范

- 整体方向：从上到下（或从左到右）单向流动，避免折回
- 从合理边距开始排布（建议 x=40, y=40），坐标根据节点数量自然延伸，不设硬性上限
- 节点间距：水平间距 ≥ 80px，垂直间距 ≥ 60px
- **生成 XML 前，先规划布局**：按列/行分区，预判每条连线路径是否会穿越其他节点
- **画布比例首选 4:3 或 16:9**：
  - 横向图（流程步骤多、左右流向）：选 **16:9**（如 960×540、1200×675）
  - 竖向图（层级深、上下流向）：选 **4:3**（如 800×600、960×720）
  - 不确定方向时默认选 **4:3**
  - 内容较多时，尽量避免使用接近 1:1 的比例（如 800×800），应根据内容方向选 4:3 或 16:9
  - 比 4:3 更窄或比 16:9 更宽的极端比例不适合流程图，应拆分子图
  - 节点较多时，优先采用**多列网格布局**（如 3×4、4×3），而不是一列竖排到底或一行横排到右
  - 上下流向图超过 6 个节点时，将节点分为左右两列或多列并排，通过连线连接各列
  - 左右流向图超过 5 个节点时，分多行排列
- **必须预留走线通道**（这是避免连线交叉的关键）：
  - 相邻两列之间的间距 ≥ 120px（不是节点边距，是两列节点左右边缘之间的空白）
  - 相邻两行之间的间距 ≥ 80px
  - 每列/行节点的 x/y 坐标必须严格对齐，不允许参差不齐
  - 走线通道示例（3列布局）：列1节点 x=40~180，通道 x=180~300，列2节点 x=300~440，通道 x=440~560，列3节点 x=560~700
- **同列多个节点纵向排列时，相互间距 ≥ 80px**，留出横向连线穿越的空隙
- **坐标全部取 10 的倍数**，与 draw.io 默认网格对齐

---

## 🎨 节点样式

节点宽度统一 **140px**，高度统一 **60px**（菱形判断节点建议 **140×80**）

| 节点类型 | 形状 | style 参考 |
|---------|------|-----------|
| 开始/结束 | 椭圆 | `ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontColor=#1B5E20;fontSize=12;fontStyle=1;` |
| 普通步骤 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=#dae8fc;strokeColor=#6c8ebf;fontColor=#0D47A1;fontSize=12;` |
| 判断分支 | 菱形 | `rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontColor=#E65100;fontSize=12;` |
| 输入/输出 | 平行四边形 | `shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=12;` |
| 成功/完成 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=#E8F5E9;strokeColor=#2E7D32;fontColor=#1B5E20;fontSize=12;` |
| 失败/异常 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=#FFEBEE;strokeColor=#C62828;fontColor=#B71C1C;fontSize=12;` |
| 外部系统 | 圆角矩形 | `rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=#F3E5F5;strokeColor=#6A1B9A;fontColor=#4A148C;fontSize=12;` |

---

## 🔗 连线路由规则（核心原则：正交 + 不交叉 + 不压节点）

> ⚠️ **连线交叉是流程图最严重的可读性问题**，必须在布局阶段彻底规避，而不是生成后补救。

### 前置原则：布局决定连线质量

**连线质量 90% 取决于布局**。如果布局导致连线必然交叉，必须重新设计布局，而不是试图用复杂 waypoint 绕行。

- **单向流动原则**：所有主流程连线应沿同一方向（统一向右或统一向下），不允许主流程连线逆向
- **分层间距原则**：相邻两列（行）之间必须留出 ≥ 120px 的走线通道，用于连线通过
- **连线数量上限**：从同一个节点出发的连线 ≤ 3 条；超过则考虑重新组织结构

---

**规则 1：严禁斜线，所有连线必须正交（水平+垂直折线）**
- ❌ 禁止：直接连接两个非正交对齐的节点（会产生斜线穿过图的中间区域）
- ✅ 正确：使用 `edgeStyle=orthogonalEdgeStyle` + waypoint 将所有线段变为水平/垂直折线
- 斜线示例（**禁止**）：`M 740 490 L 660 385`（这是斜线！）
- 正交示例（**正确**）：先水平到中间列，再垂直到目标行

**规则 2：同向多条连线必须分层，不能共用同一 y（或 x）坐标**
- 从同一节点出发的多条连线，每条必须使用不同的出口位置（exitY 错开 ≥ 0.2）
- 同方向平行的多条连线，必须保持 ≥ 15px 的间距，不能在同一坐标上重叠
- 反向连线（A→B 和 B→A）必须走对边：A→B 用 exitY=0.3，B→A 用 exitY=0.7

**规则 3：连线严禁压在任何节点上**
- ⚠️ **优先级最高**：连线路径的任意一段不得经过任意节点的 `[x, x+w] × [y, y+h]` 矩形范围内
- 判断方法：逐段检查每条水平/垂直线段，确认不与任何节点矩形相交
- 解决方案：在节点外侧（上下左右各留 ≥ 30px）规划走线通道，所有连线只在通道内走线
- 绕行策略：优先绕到整张图的边缘（最左列左侧、最右列右侧、最上行上方、最下行下方）
- **强制要求**：生成每条连线后，立即用坐标数值检查其折线段是否与所有节点矩形相交，相交则必须加 waypoint 绕行，不得跳过检查

**规则 4：每条连线必须显式指定 exitX/exitY/entryX/entryY**
- 每条连线在 style 中必须有这 4 个属性
- 连接方向规范：
  - 左→右流向：`exitX=1;exitY=0.5;entryX=0;entryY=0.5`
  - 上→下流向：`exitX=0.5;exitY=1;entryX=0.5;entryY=0`
  - 不允许 entryX 和 entryY 同时为 0 或 1（角点）

**规则 5：所有绕行使用 waypoint，路径必须清晰**

```xml
<!-- 正确示例：绕到图的右侧边缘再进入目标节点 -->
<mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;exitX=1;exitY=0.5;entryX=1;entryY=0.5;endArrow=classic;html=1;" edge="1" parent="1" source="A" target="B">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="1150" y="230"/>  <!-- 绕到图右侧边缘 -->
      <mxPoint x="1150" y="490"/>  <!-- 垂直到目标行高度 -->
    </Array>
  </mxGeometry>
</mxCell>
```

**规则 6：连线 label 必须错开，不得与其他 label 或节点文字重叠**
- 每条连线的 label 落点是**折线路径的中点线段的中心**
- 如果两条连线的中点距离 < 30px，必须用 `exitY` 或 waypoint 将其中一条路径偏移，使中点间距 ≥ 30px
- 连线 label 文字长度 **≤ 8 字**（汉字/字符数），超长截短或改写，否则背景框会与相邻节点重叠
- 在同一水平段上有多个 label 时，各 label 的 x 坐标必须错开 ≥ label 宽度

**规则 7：生成后必须逐条自检（缺一不可，发现问题必须修改后才能输出）**
1. ❌ 是否存在斜线（非水平/非垂直线段）？→ 全部改为正交折线
2. ❌ 是否有任意连线线段经过任意节点的矩形 `[x, x+w] × [y, y+h]` 区域？→ 用坐标数值验算，不得靠感觉判断，加 waypoint 绕到图外缘
3. ❌ 从同一节点出发是否有多条线走相同/相近路径（间距 < 15px）？→ 错开出口位置
4. ❌ 是否存在连线交叉（两条线路径相交）？→ 重新规划布局或拆分子图
5. ❌ 内容较多时画布比例是否接近 1:1，或超出 4:3～16:9 的范围？→ 根据内容方向改为 4:3 或 16:9
6. ❌ 是否有多条连线的 label 落点距离 < 30px？→ 调整路径使中点错开
7. ❌ 连线 label 文字是否超过 8 字？→ 缩短文案
8. ❌ 坐标是否是 10 的倍数？→ 调整到最近的 10 倍数

连线统一样式：`edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;endArrow=classic;html=1;`
````

---

## ✏️ 文字规范

- 节点文字简洁（≤ 12 字）；**连线 label ≤ 8 字**，越短越好（背景框宽度随文字等比增大，过长会压住相邻节点）
- **⚠️ value 必须是纯文本，禁止嵌入 HTML 标签**：
  - CLI 渲染器基于 SVG `<text>` 标签，**不支持任何 HTML 内容**
  - ❌ 禁止：`value="应用A&lt;div&gt;(业务系统)&lt;/div&gt;"`  → 渲染为乱码 `应用A&lt;div&gt;...`
  - ❌ 禁止：`value="第一行<div>第二行</div>"`、`value="第一行&#xa;第二行"`、`value="第一行<br>第二行"`
  - ✅ 正确：`value="应用A(业务系统)"`（括号补充说明写在同一行）
  - ✅ 正确：`value="SSO认证中心 IdP"`（空格分隔多段信息）
  - 如果文字确实过长，**优先缩短文案**，而不是尝试换行
  - ⚠️ **注意**：style 中的 `html=1` 是 draw.io 渲染引擎的样式控制开关，与 value 内容无关——**即使 style 含 `html=1`，value 也必须是纯文本**，不要写 HTML 标签
- 关键节点加粗：`fontStyle=1`
- 字号统一：`fontSize=12`；连线 label 字号 `fontSize=10`
- 判断分支连线必须标注条件文字（如"是"/"否"，或具体条件），**同样使用纯文本**
- **连线 label 也禁止使用 HTML 标签**：`value="① 发起请求"` ✅，`value="① 发起&lt;div&gt;请求&lt;/div&gt;"` ❌

---

## 第二步：将 XML 写入本地临时文件

AI 生成 XML 后，写入临时文件（推荐路径 `/tmp/diagram-<timestamp>.xml`）：

```bash
# 将 mxCell XML 内容写入临时文件
cat > /tmp/diagram.xml << 'EOF'
<mxCell id="2" value="开始" ... />
<mxCell id="3" value="处理" ... />
...
EOF
```

---

## 第三步：上传到学城

```bash
oa-skills citadel uploadDrawioToDocument \
  --contentId <目标文档ID> \
  --file /tmp/diagram.xml
```

**参数说明**：

| 参数 | 必须 | 说明 |
|------|------|------|
| `--contentId` | ✅ | 目标文档 ID，附件权限将与此文档绑定 |
| `--file` | ✅（与 --mxCells 二选一）| 包含 mxCell XML 的本地文件路径 |
| `--mxCells` | ✅（与 --file 二选一）| 直接传入 mxCell XML 字符串 |

**返回值**：

```
✅ Drawio 流程图上传成功！
学城 Drawio CDN URL：https://km.sankuai.com/api/file/cdn/<contentId>/<attachmentId>?contentType=0&isNewContent=false
附件 ID：228651870995

CitadelXML Drawio 节点（可直接插入文档 XML）：
<km-drawio src="https://km.sankuai.com/api/file/cdn/..." width="960" height="720" nodeId="uuid-xxx" />
```

---

## 第四步：插入到目标文档

使用 `getDocumentXml` → 插入 drawio 节点 → `updateDocumentByXml` 流程：

```bash
# 获取目标文档当前 XML 内容
oa-skills citadel getDocumentXml --contentId <id> --output /tmp/doc.xml

# AI 在指定位置插入 drawio 节点（<km-drawio src="..." width="<自动推算>" height="<自动推算>" nodeId="uuid-xxx" />）

# 回传更新文档
oa-skills citadel updateDocumentByXml --contentId <id> --file /tmp/doc.xml --step-version <stepVersion>
```

**CitadelXML drawio 节点格式**：

```xml
<km-drawio src="<学城CDN URL>" width="<宽度>" height="<高度>" nodeId="uuid-xxx" />
```

- `src`：学城附件 CDN URL（由 uploadDrawioToDocument 返回的 url 字段），**必填**
- `width`：画布宽度（px），由 uploadDrawioToDocument 自动推算，**必填**
- `height`：画布高度（px），由 uploadDrawioToDocument 自动推算，**必填**
- `nodeId`：插入新节点时生成新 UUID，修改已有节点时保留原属性

---

## 迭代设计流程

生成初稿后，若用户需要调整，按以下最小变更原则修改，**避免每次都全量重新生成**：

| 用户请求 | 修改动作 |
|---------|---------|
| 修改某节点颜色 | 找到对应 mxCell，只更新 style 中的 fillColor/strokeColor |
| 新增节点 | 在 XML 末尾追加新 mxCell，使用下一个可用 id |
| 删除节点 | 删除对应 mxCell vertex，以及所有 source/target 指向它的 edge |
| 移动节点位置 | 更新对应 mxCell 的 mxGeometry x/y |
| 调整节点大小 | 更新对应 mxCell 的 mxGeometry width/height |
| 新增连线 | 追加新 edge mxCell，source/target 引用已有节点 id |
| 修改 label 文字 | 更新对应 mxCell 的 value 属性 |
| 调整整体布局方向 | **全量重新生成**，重新规划 TB/LR 布局 |

**迭代规则**：
- 单元素变更：就地修改 XML，保留其他节点的位置调优
- 布局大幅重构（如 TB 改 LR）：全量重新生成
- 每次迭代后重新上传，使用 `uploadDrawioToDocument` 获取新的 CDN URL
- 将文档 XML 中原有的 `<km-drawio ...>` 替换为新的 drawio 节点（保留 nodeId）

**迭代轮次建议**：
- 5 轮内无法收敛时，建议用户直接在当前文档 编辑 流程图，这是更高效的精细调整方式

---

## 完整示例流程

**用户**：帮我在文档 https://km.sankuai.com/collabpage/1234567890 中插入一个用户注册流程图

**AI 执行步骤**：

```bash
# 第一步：AI 生成并写入 mxCell XML 到临时文件
cat > /tmp/register-flow.xml << 'EOF'
<mxCell id="2" value="用户填写注册信息" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
  <mxGeometry x="40" y="40" width="140" height="60" as="geometry"/>
</mxCell>
...（完整 mxCell 列表）
EOF

# 第二步：上传到学城（指定目标文档 ID）
oa-skills citadel uploadDrawioToDocument \
  --contentId 1234567890 \
  --file /tmp/register-flow.xml

# 第三步：获取文档 XML 内容
oa-skills citadel getDocumentXml --contentId 1234567890 --output /tmp/doc.xml

# 第四步：AI 在正确位置插入 <km-drawio ...> 节点
# 第五步：回传
oa-skills citadel updateDocumentByXml --contentId 1234567890 --file /tmp/doc.xml --step-version <stepVersion>
```

---

## 禁止事项

- **严禁直接将非学城 Drawio URL 写入文档 XML**，必须先通过 `uploadDrawioToDocument` 上传获取学城 CDN URL
- **严禁在 mxCell XML 中包含 XML 注释**（`<!-- ... -->`），会导致 draw.io 渲染失败
- **严禁在 mxCell 中嵌套 mxCell**，所有 mxCell 必须是平级的兄弟元素
- **严禁在 XML 中包含 `<mxfile>`、`<mxGraphModel>`、`<root>` 等包装标签**，工具只接受纯 mxCell 列表，传入外层结构会导致解析错误
- drawio 附件使用 `uploadDrawioToDocument` 上传，**不可使用 `uploadAttachmentToDocument`**（后者返回的 URL 格式无法被学城正确渲染为 drawio 流程图）

---

## 修改已有 Drawio 流程图

若用户要求修改文档中已有的流程图，流程如下：

1. `getDocumentXml` 获取文档 XML，找到 `<km-drawio src="<url>" ...>` 节点
2. `fetchDrawio --drawioUrl "<url>"` 获取流程图的 mxGraph XML 源数据（`mxGraphXml` 字段）
3. AI 根据 `mxGraphXml` 中的 mxCell 内容进行修改（增删改节点和连线），**只保留 mxCell 元素**，去掉 mxfile/mxGraphModel/root 外层标签
4. 将修改后的**纯 mxCell 列表** XML 写入临时文件
5. `uploadDrawioToDocument` 重新上传，获取新的 CDN URL 和 drawio 节点
6. 将文档 XML 中原有的 `<km-drawio ...>` 替换为新的 drawio 节点（保留 nodeId）
7. `updateDocumentByXml` 回传更新文档

> ⚠️ **修改流程图时基于 `mxGraphXml` 而非 `svgContent`**：`mxGraphXml` 是流程图的完整数据源（节点/连线/样式/布局），`svgContent` 是渲染后的展示图形，不可直接修改。
