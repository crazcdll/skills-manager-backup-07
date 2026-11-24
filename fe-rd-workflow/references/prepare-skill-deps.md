# Skill 依赖清单

> **⚠️ 本文件是 `prepare.md` 步骤 0.3 的唯一权威来源，由 `scripts/skill-deps.json` 同步生成。**
> **`check-deps.js` 执行时会将 `scripts/skill-deps.json`（真实源）同步到 `skills.json`。**

---

## 依赖清单

| # | Skill 名称 | 必选 | 用途 | 适用阶段 | 备选 |
|---|-----------|:----:|------|---------|------|
| 1 | `memory-skill` | ✅ | 状态持久化、用户偏好存储 | 全流程 | — |
| 2 | `fe-rd-workflow` | ✅ | 主流程编排（自身） | 全流程 | — |
| 3 | `citadel` | ✅ | 学城文档阅读、创建、查询、管理 | 全流程 | `km-doc-tools` |
| 4 | `design-spec` | ✅ | 前端需求规格 + 技术方案 + 任务拆解，含来源标识 | Stage 3 | — |
| 6 | `mt-graphify-lite` | ✅ | 前端代码知识图谱（轻量版），design-spec 前置依赖：ensure 一键就绪 + 搜索/遍历/路径/详情/统计查询 | Stage 3 | — |
| 7 | `max-material-dev` | ✅ | 源码物料新增/修改/发布（物料开发） | Stage 4 | — |
| 8 | `duo-protocol` | ✅ | 前后端交互协议生成与管理 | Stage 4 | — |
| 9 | `draw-io-km` | ✅ | 绘制架构图/流程图并插入学城文档 | Stage 3（技术方案） | `kmdrawio`、`drawio-generator` |
| 10 | `duo-fedo` | ✅ | FEDO 迭代管理、开发任务管理、流水线操作 | Stage 2、Stage 6 | — |
| 11 | `ee-fedo` | ⚠️ 参考 | FEDO 官方知识库型 Skill，作为命令参考文档；**执行依赖优先使用 `duo-fedo`** | Stage 2 Stage 6 | `duo-fedo`（主） |
| 12 | `ee-code` | ✅ | Draft PR 创建、CR 自动化报告 | Stage 6 | `code-cli` |
| 13 | `max-leez` | ✅ | Max 组件库规范参考 | Stage 4（代码开发） | — |
| 14 | `fe-ai-review` | ✅ | 本地代码审查（含 PR 远程审查） | Stage 5 | `trade-code-reviewer` |
| 15 | `catpaw-daxiang` | ✅ | 大象消息通知（任务终止/阶段完成通知） | 全流程 | — |
| 16 | `kmedit` | ✅ | 学城文档局部编辑（改写、纠错、续写、插入图表） | Stage 3 | — |
| 17 | `km-doc-tools` | ✅ | 学城文档阅读、创建、查询、管理（`citadel` 备选） | 全流程 | `citadel`（主） |
| 18 | `mermaid-tools` | ✅ | Mermaid 图表绘制工具 | 全流程 | — |
| 19 | `ai-auto-ui-test` | ⬜ 可选 | 内循环 Flow 测试用例生成：产出可执行的验收标准，供 Stage 4 做 TDD 驱动编码、Stage 5 做对照自查 | Stage 3 | — |
| 20 | `ai-tr` | ⬜ 可选 | 技术方案三维评审（文码一致性/完备性/架构合理性），产出评级报告；有学城链接时额外支持报告上传与方案原文划线评论 | Stage 3（Step 3.2.4） | — |
| 21 | `mt-code-standards-setup` | ⬜ 可选 | 业务研发平台统一编码规范接入：按仓库同步生效 L1/L2 规范到 `.mdp/rules/`，编码前读取遵循 | Stage 4（Step 4.0） | — |

> **注意**：`ee-fedo`（#10）标注为 ⚠️ 参考，不作为阻断性必选依赖。缺失时不中断流程，仅作为命令参考。
>
> **注意**：`ai-auto-ui-test`（#19）标注为 ⬜ 可选，**仅在 Stage 3 Step 3.4 生成 Flow 用例时使用，内循环不执行任何自动化测试**（端到端测试属于外循环，在研发流程之外独立发起）。缺失时不中断流程，跳过 Step 3.4，Stage 4 按常规方式编码、Stage 5 仅依据验收标准自查。
>
> **注意**：`ai-tr`（#20）标注为 ⬜ 可选，仅在 Stage 3 Step 3.2.4 对技术方案做一次三维评审。**无学城链接不阻断**：降级为「本地文件模式」，以 `docs/tech-design.md` 为输入、报告落本地 `docs/tech-design-review.md`，仅不支持报告上传与划线评论。缺失或用户不需要时跳过评审，并在 Step 3.5 确认单中记录原因，不阻断流程。
>
> **注意**：`mt-code-standards-setup`（#21）标注为 ⬜ 可选，Stage 4 Step 4.0 用它把当前仓库生效编码规范（L1/L2）同步到 `<repo_root>/.mdp/rules/`，编码以其为准。缺失或同步失败时回退 `fe-ai-review` 内置规范继续编码，不阻断流程，但需在 Stage 4 出场门禁记录「规范来源：内置规范（原因）」。

---

## check-deps.js 执行说明

```bash
# 检查所有依赖（不安装）
node {fe-rd-workflow}/scripts/check-deps.js

# 检查并自动安装缺失依赖
node {fe-rd-workflow}/scripts/check-deps.js --install
```

### 退出码语义

| 退出码 | 含义 | 后续动作 |
|--------|------|---------|
| `0` | 全部 PASS | 继续流程 |
| `1` | 有必选依赖缺失 | 立即中断，提示用户安装 |
| `2` | 仅有可选依赖缺失 | 输出警告，继续流程 |

### Skill 搜索路径（按优先级）

1. `./.catpaw/skills/`
2. `./.catpaw/skills/skills-market/`
3. `./.claude/skills/`
4. `~/.claude/skills/`
5. `~/.catpaw/skills/`
6. `~/.catpaw/skills/skills-market/`
7. `~/.openclaw/skills/`

### 降级说明

当 `check-deps.js` 脚本不可用时，手动逐一检查：

```bash
# 对每个 Skill，在上述搜索路径中查找 SKILL.md
for skill in memory-skill citadel design-spec mt-graphify-lite \
             max-material-dev duo-protocol draw-io-km duo-fedo ee-code \
             max-leez fe-ai-review catpaw-daxiang kmedit km-doc-tools mermaid-tools; do
  found=false
  for path in ".catpaw/skills" ".catpaw/skills/skills-market" \
              "$HOME/.claude/skills" "$HOME/.catpaw/skills" \
              "$HOME/.catpaw/skills/skills-market"; do
    if [ -f "$path/$skill/SKILL.md" ]; then
      echo "✅ $skill: $path/$skill/SKILL.md"
      found=true
      break
    fi
  done
  if [ "$found" = false ]; then
    echo "❌ $skill: 未找到"
  fi
done
```

缺失时安装：

```bash
# 使用 mtskills 安装
mtskills i {skill-name}

# 或使用 catpaw-skill-installer
```
