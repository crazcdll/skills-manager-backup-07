# 学城 CR 文档创建指南（Step 6）

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

> ⚠️ **日期目录也必须用 `--file` 方式创建，禁止用 `--content ""`！** `--content` 传空字符串/纯空格会报错 `❌ 请提供 --content`。

学城单个父目录下的二级子文档数量有限制，因此 CR 文档不直接创建在 `$CITADEL_PARENT_ID` 下，而是先在其下找到或创建当天日期目录，再在日期目录下创建 CR 文档。

```bash
# 0. 取当天日期
DATE_DIR=$(date +%Y-%m-%d)

# 1. 查找父目录下是否已有当天日期子目录
#    调 citadel getChildContent --contentId $CITADEL_PARENT_ID
#    在返回的子文档列表中查找 title 完全等于 $DATE_DIR 的条目
#    - 找到 → 取其 contentId 作为 DATE_PARENT_ID
#    - 未找到 → 创建日期目录（⚠️ 必须用 --file，禁止用 --content，空字符串会报错）：
#      echo "$DATE_DIR" > /tmp/cr_date_dir.md
#      citadel createDocument --title "$DATE_DIR" --file /tmp/cr_date_dir.md --parentId $CITADEL_PARENT_ID
#      rm -f /tmp/cr_date_dir.md
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
  --title "PR #{prId} Code Review：{标题}" \
  --file /tmp/cr_review_{prId}.md \
  --parentId "${DATE_PARENT_ID}"

# 3. 清理临时文件
rm -f /tmp/cr_review_{prId}.md
```

默认 `CITADEL_PARENT_ID`：`2749896619`（学城 CR 文档目录）

> ⚠️ `CITADEL_PARENT_ID` 的获取逻辑不变（优先 `get_org_info.py` 接口返回，fallback 到 `cr-config.yaml` default）。日期目录仅在其下加一层。

## 失败处理

降级：CR 结果输出到对话 + 大象通知提交人，**不阻塞 Step 7**。

## CatPaw 对比章节

创建文档后，从 PR overview 提取 CatPaw 评论（含 `🤖 AI Code Review`），写入文档「与 CatPaw 对比」章节。无 CatPaw 评论则跳过该章节。

## 文档结构模板

见 [comment-templates.md](comment-templates.md) — `学城 CR 文档结构模板` 小节。
