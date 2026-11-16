# 学城 CR 文档创建指南（Step 6）

## HTML/XML 代码与排版

> **不要用代码块外的 HTML/XML 标签给学城正文排版。**
> 学城正文排版不使用裸 HTML/XML 标签；审查对象中的 HTML/XML 代码应保留原文，放在标明语言的代码块中。

### ❌ 禁止的标签（常见误用）

```
<heading level="2">    <table>    <tr>/<td>/<th>
<blockquote>           <km-table>  <km-heading>
<strong>/<em>          <br>/<hr>    <div>/<span>
<font>                 <a href="">  <img src="">
```

### ✅ 正确替代

| 想要的效果 | ❌ 禁止写法 | ✅ 正确写法 |
|-----------|-----------|-----------|
| 二级标题 | `<heading level="2">` / `<h2>` | `## 标题` |
| 表格 | `<table><tr><td>` | `\| col1 \| col2 \|` |
| 加粗 | `<strong>text</strong>` | `**text**` |
| 斜体 | `<em>text</em>` | `*text*` |
| 链接 | `<a href="url">text</a>` | `[text](url)` |
| 引用 | `<blockquote>` | `> 引用内容` |
| 分割线 | `<hr>` | `---` |
| 换行 | `<br>` | 空行 |

> ⚠️ **子 Agent 特别注意**：LLM 天然倾向把 Markdown 升级为 HTML 以"看起来更结构化"，这在学城环境下是**灾难性的**。务必只用纯 Markdown 语法。

---

## ⚠️ 表格格式强制规范

**禁止在 `--file` 写入的 Markdown 中使用 `:::table{...}` 宏格式！**

学城的 `:::table{borderColor=...}` JSON 宏只在浏览器编辑器中生效，通过 `--file` 写入时会原样输出为乱码 JSON 字符串。

✅ 正确：标准 Markdown 表格
```markdown
| 文件名 | 变更类型 | +行数 | -行数 |
|--------|---------|-------|-------|
| Foo.java | 修改 | 12 | 3 |
```

❌ 禁止：`:::table{borderColor=...}` JSON 宏格式（会输出为原始 JSON 字符串）

---

## 写入命令

⚠️ 必须用 `--file` 方式写入，**禁止用 `--content` 传多行字符串**（`\n` 不会转换为真实换行，Markdown 会挤成一行）。

### 日期子目录（防止父目录子文档数量超限）

学城单个父目录下的二级子文档数量有限制，因此 CR 文档不直接创建在 `$CITADEL_PARENT_ID` 下，而是先在其下找到或创建当天日期目录，再在日期目录下创建 CR 文档。

```bash
# 0. 取当天日期
DATE_DIR=$(date +%Y-%m-%d)

# 1. 查找父目录下是否已有当天日期子目录
#    调 citadel getChildContent --contentId $CITADEL_PARENT_ID
#    在返回的子文档列表中查找 title 完全等于 $DATE_DIR 的条目
#    - 找到 → 取其 contentId 作为 DATE_PARENT_ID
#    - 未找到 → 创建日期目录：
#      citadel createDocument --title "$DATE_DIR" --content "" --parentId $CITADEL_PARENT_ID
#      取返回的 contentId 作为 DATE_PARENT_ID
```

### 创建 CR 文档

```bash
# 1. 把 CR 文档内容写入临时文件
cat > /tmp/cr_review_{prId}.md << 'EOF'
{完整 Markdown 内容，直接多行写入}
EOF

# 2. 用 --file 创建文档，注意 parentId 使用 DATE_PARENT_ID（日期子目录）
#    （⚠️ 不需要传 --mis，认证从缓存自动读取）
oa-skills citadel createDocument \
  --title "${DOC_TITLE}" \
  --file /tmp/cr_review_{prId}.md \
  --parentId "${DATE_PARENT_ID}"
# DOC_TITLE 由发布器生成：{org}/{repo} PR #{prId} Code Review {run_id}：{标题}
# 每轮生成一次 UUID 作为 run_id，同轮重试复用，不同轮次使用不同值。
# 标题通过参数数组、shell=False 传递；不得把外部 PR 标题拼进 shell 命令源码。

# 3. 清理临时文件
rm -f /tmp/cr_review_{prId}.md
```

默认 `CITADEL_PARENT_ID`：`2771240961`（学城 CR 文档目录）

> ⚠️ `CITADEL_PARENT_ID` 获取逻辑：优先 `get_org_info.py` 接口返回,为空时用硬编码默认 `2771240961`。日期目录仅在其下加一层。

## 失败处理

降级：CR 结果输出到对话 + 大象通知提交人，**不阻塞 Step 7**。

## CatPaw 对比章节

创建文档后，从 PR overview 提取 CatPaw 评论（含 `🤖 AI Code Review`），写入文档「与 CatPaw 对比」章节。无 CatPaw 评论则跳过该章节。

## 文档结构模板

见 [citadel-doc-template.md](citadel-doc-template.md)。
