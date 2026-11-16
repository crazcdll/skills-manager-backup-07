# 质量门禁规则

> 本文件定义 `scripts/validate.js` 实施的所有检查项，以及 ERROR/WARN 分级。
> ERROR 必须阻断交付；WARN 列入交付摘要由用户决定。

## 规则清单

### G1 文件大小（已废弃）
- **规则**：历史上曾要求单 .md 文件行数 ≤ 500，现已**取消行数硬上限与预警阈值**。
- **级别**：无（`validate.js` 不再针对行数产出 error / warning）
- **说明**：若未来需要重新启用，可在 `validate.js` 中恢复对应分支。文档拆分由作者按可读性与 `references/` 对应模板的章节粒度自行决策。

### G2 Frontmatter 必填字段
- **规则**：`category` / `description` / `domain` 三字段存在且非空
- **级别**：ERROR
- **修复**：按 `template-*.md` 示例补齐

### G3 Frontmatter 闭环枚举
- **规则**：`category` ∈ `references/metadata-spec.md` 的允许集；`domain` 同理
- **级别**：ERROR
- **修复**：改用允许值

### G4 description 长度
- **规则**：`description` 长度 ≤ 120 字（中文字符按 1 计）
- **级别**：WARN（超长）/ ERROR（缺失）
- **修复**：精简描述

### G5 tags 数量
- **规则**：`tags` 字段存在且 ≥ 5 个
- **级别**：WARN
- **修复**：按 `metadata-spec.md` 的 tags 生成规则补齐

### G6 last_updated 合法性
- **规则**：`last_updated` 为 YYYY-MM-DD 合法日期且 ≤ 今天
- **级别**：ERROR
- **修复**：改为今天日期

### G7 H1 存在
- **规则**：正文第一个标题必须是 `# ` 级 H1
- **级别**：ERROR
- **修复**：在 frontmatter 之后添加 H1

### G8 模板必备章节
- **规则**：按该文件的 `category` 对照 `references/template-*.md` 中必备的 H2 列表；缺失则标记
- **级别**：WARN（阶段 2 使用，驱动阶段 3 的变更计划表）
- **修复**：补齐章节（阶段 4 自动执行）

### G9 内部链接有效性
- **规则**：`related` 相对路径 + 正文中的 `[xxx](./foo.md)` 相对链接指向的文件实际存在
- **级别**：WARN
- **修复**：更新路径或补全文件

### G10 有效内容行占比
- **规则**：非空、非纯注释、非纯代码围栏符的行 / 总行 > 60%
- **级别**：WARN
- **修复**：删除水分

### G11 group 归属一致性
- **规则**：路径中包含 `<group>` 的文件，其 frontmatter `domain` 应为 `<group>` 或与之相关的技术栈（如 duo/mrn）
- **级别**：WARN
- **修复**：修正 domain

### G12 根 AGENTS.md 存在性
- **规则**：仓库根 `AGENTS.md` 必须存在
- **级别**：ERROR（全局级）
- **修复**：联系知识库 Owner

### G13 术语一致性（WARN）
- **规则**：文件中出现但未登记在 `context-docs/glossary/<group>.md` 或 `context-docs/glossary/general.md` 的大写缩写（≥3 字母）标记为疑似未登记术语
- **级别**：WARN
- **修复**：收录到 glossary 或用已有术语替换

### G14 禁止 `any` 示例（仅 spec/coding-standards/*.md）
- **规则**：代码块（ts/tsx）中不得出现裸 `any`（除非是反例演示且上下文明确）
- **级别**：WARN
- **修复**：改为具体类型或加"反例"标注

---

## 输出格式

`validate.js` 输出 JSON：

```json
{
  "group": "gc",
  "files": [
    {
      "path": "context-docs/overviews/gc.md",
      "errors": [],
      "warnings": [
        { "rule": "G5", "message": "tags 仅 3 个，建议补至 5" }
      ]
    }
  ],
  "summary": { "errors": 0, "warnings": 3 }
}
```

退出码：`0` = 通过；`1` = 有 ERROR。
