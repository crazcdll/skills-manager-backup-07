---
name: hotel-combine-dev
description: 酒店组合订（多品）提单页模块对照主流程提单页（单品·仅境内）做能力对齐：产出能力对齐清单 → 人工确认标签 → 写方案文档 → 落地代码 → 回填文档。当用户要梳理/开发组合订某模块（如 preview-logic、bottom-bar、guest-card）、对齐主流程、产出模块方案或迁移建议时使用。

metadata:
  skillhub.creator: "liuxin62"
  skillhub.updater: "liuxin62"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "143002"
  skillhub.high_sensitive: "false"
---

# 酒店组合订模块能力对齐（多品 vs 单品·境内）

## 触发场景
- 用户指定组合订某模块，要求对照主流程提单页梳理差异、打标签、产出方案、落地代码。
- 关键词：模块能力对齐、组合订对齐主流程、模块梳理、XXX 模块对齐、模块级方案、迁移建议。

## 输入（必填）
- 模块名（如 preview-logic）
- 主流程对应组件名（如 hotel-submit-preview-logic）
- （可选）需求范围文档、已建好的梳理文件 contentId

## 关键文档地址（固定）
| 文档 | 地址 | 用途 |
|---|---|---|
| 组合订接口文档（多品） | https://km.sankuai.com/collabpage/2784689168#b-426a8599-27fb-45be-a8e1-b4b51d0a6eb7 | 查多品结构 data.combineOrderVOList |
| 单品提单页接口文档 | https://km.sankuai.com/collabpage/2704674679 | 查单品结构 data.xxxVO |
| 前端开发流程 | https://km.sankuai.com/collabpage/2784817450 | 项目背景 / 分支 / 命名规范 |
| 提单页能力（需求范围） | https://km.sankuai.com/collabpage/2784804593 | 能力 ✅/❌ 范围、端侧范围 |
| 跳链参数 | https://km.sankuai.com/collabpage/2785874961 | 跳链参数说明 |

## 边界约定
- 主流程提单（单品）只梳理境内逻辑（isInland），境外逻辑不纳入对比。
- 端侧范围以需求范围文档为准（如仅 APP）。
- 组件依赖版本对齐：`@max/leez-dependencies` 统一用 `^2.6.67`（所有模块一致）。

## 标签体系
| 标签 | 含义 | 判定 |
|---|---|---|
| 🟢 一致 | 两边一致 | 直接复用，不写进对齐清单 |
| 🟡 需适配 | 主流程有、组合订实现不一致 | 需对齐改造 |
| 🔴 需新增 | 主流程有、组合订缺失 | 需补齐 |
| ⚪ 不处理 | 多品天然无 / 需求不支持 | 写明原因 |
| 🔵 需确认 | 需产品/后端确认 | 人工确认后改状态 |

## 流程（5 步）

### Step 0 收集上下文
1. 读开发流程文档（分支、命名规范）。
2. 读需求范围文档（能力 ✅/❌、端侧范围）。
3. 读组合订接口文档 + 单品接口文档（字段结构差异）。
4. 定位两边组件源码（material/packages/ 下）与协议绑定（protocol/struct.groovy）。

### Step 1 产出能力对齐清单
- 逐文件对比：index.tsx / mix / types / description.json / package.json，加上两边 struct.groovy 的 props 绑定。
- 只对比主流程境内逻辑，境外不梳理。
- 按模板输出表格并打标签，只输出「不一致」的能力，一致项不写。
- 写到梳理文件（学城，走 citadel）。

### Step 2 人工确认（硬检查点，必须停一次）
- 请用户确认标签、去掉一致项、拍板「需确认」项。
- 记录「本次改动范围 + 不处理边界」。

### Step 3 写方案文档 + 写代码
- 方案文档（第二部分）：改动清单表格，含「是否要测试」列。
- 组件代码（index.tsx / mix / types / description.json / package.json）与协议层（struct.groovy / constData.groovy）分别落地。

### Step 4 回填文档
- 按最终落地代码重写第二部分，去掉「待确认」等过期内容。

## 文档模板

### 第一部分 · 能力对齐清单
| 对应单品提单模块 | 能力项 | 主流程提单现状（境内） | 组合订现状 | 差异 Gap | 标签 |
|---|---|---|---|---|---|

### 第二部分 · 改动清单
| 改动项 | 改动说明 | 影响范围 | 是否要测试 |
|---|---|---|---|
（是否要测试默认「是」）

## 多品字段映射规则
单品接口的 xxxVO 在多品接口下对应组合订的 `combineOrderVOList?.getAt(x)?.xxxVO`，其中 x 为实际业务要取的订单下标（如 `getAt(0)` 取第一个订单），不固定为 0，需根据业务场景判断。

- merchantVO → combineOrderVOList?.getAt(x)?.merchantVO
- memberVO   → combineOrderVOList?.getAt(x)?.memberVO
- goodsVO    → combineOrderVOList?.getAt(x)?.goodsVO
- bookInfoVO → combineOrderVOList?.getAt(x)?.bookInfoVO

## 踩坑清单
1. 用 CONST.isError 前先查 constData.groovy 是否已定义（主流程有、组合订可能没有）。
2. 新增依赖后检查是否 hoisted 到根 node_modules。
3. groovy 闭包作用域：def 局部变量不跨闭包，多个字段各自取值，勿复用上一闭包变量。
4. 组件代码改动与协议层联动分开决策，联动是否接要显式确认。
5. 学城文档读写统一走 citadel（读 getSimpleMarkdown / 写 updateDocumentByXml），不碰 GUI。
