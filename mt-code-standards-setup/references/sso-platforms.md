# Setup Skill 的跨平台 SSO 接入

依据官方[业务 Skill 接入 SSO 身份体系 — 开发者指南](https://km.sankuai.com/collabpage/2751640363)
的「方式一：Prompt 标准注入」，2026-09-07 核对。仅使用当前用户票据，目标 audience 为 `923a237244`。

## 用户使用方式

在目标业务仓库中安装或启用 `mt-code-standards-setup` 和 `mtsso-skills-official`，然后告诉 Agent：

> 使用 mt-code-standards-setup，为当前仓库下载并同步有效编码规范。

执行 Agent 按依赖声明读取官方 SSO Skill；统一 SSO Runner 始终优先使用已注入用户票据。票据缺失时，
已知外部编码 Agent 直接使用办公官方 Skills 的便携 CIBA provider，公司内部宿主和未知宿主调用官方
`mtsso-moa-local-exchange`。同一个 Runner 调用规则包接口，校验并安装 `.mdp/rules/`。用户不需要配置 Token。
便携路径仍是公司用户认证，需要当前用户 MIS 和目标权限，不支持公司外人员或共享身份。

## 运行依赖与发布前置

- Node.js `>= 18`。
- npm CLI 固定依赖 `@it/oa-skills-shared 1.2.1`。Skill Runner 优先加载本地依赖；本地没有时，`oa-skills`
  必须可用且其内置 shared 版本至少为 `1.2.0`。缺失时才从内网 registry 安装 `@it/oa-skills`。
- 便携 provider 固定面向 `923a237244`，办公官方 Skills 默认调用方必须在 UAC 中具备对该 audience 的
  代理授权。这是发布前置，不是源码默认拥有的能力。
- Codex 真实会话已完成一次便携 CIBA 和规则安装验收；该结果不代表其余 19 个外部宿主、所有用户权限或
  新环境天然可用，仍须分别记录实际回执。

## 平台前提

以下为官方文档列出的 PROD 支持范围，不代表本项目已在每个平台完成端到端验收。

| 平台 | 前提与职责 |
| --- | --- |
| CatDesk | 使用支持官方 SSO 的版本并登录；官方指南给出的版本门槛为 `2026.0416.2127`。在 Agent 会话内调用 Skill。 |
| CatPaw（含 IDE 插件） | 平台已适配官方 SSO，当前会话具备用户登录态；由官方 Skill 选择取票路径。 |
| CatPaw 云端 Agent | 云端运行环境已绑定当前用户并完成官方 SSO 适配；本地桌面的登录态不能代替云端身份。 |
| 美团沙箱 | 沙箱创建方按官方模板完成用户绑定和身份配置，并提供 SSO CLI；普通空白沙箱不自动具备这些能力。 |
| Codex / Claude Code 等外部宿主 | 操作者仍须是有目标权限的公司用户。已注入票据优先，否则已知外部宿主直接以 `--mis <当前用户MIS>` 或 `SSO_USER_ID` 发起便携 CIBA。 |

沙箱创建方参考[Sandbox 业务 Skill 接入 SSO 身份体系](https://km.sankuai.com/collabpage/2757351876)：

- MOA 方式使用推荐的 `moa-beta-new` 模板，由 SDK 传入真实用户 MIS，并由平台安全注入
  `/root/.openclaw/sso/agent_info` 中的调用方身份配置。
- Exchange 方式使用官方 exchange 模板，由平台提供用户票据、`sandbox_agent_info` 和官方注册流程。
- 这些是沙箱创建方的职责，业务 Setup Skill 不读取、生成或写入上述身份文件。

普通本地终端能运行 Node.js 不代表它已接入官方 SSO；便携路径通过新的 CIBA 确认获取短期票据，不复制
同机另一应用的登录态。传入的 MIS 仅作 CIBA `login_hint`，业务 actor 仍由服务端验证票据确定，MIS 不会
进入规则请求作为身份事实。
共享 Agent 多人复用同一身份不在官方指南的支持范围内，不能用环境 owner 的身份代理所有使用者。

## 外部认证宿主标识

以下 20 个 canonical ID 是结合国内外常用编码 Agent 形成的高覆盖集合，不是严格市场份额排名，也不表示
这些产品官方集成了本 Setup Skill：

```text
github-copilot, cursor, windsurf, claude-code, codex, gemini-cli, amazon-q, kiro,
jetbrains-junie, devin, replit-agent, cline, roo-code, aider, trae, qoder,
tongyi-lingma, tencent-codebuddy, baidu-comate, codegeex
```

- Codex 仅在存在 `CODEX_*` 环境变量时自动识别；Claude Code 仅在存在 `CLAUDE_CODE*` 或 `CLAUDECODE*`
  环境变量时自动识别。内部 CatDesk、CatPaw、CatX、CatClaw、Agent 1024 或 Sandbox 信号优先保持官方路径。
- 其余外部宿主在执行 Runner 时显式传 `--auth-agent <canonical-id>`。参数严格校验；不要根据
  `GITHUB_ACTIONS`、`TERM_PROGRAM=vscode` 等宽泛信号猜测宿主。
- `--auth-agent` 只决定取票路径，不发送到 Board，也不扩展 `execution_agent` Schema；
  `--execution-agent` 仍只使用 Board 已支持的观测枚举。
- 已注入的 `RULE_OBSERVABILITY_USER_TOKEN` 始终优先。仅在票据被 Edge 明确返回 `unauthorized` 后，
  Runner 才移除该票据并按同一个认证宿主选择器重新取票一次。

官方 V13 的默认合同仍是通过 `mtsso-moa-local-exchange` 选择网关、扩展 Agent 或本地 MOA 换票。本 Setup
Skill 对上述独立外部编码 Agent 采用直接便携 CIBA，是为了避免一次已知无宿主 `client_id` 的失败尝试；
该专项路由不应被描述为官方 CLI 路径，也不改变官方错误分类和 UAC 约束。

便携 provider 不复用 Citadel 或其他 Skill 的 token/cache。它先加载 CLI/Skill 本地声明的
`@it/oa-skills-shared/auth`；本地没有时从当前 Node 的 `npm root -g` 下解析
`@it/oa-skills/node_modules/@it/oa-skills-shared`。它把 `cacheFile` 指向单次创建的 `0700` 临时目录，并在
`finally` 删除整个目录。provider 内部即使写盘也只能写入该目录；父 Runner 捕获 helper 的内部 stdout
作为受控进程通信且不向用户转发，不把 token 写入用户可见 stdout、receipt、manifest 或回复，也不读取、
复制或输出任何 `client_secret`。helper 不是独立命令，不应被直接执行或重定向输出。

## 认证失败时

- 缺少官方 Skill 或 CLI：先在当前执行环境安装/更新官方依赖，不改业务仓库来补认证配置。
- 未识别宿主走官方路径后缺少 Agent `client_id`、probe 明确无能力或本地换票能力不可用：有当前公司用户 MIS 时允许便携 CIBA；
  缺少 MIS 则停止并提示 `--mis` / `SSO_USER_ID`。`923a237244` 只填写在 audience 中；不要让普通用户
  提供调用方 `client_secret`。
- `sub_access_denied`、`act_access_denied`、`sub_act_access_denied`、`ric_feedback_required`：
  `exit 42` 或旧版 `exit 1` 都立即停止，安全化展示官方指引，不自动重试或切换身份。
- `MOA_NOT_LOGGED_IN` 或 `MOA_AUTH_REQUEST_PENDING`：官方本地换票已发起或等待大象 CIBA 授权卡片；
  用户确认后重新执行同一拉取。拒绝或冷却期也停止，不能绕过 CIBA 换用应用身份。
- 官方返回 `AT_FOR_GW_BASE64_` 网关占位符时按官方 Skill 原样注入，不能自行解码、签发或当成真实 Token 展示。
- 官方或便携路径发生网络错误、超时、非法响应时停止；这些错误不是“宿主能力缺失”，不得换路径重试。
- 官方进程即使退出码为 0，只要 stdout JSON 包含 `error` / `code` 或 `success:false`，仍按失败码分类。
- 注入票据被规则 Edge 明确返回 `unauthorized` 时只重新取票一次，重取仍使用同一个认证宿主选择器：已知
  外部 Agent 直达便携 CIBA，内部或未知宿主走官方优先和受限便携回退；
  其他业务拒绝和第二次失败不重试。

## 每个平台分别验收

用真实用户的新会话，在已关联且已订阅 L2 的前端仓库执行上述用户指令：

1. 用户无需手工复制票据，Agent 完成官方取票及 Runner 调用。
2. Runner 返回 `installed`，本地 manifest、文件 Hash 与 receipt 一致；包含前端 L1 和该仓库已生效的 L2。
3. 再执行一次返回 `not_modified`，本地无新 diff。
4. 取票或权限失败时展示可执行指引，保留原有本地规则包；已知外部宿主直接使用便携 CIBA，未知宿主仅
   在明确能力缺失时允许从官方路径回退。

分别记录平台/版本、使用的 Skill 版本、仓库及上述结果；不记录 Token。
手工 curl 成功只证明票据和接口可用，不能代替真实 Agent 的依赖加载、注入和文件安装验收。
