# User-Facing Message Templates

> This file contains all user-facing Markdown message templates used by the ee-code skill.
> AI agent should read this file when it needs to display formatted messages to the user.

## Table of Contents

1. [Prerequisites: CLI Not Installed](#cli-not-installed)
2. [Prerequisites: Login Failed](#login-failed)
3. [Self-Review: Case A (Has Reviewers)](#self-review-case-a)
4. [Self-Review: Case B (No Reviewers)](#self-review-case-b)
5. [Create PR: Source Equals Target Branch](#source-equals-target)
6. [Create PR: Existing PR Found](#existing-pr-found)
7. [Create PR: Uncommitted Changes (Existing PR)](#uncommitted-changes-existing-pr)
8. [Create PR: Uncommitted Changes (New PR)](#uncommitted-changes-new-pr)
9. [Create PR: No Commits to Merge](#no-commits-to-merge)
10. [Create PR: ONES Issue Not Bound](#ones-issue-not-bound)
11. [Fix Comments: Analysis Result](#fix-comments-analysis)
12. [Fix Comments: Fix Summary Comment](#fix-summary-comment)

---

## CLI Not Installed

<a id="cli-not-installed"></a>

```markdown
❌ **code-cli 未安装**

请使用以下命令安装 code-cli：
```bash
npm install -g @ee/code-cli --registry=http://r.npm.sankuai.com
```

安装完成后，请使用以下命令登录：
```bash
code-cli auth login
```
```

---

## Login Failed

<a id="login-failed"></a>

```markdown
❌ **自动登录失败**

请手动执行以下命令登录：
```bash
code-cli auth login
```
如果持续失败，请检查网络连接或联系代码仓库组的zhoudandan10。
```

---

## Self-Review: Case A (Has Reviewers)

<a id="self-review-case-a"></a>

When PR has assigned reviewers:

```markdown
❌ **无法执行该操作：作者不能评审自己的 PR**

您是 PR #<pr_id> 的作者，根据 MCode 平台规则，不允许作者自己评审（批准或拒绝）自己的 PR。

**当前分配的评审人：**
| MIS | 姓名 | 邮箱 |
|-----|------|------|
| zhangsan | 张三 | zhangsan@meituan.com |
| lisi | 李四 | lisi@meituan.com |

**解决方案：**
请联系上述评审人员之一进行代码评审和批准/拒绝操作。
```

---

## Self-Review: Case B (No Reviewers)

<a id="self-review-case-b"></a>

When PR has NO assigned reviewers:

```markdown
❌ **无法执行该操作：作者不能评审自己的 PR**

您是 PR #<pr_id> 的作者，根据 MCode 平台规则，不允许作者自己评审（批准或拒绝）自己的 PR。

**当前分配的评审人：** 无

**解决方案：**
1. 先为 PR 添加评审人员：
   ```bash
   code-cli pr add-reviewer <pr_id> -r <reviewer_mis> [--json]
   ```
2. 然后请这些评审人员执行批准或拒绝操作

**获取可用的评审人员列表：**
```bash
code-cli repo reviewers -t <target_branch> --json
```
```

---

## Source Equals Target Branch

<a id="source-equals-target"></a>

```markdown
❌ **无法创建 PR：源分支和目标分支相同**

源分支 `<source_branch>` 和目标分支 `<target_branch>` 是同一个分支，无法创建 PR。

请先创建或切换到一个不同的分支：

```bash
# 创建并切换到新分支
git checkout -b feature/your-feature-name

# 或切换到已存在的分支
git checkout your-branch-name
```

分支命名建议：
  - feature/xxx - 新功能开发
  - bugfix/xxx - Bug 修复
  - hotfix/xxx - 紧急修复
  - refactor/xxx - 代码重构
```

---

## Existing PR Found

<a id="existing-pr-found"></a>

```markdown
ℹ️ **已存在开启的 PR**

当前分支 `<source_branch>` 到 `<target_branch>` 已有一个开启的 PR：

| 项目 | 内容 |
|------|------|
| **PR ID** | #<pr_id> |
| **标题** | <pr_title> |
| **状态** | <pr_state> |
| **源分支** | `<source_branch>` |
| **目标分支** | `<target_branch>` |
| **创建时间** | <created_date> |

🔗 **[点击查看 PR](<pr_url>)**
```

---

## Uncommitted Changes (Existing PR)

<a id="uncommitted-changes-existing-pr"></a>

When existing PR is found and there are uncommitted changes:

```markdown
⚠️ **检测到未提交的修改**

当前工作目录存在以下未提交的文件：

| 状态 | 文件 |
|------|------|
| 修改 | `<file_path>` |
| 新增 | `<file_path>` |

> 是否需要将这些修改提交并推送到分支 `<source_branch>`？提交后这些修改将自动包含在已有的 PR #<pr_id> 中。

| 选项 | 操作 | 说明 |
|:----:|------|------|
| **1** | ✅ 提交并推送 | 将修改提交到当前分支并推送，更新已有 PR |
| **2** | ⏭️ 不需要 | 保持未提交的修改不变 |

请回复对应的数字（1-2）：
```

---

## Uncommitted Changes (New PR)

<a id="uncommitted-changes-new-pr"></a>

When creating new PR and there are uncommitted changes:

```markdown
⚠️ **检测到未提交的修改**

当前工作目录存在以下未提交的文件：

| 状态 | 文件 |
|------|------|
| 修改 | `src/main/java/Example.java` |
| 新增 | `src/test/java/ExampleTest.java` |
| 删除 | `docs/old-readme.md` |

> ⚠️ 这些未提交的修改将 **不会** 被包含在 PR 中。请选择如何处理：

| 选项 | 操作 | 说明 |
|:----:|------|------|
| **1** | ✅ 提交这些修改 | 将未提交的修改一起提交到当前分支，并包含在 PR 中 |
| **2** | 📦 暂存这些修改 | 使用 `git stash` 暂时保存，稍后可通过 `git stash pop` 恢复 |
| **3** | 🗑️ 丢弃这些修改 | 放弃所有未提交的修改（⛔ **不可恢复，请谨慎选择**） |
| **4** | ⏭️ 继续创建 PR | 保持未提交的修改不变，直接继续创建 PR |

请回复对应的数字（1-4）：
```

---

## No Commits to Merge

<a id="no-commits-to-merge"></a>

```markdown
❌ **无法创建 PR：没有可合并的提交**

当前分支 `<source_branch>` 与目标分支 `<target_branch>` 之间没有差异。

可能的原因：
1. 当前分支的所有提交已经合并到目标分支
2. 当前分支是从目标分支创建的，但还没有新的提交
3. 本地分支的提交还没有推送到远程仓库

请检查：
- 确保您已经提交了新的代码变更
- 确保本地提交已推送到远程仓库：`git push origin <source_branch>`
```

---

## ONES Issue Not Bound

<a id="ones-issue-not-bound"></a>

```markdown
❌ **创建 PR 失败**

当前仓库要求源分支关联 ONES 工作项，但分支 `<branch_name>` 尚未绑定任何 ONES 工作项。

请前往仓库分支管理页面绑定 ONES 工作项后再创建 PR：
🔗 [MCode 分支管理页面](https://dev.sankuai.com/code/repo-detail/{project}/{repo}/branch/all?key={branch_name})
```

---

## Fix Comments: Analysis Result

<a id="fix-comments-analysis"></a>

When there are both CLEAR and UNCLEAR comments:

```markdown
📋 **评审评论分析结果**

**✅ 以下评论修复方案明确，将直接修复：**

| 评论 ID | 文件 | 评论内容 | 修复方案 |
|--------|------|--------|--------|
| #123 | src/a.ts:10 | "缺少 null 判断" | 添加 null check |
| #124 | src/b.ts:25 | "变量名拼写错误 `contet` → `context`" | 修正拼写 |

---

**⚠️ 以下评论需要您确认修复方案：**

| 评论 ID | 文件 | 评论内容 | 问题 |
|--------|------|--------|------|
| #456 | src/c.ts:42 | "需要优化性能" | 不确定具体优化方向（缓存、算法、还是并发？） |
| #789 | src/d.ts:15 | "重构这部分代码" | 不确定重构目标（可读性、性能、还是功能调整？） |

请针对上述待确认的评论说明修复方案，例如：
#456: 使用 LRU 缓存机制优化性能
#789: 提取公共逻辑到新函数以提高可读性
```

---

## Fix Summary Comment

<a id="fix-summary-comment"></a>

Template for the PR comment posted after fixing review comments:

```text
已提交修复并推送完成：
- 已处理评论: #456, #789
- 主要修改:
  - src/a.ts: 修复空指针判断
  - src/b.ts: 调整边界条件处理
- 暂未处理: #790（原因: 需要产品确认）

