---
name: ai-auto-test-report
version: 1.1.0
description: E2E 自动化测试指标与数据报表处理。采集 ai-ui-autotest-engine 的执行报告数据、清洗转换、计算覆盖率/误报率/缺陷发现占比/提效分析等核心指标，支持人工打标校准。聚焦数据采集（只读不写）、指标计算、打标闭环。触发词：测试指标、E2E 指标、测试报告分析、覆盖率计算、误报率分析、缺陷占比、测试数据报表、打标、数据清洗、metrics、test report analysis。场景：E2E 执行完成后需要获取指标数据时；需要分析测试质量、误报率、覆盖率等数据时；需要人工确认打标校准指标时。

metadata:
  skillhub.creator: "huangshuiqing"
  skillhub.updater: "huangshuiqing"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "143489"
  skillhub.high_sensitive: "false"
---

## 工作流

```
Phase 0: 环境准备与输入检查         → scripts/run.sh
Phase 1: 数据采集（Collect）        → scripts/collector.py
Phase 2: 数据清洗（Clean）          → scripts/cleaner.py
Phase 3: 指标计算 + 回归对比 + 编码Agent反馈 → scripts/calculator.py
Phase 4: 人工打标（Label）          → scripts/labeler.py
Phase 5: 输出报告 + 编码Agent反馈输出 → scripts/reporter.py
```

所有脚本位于 `scripts/` 目录，由 `scripts/pipeline.py` 统一编排。

## 脚本清单

| 脚本 | 阶段 | 功能 |
|------|------|------|
| `scripts/run.sh` | Phase 0 | Bash 入口：检查输入源、创建输出目录、调用 pipeline.py |
| `scripts/pipeline.py` | 编排 | Python 全流程编排（采集→清洗→计算→打标→输出） |
| `scripts/collector.py` | Phase 1 | 从 report.json / mapping.yaml 读取原始数据 |
| `scripts/cleaner.py` | Phase 2 | 失败原因分类（规则引擎）、EC 映射注入、阶段耗时拆分 |
| `scripts/calculator.py` | Phase 3 | M1~M5 核心指标 + 回归对比 + 编码Agent反馈 |
| `scripts/labeler.py` | Phase 4 | 展示待确认 FAIL 分类，收集人工打标反馈，重新计算 |
| `scripts/reporter.py` | Phase 5 | 生成 metrics.json / metrics_report.md / **coding_agent_feedback.json** |

## 核心规则

1. **只读不写**：不修改原始报告数据
2. **幂等计算**：同一份输入多次计算得到相同结果（不含打标差异）
3. **可追溯**：每个指标值都可追溯到原始报告数据行
4. **打标分离**：AI 预分类与人工打标结果分开存储，可对比校准
5. **渐进增强**：有 mapping.yaml 时计算 EC 覆盖率，没有时降级

## 快速使用

```bash
cd scripts/

# 全流程一键执行
bash run.sh

# 指定 report 目录和 mapping
REPORT_DIR=.run MAPPING_PATH=../mapping.yaml bash run.sh

# 跳过人工打标（CI 环境用）
SKIP_LABEL=1 bash run.sh
```

## 分阶段执行

```bash
cd scripts/

# 全量：采集 + 清洗 + 计算（含回归对比）+ 打标 + 输出
python3 pipeline.py .run --mapping ../mapping.yaml --previous ../last-run/metrics.json

# 仅采集
python3 collector.py .run --mapping ../mapping.yaml --output .metrics

# 仅清洗（需先有 collected.json）
python3 cleaner.py --collected .metrics/collected.json --output .metrics

# 仅计算指标（需先有 cleaned.json）
python3 calculator.py --cleaned .metrics/cleaned.json --output .metrics

# 仅打标（需先有 metrics.json）
python3 labeler.py --metrics .metrics/metrics.json --output .metrics

# 仅出报告
python3 reporter.py --metrics .metrics/metrics.json --output .metrics

# 从指定阶段开始
python3 pipeline.py .run --mapping ../mapping.yaml --from calc
```

## 数据清洗设计

**失败原因分类（规则引擎）** — 对每个 FAIL 步骤自动分类：

| 分类 | 含义 | 关键词示例 |
|------|------|-----------|
| `env` | L1 环境框架问题 | 超时、timeout、设备、模拟器、sandbox、ADB |
| `data` | L2 数据依赖问题 | Mock、AppMock、泳道、找不到元素 |
| `script` | L2 脚本/Flow问题 | 断言错误、占位符、action_arg |
| `bug` | L3 业务缺陷 | 兜底（无关键词匹配时） |

**EC 映射注入** — 从 mapping.yaml 匹配 flow 文件名 → 注入 `ec_case_id`。

**阶段耗时拆分** — 按 SOP layer 聚合（B0-B3 环境准备 / C0-C5 执行 / T0-T2 报告）。

## 指标计算

| 指标 | 公式 | 打标依赖 |
|------|------|---------|
| M1 EC覆盖率 | 执行成功 EC 数 / 总 EC 数 | ❌ 否 |
| M2 误报率 | (env+data+script 失败) / 总失败 | ⚠️ 建议打标校准 |
| M4 提效 | E2E耗时 + QA参与耗时（需外部数据） | ✅ 需手工基线 |
| M5 缺陷占比 | AI发现 / (AI发现+人工发现) | ✅ 需打标 |

## 回归对比

当指定 `--previous <last-metrics.json>` 时自动计算：

| 对比项 | 含义 |
|--------|------|
| 覆盖率变化 | 本次相比上次的 EC 覆盖率差值 |
| 误报率变化 | 本次相比上次的误报率差值 |
| 新增缺陷 | 上次不存在、本次新出现的 bug（L3） |
| 已修复缺陷 | 上次存在、本次已消失的 bug（L3） |
| 持续缺陷 | 两次都存在的 bug（L3） |

## 编码Agent 反馈

`coding_agent_feedback.json` 是专供编码Agent 消费的结构化反馈：

```json
{
  "type": "e2e_test_feedback",
  "action_required": true,
  "total_bugs": 2,
  "bugs": [
    {
      "case_name": "取消订单后推荐相似酒店",
      "ec_case_id": "EC-xxx",
      "ec_priority": "P0",
      "severity": "P1",
      "failed_step": {"sid": "S3", "desc": "断言推荐酒店列表", "action": "assert-text"},
      "assertion_failures": [{"assertion": "assert_present.推荐酒店", "result": "fail"}],
      "screenshot_url": "s3://.../screenshot.png",
      "reason": "预期文案「推荐酒店」未出现",
      "regression": "new"
    }
  ]
}
```

编码Agent 可直接读取此文件，无需解析 metrics.json 全量数据。

## 与 SDLC 流水线的集成

在 `sdlc-lite-fe-autotest-agent` 的测试执行阶段（R6）完成后：

```
测试执行完成 → pipeline.py 计算指标 → 输出 coding_agent_feedback.json
  → 编码Agent 读取 feedback → 判断是否需要回炉
  → 若需回炉: 自动创建修复 Issue 并分配
  → 若无缺陷: 继续进入部署阶段
```

## 输出产物

```
.metrics/
├── collected.json              # 原始采集数据
├── cleaned.json                # 清洗后数据（含分类/映射）
├── metrics.json                # 结构化指标（AI 预分类 + 回归对比 + 编码反馈）
├── labeling_result.json        # 人工打标记录
├── metrics_final.json          # 打标修正后的精确指标
├── metrics_report.md           # 可读报告（含回归对比 + 缺陷详情）
├── metrics_summary.json        # 精简指标（供看板消费）
└── coding_agent_feedback.json  # 🔔 编码Agent 反馈（独立文件，直接可读）
```

## 约束

1. 只读不写：不修改原始报告数据
2. mapping.yaml 缺失时：EC 覆盖率降级为 case 执行覆盖率
3. 失败原因分类精度约 70-80%，建议配合人工打标校准
4. 手工基线（M3/M4）需从外部系统采集，本 Skill 不负责

## 参考

- **指标定义**: [测试环节-AI-SDLC新范式效能指标](https://km.sankuai.com/collabpage/2771969222)
- **E2E 测试建设**: [AI SDLC 测试外循环-App E2E测试建设](https://km.sankuai.com/collabpage/2780908514)
- **指标体系建设设计**: [docs/e2e-auto-test/01-指标体系建设.md](../../../docs/e2e-auto-test/01-指标体系建设.md)