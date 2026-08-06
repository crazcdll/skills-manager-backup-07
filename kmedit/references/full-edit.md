# 全文编辑（`kmedit full`）

用完整的 ProseMirror JSON 目标文档替换正文。运行时用 keyed diff 把它翻译成增量协作 step 后提交，
不做全文覆盖，因此局部改动只产生局部 step：他人光标位置不受影响，修订历史里能看出改了什么。

## 什么时候用它

- 跨区域批量改动（统一术语、批量调整表格某一列），产出天然是整篇 JSON。
- 重排章节、跨块搬移内容，用 `patch` 的结构化 operation 很难表达，但"最终文档长这样"很好写。

**小范围、位置明确的改动优先用 `kmedit patch`**。全文编辑要求你先取回整篇文档，token 成本高得多。

## 标准流程

```bash
# 1. 取当前文档与版本号
km get <docId> --json > /tmp/doc.json          # 完整 ProseMirror JSON
# stepVersion 从 patch 的 dry-run 或 km edit 的返回中获取

# 2. 本地修改 /tmp/doc.json（jq / 脚本 / 直接编辑）

# 3. 先看变更摘要
kmedit full --doc-id <docId> --json-file /tmp/doc.json --step-version <n> --dry-run

# 4. 确认无误后提交
kmedit full --doc-id <docId> --json-file /tmp/doc.json --step-version <n>
```

`--dry-run` 是可选的预览，不是必须的前置步骤：改动一致时第 4 步可直接执行。

## 硬性要求

- **只接受 JSON**。CitadelXML / CitadelMD 是官方 CLI 的输入编码，不是服务端协议，不要拿来回写。
- **`--step-version` 必填**。目标文档是基于某个基准写的；不声明基准的话，别人在这期间的改动会被静默还原。
- **不要把 `km get`（默认 markdown）或 `getSimpleMarkdown` 的输出拿去回写**，那是只读格式，会丢 nodeId 和结构。

## 冲突后怎么办

版本不一致时返回 `version_conflict`，并附带块级判定：

- `overlappingNodeCount: 0` —— 别人改的块和你改的块不相交。**重新取最新文档、在新基准上重新生成目标**后重试。
- `overlappingNodeCount > 0` —— 真冲突，`overlappingNodeIds` 列出相交的节点，需要你决定如何合并。

**不要只把 `--step-version` 换成新版本号后重投旧内容。** 旧目标是基于旧基准生成的，重投会还原别人的改动。

## 风险提醒

命中门禁时返回 `full_edit_risk_blocked`，`details.retry.acknowledgeRisks` 会列出需要逐个承认的风险码：

| 风险码 | 含义 |
|---|---|
| `large_deletion` | 删除的正文块比例过高 |
| `large_content_loss` | 文本总量流失过多（保留了块和 nodeId 但清空了正文，也会命中这条） |
| `nodeid_churn` | 大量既有 nodeId 在目标中消失 |
| `cursor_disruption` | 在线协作者光标存活率过低 |
| `empty_target` | 目标文档正文为空 |

确认这些确实是你想要的之后，逐个加 `--acknowledge-risk <code>` 重试。**不要盲目承认**——它们通常意味着目标
文档漏掉了本该保留的内容。

以下是硬失败，不能承认，必须修正输入：

- `attachment_ownership_invalid`：引用了属于其他文档的附件/图片。先用官方上传或复制流程把资源落到本文档。
- `provider_lifecycle_required`：目标里出现了基准中没有的 XTable、Data2Chart、sync block 等托管资源。
  全文编辑无法创建它们，先用对应专用命令创建，再把返回的 ID 写进目标文档。

## 不可自动重试

`commit_unverified` 表示服务端可能已经接受了提交但结果无法证实，`retrySafe: false`。
必须重新读取最新 snapshot + tail 确认实际状态后再决定，不能直接重投。
