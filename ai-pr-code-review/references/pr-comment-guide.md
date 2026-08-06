# PR 评论操作指南（Step 7）

## 前置检查（7-PRE）

```bash
$CODE_CLI user-info 2>&1
# 正常返回用户信息 → 继续；报错 → 确保浏览器已打开 dev.sankuai.com 页面
```

## 7A. P0/P1 行内评论

每个 P0/P1 问题单独一条行内评论，锚定到具体代码行：

```bash
$CODE_CLI comment-add \
  --url "{PR_URL}" \
  --file "{完整文件路径（与 pr-changes 返回的 path 完全一致）}" \
  --line {行号} \
  --line-type ADDED \
  --text "{行内评论内容}" 2>&1
```

**参数说明**：
- `--line`：从 `pr-diff` 输出直接读取（`+` 前缀行对应的行号）
- `--line-type`：`ADDED`（新增行）/ `CONTEXT`（问题在存量代码时）/ `REMOVED`（一般不挂）
- `--file-type`：默认 `TO`，无需修改

⚠️ **只对 ADDED / CONTEXT 行挂评论，REMOVED 行不挂。**

逐条发送，失败重试最多 4 次（间隔 2s）；全部失败则降级为全局评论并标注文件名+行号。

## 7B. P2/P3/Cross-Repo 全局摘要

```bash
$CODE_CLI comment-add \
  --url "{PR_URL}" \
  --text "{全局摘要}" 2>&1
```

多仓库时 Cross-Repo 问题同时写入所有涉及的 PR，注明「跨仓库问题，涉及 [{另一仓库}]」。

## 7C. 验证

```bash
$CODE_CLI pr-comments --url "{PR_URL}" 2>&1
```

确认评论已出现，且 **P0/P1 评论的 `file` 字段非 null**（为 null = 发成了全局评论，须 `comment-delete` 删除后重发 7A）。

未出现 → 重试最多 4 次；仍失败则大象通知 PR 提交人。

## 评论内容格式

见 [comment-templates.md](comment-templates.md) — `行内评论模板` / `全局评论模板` 小节。
