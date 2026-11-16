# 维度 10：反馈回路（10%，L6）

**核心原则**：AI-Ready 不是一次性改造，而是持续进化的工程文化。
反馈回路是 AI-Ready 不退化的根本保障——没有它，仓库会随需求迭代逐渐腐化，每次都要重新教 AI。

## 评估标准（通用）

- [ ] **文档更新协议存在**：有明确的"何时更新文档"规则（非一次性初始化）
- [ ] **AI 协作文件有更新记录**：git log 显示文档有持续更新，而非只有初始提交
- [ ] **有历史案例实际沉淀**：有可供参考的历史需求案例文档
- [ ] **知识腐化可检测**：文档修改时间 vs 代码修改时间偏差合理
- [ ] **有自动化触发机制**：commit hook / CI 检查触发知识更新（高分项）

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 完整反哺链路，有实际案例沉淀，有腐化检测，有自动化触发 |
| 75–89 | 更新协议存在且有实际更新记录，有部分案例沉淀，缺乏自动化触发 |
| 60–74 | 文档存在但更新记录极少，无实际案例沉淀 |
| <60 | 无反馈回路机制，文档初始化后从未更新 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 更新协议 | `ls .mdp/workflows/update-context.md .mdp/workflows/spec-to-context.md 2>/dev/null; wc -l .mdp/workflows/update-context.md 2>/dev/null` | `grep -rn "更新协议\|文档维护\|update.*doc\|when.*update" AGENTS.md .cursorrules 2>/dev/null \| head -5` |
| AI 协作文件更新历史 | `git log --oneline .mdp/ 2>/dev/null \| wc -l; git log --oneline --since="30 days ago" .mdp/ 2>/dev/null \| head -10` | `git log --oneline .cursorrules AGENTS.md .catpaw/rules/ 2>/dev/null \| wc -l; git log --oneline --since="30 days ago" .cursorrules AGENTS.md 2>/dev/null \| head -10` |
| 历史案例沉淀 | `find .mdp/context/ -name "*spec*" -o -name "*案例*" -o -name "*case*" 2>/dev/null \| wc -l` | `find docs/specs/ .catpaw/specs/ docs/ -name "*spec*" -o -name "*案例*" 2>/dev/null \| wc -l` |
| 知识腐化检测 | `find .mdp/context/ -name "*.md" -newer src/main/java 2>/dev/null \| wc -l` | `find docs/ .cursorrules -newer src/ 2>/dev/null \| wc -l` |
| 自动化触发机制 | `ls .mdp/hooks/ 2>/dev/null; grep -r "update-context\|post-commit" .mdp/ --include="*.md" 2>/dev/null \| wc -l` | `ls .husky/ 2>/dev/null && cat .husky/commit-msg 2>/dev/null; grep -r "commit-msg\|post-commit" .husky/ 2>/dev/null \| head -5` |
