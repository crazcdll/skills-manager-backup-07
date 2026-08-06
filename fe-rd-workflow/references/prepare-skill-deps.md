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

> **注意**：`ee-fedo`（#10）标注为 ⚠️ 参考，不作为阻断性必选依赖。缺失时不中断流程，仅作为命令参考。

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
