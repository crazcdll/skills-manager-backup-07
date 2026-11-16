# code 命令详细规则

## code clone — 克隆作品代码到本地

将作品关联的 Git 仓库代码克隆到本地目录。

```bash
nocode code clone <chatId>
nocode code clone <chatId> --dir ~/my-project
nocode code clone <chatId> --json
```

**内部流程：**

1. 检查 git 是否可用（`git --version`）
2. 获取作品详情 → 拿到 `repo.sshUrl`、`repo.branch`
3. 确定本地目标路径：`--dir` 指定 或 默认 `~/.nocode/workspaces/nocode-<chatId>/`
4. 智能决策：
   - 本地已有 `.git` → 增量更新（`git fetch origin` + `git reset --hard origin/<branch>`）
   - 本地无 `.git` → 全量 `git clone`

**参数：**

| 参数 | 说明 |
|------|------|
| `--dir <path>` | 指定克隆目录（默认 `~/.nocode/workspaces/nocode-<chatId>/`） |
| `--json` | JSON 格式输出（包含 localPath、branch、commitId 等） |

**输出示例：**

```
✨ 代码已准备就绪

📁 本地路径
   /Users/xxx/.nocode/workspaces/nocode-abc123/

📦 版本信息
   分支:   master
   Commit: a1b2c3d4e5f6
```

### 常见错误

| 错误信息 | 处理方式 |
|---------|----------|
| `该作品没有关联的 Git 仓库，无法克隆` | 作品尚未初始化代码，需先通过 `nocode create`/`nocode send` 生成代码 |
| `Permission denied (publickey)` | SSH key 未配置，提示用户配置 Git SSH key |
| `git: command not found` | 提示用户先安装 Git |

### ⛔ 本地开发必须遵循 Spec-Driven 工作流

使用 `code clone` 克隆代码到本地后，**必须严格按照 [workflow-local-dev.md](../workflows/workflow-local-dev.md) 的 Spec-Driven 流程执行**（Phase 0–5：INITIALIZE → ANALYZE → DESIGN → IMPLEMENT → VALIDATE → HANDOFF）。不要自行编排流程。

### 注意事项

- **一个 chatId 对应一个仓库**，仓库有多个分支但 API 返回的是固定的默认分支
- **⛔ 必须在 `repo.branch` 分支上修改代码**：NoCode 只认 `repo.branch` 返回的分支，提交到其他分支的代码无法通过 `code pull` 同步回 NoCode。严禁切换分支或创建新分支开发
- **重复执行是安全的**：已有 `.git` 时会自动走增量更新而非重新 clone
- **增量更新会丢弃本地未提交的修改**（`reset --hard`），确保本地修改已 commit + push 后再执行

---

## code pull — 从远程仓库拉取代码到 Sandbox

将远程 Git 仓库的最新代码同步到 Sandbox（即主站"同步回NoCode"功能）。

```bash
nocode code pull <chatId>
nocode code pull <chatId> --force
nocode code pull <chatId> --json
```

**内部流程：**

1. 获取对话详情 → 拿到 ideId
2. 检查容器状态（自动冷启动）
3. `checkNeedSync` — 检查仓库是否有新的提交（无更新则直接结束）
4. `checkNeedSyncToRepo` — 检查 Sandbox 是否有未推送的本地变更（有则警告）
5. `syncFromRepo` — 执行同步（Repo → Sandbox），生成新版本

## ⚠️ 变更保护机制

如果 Sandbox 中有未推送到仓库的本地变更（比如通过 `nocode send` 让 Agent 修改了代码但还没 push 到仓库），`code pull` 会拒绝执行并输出警告：

```
⚠️  警告：拉取会覆盖以下本地变更：
   × src/App.jsx
   × src/index.css

如确认要覆盖，请使用 --force 参数：
  nocode code pull <chatId> --force
```

**处理流程：**

1. **先不加 `--force` 执行** `nocode code pull <chatId>`
2. 如果输出包含"未推送的本地变更"警告：
    - **必须将警告内容展示给用户**，告知哪些文件会被覆盖
    - **询问用户是否确认覆盖**
    - 用户确认后，再执行 `nocode code pull <chatId> --force`
3. 如果输出"代码已是最新，无需拉取"，直接告知用户即可

**⛔ 禁止未经用户确认直接使用 `--force`**

## ⚠️ 使用场景

1. **用户在本地（Git 仓库）修改了代码后**，需要将修改同步回 NoCode Sandbox
2. **用户要求"同步代码"、"拉取最新代码"、"更新 Sandbox"** 时使用
3. **开发者模式工作流**：本地修改 → git push → `code pull` 同步回 Sandbox → 截图确认

## ⚠️ 常见错误

| 错误信息 | 处理方式 |
|---------|---------|
| `代码已是最新，无需拉取` | 告知用户无需操作 |
| Sandbox 有未推送的本地变更（非 `--force`） | 展示变更文件列表，询问用户是否确认覆盖 |
| `容器启动等待超时` | 检查网络或稍后重试 |

