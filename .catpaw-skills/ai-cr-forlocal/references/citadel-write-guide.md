# 学城 CR 文档创建指南（Step 6）

## 写入命令

⚠️ 必须用 `--file` 方式写入，**禁止用 `--content` 传多行字符串**（`\n` 不会转换为真实换行，Markdown 会挤成一行）。

```bash
# 1. 把 CR 文档内容写入临时文件
cat > /tmp/cr_review_{repoName}_{branch_safe}.md << 'EOF'
{完整 Markdown 内容，按 comment-templates.md 中的学城文档结构模板填写}
EOF

# 2. 用 --file 创建文档（⚠️ 不需要传 --mis，认证从缓存自动读取）
oa-skills citadel createDocument \
  --title "{repoName}/{branch} 本地 CR — {YYYY-MM-DD}" \
  --file /tmp/cr_review_{repoName}_{branch_safe}.md \
  --parentId "${CITADEL_PARENT_ID}"

# 3. 清理临时文件（走 cr-cli.sh clean 统一入口，避免主 Agent 直接跑 rm）
bash "$SKILL_ROOT/tools/cr-cli.sh" clean
```

**变量说明：**

| 变量 | 说明 | 示例 |
|------|------|------|
| `{repoName}` | 仓库名（不含 org 前缀） | `sku-admin-service` |
| `{branch_safe}` | 分支名中 `/` 替换为 `-` | `feature/add-sku` → `feature-add-sku` |
| `{YYYY-MM-DD}` | 当前日期 | `2026-07-14` |

默认 `CITADEL_PARENT_ID`：`2752508777`（学城 CR 文档目录）

## 文档结构

文档结构模板见 [comment-templates.md](comment-templates.md) — `学城 CR 文档结构模板（Step 6）` 小节。

**章节固定为六节**（不得增减）：

1. **CR 概述** — 仓库/分支/时间/Skill版本
2. **变更综述** — 本次变更整体概括
3. **Review 发现** — 按 P0→P1→P2→P3 分组，组内编号 `[P0-01]` `[P1-01]` ...
4. **总体评价** — 结论 + 发现汇总
5. **人工复审要点** — 需人工验证的事项（含 SDD 校验要点，如有）
6. **附录** — Skill 信息、审查模式

## 失败处理

降级：CR 结果输出到对话，**不阻塞后续步骤**。
