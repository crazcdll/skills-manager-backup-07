---
name: trade-hotel-ai-coding-summary
description: "同步酒店 AI-Coding 需求开发统计文档与本周需求列表。当用户提到「同步 AI-Coding」「更新 AI-Coding 需求列表」「整理 AI-Coding」「AI-Coding 统计更新」「酒店需求同步」「更新酒店 AI-Coding 文档」时激活。输入两个学城文档链接（AI-Coding 文档 + 需求列表文档），自动对比并更新酒店需求的增删与链接修正，优先使用 PRD km 链接，最后输出变更报告。"
---

# 酒店 AI-Coding 需求文档同步

将本周需求列表与上周 AI-Coding 统计文档进行对比，同步酒店需求的增减与链接修正。

## 输入

用户提供两个学城文档 contentId：
1. **AI-Coding 文档**（要被更新的目标文档）：包含酒店各需求行
2. **需求列表文档**（作为基准的需求池）：包含本周酒店所有活跃需求

## 完整执行流程

### 1. 获取文档

```bash
# 切换到 Node 18+（oa-skills 需要 fetch API）
source ~/.nvm/nvm.sh && nvm use 18

# 获取 AI-Coding XML（记录 stepVersion）
oa-skills citadel getDocumentXml --contentId <ai_coding_id> --output /tmp/aicoding.xml

# 获取需求列表 Markdown
oa-skills citadel getSimpleMarkdown --contentId <requirement_id> --output /tmp/requirement.md
```

### 2. 运行同步脚本

```bash
python3 scripts/sync_ai_coding.py \
  --xml-path /tmp/aicoding.xml \
  --requirement-md /tmp/requirement.md \
  --output /tmp/aicoding_synced.xml \
  --changes-output /tmp/changes.json
```

脚本执行以下操作：
1. 解析 XML，定位统计表中的酒店行（通过 `rowspan` 方向标签）
2. 解析需求列表 markdown，提取所有 `product=20645` 或 `product=20421` 的酒店项
3. 按「km ID 精确匹配 → ONES ID 匹配 → 标题模糊匹配 → 研发同学匹配」建立映射
4. **保留行**：更新链接（PRD 优先），保留其他所有列原样
5. **删除**：AI-Coding 中存在但需求列表中不存在的行
6. **新增**：需求列表中存在但 AI-Coding 中不存在的行（16 标准列格式）
7. 更新 rowspan 数量 = 更新后的酒店行总数
8. **脚注修复**：自动检测并移除 `<km-footnote-item>` 内的 `<del>` 标签（这些删除线会导致 hover 表头注释时不显示内容）

### 3. 确认变更

读取 `/tmp/changes.json`，向用户展示摘要：
- 删除了哪些行
- 新增了哪些行
- 哪些行更新了链接（ONES → PRD）
- 保留了哪些行

**请用户确认后再执行上传。**

### 4. 上传更新

```bash
oa-skills citadel updateDocumentByXml \
  --contentId <ai_coding_id> \
  --file /tmp/aicoding_synced.xml \
  --step-version <stepVersion>
```

`stepVersion` 从步骤 1 返回的 `stepVersion` 字段获取。

### 5. 清理临时文件

```bash
rm -f /tmp/aicoding.xml /tmp/aicoding_synced.xml /tmp/requirement.md /tmp/changes.json
```

## 链接选择规则

需求列遵循「PRD 优先，ONES 兜底」原则：
1. 如果需求列表 prd 列有有效的 km PRD 链接 → 使用 PRD km 链接
2. 如果 prd 列为空、无链接、或仅有 ONES 链接 → 使用需求列表的 ones 链接

## 匹配算法

对每个需求列表项与每个 AI-Coding 酒店行计算匹配分数（≥ 0.3 视为匹配）：

| 匹配条件 | 加分 |
|---------|------|
| PRD km ID 精确匹配 | +0.9 |
| ONES ID 精确匹配 | +0.8 |
| 标准化标题完全一致 | +0.7 |
| 标准化标题包含关系 | +0.5 |
| 标题字符 Jaccard 相似度 | +0~0.3 |
| 研发同学交集非空 | +0.3 |

使用贪心算法：按分数降序排列，依次分配不冲突的匹配对。

## 表结构约束

AI-Coding 文档的统计表结构：
- **酒店首行**：17 逻辑列（含 `<td rowspan="N">` 方向标签）
- **后续酒店行**：16 逻辑列（由 rowspan 覆盖方向）
- 每行 16/17 个 `<td>` 必须完整存在

列顺序：#、需求、(方向)、研发同学、需求人力、开发状态、需求任务拆解、开发工具、AI工具开发情况、未使用AI开发原因、是否可以使用AI开发、AI完成度、AI成熟度分析、one-shot代码采纳率、人工参与成本、人工参与任务、AI提效

## 注意事项

- nodeId 属性在输出时会被移除，上传后学城自动重新生成，不影响数据完整性
- 保留行的所有数据列（开发状态、AI 提效等）原样保留，仅可能更新「需求」列的链接标题
- 新增行只有「需求」列和「研发同学」列有数据，其余列留空（空 `<p />`）
- 脚注修复仅作用于 `<km-footnote-item>` 节点内部，正文区域（如已删除的方向标签）的 `<del>` 标签不受影响

## 常见问题

### 脚注 hover 不显示内容

当 AI-Coding 文档是通过模板复制创建时，脚注注释可能被 `<del>` 标签包裹，导致鼠标 hover 表头上标时只显示"注释 [N]"而无具体内容。

脚本会自动检测并修复此问题：遍历 `<km-footnote-list>` 下的所有 `<km-footnote-item>`，移除内部的 `<del>` 和 `</del>` 标签，保留注释原文。修复情况会在输出日志中提示（如 `[INFO] 已修复 6 处脚注 <del> 标签`）。
