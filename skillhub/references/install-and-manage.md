# 安装与本地管理

## 目录

1. [安装 Skill](#安装-skill)
2. [列出已安装 Skill](#列出已安装-skill)
3. [拉取更新 Skill（广场→本地）](#拉取更新-skill)
4. [卸载 Skill](#卸载-skill)
5. [同步到 AGENTS.md](#同步到-agentsmd)
6. [定时自动拉取更新（广场→本地）](#定时自动拉取更新)

---

## 安装 Skill

### 安装范围

| 安装模式 | 命令 | 安装位置 | 适用场景 |
|---|---|---|---|
| **全局安装**（**默认**，推荐） | `mtskills i <name> -g` | `~/.agent/skills/` 或 `~/.claude/skills/` | CatPaw 环境，所有项目均可使用 |
| **项目安装** | `mtskills i <name>`（省略 `-g`） | `.claude/skills/`（当前目录） | 仅当前项目使用 |
| **通用安装** | `mtskills i <name> -u` | `.agent/skills/`（当前目录） | 用于通用 AGENTS.md |
| **指定目录** | `mtskills i <name> --target-dir <path>` | 自定义路径 | 预览/测试用 |
| **CatClaw / OpenClaw** | `mtskills i <name> --target-dir ~/.openclaw/skills` | OpenClaw Skill 目录 | CatClaw/OpenClaw 环境专用 |

> **环境判断**：若用户明确说明在 CatClaw / OpenClaw 中使用，或环境中有 `openclaw` 相关特征，使用 OpenClaw 安装模式；其余情况默认使用全局安装（`-g`）。

```bash
# 全局安装（默认，CatPaw 环境推荐）
mtskills i xlsx -g
mtskills i pdf -g

# 安装指定版本（全局）
mtskills i xlsx@1.0.0 -g

# 批量安装（逗号分隔，全局）
mtskills i skill-a,skill-b,skill-c -g

# 安装到当前项目（仅项目专用）
mtskills i xlsx

# 安装到 .agent/skills/（用于通用 AGENTS.md）
mtskills i xlsx -u

# 安装到指定目录（用于预览）
mtskills i xlsx --target-dir /tmp/preview/

# CatClaw / OpenClaw 环境安装
mtskills i xlsx --target-dir ~/.openclaw/skills
mtskills i xlsx@1.0.0 --target-dir ~/.openclaw/skills
mtskills i skill-a,skill-b --target-dir ~/.openclaw/skills
```

### 认证方式

| 场景 | 命令 |
|---|---|
| CatPaw（本地开发默认） | `mtskills i xlsx -g` |
| 任意环境（无头/有头） | 先尝试不带认证参数运行（内部自动走 MOA → 浏览器 SSO）；若均失败再加 `--ciba <your-mis>`（mis Id 已知直接用，否则询问用户） |
| CI/CD | `mtskills i xlsx -g --app-auth "clientId,secret"` |

---

## 列出已安装 Skill

```bash
# 列出所有已安装的 Skill（全局 + 项目）
mtskills list

# 输出示例：
# Global skills (~/.agent/skills/ 或 ~/.claude/skills/):
#   xlsx          v2.1.0   [verified]
#   pdf           v1.3.2   [verified]
#   meituan-km    v1.0.5
#
# Project skills (.claude/skills/):
#   my-custom     v0.1.0
```

---

## 拉取更新 Skill

拉取更新方向：**广场 → 本地**（`mtskills pull`）

### 手动拉取更新

```bash
# 拉取更新单个 Skill
mtskills pull xlsx

# 拉取更新全部已安装 Skill
mtskills pull --all
```

拉取更新完成后，mtskills 会显示每个 Skill 的版本变化：
```
✅ xlsx: v2.0.0 → v2.1.0
✅ pdf:  已是最新版 (v1.3.2)
```

### 回滚

如果更新后出现问题，`mtskills` 暂不支持内置回滚命令。建议在更新前通过 git 或手动备份 Skill 目录：

```bash
# 更新前备份（可选）
cp -r ~/.agent/skills/xlsx ~/.agent/skills/xlsx.bak

# 如需回滚
rm -rf ~/.agent/skills/xlsx
mv ~/.agent/skills/xlsx.bak ~/.agent/skills/xlsx
```

---

## 卸载 Skill

```bash
# 卸载 Skill
mtskills remove xlsx

# 确认已卸载
mtskills list
```

---

## 同步到 AGENTS.md

`AGENTS.md` 是项目级别的 Agent 配置文件，`mtskills sync` 会将已安装的 Skill 列表同步写入其中：

```bash
# 交互式确认后同步
mtskills sync

# 自动确认，无需手动确认
mtskills sync -y

# 指定输出文件（默认 AGENTS.md）
mtskills sync -y -o AGENTS.md
```

**何时使用**：团队协作项目中，将 `AGENTS.md` 提交到 git，团队成员可以看到项目需要哪些 Skill，并统一安装。

---

## 定时自动拉取更新

使用系统原生调度机制（macOS/Linux 用 crontab，Windows 用 Task Scheduler）定期执行 `mtskills pull --all`，保持本地 Skill 与广场同步。

**建议**：选择凌晨 02:00–05:59 间的随机时间点（避免用户集中触发），默认每 24 小时执行一次。cron tag 使用 `# skillhub auto-update` 便于后续识别和删除。
