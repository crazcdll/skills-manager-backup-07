# Stage 7：反馈总结

## 阶段概述

> **目标**：汇总全流程产出物，生成交付报告，更新最终状态，完成流程闭环。
> **阻塞级别**：🔴 最终阶段 — 标记整个流程结束。

---

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 所有阶段产出物 | Stage 1-6 | 文档 + 代码 + 配置 |
| 部署结果 | Stage 6 输出 | PR 链接 + 测试环境地址 |
| 用户反馈 | 对话上下文 | 过程中的确认和修改意见 |
| workflow-context | Stage 6 更新 | 全流程状态记录 |

---

## 过程

### Step 7.1：汇总所有产出物

```markdown
## 交付物清单

### 文档类
- [ ] `demand-spec.md` — 需求规格说明
- [ ] `tech-design.md` — 开发计划
- [ ] `dev-tasks.md` — 开发任务清单
- [ ] `03-implementation-checklist.md` — 验收清单
- [ ] `04-delivery-reports.md` — 交付报告（本文件）

### 代码类
- [ ] 物料组件源码（如涉及）
- [ ] DUO 协议文件（如涉及）
- [ ] 业务逻辑代码
- [ ] Mock/Demo 数据

### 配置类
- [ ] `workflow-context.json` — 全流程状态记录
```

### Step 7.2：生成交付报告

输出 `04-delivery-reports.md`：

```markdown
# 交付报告

## 1. 项目概要
- **项目名称**：{名称}
- **MIS**：{mis}
- **需求来源**：{PRD 链接}
- **执行模式**：{quick_delivery / single_agent / multi_agent}
- **复杂度**：{L/M/H}
- **起止时间**：{开始} → {结束}

## 2. 执行摘要

### 2.1 各阶段耗时分析

| 阶段 | 耗时（AI执行耗时） | 状态 |
|------|------|------|
| Stage 1：环境检查 | X min | completed |
| Stage 2：仓库初始化 | X min | completed |
| Stage 3：需求分析与技术设计 | X min | completed |
| Stage 4：物料组件和页面协议开发 | X min | completed |
| Stage 5：验证测试 | X min | completed |
| Stage 6：CI/CD | X min | completed |

### 2.2 关键指标
- 总代码改动：+XXX 行 / -XX 行
- 新增文件：XX 个
- 修改文件：XX 个
- 新增组件：X 个
- 修改组件：X 个
- P0 问题：0 个
- P1 问题：X 个

## 3. 交付物索引
（见 §1 交付物清单）

## 4. 遗留事项与风险
| 事项 | 级别 | 计划处理时间 |
|------|------|-------------|
| ... | P1/P2 | ... |

## 5. 后续建议
- [ ] 建议 1
- [ ] 建议 2

## 6. 链接汇总
- PR：{链接}
- 测试环境：{链接}
- 流水线：{链接}
- 学城文档：{链接}
```

### Step 7.3：更新 workflow-context 最终状态

```json
{
  "runtime": {
    "current_stage": "stage7",
    "stages_status": {
      "stage1": "completed",
      "stage2": "completed",
      "stage3": "completed",
      "stage4": "completed",
      "stage5": "completed",
      "stage6": "completed",
      "stage7": "completed"
    },
    "completed_at": "ISO8601",
    "status": "completed"
  }
}
```

### Step 7.4：文档落地（按策略）

根据 `doc_write_strategy` 执行：

| 策略 | 动作 |
|------|------|
| `local_only` | 保持本地 `.duo/docs/` 目录 |
| `km_only` | 上传所有文档到学城指定目录 |
| `dual_write` | 本地保留 + 学城上传 |

**依赖 Skill（必选）**：
- `citadel` / `km-doc-tools`：学城文档上传（缺失时暂停，提示用户安装）

### Step 7.5：清理与归档

- 清理临时文件（如中间生成的 diff 文件）
- 归档 workflow-context.json 为只读状态
- （可选）发送完成通知到大象群
- 提交最后的产物到代码仓库
---

## 输出

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 交付报告 | `.duo/docs/04-delivery-reports.md` | 全流程总结 |
| 最终状态 | `.duo/workflow-context.json` | completed 状态 |
| 学城文档 | KM 链接（如 dual_write/km_only） | 知识沉淀 |

---

## 流程结束标志

当以下条件全部满足时，标记流程正式结束：

- 所有 7 个阶段状态为 completed
- 交付报告已生成
- workflow-context.status = "completed"
- 已通知用户流程结束

---

## 异常处理

| 场景 | 处理方式 |
|------|----------|
| 文档上传失败 | 保存到本地，提示用户稍后手动上传 |
| 状态写入失败 | 重试一次，仍失败则输出警告但不阻断 |
| 用户要求补充内容 | 更新交付报告，重新生成 |

---

## 依赖 Skill

| Skill | 用途 | 必要性 | 缺失时行为 |
|-------|------|--------|-----------|
| `citadel` / `km-doc-tools` | 学城文档上传 | 必选 | 暂停，提示用户安装 |
| `catpaw-daxiang` | 发送大象通知 | 必选 | 暂停，提示用户安装 |
