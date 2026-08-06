---
name: explore-design-tree-ingee
description: |
  印迹（Ingee）设计稿数据获取与分析工具集（自包含版本，不依赖 explore-design-tree-remote）。
  当用户提供 ingee.meituan.com 设计稿链接，或需要从印迹设计稿中提取结构/样式/CSS 信息时触发。
  关键词：设计稿、印迹、ingee、d2c、图层、节点、CSS、样式。

metadata:
  skillhub.creator: "zhangyixuan22"
  skillhub.updater: "zhangyixuan22"
  skillhub.version: "V23"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3855"
  skillhub.high_sensitive: "false"
---

# Ingee 设计稿数据获取与分析工具集

> 本 skill 的核心职责是**设计稿数据提取与分析**。
>
> ⚠️ **编码铁律**：当用户要求基于设计稿写代码时，**必须先读取 `references/d2c-coding-workflow.md`**，禁止跳过直接编码。
> 所有样式值、文本内容、切图资源必须从工具输出获取，禁止凭经验猜测。违反即为不合规。

## 💡 推荐

如果你使用的是 **imd.sankuai.com（MasterGo）** 设计稿，欢迎使用 [explore-design-tree](https://friday.sankuai.com/skills/skill-detail?activeTab=overview&activeTestTab=cases&from=/skills-market?deepSearch=false%26keyword=explore-design-tree%26mainView=skill%26orderByDownloadCount=all%26orderByTotalCallCount=all%26orderByTotalCallerCount=all%26page=1%26pageSize=30%26securityScanStatus=all%26spaceKeyword=%26spaceSortOrder=default%26spaceTypeFilter=org,project%26spaceVerifiedFilter=all%26tag=%26verifiedType=all%26viewMode=card%26visibility=all&id=13388)——数据无清洗，准确度更高。

---

## 使用方式

### 0. layerId 交互确认（URL 解析后、下载前）

当用户提供的 Ingee URL 中包含 `layerId` 参数时，**必须先询问用户意图**，再决定下载方式：

> 检测到你选中了一个具体图层（layerId=xxx），你是想：
> 1. **只分析这个局部区域**
> 2. **分析完整画板**（可能是误点到了某个图层）

- 用户选 1 → 带 layerId 下载（局部子树）
- 用户选 2 → **去掉 layerId**，只用 imageId 下载完整画板

> **为什么要确认？** 用户在 Ingee 中浏览设计稿时，经常会不小心点到某个切图层/子节点，
> 导致 URL 自动带上 layerId。如果不确认就直接拉局部数据，会丢失全局上下文。

如果 URL 不含 layerId，则直接进入下载步骤，无需确认。

### 1. 下载设计稿数据

```bash
# 完整画板（无 layerId 或用户确认要完整画板）
python ${SKILL_DIR}/scripts/download_ingee.py --image-id <imageId> --outdir "$PWD/.d2c"

# 局部子树（用户确认只分析该区域）
python ${SKILL_DIR}/scripts/download_ingee.py "<ingee_url>" --outdir "$PWD/.d2c"
```

或使用 imageId + layerId：

```bash
python ${SKILL_DIR}/scripts/download_ingee.py --image-id 1416266 --layer-id "743:043823" --outdir "$PWD/.d2c"
```

> 下载完成后自动生成归一化 JSON（`.semantic.json`）+ `_ready.json`。
> 归一化后的格式与 IMD 兼容，可直接使用所有分析脚本。

### 2. 手动归一化（如果已有原始 JSON）

```bash
python ${SKILL_DIR}/scripts/_normalize.py raw_ingee.json --output normalized.json
```

## 数据存储结构

```
.d2c/
├── _index.json                          # 索引
├── {imageId}/
│   ├── _ready.json                      # 快速索引（含 previewPath/previewUrl）
│   ├── preview.png                      # 画板预览图（下载时自动导出）
│   ├── {frameName}.json                 # 原始 Ingee JSON（MCP 返回原样）
│   ├── {frameName}.semantic.json        # 归一化 JSON（IMD 兼容 + semantic 标注）
│   └── (切图由 MCP 按需导出)
```

> **与 IMD 的关键区别**：Ingee 的数据中切图 CDN 链接已直接包含在 `image_urls` 中，无需单独下载切图资产。

## 工作流

### Phase 0: 视觉理解（最优先）

> **为什么要先看图？** 没有视觉上下文，agent 容易编造假数据、搞错布局结构。
> 这一步让你在开始分析 JSON 之前，先对设计稿建立全局视觉印象。

下载时会自动导出画板预览图到 `.d2c/{imageId}/preview.png`。

> **注意**：由于在下载前已通过「layerId 交互确认」步骤确保了正确的下载范围，
> 此时的 preview.png 已经是用户期望的视觉范围（完整画板或指定局部）。

```bash
# 直接查看预览图
read .d2c/{imageId}/preview.png
```

**关键**：先看 preview.png → 脑子里建立"这个页面长什么样" → 再进入 Phase 1 分析 JSON。

#### 多树场景（treeCount > 1）

当 `_ready.json` 中 `treeCount > 1` 时，说明设计稿包含多棵独立的图层树（通常对应页面的不同区块）。

1. **先不带 layerId 拉全量数据**：确保所有树都被下载和归一化
2. **查看 `_meta.trees[]` 中每棵树的 `rect` 位置**：`rect.y` 从小到大就是从上到下的视觉顺序（归一化后已自动按 `rect.y` 升序排列）
3. **用完整预览图（不带 layerId）建立整体视觉认知**：多树场景下，preview.png 覆盖整个画板，能看到所有树的相对位置关系
4. **按 `trees[]` 数组顺序逐树分析**：数组顺序即视觉从上到下的顺序

如果预览图缺失或需要单独导出某个节点的截图：
```bash
# 手动调用 MCP 导出指定节点
python -c "
from download_ingee import mcp_call
resp = mcp_call('ingee_export_image', {'imageId': '{imageId}', 'layerId': '{nodeId}', 'localPath': '/tmp/node.png'})
print(resp.get('imageUrl', ''))
"
# 然后用 curl 下载 imageUrl
```


### Phase 1: 结构分析

1. **读摘要**：Read `.d2c/{imageId}/_ready.json`，了解节点总数、切图数量
2. **看骨架**：`fetch_skeleton $SEMANTIC_JSON --compact` 查看模块层级
3. **定位模块**：根据骨架划分组件边界，记录每个模块的根 nodeId，用 `search_nodes` 定位具体节点
4. **确认切图策略**：
   - `search_nodes --has-cdn --max-results 200 --compact` 列出所有有 CDN 链接的节点（`_exportSrc` 字段）
   - `search_nodes --exportable --max-results 200 --compact` 列出所有可导出节点（语义标注）
   - `search_nodes --prefer asset --compact` 看哪些节点语义建议当切图（不等于有 CDN）
   - `search_nodes --prefer review --compact` 看哪些需要人工判断
5. **切图清单**：区分"有 CDN 可直接用"（`--has-cdn`）、"需要导出但没 CDN"、"代码还原"三类
6. **导出切图**：需要导出的节点统一用 `smart_export.py --batch` 批量导出（自动处理 SVG 叶子提升）

> 不需要编码的场景到这里即可结束。

### Phase 2: 编码（当用户要求写代码时触发）

**铁律（违反任一条即为不合规，必须停下来检查）**：

1. **禁止主 session 直接写代码** → 必须 spawn 子 agent 逐模块编码
2. **禁止凭记忆取样式值** → 必须逐模块 `inspect_node` 从原始 JSON 取 style
3. **禁止跳过 Diff** → 每个模块写完必须截图对比设计稿
4. **禁止跳过此步骤** → 必须先读取 `references/d2c-coding-workflow.md`，按其流程执行

**必须完成的前置动作**（读完 workflow 后执行）：
- 落盘 `CDN_ASSETS.json`（切图资源清单）
- 产出组件选型决策表
- 将 max-preflight 规范要点内联到子 agent task 中

详细流程见 `references/d2c-coding-workflow.md`（**必读**，不是建议）。

## Edit Mode：迭代已有设计稿

> 用户提供 before + after 两个 Ingee 设计稿，且已有代码对应 before 版本。
> 与 Create Mode 的区别：不全量重写，而是识别变更范围、最小化改动。
> 完整设计说明 → `references/edit-mode.md`

**Step 1** 下载两帧（各一次 `download_ingee.py`，带 `--image-id`）

**Step 2** 生成视觉摘要：`python ${SKILL_DIR}/scripts/analyze/visual_diff.py before.semantic.json after.semantic.json`
输出 `unchanged / changed / new / gone` 四类极简标注，无交叉引用。

**Step 3** 视觉优先判断：**先看 `preview.png` 截图 → 再看摘要 → 再看代码**。合并同构/父子 new 条目，看截图确认 gone 是否真消失。

**Step 4** 输出 Edit Plan（不动 / 更新 / 新增 / 删除各列模块，每项写视觉变化 + 行动）

**Step 5 Loop Guard** — 输出后必须自检，有违规则删除后重新输出：
- ❌ 描述层级变化（"从容器 A 移到容器 B"）、引用 before nodeId 描述 after 模块、使用结构性动词（合并/拆分/提取/重组）、解释 new↔gone 对应关系
- ✅ 只描述视觉变化、只描述代码行动、用截图可见内容命名模块

**Step 6** 逐模块执行：不动→跳过 | 更新→inspect+修改+Diff | 新增→Create Mode | 删除→移除代码

## 快速参考

### 视觉理解

| 工具 | 用途 |
|------|------|
| `analyze/visual_diff.py $BEFORE $AFTER` | 生成极简视觉级变更摘要（unchanged/changed/new/gone），Edit Mode 核心工具 |
| `analyze/diff_report.py $BEFORE $AFTER [-o report.html]` | 生成 HTML 可视化对比报告，供人工 review |

### 结构查看

| 工具 | 用途 |
|------|------|
| `layout_blueprint.py $JSON` | ASCII 布局树，直观展示层级和尺寸。支持 `--root-id` 聚焦子模块、`--max-depth N` 控制深度 |
| `fetch_skeleton.py $JSON` | 轻量骨架树，标注节点类型/文本/切图标记。支持 `--root-id`、`--max-depth N`、`--collapse` |

### 节点查询

| 工具 | 用途 |
|------|------|
| `search_nodes.py $JSON` | 多条件搜索：`--text`/`--name`/`--exportable`/`--has-cdn`/`--role`/`--prefer`/`--style key=val` |
| `inspect_node.py $JSON "nodeId"` | 获取节点的完整 CSS 样式+子树。`--with-parent` 附加父容器布局和兄弟节点 |
| `extract_leaves.py $JSON "nodeId"` | 提取指定节点下所有叶子节点（文本、图片、样式） |
| `analyze/to_css.py $JSON "nodeId"` | 节点 style 渲染为可直接粘贴的 CSS，属性按定位→盒模型→布局→视觉→排版分组。`--with-children` 附带直接子节点 |

### 空间测量（Diff 阶段必用）

> 依赖 `_normalize.py` 写入的 `_abs` 绝对坐标字段，归一化时自动生成，覆盖全节点。
> 节点引用支持 id / `text:子串` / `name:子串`，`--up N` 上提到模块层。

| 工具 | 用途 |
|------|------|
| `analyze/measure.py $JSON <ref>` | 单节点到 Frame 四边的边距 |
| `analyze/measure.py $JSON <refA> <refB>` | 两节点水平/垂直间隙 + 对齐边 + 包含关系 |
| `analyze/measure.py $JSON <ref1> <ref2> <ref3>` | 多节点相邻间距 + 等距判定（`uniformGap`） |
| `analyze/measure.py $JSON <ref> --prev/--next` | 量与上/下（左/右）相邻兄弟的距离 |
| `analyze/measure.py $JSON <ref> --neighbors` | 四向最近邻 + 间距，一次看清上下左右 |
| `analyze/crop_node.py $JSON <ref>` | 裁切节点区域设计稿截图（自动找 preview.png），逐模块 Diff 必用 |
| `analyze/locate_at.py $JSON <x> <y>` | XY 坐标反查节点链，Diff 发现"某处不对"时快速定位 |

```bash
# 示例
SEMANTIC_JSON=".d2c/123456/MyFrame.semantic.json"

# 量某模块到 Frame 四边的边距
python ${SKILL_DIR}/scripts/analyze/measure.py $SEMANTIC_JSON name:做任务赢积分

# 量两个模块间距
python ${SKILL_DIR}/scripts/analyze/measure.py $SEMANTIC_JSON "457:89615" "457:89650"

# 量列表项是否等距
python ${SKILL_DIR}/scripts/analyze/measure.py $SEMANTIC_JSON "id1" "id2" "id3"

# 裁出某模块的设计稿截图做 Diff
python ${SKILL_DIR}/scripts/analyze/crop_node.py $SEMANTIC_JSON name:积分钱包

# 截图某点坐标反查节点
python ${SKILL_DIR}/scripts/analyze/locate_at.py $SEMANTIC_JSON 320 480

# 节点样式转 CSS
python ${SKILL_DIR}/scripts/analyze/to_css.py $SEMANTIC_JSON "457:89615"
python ${SKILL_DIR}/scripts/analyze/to_css.py $SEMANTIC_JSON "457:89615" --with-children
```

### 切图导出（推荐）

| 工具 | 用途 |
|------|------|
| `export/smart_export.py $JSON "nodeId"` | **智能单个导出**：自动检测 SVG 叶子并向上提升到父容器，避免裁切不全。支持 `--name` 指定文件名 |
| `export/smart_export.py $JSON --batch "id1,id2,..."` | **智能批量导出**：一条命令导出多个节点，自动提升 + 下载到本地 |

> **为什么用 smart_export 而不是直接调 MCP？**
> `ingee_export_image` 按节点 rect 裁切画板截图。SVG 叶子节点（path/pen）的 rect 只是路径本身的 bounding box，
> 不含周围留白，导致 icon 被裁紧甚至缺边。`smart_export` 自动检测这种情况并向上找到合适的父容器导出。
>
> 规则：SVG 叶子 + 父容器只有 1 个 child → 用父容器 ID 导出（最多向上 3 级）

```bash
# 示例：传叶子 ID 也能自动找到正确容器
python ${SKILL_DIR}/scripts/export/smart_export.py $SEMANTIC_JSON \
  "878:087539/171:27491/171:27244/171:30018" \
  --outdir .d2c/{imageId}/exports

# 批量导出
python ${SKILL_DIR}/scripts/export/smart_export.py $SEMANTIC_JSON \
  --batch "id1,id2,id3" \
  --outdir .d2c/{imageId}/exports
```

### 切图管理（高级）

| 工具 | 用途 |
|------|------|
| `attach_exports.py $JSON` | 将切图路径回写到 JSON 节点 |
| `upload_exports.py $EXPORTS_JSON --token $SSO_TOKEN` | 批量上传切图到 CDN |

### 后处理

| 工具 | 用途 |
|------|------|
| `postprocess.py normalize $JSON` | 生成 semantic companion（下载时已自动执行） |

> 所有脚本默认推荐 `--compact`，减少上下文消耗。调试时可去掉。

> **分析脚本说明**：analyze/ 下的脚本为独立实现（V4+ 不依赖 explore-design-tree-remote），数据格式与 IMD 兼容。

## Ingee 特有数据特点

- **CSS 是字符串数组**：`["display: flex;", "color: #111;"]` → 归一化后解析为标准 style dict
- **文本在 `content` 字段**：→ 归一化为 `textContent` + `textSegments`
- **位置在 `rect` 对象**：`{x, y, width, height, relativeX, relativeY}` → 归一化到 `style`
- **切图 CDN**：`image_urls` 直接提供 CDN 链接，无需上传
- **节点类型**：`objectType` (FRAME/TEXT/RECTANGLE/...) → 归一化为 HTML `tag`

## 核心规范

- **数据驱动**：样式数值来自工具输出，不凭记忆猜测
- **按需获取**：按模块分批提取，不要一次读整个 JSON
- **避免**将大型 JSON（>500 行）全量 Read 到上下文——使用 Python 脚本按需提取
- **避免重复实现**：`_exportSrc` 与 `children` 共存时，默认同一模块
- **切图优先走 SOP**：search_nodes → 确认清单 → smart_export 批量导出 → attach_exports

## 详细参考（按需读取）

| 文件 | 内容 | 何时查阅 |
|------|------|----------|
| `references/ingee-format.md` | Ingee 原始数据格式说明 | 需要理解 JSON 字段含义时 |
| `references/d2c-coding-workflow.md` | D2C 编码流程（子 agent 编排、CDN 资源传递、决策分工） | 用户要求基于设计稿写代码时 |
| `references/edit-mode.md` | Edit Mode 设计原理与架构说明（三层架构、Loop Guard 设计决策） | 迭代已有设计稿时 |

## 与 IMD (explore-design-tree-remote) 的关系

本 Skill 是 explore-design-tree-remote 的 Ingee 适配版（V4+ 完全自包含）：
- **归一化层**：`_normalize.py` 将 Ingee 格式转为 IMD 兼容格式
- **语义引擎**：`_semantic.py` 归一化后自动调用，给每个节点标注 `semantic: {role, prefer, asset}`
- **分析脚本**：analyze/ 下独立实现（不依赖 symlink）
- **差异**：下载方式不同（MCP vs Supabase），切图天然内嵌 CDN 链接

