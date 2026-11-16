# 维度 5：代码可扩展性（5%，L3）

**参考设计原则**：OCP（开闭原则）、DIP（依赖倒置原则）、ISP（接口隔离原则）
**参考设计模式**：策略模式、工厂模式、模板方法模式

**核心原则**：AI 新增功能时能找到正确的扩展点，不需要修改核心代码。

## 评估标准（通用）

- [ ] **扩展点有文档说明**：哪些地方预留了扩展能力，如何扩展（新增功能/模块的步骤）
- [ ] **扩展机制有注释**：核心扩展机制的使用意图有说明
- [ ] **遵循开闭原则**：扩展通过新增而非修改已有核心代码
- [ ] **依赖倒置**：高层模块依赖抽象（接口/Props/Hook），不依赖具体实现
- [ ] **抽象设计合理**：接口/组件职责单一，不强迫实现/使用不需要的能力
- [ ] **核心抽象有设计意图说明**（为什么这么抽象）

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 扩展点文档完整，扩展机制有注释，遵循 OCP/DIP，核心抽象意图清晰 |
| 75–89 | 主要扩展点有说明，设计原则基本遵守，但文档不完整 |
| 60–74 | 有扩展设计但无文档，或部分违反 OCP |
| <60 | 无扩展性设计，修改功能需要改动大量已有代码 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 扩展点文档 | `grep -r "扩展点\|extension point\|如何扩展\|how to extend" . --include="*.md" --include="*.java" 2>/dev/null \| wc -l` | `grep -rn "扩展点\|如何新增\|如何添加\|extension\|how to add" docs/ README.md .cursorrules 2>/dev/null \| wc -l` |
| 抽象/接口数量 | `find . -path "*/src/main/java/*" -name "*.java" \| xargs grep -l "^public interface\|^public abstract class" 2>/dev/null \| wc -l` | `find . \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" 2>/dev/null \| xargs grep -l "^export interface\|^export type\|^export abstract" 2>/dev/null \| wc -l` |
| 扩展模式使用 | `find . -name "*Strategy*.java" -o -name "*Factory*.java" -o -name "*Template*.java" 2>/dev/null \| wc -l` | `grep -rn "children\|renderXxx\|render[A-Z]\|slots\|plugin\|middleware" . --include="*.tsx" --include="*.ts" 2>/dev/null \| grep -v "node_modules\|test\|spec" \| wc -l` |
| 配置驱动设计（前端专用） | 无 | `grep -rn "config\|registry\|register\|plugin" . --include="*.ts" 2>/dev/null \| grep -v "node_modules\|test" \| wc -l` |
