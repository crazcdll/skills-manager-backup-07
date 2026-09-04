# 维度 4：代码可维护性（7%，L3）

**参考设计原则**：SRP（单一职责原则）、低耦合高内聚、迪米特法则（最少知识原则）

**核心原则**：AI 修改代码时不会意外破坏架构，能识别哪些地方不能随意改。

## 评估标准（通用）

- [ ] **技术债可识别**：已知债务有 `TODO` / `FIXME` 标注，AI 知道哪些地方不能改
- [ ] **架构边界保护**：架构约束文档明确说明，禁止跨层/跨模块随意调用
- [ ] **单一职责遵守**：类/组件职责单一，无"上帝类/巨型组件"
- [ ] **低耦合**：模块间依赖通过抽象（接口/Props/Hook）而非具体实现
- [ ] **废弃代码有标记**（`@Deprecated`/`@deprecated` + 替代方案说明）
- [ ] **大文件已拆分**（单文件行数合理）

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 技术债有标注，架构边界约束明确，单一职责遵守良好，低耦合设计规范 |
| 75–89 | 大部分满足，但技术债标注不完整或架构边界约束不清晰 |
| 60–74 | 有意识但不系统，存在上帝类/巨型组件或跨层调用 |
| <60 | 无技术债标注，架构边界无保护，大量上帝类/巨型组件 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 技术债标注 | `grep -rn "@TODO\|@FIXME\|FIXME\|TODO" . --include="*.java" 2>/dev/null \| wc -l` | `find . \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null \| xargs grep -n "TODO\|FIXME\|HACK\|XXX" 2>/dev/null \| wc -l` |
| 超大文件检查 | `find . -name "*.java" -type f -exec wc -l {} \; \| awk '$1 > 500 {print}' \| wc -l` | `find . -name "*.tsx" -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null \| xargs wc -l 2>/dev/null \| awk '$1 > 500 {print}' \| sort -rn \| head -10` |
| 巨型 Hook（前端专用） | 无 | `find . \( -path "*/hooks/*.ts" -o -path "*/hooks/*.tsx" \) -not -path "*/node_modules/*" 2>/dev/null \| xargs wc -l 2>/dev/null \| awk '$1 > 300 {print}' \| sort -rn \| head -10` |
| 废弃代码标记 | `grep -rn "@Deprecated" . --include="*.java" 2>/dev/null \| wc -l` | `find . \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" 2>/dev/null \| xargs grep -n "@deprecated" 2>/dev/null \| wc -l` |
| 跨边界引用检查 | `grep -r "禁止跨层\|架构约束\|不得直接调用" .mdp/ --include="*.md" 2>/dev/null \| wc -l` | `find packages/ -name "*.ts" -o -name "*.tsx" 2>/dev/null \| xargs grep -n "from '\.\./\.\./[a-z]" 2>/dev/null \| grep -v "shared-lib\|ui-components" \| head -10` |
