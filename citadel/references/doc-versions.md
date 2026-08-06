# 文档历史版本管理

## 查看/还原文档历史版本

```bash
# Step 1：获取历史版本列表（最多 200 条，按时间降序；返回 stepVersion、title、editors 等）
oa-skills citadel getDocumentVersions --contentId <id>

# Step 2：获取目标版本的 CitadelXML 并保存（--stepVersion 取上一步返回的 stepVersion 字段，非 version 字段）
oa-skills citadel getDocumentVersionXml --contentId <id> --stepVersion <stepVersion> --output /tmp/restore.xml

# Step 3：还原文档（覆写当前内容，执行前先与用户确认目标版本）
oa-skills citadel updateDocumentByXml --contentId <id> --file /tmp/restore.xml
```

## 注意事项

- `--stepVersion` 必须来自 `getDocumentVersions` 返回结果中的 `stepVersion` 字段，**不是** `version` 字段
- Step 3 执行前必须先与用户确认目标版本，还原操作会覆盖当前文档内容
- 还原成功后提醒用户刷新页面查看
