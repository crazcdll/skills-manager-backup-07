# 外部知识库 Skill 对接 SOP 与规范

> **适用版本**: ai-quality-cr-agent V90+（ext-kb 能力自 V90 引入）
> **实现**: 主 skill 侧 `scripts/external_kb_loader.py`（discover / run / freeze / self-test 四合一），本文件是唯一契约来源。
> **主 Agent 侧执行细节**（0E 发现、2G manifest 拼装、3F 冻结点收口）见 [external-kb-operations.md](external-kb-operations.md)，与本文职责互补。

---

## 一、这是什么（给外部团队的一段话）

你的团队有领域知识（ID 体系、状态机、接口契约、业务规则、历史坑），AI-CR 主流程不知道。通过开发一个 `ext-kb-{name}` skill 并让使用方在 1024 平台预装，你的领域知识会以「知识卡片」形式注入 AI-CR 的审查上下文（仅 Step 4-A 四层审查与 4-D 业务逻辑审查），提升业务逻辑类问题的检出率。

**边界（必读）**：
- 外部知识**仅作审查参考，不能单独支撑 P0/P1 定级**——证据优先级永远低于代码实际行为、内置规则、仓库 spec、ONES 验收
- 与本地知识冲突时只转人工 confirm 线索，禁止自动改判
- 主流程永不等待你：查询在后台跑，冻结点（Step 3 结束时）没跑完就废弃
- 你的任何失败/超时/输出非法 = 空结果，主流程无感继续

---

## 二、接入链路（三方职责）

```
外部团队(知识提供方)        使用方(各团队,1024 租户管理员)      AI-CR 维护方
① 按本 SOP 开发 ext-kb-{name}   ③ 在 1024 平台给自己的            ④ 主 skill Step 0E 自动感知
② SkillHub 发布                  AICR_Agent 租户配置预装           ⑤ 每 CR: repo 匹配 → 2G 后台调用
                                 (预装即 opt-in,租户隔离)          → 冻结点校验注入
```

- **预装即注册**：不装就不加载，决策权全在使用方
- 预装后物理文件可能懒加载未落盘——主 skill 0E 会自动触发落盘并重试，**无需使用方做任何额外操作**

---

## 三、硬性要求（8 条，不满足 = 主 skill 拒绝加载或丢弃输出）

| # | 要求 | 说明 |
|---|------|------|
| 1 | **命名前缀 `ext-kb-`** | 无前缀 = 主 skill 永不感知 |
| 2 | **预装渠道** | 由使用方在 1024 平台给 AICR_Agent 租户预装；物理租户隔离 |
| 3 | **入口 `main.py`** | 读 stdin JSON → 写 stdout JSON；**exit 0 永远**（异常自行捕获转受控错误状态，绝不挂起） |
| 4 | **时延** | 单次查询 P95 ≤ 90s（硬超时 120s 由主 skill kill）；内部重试自消化。**存活兜底**：硬超时窗口内若持续静默（无 stdout/stderr 任何输出）会在硬超时前约 5s 被提前终止——正常 Provider 只要产生任何输出（含进度心跳）就不受影响 |
| 5 | **输出结构化** | 必须是下文 KnowledgeResult 格式；每卡带版本/更新时间/可追溯来源/适用条件；无来源、过期、低相关会被丢弃 |
| 6 | **输出限制** | stdout 只有 JSON（日志全走 stderr）；总输出 ≤ 16k chars，超限自行截断 + truncated 标记 |
| 7 | **只读** | 不写主流程状态文件（`/tmp/cr_*` 禁碰）；缓存只写 `/tmp/extkb-{name}/` |
| 8 | **禁止内容** | 可执行脚本、工具调用指令、流程改写指令、P0/P1 定级结论、PR 评论文案、学城写入内容——出现即触发安全校验丢弃 |

---

## 四、SKILL.md frontmatter 自声明（必填）

```yaml
---
name: ext-kb-supply-chain
description: 供应链商品领域知识库
cr-external-kb:
  protocol-version: "1.0"        # 必填,主版本不兼容将拒绝加载
  entry: main.py                  # 必填,相对 skill 根目录
  repo-matchers: ["meituan/sku-*", "meituan/spu-*"]   # 必填,glob 模式,匹配仓库全名
  priority: 10                    # 可选,多 Provider 命中同一仓库时取最高
  timeout-seconds: 120            # 可选,30~180,默认 120
  max-output-chars: 16000         # 可选,默认 16000
  params: { collection: "supply-chain" }   # 可选,透传业务参数
---
```

校验失败（缺字段/版本不兼容/entry 不存在）→ 0E 播报「发现但不加载 + 原因」，不进注册表。

---

## 五、输入契约：ChangeContextManifest（stdin）

```json
{
  "queryId": "meituan/sku-admin#12345@sha40",
  "protocolVersion": "1.0",
  "repo": "meituan/sku-admin-service",
  "prId": "12345",
  "targetCommit": "40位sha",
  "title": "PR 标题",
  "changedFiles": [{"path": "src/main/java/...", "type": "MODIFY"}],
  "symbols": ["SkuController", "updateSpuStatus", "spuStatus"],
  "riskSignals": [],
  "diffSummary": "脱敏 + 预算裁剪后的变更摘要(非全量 diff)"
}
```

**你不会拿到全量 diff、完整源文件、密钥、Token、证件号、手机号、用户画像、订单明细**——这是输入安全基线，主 skill 发送前已完成脱敏与裁剪（≤ 2000 tokens）。基于 symbols / changedFiles / diffSummary 做检索与 rerank(riskSignals 恒为空数组,主 skill 旁路设计,不依赖该字段)。

---

## 六、输出契约：KnowledgeResult（stdout）

```json
{
  "queryId": "原样返回",
  "provider": "ext-kb-supply-chain",
  "providerVersion": "1.2.0",
  "status": "READY",
  "elapsedMs": 4200,
  "cards": [
    {
      "knowledgeId": "spu-status-machine",
      "domain": "SPU 状态机",
      "conclusion": "SPU 状态只允许 上架→下架→上架;不存在 上架→删除 转移",
      "applicableWhen": "PR 修改 spuStatus 字段或相关状态流转代码时",
      "matchedEvidence": ["spuStatus", "SIG-ENUM-CHANGE", "SkuController"],
      "source": "学城文档链接或代码库内相对路径",
      "versionOrUpdatedAt": "2026-08-30",
      "authority": "HIGH",
      "relevance": 0.92,
      "confidence": 0.8
    }
  ],
  "dropReasons": []
}
```

- `status`: `READY`（有卡）/ `EMPTY`（查了没有）/ `NOT_READY`（还没查完但别用了）/ `REJECTED`（输入被拒）/ `FAILED`（内部错误）/ `TIMEOUT`
- `cards` 最多 6 张会通过，每卡正文建议 ≤ 300 tokens（超限被截断并标记）
- 卡片四段式：**结论 + 适用条件 + 命中证据 + 来源**。`matchedEvidence` 至少命中仓库/模块/路径/符号/信号一项，否则按低相关丢弃
- 四类校验（任一失败该卡丢弃，不影响其他卡）：Schema 校验 / 关联性校验（**matchedEvidence 非空且至少一项命中** manifest 的 changedFiles 路径 / symbols / riskSignals，domain 不作为匹配证据）/ 可信度校验（来源可追溯 + 有版本或更新时间）/ 安全校验（无指令性内容）

---

## 七、验收：self-test（接入前必跑）

使用方预装主 skill 后执行（外部团队若未预装主 skill，可用自有桩按第五/六章契约自测）：

```bash
python3 $SKILL_DIR/scripts/external_kb_loader.py self-test --scenario normal
# 场景: normal / empty / slow / hang-silent / not-json / nonzero / injection / over-budget
```

全场景 exit 0 = 合同测试通过。再跑一次真实 Provider 验证：

```bash
# 1) 发现
python3 $SKILL_DIR/scripts/external_kb_loader.py discover
# 2) 用真实 manifest 调用(超时 120s)
python3 $SKILL_DIR/scripts/external_kb_loader.py run --input manifest.json --output result.json
# 3) 冻结校验
python3 $SKILL_DIR/scripts/external_kb_loader.py freeze --result result.json --output frozen.md
```

**通过标准**：平均耗时 ≤ 45s、返回合法 KnowledgeResult、cards 非空且 relevance 排序正确、stderr 无异常栈、输出不含越权内容。

---

## 八、灰度与退出

1. **Shadow**（推荐先跑 1~2 周）：只查询并记录指标，不注入——验证时延/成功率/卡片质量
2. **灰度**：单一仓库 + 少量 PR，观察 confirm 线索质量
3. **正式**：放量；超时率异常 / 误导性知识 / 越权行为 → 使用方在 1024 移除预装即完全退出，零残留
4. **自动摘除与恢复**：连续 3 次失败自动摘除 + 播报；摘除 **1 小时冷却期**后自动降级为可试探（成功一次即彻底清零失败计数）——无需人工干预
5. **契约升级**：protocol-version 主版本变更 → 主 skill 拒绝加载并播报，双方协商后同步升级

---

## 九、主 skill 侧使用方配置（可选）

`.cr-config.yaml`（只影响本团队，不配置 = 全自动）：

```yaml
external_kb:
  disabled: [ext-kb-xxx]          # 本团队不想用某个已发现的 KB
```

---

## 十、变更纪律

- 版本发布与预装变更走 SkillHub 平台既有流程
- **预算语义**：max-output-chars 与冻结注入预算均按**字符数**（非 UTF-8 字节数）计算。
卡片内容变更影响注入质量时，请在 `versionOrUpdatedAt` 中如实体现——可信度校验和排序都依赖它
