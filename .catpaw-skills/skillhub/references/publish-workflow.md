# 发布上架完整流程

## 目录

1. [前置准备](#前置准备)
2. [发布流程](#发布流程)
3. [安全扫描（可选）](#安全扫描可选)
4. [可见性管理](#可见性管理)
5. [认证失败处理](#认证失败处理)
6. [完整命令速查](#完整命令速查)

---

## 前置准备

### 1. 安装 mtskills

```bash
npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com
```

验证安装：`mtskills --version`（最低版本 8.3.1）

> ⚠️ 若当前版本低于 8.3.1，请先执行 `npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com` 升级，再执行后续发布操作。

### 2. Skill 目录结构要求

```
my-skill/
├── SKILL.md               # 必须，含 YAML frontmatter
├── references/            # 可选，参考文档
└── scripts/               # 可选，辅助脚本
```

**SKILL.md frontmatter 必填字段**：

```yaml
---
name: my-skill-name        # 必填，全小写，连字符分隔
description: |             # 必填，20-500 字符
  ...触发词和功能描述...
---
```

---

## 发布流程

发布和安全扫描相互独立，安全扫描是**可选**的前置步骤。

### 首次发布新 Skill

```bash
cd /path/to/my-skill

# 发布到广场（**默认 private 私有**）
mtskills publish

# 公开发布（需显式指定）
mtskills publish --visibility public
```

发布成功后返回：
```
✅ 发布成功！
Skill ID: 12345
市场链接：https://friday.sankuai.com/mcp/skill-detail?id=12345
```

### 推送新版本

```bash
cd /path/to/my-skill

# 推送新版本，自动从 SKILL.md 读取 description 同步到平台
mtskills push --intro auto

# 自定义描述
mtskills push --intro "修复了 XXX 问题，新增 YYY 功能"
```

> **版本管理建议**：建议在 SKILL.md frontmatter 中维护 `version` 字段（如 `version: 1.2.0`），每次发布前手动递增。

### 从已绑定 Git 仓库触发发布流水线

平台 Skill 已绑定 Git 仓库时，触发平台从 Git 拉取最新代码；如检测到文件变更，会创建草稿版本并提交发布流水线。

```bash
mtskills publish-from-git <skill-id>
```

示例：

```bash
mtskills publish-from-git 123
mtskills publish-from-git 123 --env test
mtskills publish-from-git 123 --json
```

说明：

- `<skill-id>` 是平台 Skill ID，可从 Skill 详情页 URL 或平台返回信息中获取。
- 该命令不会向 Git 仓库写入内容，只会触发平台读取已绑定仓库并发起 Skill 发布流程。
- 如果仓库没有文件变更，平台不会创建新的发布流水线。
- `--json` 可用于自动化场景，读取 `pipelineId`、`filesChanged`、`commitHash` 等返回字段。

---

## 安全扫描（可选）

发布前可自愿运行安全扫描，检查潜在风险。扫描结果不阻断 `mtskills publish/push`，由开发者自行决定是否处理。

### Stage 1：通用静态扫描

```bash
# 扫描当前目录
python /path/to/skillhub/scripts/security-scan.py

# 扫描指定目录
python /path/to/skillhub/scripts/security-scan.py /path/to/my-skill
```

退出码：`0` 全 PASS / `1` 有 WARN / `2` 有 FAIL

### Stage 2：美团内部专项检查

```bash
python /path/to/skillhub/scripts/security-check.py /path/to/my-skill
```

退出码同上。

### 扫描结果说明

| 结果 | 含义 | 建议处理 |
|---|---|---|
| PASS | 无问题 | 直接发布 |
| WARN | 有风险提示 | 评估后酌情处理 |
| FAIL | 有高风险问题 | 建议修复后再发布 |

规则详情见 `references/security-scan-rules.md`。

### LLM 语义审查维度（Stage 3，可选）

在静态扫描通过后，可进一步执行 LLM 内置语义审查：

1. **意图一致性**：`description`、SKILL.md body、`scripts/` 代码三者行为是否一致
2. **Prompt Injection**：间接注入、DAN 变体、system prompt markers、HTML 注释
3. **数据流分析**：跟踪用户输入 → 网络传输的完整路径
4. **权限最小化**：所请求工具权限是否超出功能需要
5. **隐蔽行为**：条件触发、sleep + 恶意操作、字符串拼接绕过
6. **持久化**：`.bashrc` / crontab / systemd / authorized_keys 修改
7. **供应链风险**：`curl | bash`、不受信任的包源

---

## 可见性管理

| 可见性 | 说明 | 适用场景 |
|---|---|---|
| `public` | 公开，所有用户可见 | 通用 Skill；需显式指定 |
| `private` | 私有，仅自己可见 | **默认**，内测阶段、个人专用 |
---

## 认证失败处理

发布时**推荐使用用户身份**（不带 `--app-auth`）：应用身份发布会导致 `isManager=false`，个人用户将无法后续编辑和删除自己的 Skill。

| 场景 | 处理方式 |
|---|---|
| 本地开发，触发浏览器 SSO | `mtskills publish`（首次运行自动弹出） |
| 任意环境 | 先尝试 `mtskills publish`（内部自动走 MOA → 浏览器 SSO）；若均失败再加 `--ciba <your-mis>`（mis Id 已知直接用，否则询问用户） |
| CI/CD 自动化 | `mtskills publish --app-auth "clientId,secret"` |

Token 缓存于 `~/.mtskills-sso-tokens/`，认证后自动复用。

---

## 完整命令速查

```bash
# 首次发布（**默认 private 私有**）
mtskills publish
mtskills publish --visibility public            # 公开（需显式指定）
mtskills publish                                # 优先（内部自动走 MOA → 浏览器 SSO）
mtskills publish --ciba <your-mis>              # 降级：上述方式均失败时手动指定

# 推送新版本
mtskills push --intro auto                  # 同步 SKILL.md description
mtskills push --intro "自定义描述"

# 从已绑定 Git 仓库触发发布流水线
mtskills publish-from-git <skill-id>        # 触发平台从 Git 读取代码并发起发布流程
mtskills publish-from-git <skill-id> --json # 输出 pipelineId / filesChanged 等字段

# 安全扫描（可选，独立运行）
python scripts/security-scan.py             # Stage 1 通用扫描（当前目录）
python scripts/security-scan.py /path/to/skill   # 指定目录
python scripts/security-check.py /path/to/skill  # Stage 2 美团内部检查

# 查看已管理的 Skill
mtskills list
```

---

## description 质量检查清单

发布前请对照检查：

- [ ] **长度**：20-500 字符（过短则触发词不足，过长则占用 context window）
- [ ] **触发词覆盖**：包含用户最可能说的关键词（中英文均考虑）
- [ ] **功能说明**：清晰描述 Skill 能做什么（"覆盖 (1)… (2)… (3)…" 格式推荐）
- [ ] **使用场景**：包含"当用户提到…时触发"句式
- [ ] **无歧义**：不与同类 Skill 混淆
