---
constraint: soft
category: page-asset
description: <!-- TODO: 一句话描述：XX 组交易前端页面索引，汇总所有页面及配套服务信息（仓库/Bundle/DUO/FEDO/监控/学城文档等） -->
domain: <GROUP>
tags:
  - <!-- TODO: ≥ 5 个，如 page-index, 提单, 订详, 仓库, bundle, MRN, DUO，根据业务组自补 -->
last_updated: <YYYY-MM-DD>
---

# <!-- TODO: XX 组交易前端页面索引 -->

> **数据来源**：<!-- TODO: 学城 collabpage 链接，如 https://km.sankuai.com/collabpage/xxx -->
> **更新时间**：<YYYY-MM-DD>

> **本文档与 [service-map](../../service-maps/<GROUP>.md) 的分工**：
> - **page-index（本文）**：**微观视角** — 每个具体页面的完整资产信息（Code 仓库、Bundle、DUO 页面、Raptor 监控、CID、CIA、FEDO/Talos 发布、学城文档、后端日志等）。"要改某个页面时去哪里找代码、查监控、看日志"。
> - **service-map**：**宏观视角** — 业务范围、服务依赖、技术架构、发布平台。"这个组做什么、服务之间如何交互"。

---

<!--
  ⚠️ 本模板遵循 **五维度视角** 设计（参考 gc/page-index.md）：
    维度 1（主索引）：页面索引表 — 每页面一行，含完整资产矩阵
    维度 2（技术栈）：按技术栈分类 — 按 MRN / DUO / H5 / 小程序 分组
    维度 3（仓库）：仓库索引 — 反向映射"仓库 → 包含页面"
    维度 4（跳转）：常用跳转链接模板 — 高频页面的 scheme / URL 模板
    维度 5（历史）：变更记录 — 变更审计
  各组可按实际情况：
    - food / ticket / hotel：可把"维度 1 主索引"进一步按**业务功能**分区（提单 / 购物车 / 订详 / 支付 / …）
    - gc：使用扁平表 + 技术栈 / 仓库双分类（见示例）
    - platform：维度 1 可替换为 DUO 物料清单或跨组能力清单
  本 skill 强制三大板块存在：**维度 1（主索引）/ 维度 3（仓库索引）/ 维度 5（变更记录）**。
  维度 2、4 为推荐，可按组实际情况保留或删除。
-->

## 一、页面索引表（维度 1：主索引 · 必有）

<!-- 推荐列字段（若不适用可删减，顺序可调整）：
     序号 | 页面名称 | 技术栈 | 仓库地址 | DUO 地址 | 跳转链接 | 发布地址（FEDO/Talos） | 文档链接（学城） | 详细文档（模块速查）
-->

<!-- TODO: 由用户补充具体页面列表。示例见下方表格，删除示例行后填入真实数据。 -->

| 序号 | 页面名称 | 技术栈 | 仓库地址 | DUO 地址 | 跳转链接 | 发布地址 | 文档链接 | 详细文档 |
|------|----------|--------|----------|----------|----------|----------|----------|----------|
| 0x1 | <!-- 示例：订单详情页 --> | MRN | [<repo>](https://dev.sankuai.com/code/repo-detail/<ns>/<repo>/file/list) | - | `imeituan://www.meituan.com/mrn?mrn_biz=<GROUP>&mrn_entry=<entry>&mrn_component=<comp>&orderid=${orderid}` | [FEDO](https://fedo.sankuai.com/group/<gid>/sprint/<sid>) | [学城](https://km.sankuai.com/collabpage/<cid>) | [模块速查](./<xxx-modules>.md) |

<!-- 如果本组页面过多（食品/酒店/门票常见），推荐按业务功能分区展开：

### 1.1 <分区名，如"提单类" / "主链路" / "国内酒店"> <!-- food/ticket/hotel 适用 -->

| 序号 | 页面名称 | 技术栈 | 仓库 | 跳转 | 学城 |
|------|---------|-------|-----|------|------|
| 0x1 | … | … | … | … | … |

### 1.2 <分区名，如"订详类" / "非主链路" / "境外酒店">

…
-->

---

## 二、按技术栈分类（维度 2：技术栈视角 · 推荐）

<!--
  按 MRN / DUO / H5 / 小程序（美小 / 点小）分组，便于：
  - 按技术栈统一排查（如 MRN 版本升级影响面）
  - 新同学按技术栈熟悉工程
  若本组只用单一技术栈（如 platform 只有 DUO），可删除本章节或保留单一子表。
-->

### 2.1 MRN 页面

| 页面名称 | 仓库 | 文档链接 |
|----------|------|----------|
| <!-- TODO --> | <!-- TODO --> | [学城](https://km.sankuai.com/collabpage/<cid>) |

### 2.2 DUO 页面

| 页面名称 | 仓库 | DUO 页面 | 文档链接 |
|----------|------|----------|----------|
| <!-- TODO --> | <!-- TODO --> | [DUO](https://duo.sankuai.com/portal/page/detail2/<pid>) | [学城](https://km.sankuai.com/collabpage/<cid>) |

### 2.3 H5 页面

| 页面名称 | 仓库 | 文档链接 |
|----------|------|----------|
| <!-- TODO --> | <!-- TODO --> | [学城](https://km.sankuai.com/collabpage/<cid>) |

<!-- 如本组有原生小程序页面（美小/点小），在此新增 2.4 小程序页面 子表。 -->

---

## 三、仓库索引（维度 3：仓库视角 · 必有）

<!--
  反向映射：仓库 → 包含的页面。用于：
  - 评估某仓库变更的影响面
  - 定位仓库归属团队
-->

| 仓库名称 | Code 地址 | 技术栈 | 负责团队 | 包含页面 |
|----------|-----------|--------|---------|----------|
| <!-- TODO: repo-name --> | [链接](https://dev.sankuai.com/code/repo-detail/<ns>/<repo>/file/list) | MRN/DUO/H5 | <!-- TODO --> | <!-- TODO: 逗号分隔的页面名列表 --> |

---

## 四、常用跳转链接模板（维度 4：跳转视角 · 推荐）

<!--
  列出**高频使用**的跳转 scheme / URL 模板，供测试联调、灰度演练、客服排障复用。
  不需要每个页面都列，只列"经常用到" + "参数多容易写错"的。
  若本组没有稳定跳转规律（如 platform 无 C 端页面），可删除本章节。
-->

### 4.1 <!-- 示例：团购提单页 -->

```
imeituan://www.meituan.com/mrn?mrn_biz=<GROUP>&mrn_entry=<entry>&mrn_component=<comp>&dealid=${dealid}&shopid=${shopid}
```

<!-- TODO: 补充其他高频跳转模板 -->

---

## 五、变更记录（维度 5：历史视角 · 必有）

| 日期 | 变更内容 | 操作人 |
|------|---------|-------|
| <YYYY-MM-DD> | 按 trade-fe-knowledge-editor skill 模板初始化 / 补齐 frontmatter | <!-- TODO: @xxx --> |
