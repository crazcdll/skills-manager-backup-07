# Stage 6：CI/CD 部署

## 阶段概述

> **目标**：将代码提交、创建 PR、触发流水线、部署到测试环境。
> **阻塞级别**：🟢 不阻塞 — 部署失败可手动重试或跳过。

---

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 验收通过的代码 | Stage 5 输出 | 已通过验证的代码变更 |
| 验收清单 | Stage 5 输出 | `03-implementation-checklist.md` |
| workflow-context | Stage 5 更新 | checklist.status = passed |

---

## 过程

### Step 6.1：代码提交

进入项目目录
```bash
cd {project_root}
# 提交规范
git add .
git commit -m "feat: {需求简述} - #{ONES任务号}"

# Commit Message 格式遵循 Conventional Commits
# feat: 新功能 / fix: 修复 / docs: 文档 / style: 格式 / refactor: 重构
```

### Step 6.2：推送到远程

```bash
git push -u origin {current_dev_branch}
```

> `current_dev_branch` 取值说明：一定是feature分支，stage4-encoding 分支

### Step 6.3：创建 Draft PR（feature -> master）

** PR 约束（强制）**：
- 创建 **Draft PR**
- 源分支为 {current_dev_branch}
- 目标分支固定为 `master`

**PR 模板**：

```markdown
## 需求概述
{需求背景和目标}

## 改动范围
- [ ] 页面改动：...
- [ ] 组件改动：...
- [ ] 协议改动：...

## 测试情况
- [ ] 本地编译通过
- [ ] 功能自测通过
- [ ] 验收清单：[链接]

## 关联任务
- ONES: {任务链接}
- FEDO: {流水线链接}（如有）

```

**依赖 Skill（必选）**：
- `ee-code`：通过 Code CLI 创建和管理 PR（缺失时暂停，提示用户安装）

### Step 6.4：触发 CI/CD 流水线

**操作步骤**：
1. 确认 Step 6.3 已创建主 Draft PR（{current_dev_branch} -> `master`）
2. 检查 `workflow-context.json`：若 `stage2.1` 未选择 `fedo`（或 `outputs.fedo.task_id` 为空），执行兜底流程：
   - 使用 `duo-fedo` skill 创建、启动并 FEDO 任务，获取 FEDO 创建的 `feature` 分支
   - 创建 {current_dev_branch} -> FEDO 创建的 `feature` 分支，提示用户确认并合并
3. 使用 `duo-fedo` skill执行FEDO任务

**依赖 Skill（必选）**：
- `duo-fedo`：FEDO 任务创建、启动与流水线管理（缺失时暂停，提示用户安装）
- `ee-code`：PR 创建与状态管理（主 PR + 桥接 PR，缺失时暂停，提示用户安装）

### Step 6.5：部署验证

```
检查项：
□ 流水线构建成功
□ 测试环境部署成功
□ 页面可正常访问
□ 核心功能在测试环境验证通过
```

---

## 输出

| 产出物 | 说明 |
|--------|------|
| Git Commit | 代码已提交到远程分支 |
| 主 Draft PR 链接 | `{current_dev_branch} -> master` 的 Pull request 地址 |
| 桥接 PR 链接（可选） | `{current_dev_branch} -> feature` 的 Pull request 地址（仅 Stage2 非 fedo 场景） |
| 流水线状态 | 构建和部署状态 |
| 测试环境地址 | 可访问的预览地址 |

---

## 部署策略

| 策略 | 适用场景 | 说明 |
|------|----------|------|
| **全量部署** | 正式需求 | 完整 CI/CD 流程 |
| **快速预览** | 紧急修复 | 跳过部分环节，快速上线 |
| **仅提交不部署** | 代码评审阶段 | 只创建 PR，不触发部署 |

---

## 异常处理

| 场景 | 处理方式 |
|------|----------|
| 推送冲突 | rebase 后重试 |
| 桥接 PR 未合并 | 提示用户先确认并合并 `{current_dev_branch} -> fedo feature`，再继续执行FEDO任务 |
| 流水线失败 | 查看日志定位问题，修复后重新触发 |
| 部署超时 | 检查资源配额，联系运维 |
| PR 审批延迟 | 在群内提醒 Reviewer |

---

## 依赖 Skill

| Skill | 用途 | 必要性 | 缺失时行为 |
|-------|------|--------|-----------|
| `duo-fedo` | FEDO 流水线管理（**首选**） | 必选 | 暂停，提示用户安装 |
| `ee-code` | PR 创建与管理 | 必选 | 暂停，提示用户安装 |
| `ee-fedo` | FEDO 流水线管理（**备用**，`duo-fedo` 不可用时降级使用） | 可选 | 降级到 `duo-fedo`，不阻塞流程 |

> **⚠️ `duo-fedo` 与 `ee-fedo` 功能重叠，优先使用 `duo-fedo`。**
> 仅当 `duo-fedo` 不可用时，才降级使用 `ee-fedo`，两者不同时必选。
