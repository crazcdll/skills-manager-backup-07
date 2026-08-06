---
name: ee-code
description: ALWAYS use this skill for ANY PR operations in Meituan code repositories like creating/merging/closing PR, fixing comments by reviewers, checking CI status, etc.. Talking anything about "PR" or "pull request", this skill comes first, especially before attempting `gh` liked commands.
version: 2.1.0
tag: [PR, PullRequest, CodeReview, MCode, CLI, ReviewComment, Fix, CI, Status, Check, Merge, Approve, Meituan]

metadata:
  skillhub.creator: "zhoudandan10"
  skillhub.updater: "lenghan"
  skillhub.version: "V3"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3439"
  skillhub.high_sensitive: "false"
---

# ee-code

# References

> - **User-facing message templates**: Read `references/templates.md` for all formatted error messages, status displays, and interactive prompts.
> - **CLI command reference**: Read `references/cli-reference.md` for full `code-cli` command syntax, flags, and JSON output formats.

# Overview

This skill provides comprehensive PR (Pull Request) workflow management using `code-cli`:

1. **Create PR** (Part 1) - Intelligent workflow with validation and checks
2. **Fix PR Comments** (Part 2) - Complete review comment resolution flow
3. **Simple PR Operations** (Part 3) - Status checks, merge, close, and other operations

---

# When to Use

**Trigger this skill for ANY PR-related request.**

| User Intent | Part |
|-------------|------|
| 创建/提交/发起 PR, create/open/submit PR, draft PR, 合并到 master | **Part 1** |
| 修复/处理/解决 PR 评论, fix/address review comments, 修复待解决问题 | **Part 2** |
| 查看 PR/CI 状态, 合并/关闭 PR, 审批/拒绝 PR, 添加评审人, 其他 PR 操作 | **Part 3** |

---

# Prerequisites

Before executing any PR workflow, verify that `code-cli` is installed and authenticated.

## Step 0.1 Check if `code-cli` is installed
- Run `code-cli --version` to verify installation
- If the command fails, display the "CLI Not Installed" template from `references/templates.md`

## Step 0.2 Check authentication status
- Run `code-cli auth status` to verify login status
- If not logged in, **automatically execute** `code-cli auth login`
- After login, run `code-cli auth status` again to verify
- If login succeeded: ✅ Proceed
- If login failed: ❌ **STOP**, display the "Login Failed" template from `references/templates.md`

---

# Global Rules

## 🔄 Data Freshness Rule

> **⚠️ CRITICAL**: Every invocation = fresh start. **NEVER reuse data from previous interactions.** Re-query ALL runtime data every time.

**Must re-fetch on every invocation:**

| 数据 | 获取方式 |
|------|----------|
| 当前分支名 | `git branch --show-current` |
| 仓库信息 | 解析 `git remote get-url origin` |
| 默认分支 | `code-cli repo branch default --json` |
| PR 列表/详情 | `code-cli pr list` / `code-cli pr view` |
| 评审人列表 | `code-cli repo reviewers` |
| 仓库设置 | `code-cli repo settings --json` |
| 未提交修改 | `git status --porcelain` |
| 认证状态 | `code-cli auth status` |

## 🔐 Self-Review Prohibition Rule

> **⚠️ CRITICAL**: PR authors CANNOT review their own PRs on MCode platform. This applies to **Approve** and **Request Changes** operations.

**Permission Validation (MANDATORY before executing approve/request-changes):**

**Step 1: Query PR and User Information**
- Run `code-cli pr view <pr_id> --json` to get PR author and assigned reviewers
- Run `code-cli auth status --json` to get current user's MIS

**Step 2: Compare author with current user**
- If PR author == current user → **IMMEDIATELY STOP**, proceed to Step 3
- If PR author != current user → ✅ proceed with the operation

**Step 3: Build error message (if author is self)**

- **Case A (PR has reviewers)**: Display "Self-Review: Case A" template from `references/templates.md`, filling in reviewer list
- **Case B (PR has NO reviewers)**: Display "Self-Review: Case B" template from `references/templates.md`

---

# Part 1: Create PR

> ⚠️ Apply **Data Freshness Rule**: re-fetch all data from Step 1. No skipping, no reuse.

## User Input (optional)

Users may provide: title, description, target branch, reviewers (MIS IDs), draft flag.
Defaults: target branch = default branch via `code-cli repo branch default`, reviewers = candidates from `code-cli repo reviewers`.

## Create PR Flow

### Step 1. Get branch info and validate

**1.1** Parse `git remote get-url origin` → extract `project`/`repo`. Run `git branch --show-current` → source branch.

**1.2** Run `code-cli repo branch default --json` → default branch.

**1.3** Target branch = user-specified or default branch.

**1.4** Run `code-cli repo branch view <target_branch> --json` to verify it exists. Stop if not found.

**1.5** If source == target: ❌ **STOP**, display "Source Equals Target Branch" template. Otherwise ✅ proceed.

### Step 1.6 Check if an open PR already exists

**1.6.1** Run `code-cli pr list -H <source_branch> -s open --json`

**1.6.2** If any PR has `toRef.branch` == target: existing PR found → Step 1.6.3. Otherwise ✅ proceed to Step 2.

**1.6.3** Display "Existing PR Found" template from `references/templates.md`.

**1.6.4** Run `git status --porcelain`. If empty: **STOP**. If uncommitted changes: display "Uncommitted Changes (Existing PR)" template.

**1.6.5** Handle choice: (1) commit+push to update existing PR, or (2) skip. Then **STOP** — do NOT create new PR.

### Step 2. Check for uncommitted changes

**2.1** Run `git status --porcelain`. If empty → skip to Step 2.4. If changes exist → ask user.

**2.2** Display "Uncommitted Changes (New PR)" template from `references/templates.md`.

**2.3 Handle user's choice**

| Option | Action | Git Commands |
|--------|--------|-------------|
| 1️⃣ 提交这些修改 | Add all changes, commit with a message, and push | `git add .` → `git commit -m "<message>"` → `git push` |
| 2️⃣ 暂存这些修改 | Stash the changes temporarily | `git stash push -m "Stashed before PR creation"` |
| 3️⃣ 丢弃这些修改 | Discard all uncommitted changes (⚠️ with confirmation) | `git checkout -- .` + `git clean -fd` |
| 4️⃣ 继续创建 PR | Proceed without handling uncommitted changes | No git commands needed |

### Step 2.4. Check for diff between source and target branch

**2.4.1 Fetch latest changes from remote**
- Execute `git fetch origin` to ensure local refs are up to date

**2.4.2 Ensure source branch is pushed to remote**
- Execute `git push origin <source_branch>` to ensure the source branch is up to date

**2.4.3 Check if there are commits to merge**
- Execute `git log origin/<target_branch>..origin/<source_branch> --oneline`

**2.4.4 Validation logic:**
- If there are commits: ✅ Diff exists, proceed to Step 3
- If there are no commits: ❌ **STOP IMMEDIATELY**, display "No Commits to Merge" template from `references/templates.md`

### Step 3. Check source branch ONES issue binding requirement

> **⚠️ MANDATORY STEP**: This step contains critical validation that MUST be executed.

**3.1 Query PR settings**
- Run `code-cli repo settings --json` to get repository settings
- Check the `requireIssueAssociated` field
- If `requireIssueAssociated` is `false`, skip Step 3.2 and proceed to Step 4
- **If `requireIssueAssociated` is `true`, you MUST proceed to Step 3.2**

**3.2 Verify branch ONES issue binding (MANDATORY when requireIssueAssociated is true)**

- **MUST** run `code-cli repo branch view <current_branch> --json`
- Check the `issues` array in the response
- **Save the `issues` array for later display**
- **Validation logic:**
    - If `issues` array is **not empty**: ✅ Branch has bound ONES issues, **save the issues info** and proceed to Step 4
    - If `issues` array is **empty or null**: ❌ **IMMEDIATELY STOP**, display "ONES Issue Not Bound" template from `references/templates.md`. **DO NOT proceed to Step 4.**
  
### Step 4. Query reviewer candidates

**4.1 Primary query: Get candidate reviewers for target branch**
- Run `code-cli repo reviewers -t <target_branch> --json`
- Extract reviewer MIS IDs: `candidates.map(c => c.mis)`

**4.2 Fallback: Get default reviewers (if candidates is empty)**
- If `candidates` array is **empty**, run `code-cli repo reviewers --json` as fallback
- Extract reviewer MIS IDs: `response.map(r => r.mis)`

### Step 5. Collect PR metadata

**5.1 Generate PR title**
- If user provides title, use it directly
- Otherwise, auto-generate with priority:
    1. **ONES issue name**: If branch has bound ONES issues, use the first issue's `name`
    2. **Latest commit message**: If no ONES issues
    3. **Branch name**: If commit message is not suitable

**5.2 Generate PR description**
- If user provides description, use it directly
- Otherwise, collect commit messages from the source branch

**5.3 Collect reviewers**
- If user provides reviewers, parse and validate them
- If user does not provide reviewers, use all reviewer candidates as default

**5.4 Determine draft status**
- If user explicitly mentions "draft PR", "草稿 PR", or "draft", use the `-d` flag

### Step 6. Build and execute PR create command

```bash
code-cli pr create -t "<title>" -B <target_branch> [options]
```

**Example command:**
```bash
code-cli pr create -t "feat: add new feature" -B master -r zhangsan -r lisi --json
```

### Step 7. Return results

- Display the PR link and ID
- Show a summary of the created PR (title, source → target branch, reviewers)
- **If branch has associated ONES issues, display the issue information:**
  ```
  | **关联 ONES** | [#<issue_id> - <issue_name>](<issue_link>) (<typeName>) |
  ```

---

# Part 2: Fix PR Comments

> ⚠️ Apply **Data Freshness Rule**: re-fetch all data from Step 1. No skipping, no reuse.

## Constraints

- PR ID required (do not guess). Query open comments before fixing.
- Push only to PR source branch (`fromRef.branch`). Only fix files related to comments.
- Run `code-cli pr resolve <pr_id> <assignment_id>` for each fixed comment — only after fix is pushed.
- Only implement changes **explicitly confirmed by user**. Keep changes minimal and targeted.

## Fix PR Comments Flow

### Step 1. Load PR context

**1.1 Query PR details**
- Run `code-cli pr view <pr_id> --json`
- Extract: `fromRef.branch` (source), `toRef.branch` (target), `url` (PR link)

**1.2 Ensure current branch equals PR source branch**
- Run `git branch --show-current`
- If different from source branch:
    - `git fetch origin`
    - switch to source branch (`git checkout <source_branch>`)
    - if local branch missing: `git checkout -b <source_branch> origin/<source_branch>`

**1.3 Validate PR state**
- If PR state is not `OPEN`/`DRAFT`, stop and tell user PR is not in a fixable state.

### Step 2. Query unresolved comments

**2.1 Query open comments**
- Run `code-cli pr comments <pr_id> -s open --json`

**2.2 Normalize comment list**
For each comment, capture at least:
- `id` (use as `<assignment-id>` for `code-cli pr resolve`)
- `path`
- `line`
- `text`
- `source` (`human` / `ai`)
- `state`

**2.3 Validate open comments exist**
- If list is empty, stop and tell user: no unresolved comments.

**2.4 Determine fix scope**
- If user gave comment IDs, filter to those IDs
- Otherwise fix all open comments

### Step 2.5. Assess fix clarity

For each comment, classify as **CLEAR** or **UNCLEAR**:
- **CLEAR**: Specific fix direction evident (typo, null check, explicit add/delete, concrete bug) → fix directly
- **UNCLEAR**: Ambiguous, requires business context, architecture changes, vague "optimize"/"refactor" → must confirm with user

**Action paths:**
- **All CLEAR** → proceed to Step 3 directly
- **Any UNCLEAR** → display "Fix Comments: Analysis Result" template from `references/templates.md`, ask user to confirm unclear items before fixing

### Step 3. Fix code according to unresolved comments

**3.1 Build fix checklist**
- Group comments by file and location
- Create a checklist of concrete code changes
- CLEAR 评论：按评估时确定的修复方案执行
- UNCLEAR 评论（已确认）：按用户提供的修复方案执行

**3.2 Apply minimal and targeted changes**
- Edit only relevant files
- Keep behavior changes aligned with review intent
- Avoid unrelated changes or speculative modifications

**3.3 Self-check before commit**
- Verify each targeted comment has a corresponding code update
- Cross-reference changes with confirmed fix intent（CLEAR 评论对照评估方案，UNCLEAR 评论对照用户指示）
- If some comments cannot be fixed now, record the reason for final summary

### Step 4. Commit fix version

**4.1 Check local changes**
- Run `git status --porcelain`
- If no changes, stop and explain why no code was changed

**4.2 Stage relevant files**
- Prefer staging only files related to the fix

**4.3 Commit changes**
- Recommended commit message: `fix(pr-<pr_id>): address review comments`
- If user provides commit message, use user message

### Step 5. Push fix version

**5.1 Push to PR source branch**
- Run `git push origin <source_branch>`

**5.2 Handle non-fast-forward**
- If push rejected:
    - `git pull --rebase origin <source_branch>`
    - resolve conflicts
    - `git push origin <source_branch>`

### Step 6. Update unresolved comment status

**6.1 Resolve fixed comments via CLI**
- For each fully fixed comment, run:
  ```bash
  code-cli pr resolve <pr_id> <assignment_id>
  ```

**6.2 Post fix summary comment on PR**
- Run `code-cli pr comment <pr_id> -b "<summary>"`
- Use the "Fix Summary Comment" template from `references/templates.md`

**6.3 Verify remaining open comments**
- Run `code-cli pr comments <pr_id> -s open --json` again
- Return remaining open comment IDs as follow-up list

### Step 7. Return result summary

Return a structured summary including:
- PR ID and link
- Source branch and pushed commit info
- Fixed comment IDs
- Remaining open comment IDs
- Any comments intentionally deferred and reasons

---

# Part 3: Simple PR Operations

> ⚠️ Apply **Data Freshness Rule**: re-fetch branch, repo info, and PR ID before any operation.

## Overview

For simple PR operations that don't require complex workflow orchestration, use `code-cli` help to discover and execute commands.

## Discovering Available Operations

Run `code-cli pr --help` or `code-cli pr <subcommand> --help` to discover commands and flags at runtime. See `references/cli-reference.md` for full syntax.

## General Flow for Simple Operations

When user requests a PR operation not covered in Part 1 or Part 2:

### Step 1. Identify the operation
- Understand what the user wants to do
- Determine if it's a simple operation (doesn't need complex workflow)

### Step 2. Find PR ID (if needed)

**If user provides PR ID**, use it directly.

**If user doesn't provide PR ID**, find it from current branch:
```bash
# MUST re-query current branch first
git branch --show-current

# Then list PRs for the CURRENT branch (not a cached branch name)
code-cli pr list -H $(git branch --show-current) --json

# Or list all open PRs
code-cli pr list -s open --json
```

### Step 3. Check command usage (if unsure)
```bash
code-cli pr <subcommand> --help
```

### Step 4. Execute the command
- Use appropriate flags
- Prefer `--json` flag for programmatic parsing
- Handle errors appropriately
- **For Approve/Request Changes: MUST apply Self-Review Prohibition Rule (see Global Rules) before executing**

### Step 5. Display results
- Parse JSON output if available
- Format and present information clearly to user
- Include relevant links (PR URL, CI dashboard, etc.)

---

# Error Handling

| Error | Solution |
|-------|----------|
| code-cli not found | `npm install -g @ee/code-cli --registry=http://r.npm.sankuai.com` |
| Not authenticated | Auto-run `code-cli auth login`; if fails, prompt manual login |
| Repository/branch not found | Verify project/repo name and branch exist |
| Permission denied | Confirm user has repo write access |
| No diff / No commits | Ensure new commits exist and are pushed |
| PR already exists | Check existing PR or use different branch |
| Push rejected | `git pull --rebase` then push again |
| Author cannot review own PR | Apply Self-Review Prohibition Rule (see Global Rules) |

---

# Examples

## Example 1: Create PR

**User:** `创建PR，评审人是 zhangsan`
**Flow:** Prerequisites → Step 1~7 (full flow)
**Command:** `code-cli pr create -t "fix: 修复仓库权限问题" -B master -r zhangsan --json` (add `-d` for draft)

## Example 2: Fix PR comments

**User:** `修复 PR #123 的待解决评论`
**Flow:**
1. `code-cli pr view 123 --json` → get source branch
2. `code-cli pr comments 123 -s open --json` → get open comments
3. Assess clarity → fix code
4. `git commit -m "fix(pr-123): address review comments"` → `git push origin <source_branch>`
5. `code-cli pr resolve 123 <assignment_id>` for each fixed comment
6. `code-cli pr comment 123 -b "已处理评论 ..."` → re-check open comments

