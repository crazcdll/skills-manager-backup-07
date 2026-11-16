---
name: aicr-webhook-setup
description: "代码仓库 AI-CR WebHook 自动接入工具。自动完成权限检查、管理员申请、WebHook 配置全流程。通过 MOA SSO 无感换票自动获取认证，无需手动提供 Cookie。触发词：接入 AI-CR、配置 webhook、仓库接入自动CR、设置代码审查 hook、aicr webhook、接入自动代码审查。"

metadata:
  skillhub.creator: "zengjiantao"
  skillhub.updater: "zengjiantao"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "98916"
  skillhub.high_sensitive: "false"
---

# AI-CR WebHook 自动接入工具

为美团代码仓库（dev.sankuai.com）自动配置 AI-CR WebHook，实现 PR 提交时自动触发代码审查。

## 前置依赖

- Python 3.6+（标准库，无需额外安装）
- `mtsso-moa-local-exchange`（MOA SSO 换票，通过 npx 调用，自动获取认证）

## 脚本定位

```bash
SKILL_DIR=$(dirname "$(mtskills path aicr-webhook-setup 2>/dev/null)")
SCRIPT="${SKILL_DIR}/scripts/setup_webhook.py"
```

## 子命令与参数

脚本提供 4 个子命令，所有子命令共享以下公共参数：

| 参数 | 缩写 | 说明 |
|------|------|------|
| `--project` | `-p` | 项目名（org 名称） |
| `--repo` | `-r` | 仓库名 |
| `--url` | `-u` | 仓库 URL，自动解析 project/repo |
| `--token` | `-t` | 手动指定 SSO token（可选，默认 MOA 换票） |

> `--project` + `--repo` 和 `--url` 二选一。

| 子命令 | 说明 | 额外参数 |
|--------|------|----------|
| `check-admin` | 查询管理员列表，检查 `1024_aicragent` 是否已是管理员 | 无 |
| `apply-admin` | 向指定审批人申请 REPO_ADMIN 永久权限 | `--approver`（必须） |
| `check-webhook` | 查询现有 webhook，检查 AI-CR hook 是否已存在 | 无 |
| `create-webhook` | 创建 AI-CR WebHook | 无 |

所有子命令输出 JSON 格式，便于解析。

## 执行流程（分步调用，严格按顺序）

用户提供仓库信息（`--project`/`--repo` 或 `--url`）后，按以下步骤执行：

### Step 1：检查管理员权限

```bash
python3 "$SCRIPT" check-admin --project <project> --repo <repo>
```

输出示例：
```json
{"project": "fun", "repo": "myrepo", "is_admin": false, "admins": ["zhangsan", "lisi"]}
```

解析 JSON 结果：
- `is_admin == true` → 跳过 Step 2，直接进入 Step 3
- `is_admin == false` → 进入 Step 2

### Step 2：申请管理员权限（仅 is_admin == false 时）

**审批人选择规则**：
1. 优先选择发起者本人（当前用户的 MIS）——如果发起者在 `admins` 列表中
2. 如果发起者不在 `admins` 列表中，选择列表中第一个管理员

```bash
python3 "$SCRIPT" apply-admin --project <project> --repo <repo> --approver <选定的审批人>
```

输出示例：
```json
{"success": true, "project": "fun", "repo": "myrepo", "approver": "zhangsan", "permission": "REPO_ADMIN", "duration": "permanent"}
```

**申请成功后，执行以下两个操作**：

**1. 通知用户：**

> 已向 `{approver}` 发起了仓库 `{project}/{repo}` 的 REPO_ADMIN 权限申请。审批完成后告诉我，或者我会每 10 分钟自动检查一次审批状态。

**2. 创建定时轮询任务：**

用 cron 工具创建一个每 10 分钟执行的 isolated agentTurn 任务，让它自动检查权限并在审批通过后完成 webhook 配置。

定时任务 payload.message 内容模板：

```
定时检查任务：仓库 {project}/{repo} 的 AI-CR WebHook 接入。

请执行以下操作：
1. 定位脚本：SKILL_DIR=$(dirname "$(mtskills path aicr-webhook-setup 2>/dev/null)") && SCRIPT="${SKILL_DIR}/scripts/setup_webhook.py"
2. 执行: python3 "$SCRIPT" check-admin --project {project} --repo {repo}
3. 解析 JSON 结果：
   - is_admin == true → 继续执行 check-webhook 和 create-webhook，完成后向用户发送完成通知，并删除本定时任务
   - is_admin == false → 不做任何操作，等待下次轮询
```

cron 任务参数：
- schedule: `{"kind": "every", "everyMs": 600000}`（10 分钟）
- sessionTarget: `"isolated"`
- payload.kind: `"agentTurn"`
- delivery.mode: `"announce"`（完成后通知用户）
- 记录返回的 jobId，后续需要用它删除任务

**用户主动告知审批完成时的处理：**

如果用户在对话中主动告知审批已通过，则：
1. 立即执行 Step 3（check-webhook）和 Step 4（create-webhook）
2. 删除之前创建的定时轮询任务（通过记录的 jobId）
3. 告知用户配置完成

### Step 3：检查 WebHook

```bash
python3 "$SCRIPT" check-webhook --project <project> --repo <repo>
```

输出示例：
```json
{"project": "fun", "repo": "myrepo", "webhook_exists": false, "webhook_count": 2, "target_url": "https://spt.sankuai.com/api/pr-cr-hook"}
```

解析 JSON 结果：
- `webhook_exists == true` → 告知用户 webhook 已存在，无需重复配置，流程结束
- `webhook_exists == false` → 进入 Step 4

### Step 4：创建 WebHook

```bash
python3 "$SCRIPT" create-webhook --project <project> --repo <repo>
```

输出示例：
```json
{"success": true, "project": "fun", "repo": "myrepo", "webhook_url": "https://spt.sankuai.com/api/pr-cr-hook", "events": ["pull_request_events", "draft_pull_request_events"]}
```

成功后告知用户：

> ✅ 仓库 `{project}/{repo}` 的 AI-CR WebHook 配置完成！后续 PR 将自动触发 AI 代码审查。

## 约束

- 🔒 不在终端或对话中输出 token / cookie 明文
- 🔒 SSO token 缓存 30 分钟，避免重复换票
- ⚠️ Step 2 申请权限后必须等用户确认审批通过，不可自动跳过
- ⚠️ 认证优先级：`--token` 参数 > MOA SSO 换票 > `~/.openclaw/mcode_cookie.txt`
