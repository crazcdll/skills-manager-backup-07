# CHANGELOG — crash-alarm-check

## v2.0.0 — 2026-03-25

### 重构：移除 SSO/token 鉴权，crash-mcp-server 改为无鉴权模式

**背景**：crash-mcp-server（接入点 0fbcecb097ec48）实测无需 token 即可访问，
历史换票逻辑属多余，且 sso-auth-cli CIBA 换票不稳定。

- **删除换票脚本**：移除 `scripts/refresh_token.py`
- **删除鉴权配置**：移除 `config.json` 和 `config.json.example`（含 client_id、mis、token_ttl）
- **SKILL.md**：新增"前置依赖"章节，含 Friday 链接 + 接入点 + 注册命令；删除"配置"章节
- **README.md**：前置依赖更新为无鉴权说明；删除 CIBA FAQ
- **references/example.md**：删除"第二步：换票"步骤，示例流程从解析告警直接跳到 MCP 查询

---

## v1.5.5 — 2026-03-24

### 优化：mis 自动读取，不再依赖 config.json 硬编码

- mis 读取优先级：sso-auth-cli cache.json → USER.md → 交互式询问
- 与 component-crash-chart v1.6.4 逻辑对齐

---

## v1.5.4 — 2026-03-24

### 修复：sso-auth-cli 换票 stdout 为空问题

- 根因：`sso-auth-cli` 不输出到 stdout，`result.stdout.strip()` 永远为空
- 修复：`run_sso_auth_cli()` 改用 `--cookie` 模式，从合并输出中正则提取 `<clientId>_ssoid=<token>`
- 影响：其他用户第一次安装时可自动完成换票

---

## v1.5.3 — 2026-03-24

### 改进：mis 自动从 USER.md 读取，零配置安装

- 首次使用时脚本自动读取 `~/.openclaw/workspace/USER.md` 中的 mis（正则匹配括号内账号格式）
- USER.md 不存在或读取失败时，降级为交互式 prompt 询问
- 读取成功则静默保存 `config.json`，全程无需手动操作
- 覆盖绝大多数 OpenClaw 用户场景，真正零配置开箱即用

---

## v1.5.2 — 2026-03-24

### 改进：首次安装交互式引导输入 mis

- 脚本启动时检测 `config.json` 是否存在及 mis 是否为占位符
- 若未配置，自动 prompt 用户输入 mis，无需手动 cp config.json.example
- 输入后自动写入 `config.json`（权限 600），下次不再询问

---

## v1.5.1 — 2026-03-24

### 改进：新用户安装引导 + README 快速开始

- 新增 `config.json.example` 模板（打包包含），`client_id` 和 `mcp_endpoint` 已预填
- 新用户只需 `cp config.json.example config.json` 并填入 mis
- README 补充"快速开始"章节，3步完成安装

---

## v1.5.0 — 2026-03-24

### 改进：配置外置 + 端到端示例 + 多平台字段说明

- **config.json 抽离硬编码**：`CLIENT_ID`、`MIS`、`MCP_ENDPOINT` 从脚本移至 `config.json`（权限 600），换人/换应用只改配置，不动脚本
- **端到端示例**：新增 `references/example.md`，展示完整的"告警消息 → 分析输出"对照，便于 Agent 对齐输出格式
- **多平台字段名说明**：`androidLog` 字段标注 Android/鸿蒙适用，iOS 对应字段为 `iosLog`
- **README 版本号同步**：更新至 v1.5.0，补充版本历史

---

## v1.4.1 — 2026-03-24

### 改进：补充触发边界 + Token 文件权限加固

- **新增 "适用场景" 章节**：明确 When to Use / When NOT to Use，避免与 component-crash-chart 等 skill 触发混淆
- **Token 安全加固**：`save_cache()` 写入后立即 `chmod 600`，防止同机其他进程读取明文 token
- 存量 `token-cache.json` 文件权限同步修正为 600

---

## v1.4.0 — 2026-03-24

### 重构：SKILL.md 精简 + 换票逻辑脚本化

对照 create-skill 规范全面优化：

- **SKILL.md 行数**：283 行 → 136 行（减少 52%）
- **Description**：改为第三人称，去掉 emoji 前缀，提升 Agent 匹配准确性
- **前置依赖章节**：删除过时的"安装 Friday Skill"描述，改为直接执行换票脚本
- **换票逻辑脚本化**：内联 Python 代码提炼为 `scripts/refresh_token.py`，SKILL.md 只保留一行调用命令
- **异常类型表格外置**：三平台约 40 行表格移至 `references/exception-types.md`，按需读取
- **Progressive Disclosure**：主流程保留在 SKILL.md，参考资料通过链接引用

---

## v1.3.2 — 2026-03-24

### 优化：换票升级为三级 fallback，与 component-crash-chart 对齐

**背景**：v1.3.0/1.3.1 的换票流程仅调用一次 sso-auth-cli，若 stdout 为空（CIBA 无缓存、用户未确认授权）则直接失败，无兜底。

**改动**：换票逻辑升级为三级 fallback：
1. **第一次调用** sso-auth-cli：CIBA 有缓存→静默换票，无缓存→推大象授权消息
2. **stdout 为空**：等待 30s 后重试（等待用户点击大象授权消息）
3. **重试仍为空**：从 sso-auth-cli 自身 `cache.json` 读取 CIBA token（有效期 3 天）
4. **仍为空**：提示用户"请在大象确认 CIBA 授权消息后重试"

用户日常使用完全透明，仅在 token 彻底失效且无任何缓存时才需要点一次大象授权。

---

## v1.3.1 — 2026-03-23

### 优化：sso-auth-cli 自动安装

- 换票前检测 `sso-auth-cli` 是否存在，未安装时自动 `npm install`
- 新用户无需手动安装前置依赖

---

## v1.3.0 — 2026-03-23

### 优化：换票改用 sso-auth-cli，Token 缓存延长至 3 天

**背景**：之前使用 `exchange-token.sh app` 换票，app 模式 token 有效期 1.5 小时，频繁触发鉴权。但 crash-mcp-server 需要用户身份（app 模式报 invalid code 201），每次都需手动提供 ssoid。

**改动**：
- 换票命令改为 `sso-auth-cli 6b17cdea54 --mis nieyunlong`，自动处理 user 身份换票
- Token 缓存 TTL 从 5400 秒（1.5 小时）提升至 259200 秒（3 天）
- sso-auth-cli 命中自身缓存时无感，真正过期才需要大象授权
- 调用失败时自动清缓存并重换票，无需手动干预

---

## v1.2.0 — 2026-03-20

### 修复：换票改为 app 模式，解决卡死问题

**根因**：换票脚本需要 ssoid，而之前传入的是 mis 账号，参数不匹配导致换票失败；token 为空时 mcporter 无有效 token，调用全部超时卡死。

**修复**：换票统一改为 `app` 模式（client_credentials），无需用户 ssoid 和 mis 账号，完全自动，不会阻塞。

---

## v1.1.0 — 2026-03-20

### 修复：换票脚本路径修正

- 脚本路径从旧版 `/app/skills/friday-mcp/scripts/exchange-token.sh` 更新为 `/app/skills/friday-catclaw-mcp/scripts/exchange-token.sh`
- mis 账号优先从 token-cache.json 缓存读取，其次读 USER.md，最后才询问用户——不再写死，支持多用户
- token 缓存 TTL 1.5 小时，有效期内直接复用，无需重复授权

---

## v1.0.0 — 初始版本

- 支持 Crash 告警解析 + MCP 拉取堆栈 + 根因分析
- 覆盖 Android / iOS / 鸿蒙
- token-cache.json 本地缓存机制

## v1.6.0 — 2026-03-25

### 强制改用 crash_all_stack
- **强制**：拉取堆栈必须使用 `crash_all_stack`，禁止使用 `crash_log_detail_post_json`
- `crash_log_detail_post_json` 不返回完整 `androidLog`，基于它的分析无效

### 禁止空堆栈推断
- `androidLog` 为空时禁止基于 `lastPageTrack` 推断堆栈内容
- 必须明确告知"堆栈为空，无法分析"

### 新增第零步：前置环境检查
- 每次执行前自动检查 mcporter 可用性 + crash-mcp-server 注册状态
- 未注册时自动执行 `mcporter config add` 完成注册
