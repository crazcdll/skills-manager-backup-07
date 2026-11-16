# CLI Command Reference

> Complete reference for `code-cli` commands used in PR workflows.
> Read this file when you need exact command syntax, flags, or JSON output formats.

## Table of Contents

1. [Repository Commands](#repository-commands)
   - [repo branch default](#code-cli-repo-branch-default)
   - [repo branch view](#code-cli-repo-branch-view)
   - [repo settings](#code-cli-repo-settings)
   - [repo reviewers](#code-cli-repo-reviewers)
2. [PR Commands](#pr-commands)
   - [pr create](#code-cli-pr-create)
   - [pr view](#code-cli-pr-view)
   - [pr list](#code-cli-pr-list)
   - [pr comments](#code-cli-pr-comments)
   - [pr resolve](#code-cli-pr-resolve)
   - [pr comment](#code-cli-pr-comment)
   - [pr checks](#code-cli-pr-checks)
   - [pr add-reviewer](#code-cli-pr-add-reviewer)
   - [pr merge / close / approve](#other-pr-commands)

---

## Repository Commands

### `code-cli repo branch default`
Get the default branch of the repository.
```bash
code-cli repo branch default --json
```
JSON output example:
```json
{
  "name": "master",
  "commitId": "abc123",
  "issues": []
}
```

### `code-cli repo branch view <branch>`
Query branch information including associated ONES issues.
```bash
code-cli repo branch view feat/my-branch --json
```
JSON output example:
```json
{
  "name": "feature/PRJ-BAC883D7-93553023/test",
  "commitId": "c4770c3371090487a61f63c29e74d468d0468d62",
  "issues": [
    {
      "id": "93553023",
      "name": "test",
      "typeName": "任务",
      "state": "处理中",
      "link": "https://mep.sankuai.com/app/ones/space/1031002/workItem/devtask/detail/93553023"
    }
  ]
}
```

### `code-cli repo settings`
Query repository PR settings.
```bash
code-cli repo settings --json
```
JSON output example:
```json
{
  "approveSize": 1,
  "certificatedApproveSize": 0,
  "buildStatusSize": 0,
  "mergeMethod": "MERGE_COMMIT",
  "workflowCheckEnabled": false,
  "resetApprovalsOnRescope": false,
  "requireIssueAssociated": false,
  "pullRequestAutoMerge": false,
  "enableMergeQueue": false
}
```

### `code-cli repo reviewers`
Query candidate reviewers for a target branch.
```bash
# Get default reviewers
code-cli repo reviewers --json

# Get candidate reviewers for a specific target branch
code-cli repo reviewers -t master --json
```
JSON output example:
```json
{
  "candidates": [
    {
      "mis": "xiang.fei",
      "name": "费翔",
      "email": "xiang.fei@meituan.com",
      "active": true
    }
  ],
  "required": []
}
```

---

## PR Commands

### `code-cli pr create`
Create a pull request.
```bash
code-cli pr create -t "<title>" -B <base-branch> [options]
```

| Flag | Required | Description |
|------|----------|-------------|
| `-t, --title <title>` | ✅ | Title for the pull request |
| `-B, --base <branch>` | ✅ | Target branch to merge into |
| `-b, --body <body>` | ❌ | Body/description for the pull request |
| `-H, --head <branch>` | ❌ | Source branch (default: current branch) |
| `-d, --draft` | ❌ | Mark as draft PR |
| `-r, --reviewer <login>` | ❌ | Reviewer MIS ID (can be repeated) |
| `--no-default-reviewers` | ❌ | Skip adding default reviewers |
| `--json` | ❌ | Output as JSON |
| `-R, --repo <PROJECT/REPO>` | ❌ | Specify repository |

### `code-cli pr view`
Query PR details.
```bash
code-cli pr view <pr_id> --json
```

### `code-cli pr list`
List pull requests for the current repository or branch.
```bash
# List PRs for specific branch
code-cli pr list -H <branch> --json

# List PRs with specific state
code-cli pr list -s open --json
```

### `code-cli pr comments`
Query PR comments.
```bash
code-cli pr comments <pr_id> -s open --json
```

### `code-cli pr resolve`
Mark an unresolved assignment comment as resolved.
```bash
code-cli pr resolve <pr_id> <assignment_id>
```

### `code-cli pr comment`
Post a comment on a PR.
```bash
code-cli pr comment <pr_id> -b "<text>"
```

### `code-cli pr checks`
Query PR check status including CI builds, approvals, and other checks.
```bash
code-cli pr checks <pr_id> --json
```
JSON output example:
```json
{
  "checks": [
    {
      "name": "CI Build",
      "status": "SUCCESS",
      "conclusion": "PASSED",
      "url": "https://..."
    }
  ],
  "approvals": {
    "required": 1,
    "approved": 1,
    "reviewers": [
      {
        "mis": "zhangsan",
        "status": "APPROVED"
      }
    ]
  }
}
```

### `code-cli pr add-reviewer`
Add one or more reviewers to a pull request.
```bash
code-cli pr add-reviewer <pr_id> -r <reviewer_mis> [--json]
# Multiple reviewers: repeat -r flag
code-cli pr add-reviewer <pr_id> -r reviewer1 -r reviewer2 --json
```

### Other PR Commands
For merge, close, approve, and other operations, use `code-cli pr <subcommand> --help` to see usage:
```bash
code-cli pr merge <pr_id> --json
code-cli pr close <pr_id> --json
code-cli pr approve <pr_id> --json
code-cli pr request-changes <pr_id> --json

