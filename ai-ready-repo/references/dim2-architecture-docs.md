# 维度 2：架构文档完整性（12%，L2）

**核心原则**：AI 需要理解仓库的整体结构和各模块分工，才能精准定位修改范围，避免改 A 坏 B。
不只是"有文档"，而是文档能否帮助 AI 理解"为什么这么设计"。

> ⚠️ **重要**：架构文档必须本地可访问；外部链接（如学城 km.sankuai.com）对 AI 不可见，不计入得分。

## 评估标准（通用）

- [ ] 架构设计文档存在且内容充实（非空模板）
- [ ] 包含模块/目录结构图（ASCII 图或文字描述）
- [ ] 模块/子应用职责有说明，依赖关系显性化
- [ ] **核心设计意图有说明**（为什么这么设计，不只是做什么）
- [ ] 典型调用链路/业务流程有说明
- [ ] 架构决策记录（ADR）存在，含背景和理由（加分项）
- [ ] 分层/分区架构清晰，各层/各模块职责单一

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 架构文档完整，含结构图、调用链/业务流程、设计意图、ADR |
| 75–89 | 架构文档存在，但缺 ADR 或设计意图说明 |
| 60–74 | 有基础架构描述，但细节不足 |
| <60 | 无架构文档 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 架构文档位置 | `find . -name "*architecture*.md" -o -name "*架构*.md" 2>/dev/null; find .mdp/context/ -name "*architecture*" -type f 2>/dev/null` | `find docs/ -name "*.md" -type f 2>/dev/null; ls README.md 2>/dev/null` |
| 文档行数 | `find .mdp/context/ -name "*architecture*" -type f 2>/dev/null \| while read f; do echo "$(wc -l < "$f") 行: $f"; done` | `find docs/ -name "*.md" -type f 2>/dev/null \| while read f; do echo "$(wc -l < "$f") 行: $f"; done; wc -l README.md 2>/dev/null` |
| 结构图存在性 | `grep -r "├\|└\|│" .mdp/context/ 2>/dev/null \| wc -l` | `grep -rn "├\|└\|│\|packages/\|src/" docs/ README.md 2>/dev/null \| wc -l` |
| 设计意图描述 | `grep -r "为什么\|设计意图\|why\|rationale" .mdp/context/ --include="*.md" 2>/dev/null \| wc -l` | `grep -rn "为什么\|设计意图\|why\|rationale\|选型\|决策" docs/ README.md 2>/dev/null \| wc -l` |
| ADR 记录 | `find . -name "ADR*.md" -o -name "adr*.md" 2>/dev/null` | `find docs/ -name "ADR*" -o -name "adr*" -o -name "decision*" 2>/dev/null` |
| 依赖关系描述 | `grep -r "依赖\|上游\|下游\|upstream\|downstream" .mdp/context/ --include="*.md" 2>/dev/null \| wc -l` | `grep -rn "依赖\|shared-lib\|packages\|子应用\|micro" docs/ README.md 2>/dev/null \| wc -l` |
