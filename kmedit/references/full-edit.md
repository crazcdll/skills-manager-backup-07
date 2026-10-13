# 全文编辑（`kmedit full`）

2.0 文档优先使用带保留标记的 Markdown。Agent 编辑正文语义，运行时读取最新原生 JSON，保留复杂节点，
再用 keyed diff 生成 Parker + Pike 增量 step。也支持完整 ProseMirror JSON；1.0 使用 HTML。

小范围、位置明确的文字/节点修改优先使用 `patch`；章节重排、正文改写使用 `full`。

## Markdown 工作流

```bash
# 同一次读取返回当前版本；文件含最新 snapshot + tail
kmedit inspect --doc-id <docId> --markdown-file /tmp/body.md
# stdout 中的 currentStepVersion 是以下命令的基准版本

# 修改 /tmp/body.md 的普通 Markdown，保留 document 标记和需要保留的 keep 块
kmedit full --doc-id <docId> --markdown-file /tmp/body.md --step-version <n> --dry-run
kmedit full --doc-id <docId> --markdown-file /tmp/body.md --step-version <n>
```

可选同时加 `inspect --snapshot-file /tmp/native.json` 留存原生基线；无需把整棵 JSON 填入 Agent 上下文。
`full --markdown-file -` 接受 stdin。`--dry-run` 无写入，执行相同校验并返回变更、风险和保留统计。

### 导出格式

```markdown
<!-- kmedit:document 123 version=7 -->

<!-- kmedit:block paragraph-id -->
可编辑的 **正文**。
<!-- kmedit:end -->

<!-- kmedit:keep drawing-block-id -->
> 保留原生 paragraph：drawio；以下为只读预览
>
<!-- kmedit:end -->
```

- `document` 绑定文档和版本，不要改写版本绕过冲突。
- `block` 内可修改普通 Markdown。未变块恢复完整原节点；修改块尽可能继承相同类型的 nodeId 和非 Markdown 属性。
  重排时连同起止标记一起移动。新增段落/标题/列表/引用/代码/链接/简单表格可直接写在块外。
- `keep` 引用原生块，不是 Markdown 图片占位。图表、图片、图标、附件、音视频、托管宏、所有既有表格、
  不支持的 marks/节点以及带评论 `quote` 的块均完整保留。嵌套资源保护其整个顶层块。
- keep 块可以整体移动，也可移除只读预览、仅保留起止标记；不能改写预览来编辑原节点。
  图表/表格的内部修改使用对应 `patch` operation。带评论的文字修改使用精确 patch，以保留 quote 标记。
- Markdown 全文仅修改正文，原生标题及其评论标记原样保留；改标题使用 `rename` 或 JSON full。
- `inspect` 的 `preservedNodes` 列出保留块的 `nodeId/type/nativeTypes/quoteIds`。
  保留块的 quoteId 和原节点保持不变，因此已有评论继续关联原内容；不会重新创建或修改评论线程。
- 原生保留节点被遗漏时返回 `markdown_preservation_required`，列出缺失项，提交前停止。
  只有用户确实要求删除时，移除该 keep 块并传 `--drop-preserved-node <nodeId>`（可重复）。删除仍受原有风险门禁约束。
- 未知、重复、嵌套或格式错误的标记、文档/版本不匹配、只读预览被修改都会报错。
  fenced/indented code 中的标记文字按代码处理。

### 直接生成新 Markdown

没有需要保留的复杂节点/评论块时，可以直接生成新的正文 Markdown，无需参考原 JSON。
已有复杂内容时，生成新正文并把导出的 keep 块放在所需位置；遗漏会报错，不能静默抛弃。
普通块的标记可省略，但相应 nodeId 会重建，可能触发删除、nodeId 变动及光标风险门禁。

支持普通 Markdown 标题、段落、粗体/斜体/删除线/行内代码、列表、引用、代码块、链接、水平线及简单表格。
不执行原始 HTML。新图片 `![...](...)` 会返回 `provider_lifecycle_required`，先用 `patch` + paste/insert_image
上传，再重新导出；新 DrawIO、附件、Data2Chart、XTable 等同样先走专用生命周期。

**`km get` / getSimpleMarkdown 是只读语义视图，不含保留契约。需要保留原内容时必须使用 `inspect --markdown-file`。**

## 原生 JSON 工作流

```bash
kmedit inspect --doc-id <docId> --snapshot-file /tmp/native.json
# 修改完整 native.json，使用同次 inspect 返回的 currentStepVersion
kmedit full --doc-id <docId> --json-file /tmp/native.json --step-version <n> --dry-run
kmedit full --doc-id <docId> --json-file /tmp/native.json --step-version <n>
```

三个输入 `--markdown-file`、`--json-file`、`--html-file` 必须且只能选择一个。
CitadelXML/CitadelMD 是官方 CLI 的输入编码，不能当作这里的 Markdown 保留格式或服务端协议。

## 版本与失败处理

`--step-version` 必填。版本变化返回 `version_conflict`；重新导出最新内容，在新基准上重新应用编辑。
不要只更换命令中的版本或 Markdown document 标记后重投旧正文，那会还原他人改动。
JSON full 可提供冲突块判定；Markdown 在编译保留引用前即拒绝过期版本。

`full_edit_risk_blocked` 的 `details.retry.acknowledgeRisks` 列出风险码：

| 风险码 | 含义 |
|---|---|
| `large_deletion` | 删除正文块比例过高 |
| `large_content_loss` | 正文文本流失过多 |
| `nodeid_churn` | 大量既有 nodeId 消失 |
| `cursor_disruption` | 光标存活率过低 |
| `empty_target` | 正文为空 |

核对是否符合用户意图，再逐个加 `--acknowledge-risk <code>`。不得用风险确认绕过缺失保留标记、
资源归属、Provider 生命周期或 schema 失败；这些问题必须修正输入。

`commit_unverified` 表示服务端可能已接受提交，`retrySafe: false`；先 inspect 确認实际状态，不可直接重投。
成功读回只能证明保存；E2E 还需打开文档确认编辑器初始化、图形/附件/复杂表格加载和评论锚点。

## 1.0 文档

1.0 使用 `full --html-file` 与 page version，不接受 Markdown 或 ProseMirror JSON。
详见 [1.0 HTML 编辑](CITADELMD_IN_PLACE_EDIT.md)。
