---
name: skillhub
description: SkillHub（Friday 技能广场 / skill 广场）Skill 全功能管理工具，支持搜索/发现/安装/更新/卸载 Skill、查看评论、发表评论、回复评论，以及发布/推送新版本到广场。当用户提到找 skill、搜索 skill、安装 skill、查看 skill、skill 市场、拉取更新、skill 评论、发评论、回复评论，或需要发布/上架/推送 skill 到广场，或发送了 SkillHub / Friday / skills.sankuai.com 详情页 URL 时使用。

metadata:
  skillhub.creator: "dulong03"
  skillhub.updater: "liufeiyu"
  skillhub.version: "V25"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "14318"
  skillhub.high_sensitive: "false"
---

# SkillHub — Skill 全功能管理工具

底层统一使用 `mtskills`（`@mtfe/mtskills`）完成所有平台交互。

**前置依赖**：`npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com`

> ⚠️ **每次执行 mtskills 命令前**，先执行 `npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com` 更新到最新版本。

---

## 意图路由

| 用户意图 | 操作 | 参考文档 |
|---|---|---|
| 搜索 / 发现 Skill | `mtskills search <关键词>` 或 `--tag <标签>` 或 `--verified` | `references/search-and-discover.md` |
| 交互式浏览市场 | `mtskills i mt [--keyword <词>] [--tag <标签>] [--verified]` | `references/search-and-discover.md` |
| 查看 Skill 详情 | `mtskills read <skill名称>` | `references/search-and-discover.md` |
| 查看 Skill 评论 | `mtskills comment list <skill-id>` | 见下方「Skill 评论管理」 |
| 发表顶级评论 | `mtskills comment create <skill-id> --content <text>` | 见下方「Skill 评论管理」 |
| 回复评论 | `mtskills comment reply <skill-id> --to-comment-id <id> --content <text>` | 见下方「Skill 评论管理」 |
| 通过 URL 链接安装 | 解析 URL 中的 skill id → `mtskills i mt --id <id> -g`（CatClaw/OpenClaw 环境见下方「环境感知安装」） | 见下方「URL 安装」 |
| 安装 Skill | `mtskills i <skill名称>[@<版本>] -g`（项目安装省略 `-g`；CatClaw/OpenClaw 环境见下方「环境感知安装」） | `references/install-and-manage.md` |
| 批量安装 | `mtskills i skill-a,skill-b,skill-c -g` | `references/install-and-manage.md` |
| 列出已安装 | `mtskills list` | `references/install-and-manage.md` |
| 卸载 Skill | `mtskills remove <skill名称>` | `references/install-and-manage.md` |
| 同步到 AGENTS.md | `mtskills sync [-y] [-o <输出文件>]` | `references/install-and-manage.md` |
| 拉取更新（单个） | `mtskills pull <skill名称>` | `references/install-and-manage.md` |
| 拉取更新（全部） | `mtskills pull --all` | `references/install-and-manage.md` |
| 配置定时自动更新 | macOS/Linux: `crontab -e`，Windows: `schtasks` | `references/install-and-manage.md` |
| 安装前安全评估 | 读取并按 `references/pre-install-vetting.md` 规则审查 Skill 目录 | `references/pre-install-vetting.md` |
| 首次发布新 Skill | ⚠️ **执行前须向用户确认**，确认后执行 `mtskills publish`（默认 private；需公开显式指定 `--visibility public`） | `references/publish-workflow.md` |
| 推送新版本 | ⚠️ **执行前须向用户确认**，确认后执行 `mtskills push --intro auto` | `references/publish-workflow.md` |
| 从已绑定 Git 仓库触发发布流水线 | ⚠️ **执行前须向用户确认**，确认后执行 `mtskills publish-from-git <skill-id>` | `references/publish-workflow.md` |
| 发布前安全扫描（可选） | `python scripts/security-scan.py [<skill目录>]` | `references/security-scan-rules.md` |
| 美团内部专项检查（可选） | `python scripts/security-check.py <skill目录>` | `references/security-scan-rules.md` |

---

## Skill 评论管理

### 查看评论

```bash
mtskills comment list <skill-id> [--env dev|test|prod] [--page <n>] [--page-size <n>] [--order-by time|hot] [--json]
```

### 发表评论（顶级评论）

```bash
mtskills comment create <skill-id> --content "<评论内容>" [--env dev|test|prod] [--json]
```

### 回复评论（二级评论）

```bash
mtskills comment reply <skill-id> --to-comment-id <comment-id> --content "<回复内容>" [--env dev|test|prod] [--json]
```

- to-comment-id 传通过mtskills comment list获取的评论id

### 评论相关鉴权参数（按需）

可按场景附加：`--ciba <mis>`、`--token <ssoid>`。

### 常见组合流程

1. 先看评论：`mtskills comment list <skill-id>`
2. 发评论：`mtskills comment create <skill-id> --content "..."`
3. 回复评论：`mtskills comment reply <skill-id> --to-comment-id <id> --content "..."`

---

## URL 安装说明

| URL 格式 | skill id 提取规则 |
|---|---|
| `https://friday.sankuai.com/skills/skill-detail?...&id=<id>` | 取 query 参数 `id` 的值 |
| `https://skills.sankuai.com/skill-detail?...&id=<id>` | 取 query 参数 `id` 的值 |
| `https://skillhub.sankuai.com/skills/<id>` | 取路径最后一段 |

解析到 id 后执行：`mtskills i mt --id <id> -g`

> **CatClaw/OpenClaw 环境**：解析到 id 后执行 `mtskills i mt --id <id> --target-dir ~/.openclaw/skills`（见下方「环境感知安装」）

---

## 环境感知安装

当运行环境为 **CatClaw** 或 **OpenClaw** 时，Skill 需安装到 OpenClaw 的专用目录，否则 Agent 无法加载：

| 环境 | 安装命令 | 说明 |
|---|---|---|
| CatPaw（默认） | `mtskills i <name> -g` | 安装到 `~/.claude/skills/` 或 `~/.agent/skills/` |
| **CatClaw / OpenClaw** | `mtskills i <name> --target-dir ~/.openclaw/skills` | 安装到 OpenClaw Skill 目录 |

### 如何判断当前环境

- 若用户明确说明在 CatClaw / OpenClaw 中使用，或当前工作目录/环境变量中有 `openclaw` 相关特征 → 使用 OpenClaw 安装命令
- 其余情况默认使用 CatPaw（`-g`）安装

### OpenClaw 环境安装示例

```bash
# 单个安装
mtskills i xlsx --target-dir ~/.openclaw/skills

# 指定版本
mtskills i xlsx@1.0.0 --target-dir ~/.openclaw/skills

# 通过 id 安装（URL 解析场景）
mtskills i mt --id <id> --target-dir ~/.openclaw/skills

```

> ⚠️ **注意**：`--target-dir` 与 `-g` 互斥，不可同时使用。安装后重启 CatClaw/OpenClaw 使 Skill 生效。

---

## 认证

详见各 references 文件。核心原则：**发布时用用户身份**（不带 `--app-auth`），否则 `isManager=false`，无法后续编辑自己的 Skill。

### 认证说明

**始终优先尝试不带任何认证参数直接运行**。mtskills 内部认证顺序为：MOA 无感登录 → 浏览器 SSO。

只有在无参数方式（MOA + SSO）均失败时，降级到其他方式：

- **CIBA 降级**：加 `--ciba <your-mis>`；mis Id 已知或本次会话中用户已提供则直接使用，否则询问用户；用户提供后**记住并在后续操作中复用**，**严禁猜测或伪造**
- **CI/CD**：使用 `--app-auth "clientId,secret"`
