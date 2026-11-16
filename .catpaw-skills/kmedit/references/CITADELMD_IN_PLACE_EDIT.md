# 1.0 HTML 文档编辑与重命名

直接使用本地 `kmedit`，无需额外文档编辑 CLI。1.0 存储 HTML，没有协作 step 通道。

## 读取与编辑

```bash
kmedit inspect --doc-id <docId> --snapshot-file /tmp/km-page.html
```

确认输出 `docVersion: "1.0"`，记录 `version`。文件是原始 HTML，保留原有宏、资源地址与属性，只修改目标内容。
`writable: false` 表示 inspect 本身只读，不代表没有编辑权限；`canEdit` 为服务端返回的权限状态。

```bash
kmedit full --doc-id <docId> --html-file /tmp/km-page.html --step-version <version> --dry-run
kmedit full --doc-id <docId> --html-file /tmp/km-page.html --step-version <version>
```

这里 `--step-version` 使用 1.0 的 page version。保存前核对版本，保存请求也携带版本；冲突时重新读取并重新应用修改，不能只换版本号。成功后检查 `readback.verified` 和新版本。
不接受 ProseMirror JSON、Markdown 或节点级 patch；2.0 整篇编辑参见 [full-edit.md](full-edit.md)。

## 重命名

```bash
kmedit rename --doc-id <docId> --title "新标题" --expected-step-version <version>
```

正文保持不变。2.0 同样支持 rename，其 expected version 来自 inspect 的 `currentStepVersion`。
