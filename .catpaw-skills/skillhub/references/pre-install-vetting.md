# 安装前安全评估

## 何时需要评估

| 情形 | 建议 |
|---|---|
| Skill 带有 `verified: true` 标记 | 可直接安装，平台已审核 |
| 社区 Skill（无 verified 标记） | **建议先评估** |
| 来源不明的 Skill 文件 | **强烈建议评估** |
| Skill 请求高危工具权限（Bash/exec） | **强烈建议评估** |

---

## 评估方式

对已下载到本地的 Skill 目录，**逐一读取所有文件**（SKILL.md、scripts/ 下的代码、references/ 下的文档），按照下方规则清单逐项判断，最终给出风险等级和建议。

---

## 审查规则清单

以下规则来自 skill-vetter，原样引用：

### Step 1: Source Check

```
Questions to answer:
- [ ] Where did this skill come from?
- [ ] Is the author known/reputable?
- [ ] How many downloads/stars does it have?
- [ ] When was it last updated?
- [ ] Are there reviews from other agents?
```

### Step 2: Code Review (MANDATORY)

Read ALL files in the skill. Check for these **RED FLAGS**:

```
🚨 REJECT IMMEDIATELY IF YOU SEE:
─────────────────────────────────────────
• curl/wget to unknown URLs
• Sends data to external servers
• Requests credentials/tokens/API keys
• Reads ~/.ssh, ~/.aws, ~/.config without clear reason
• Accesses MEMORY.md, USER.md, SOUL.md, IDENTITY.md
• Uses base64 decode on anything
• Uses eval() or exec() with external input
• Modifies system files outside workspace
• Installs packages without listing them
• Network calls to IPs instead of domains
• Obfuscated code (compressed, encoded, minified)
• Requests elevated/sudo permissions
• Accesses browser cookies/sessions
• Touches credential files
─────────────────────────────────────────
```

### Step 3: Permission Scope

```
Evaluate:
- [ ] What files does it need to read?
- [ ] What files does it need to write?
- [ ] What commands does it run?
- [ ] Does it need network access? To where?
- [ ] Is the scope minimal for its stated purpose?
```

### Step 4: Risk Classification

| Risk Level | Examples | Action |
|------------|----------|--------|
| 🟢 LOW | Notes, weather, formatting | Basic review, install OK |
| 🟡 MEDIUM | File ops, browser, APIs | Full code review required |
| 🔴 HIGH | Credentials, trading, system | Human approval required |
| ⛔ EXTREME | Security configs, root access | Do NOT install |

---

## 输出报告格式

评估完成后，按以下格式输出结果：

```
SKILL VETTING REPORT
═══════════════════════════════════════
Skill: [name]
Source: [SkillHub / GitHub / other]
Author: [username]
Version: [version]
───────────────────────────────────────
METRICS:
• Downloads/Stars: [count]
• Last Updated: [date]
• Files Reviewed: [count]
───────────────────────────────────────
RED FLAGS: [None / List them]

PERMISSIONS NEEDED:
• Files: [list or "None"]
• Network: [list or "None"]
• Commands: [list or "None"]
───────────────────────────────────────
RISK LEVEL: [🟢 LOW / 🟡 MEDIUM / 🔴 HIGH / ⛔ EXTREME]

VERDICT: [✅ SAFE TO INSTALL / ⚠️ INSTALL WITH CAUTION / ❌ DO NOT INSTALL]

NOTES: [Any observations]
═══════════════════════════════════════
```

---

## Trust Hierarchy

1. **verified 认证 Skill** → 平台已审核，低审查力度（仍建议浏览）
2. **高下载量社区 Skill** → 中等审查力度
3. **已知作者** → 中等审查力度
4. **新建/来源不明** → 最高审查力度
5. **请求凭据权限** → 始终需人工确认

---

## 手动审查建议

当风险等级为 MEDIUM 或以上时，重点检查：

1. **scripts/ 目录**：查看所有 Python/Shell 脚本，确认无隐藏行为
2. **SKILL.md 正文**：确认描述与实际代码行为一致（意图一致性）
3. **网络请求目标**：确认外部请求的目标域名合法，无敏感数据上传
4. **工具权限**：frontmatter 中 `allowed-tools` 是否包含不必要的高危权限（Bash/Write/exec）
5. **条件触发**：是否存在只在特定条件下才执行的隐蔽操作
