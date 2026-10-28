# 文档历史版本管理

先识别文档类型。2.0 使用 CitadelXML；原生 MD（`type=7`）使用原生 Markdown。两者都复用相应类型的全文覆盖命令完成还原，没有独立的历史还原命令。

## 2.0 文档

```bash
# Step 1：获取历史版本列表（最多 200 条，按时间降序；返回 stepVersion、title、editors 等）
oa-skills citadel getDocumentVersions --contentId <id>

# Step 2：获取目标版本的 CitadelXML 并保存（--stepVersion 取上一步返回的 stepVersion 字段，非 version 字段）
oa-skills citadel getDocumentVersionXml --contentId <id> --stepVersion <stepVersion> --output /tmp/restore.xml

# Step 3：确认目标版本并备份当前内容后，覆写当前正文
oa-skills citadel updateDocumentByXml --contentId <id> --file /tmp/restore.xml
```

## 原生 MD 文档

```bash
# Step 1：获取历史版本列表，选择 stepVersion
oa-skills citadel getDocumentVersions --contentId <id>

# Step 2：读取精确历史 Markdown
oa-skills citadel getMarkdownDocumentVersion --contentId <id> --stepVersion <历史版本> --output /tmp/restore.md

# Step 3：确认目标版本，再读取当前内容和版本，保存独立备份
oa-skills citadel getMarkdownDocument --contentId <id> --output /tmp/current-before-restore.md

# Step 4：使用 Step 3 返回的当前 stepVersion 覆写；不得使用历史版本号
oa-skills citadel updateMarkdownDocument --contentId <id> --step-version <当前读取的版本> --file /tmp/restore.md

# Step 5：回读核对目标标题与正文
oa-skills citadel getSimpleMarkdown --contentId <id>
```

MD 的完整输出、保存回执与停止条件以 [MD 文档操作说明](markdown-documents.md#历史版本读取与还原) 为准。全文覆盖不承诺恢复历史节点身份和划词评论锚点。

## 注意事项

- 2.0 和 MD 的历史正文均通过安全屋入口读取；达到服务端保护密级时，需要平台提供有效且已开启安全屋的 Token。收到安全屋提示时停止，不切换普通读取入口。版本列表可查询不代表历史正文可读取。
- `--stepVersion` 必须来自 `getDocumentVersions` 返回结果中的 `stepVersion` 字段，**不是** `version` 字段
- 获取历史内容时会校验服务端实际版本；版本不匹配或正文缺失时失败，不用最新正文代替目标历史版本
- 版本列表的 `title` 是版本展示标签，不能当作文档标题；MD 历史标题以历史快照正文中的标题为准，2.0 覆写正文不会自动还原历史标题，需要时先确认标题再显式传 `--title`
- 覆写执行前必须先与用户确认目标版本，还原操作会覆盖当前文档内容
- 还原成功后提醒用户刷新页面查看
