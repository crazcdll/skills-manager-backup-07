---
name: trade-hotel-ai-coding-summary
description: "同步酒店 AI-Coding 需求开发统计文档与本周需求列表。当用户提到「同步 AI-Coding」「更新 AI-Coding 需求列表」「整理 AI-Coding」「AI-Coding 统计更新」「酒店需求同步」「更新酒店 AI-Coding 文档」时激活。输入排期文档 + AI-Coding 文档两个学城链接，自动从排期文档提取本周需求池需求，生成需求列表子文档挂到 AI-Coding 文档下，再同步 AI-Coding 文档的酒店需求增删与链接修正，优先使用 PRD km 链接，最后输出变更报告。"

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V3"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "114687"
  skillhub.high_sensitive: "false"
---

# 酒店 AI-Coding 需求文档同步

从排期文档自动提取本周需求池需求，生成需求列表挂到 AI-Coding 文档下，再与上周 AI-Coding 统计文档对比，同步酒店需求的增减与链接修正。

## 输入

用户提供两个学城文档 contentId：
1. **排期文档**（需求来源）：含境内酒店、境外酒店、民宿三个多维表格，"需求排期"列标记"本周需求池"
2. **AI-Coding 文档**（要被更新的目标文档）：包含酒店各需求行

## 完整执行流程

### 1. 前置检查

```bash
# 切换到 Node 18+（oa-skills 需要 fetch API）
source ~/.nvm/nvm.sh && nvm use 18

# 确保 oa-skills 可用
command -v oa-skills || npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com
```

### 2. 从排期文档提取本周需求列表

```bash
python3 scripts/extract_requirements.py \
  --contentId <排期文档contentId> \
  --mis zhangce07 \
  --output /tmp/requirement.md
```

脚本执行步骤：
1. 获取排期文档 XML，解析其中的 `<km-xtable>` 标签，通过 h4 标题匹配出国内酒店、境外酒店、民宿三个业务线表格
2. 对每个表格调用 `getTableMeta` 获取列结构，动态查找"需求排期""需求ones""需求文档""需求主R""研发状态"列的 columnId
3. 用 `queryTableData` 筛选"需求排期 == 本周需求池"的行
4. **按业务线过滤研发状态**（排除已终态需求）：
   - 国内酒店、境外酒店：排除"已上线""已归档"
   - 民宿：排除"已完成"
5. 提取每行的 ONES 链接、PRD 链接、需求主R MIS
6. 输出 Markdown 表格（`| ones | prd | 研发同学 |`），格式兼容 `sync_ai_coding.py` 的 `parse_requirement_md`

向用户展示提取摘要：各业务线需求数量、负责人分布。

### 3. 创建需求列表子文档（挂到 AI-Coding 文档下）

```bash
oa-skills citadel createDocument \
  --title "本周需求列表" \
  --file /tmp/requirement.md \
  --parentId <ai_coding_contentId> \
  --mis zhangce07
```

将生成的需求列表作为 AI-Coding 文档的子文档创建。创建成功后向用户展示子文档链接。

> 说明：子文档用于归档本周需求列表，方便回溯。同步步骤直接用本地 `/tmp/requirement.md`，不依赖子文档读取，避免新建文档的缓存延迟。

### 4. 获取 AI-Coding XML

```bash
oa-skills citadel getDocumentXml --contentId <ai_coding_id> --mis zhangce07 --output /tmp/aicoding.xml
```

记录返回的 `stepVersion` 字段，上传时需要。

### 5. 运行同步脚本

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
4. **标题一致性过滤**：匹配时校验需求标题一致（normalize 后），避免同人不同需求被错误配对、仅换链接保留旧数据
5. **保留行**：更新链接（PRD 优先），保留其他所有列原样
6. **删除**：AI-Coding 中存在但需求列表中不存在的行
7. **新增**：需求列表中存在但 AI-Coding 中不存在的行（16 标准列格式）
8. 更新 rowspan 数量 = 更新后的酒店行总数
9. **脚注修复**：自动检测并移除 `<km-footnote-item>` 内的 `<del>` 标签

### 6. 确认变更

读取 `/tmp/changes.json`，向用户展示摘要：
- 删除了哪些行
- 新增了哪些行
- 哪些行更新了链接（ONES → PRD）
- 保留了哪些行

**请用户确认后再执行上传。**

### 7. 上传更新

```bash
oa-skills citadel updateDocumentByXml \
  --contentId <ai_coding_id> \
  --file /tmp/aicoding_synced.xml \
  --mis zhangce07
```

若提示"当前有其他编辑者正在进行编辑操作"，重新执行步骤 4 获取最新 stepVersion，再重跑步骤 5~7。

### 8. 清理临时文件

```bash
rm -f /tmp/aicoding.xml /tmp/aicoding_synced.xml /tmp/requirement.md /tmp/changes.json
```

## 研发状态过滤规则

"本周需求池"中可能残留已上线/已归档等终态需求（需求主R未及时更新排期标签），需按业务线排除：

| 业务线 | 排除的研发状态 | 原因 |
| --- | --- | --- |
| 国内酒店、境外酒店 | 已上线、已归档 | 需求已交付，不应计入本周需求 |
| 民宿 | 已完成 | 同上（民宿表用"已完成"表示终态） |

过滤逻辑在 `extract_requirements.py` 的 `get_dev_status_excludes()` 函数中，按业务线名称匹配。

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

使用贪心算法：按分数降序排列，依次分配不冲突的匹配对。匹配后再用标题一致性过滤，normalize 后标题不一致的匹配会被取消，避免同人不同需求被错误配对。

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
- 脚注修复仅作用于 `<km-footnote-item>` 节点内部，正文区域的 `<del>` 标签不受影响
- 排期文档每周更新，contentId 不变但表格内容会变；多维表格列结构可能因业务调整而变化，脚本通过列名关键词动态查找列 ID

## 常见问题

### 新增 @ 人失败

新增需求行的"研发同学"列需要 @ 对应人员。人员映射从 AI-Coding 文档现有 XML 的 `<km-mention>` 标签中提取（uid + empId）。如果该人员从未在本文档中被 @ 过，则无法生成 mention 标签，会降级为纯文本。

解决方法：手动提供该人员的 empId，或先在文档中 @ 一次该人员再重新同步。

### 脚注 hover 不显示内容

当 AI-Coding 文档是通过模板复制创建时，脚注注释可能被 `<del>` 标签包裹，导致鼠标 hover 表头上标时只显示"注释 [N]"而无具体内容。脚本会自动检测并修复：遍历 `<km-footnote-list>` 下所有 `<km-footnote-item>`，移除内部 `<del>` 和 `</del>` 标签，保留注释原文。

### 并发编辑冲突

`updateDocumentByXml` 可能因其他人正在编辑而失败，报"当前有其他编辑者正在进行编辑操作"。重新获取最新 XML 和 stepVersion，重跑同步与上传即可。
