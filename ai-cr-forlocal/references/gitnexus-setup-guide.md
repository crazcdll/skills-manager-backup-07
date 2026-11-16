# GitNexus 安装指南

> 本文档仅涵盖 GitNexus CLI 的安装说明。建图逻辑（同步全量建图）的权威描述在 `SKILL.md` Step 0B 中。

## 安装步骤

### 1. 安装 Node.js 22

```bash
# 方式一：nvm（推荐）
nvm install 22
nvm use 22

# 方式二：Homebrew（macOS）
brew install node@22
```

### 2. 安装 GitNexus CLI

```bash
npm install -g gitnexus@1.5.3
```

### 3. 验证安装

```bash
gitnexus --version
```

### 4. 配置 Embedding 环境变量（自动，无需手动操作）

env-check.sh 和 SKILL.md Step 0B 会自动配置以下环境变量：

```bash
# 优先从 ~/.openclaw/sqt-env 加载（如果文件存在）
# 否则使用默认值：
export GITNEXUS_EMBEDDING_URL=https://mmc.sankuai.com/openclaw/v1/native
export GITNEXUS_EMBEDDING_API_KEY=catpaw
export GITNEXUS_EMBEDDING_MODEL=text-embedding-3-large
export GITNEXUS_EMBEDDING_DIMS=3072
```

如需自定义 Embedding 配置，创建 `~/.openclaw/sqt-env` 文件并写入对应的 export 语句即可。

## 安装后无需额外操作

安装 GitNexus 后，重新运行 CR 即可自动启用：
1. `env-check.sh` 检测到 `gitnexus` 命令 → 设置 `GITNEXUS_INSTALLED=true`
2. `SKILL.md` Step 0B 执行同步全量建图 → 设置 `GITNEXUS_AVAILABLE=true/false`
3. Step 2B 根据 `GITNEXUS_AVAILABLE` 选择 GitNexus 主路径或 grep fallback

## 为什么每次 CR 都重建图谱？

forlocal 审查的是本地分支的当前代码状态，分支代码随时在变。只有每次全量重建（`gitnexus analyze --force`），图谱才能 100% 反映当前分支。建图耗时约 30~60s，本地环境完全可接受。

## 建图失败不阻塞

`$GITNEXUS_AVAILABLE=false` 时所有 GitNexus 步骤跳过，走原版 grep 逻辑，零退化。
