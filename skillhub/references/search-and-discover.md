# 搜索与发现 Skill

## 关键词搜索

```bash
# 基础关键词搜索（覆盖内部 SkillHub 市场）
mtskills search <关键词>

# 示例
mtskills search excel          # 搜索处理 Excel 的 Skill
mtskills search 数据分析       # 支持中文关键词
mtskills search pdf            # 搜索 PDF 相关 Skill
mtskills search ppt 演示       # 多关键词
```

## 按标签筛选

```bash
mtskills search --tag <标签>

# 常用标签示例
mtskills search --tag 文档处理
mtskills search --tag 数据处理
mtskills search --tag 美团内部
mtskills search --tag 自动化
```

关键词 + 标签可组合使用：
```bash
mtskills search excel --tag 数据处理
```

## 查看 Skill 详情

```bash
# 查看 SKILL.md 原文（含 description、认证状态、作者、版本等）
mtskills read <skill名称>

# 示例
mtskills read xlsx
mtskills read pdf
```

## 认证标记说明

搜索结果和详情中，Skill 来源分为两类：

| 标记 | 含义 | 建议 |
|---|---|---|
| `verified: true` | SkillHub 官方认证 | 优先选择，经过平台安全审核 |
| 无 verified 标记 | 社区贡献 | 建议先用 `pre-install-vetting.md` 进行安全评估再安装 |

查看认证状态：
```bash
mtskills read <skill名称>
# 在输出的 frontmatter 部分查找 verified: true
```

## 搜索技巧

1. **用功能描述搜索**，而非技术术语。例如用"Excel 处理"而非"openpyxl"
2. **看 description 全文**：`mtskills read <name>` 可查看触发条件，判断是否匹配你的使用场景
3. **优先选 verified**：多个同类 Skill 并存时，选带 `verified: true` 标记的官方认证版本
4. **安装前评估**：对无 verified 标记的社区 Skill，参考 `references/pre-install-vetting.md` 进行安全评估

## 典型场景

**场景：找一个处理 Excel 的 Skill**

```bash
mtskills search excel
# 查看搜索结果，找到候选 skill 名称（如 xlsx）

mtskills read xlsx
# 阅读 SKILL.md，确认功能是否匹配，查看 verified 状态

# 若无 verified 标记，先评估安全性
mtskills i xlsx --target-dir /tmp/xlsx-preview
# 参考 references/pre-install-vetting.md 审查下载的 Skill 目录

# 确认安全后正式安装
mtskills i xlsx -g
```
