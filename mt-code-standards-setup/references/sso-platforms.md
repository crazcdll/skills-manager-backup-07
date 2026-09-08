# Setup Skill 的跨平台 SSO 接入

依据官方[业务 Skill 接入 SSO 身份体系 — 开发者指南](https://km.sankuai.com/collabpage/2751640363)
的「方式一：Prompt 标准注入」，2026-09-07 核对。仅使用当前用户票据，目标 audience 为 `923a237244`。

## 用户使用方式

在目标业务仓库中安装或启用 `mt-code-standards-setup` 和 `mtsso-skills-official`，然后告诉 Agent：

> 使用 mt-code-standards-setup，为当前仓库下载并同步有效编码规范。

执行 Agent 按依赖声明读取官方 SSO Skill；统一 SSO Runner 先使用已注入用户票据，缺失时才调用官方
`mtsso-moa-local-exchange`。同一个 Runner 调用规则包接口，校验并安装 `.mdp/rules/`。用户不需要配置 Token。
业务 Skill 不实现非官方认证，也不读取、生成或展示票据。

## 平台前提

以下为官方文档列出的 PROD 支持范围，不代表本项目已在每个平台完成端到端验收。

| 平台 | 前提与职责 |
| --- | --- |
| CatDesk | 使用支持官方 SSO 的版本并登录；官方指南给出的版本门槛为 `2026.0416.2127`。在 Agent 会话内调用 Skill。 |
| CatPaw（含 IDE 插件） | 平台已适配官方 SSO，当前会话具备用户登录态；由官方 Skill 选择取票路径。 |
| CatPaw 云端 Agent | 云端运行环境已绑定当前用户并完成官方 SSO 适配；本地桌面的登录态不能代替云端身份。 |
| 美团沙箱 | 沙箱创建方按官方模板完成用户绑定和身份配置，并提供 SSO CLI；普通空白沙箱不自动具备这些能力。 |

沙箱创建方参考[Sandbox 业务 Skill 接入 SSO 身份体系](https://km.sankuai.com/collabpage/2757351876)：

- MOA 方式使用推荐的 `moa-beta-new` 模板，由 SDK 传入真实用户 MIS，并由平台安全注入
  `/root/.openclaw/sso/agent_info` 中的调用方身份配置。
- Exchange 方式使用官方 exchange 模板，由平台提供用户票据、`sandbox_agent_info` 和官方注册流程。
- 这些是沙箱创建方的职责，业务 Setup Skill 不读取、生成或写入上述身份文件。

普通本地终端能运行 Node.js 不代表它已接入官方 SSO；将同机另一应用的登录态复制过来不属于本方案。
共享 Agent 多人复用同一身份不在官方指南的支持范围内，不能用环境 owner 的身份代理所有使用者。

## 认证失败时

- 缺少官方 Skill 或 CLI：先在当前执行环境安装/更新官方依赖，不改业务仓库来补认证配置。
- 缺少 `client_id`、MOA 未绑定或无换票能力：由平台管理方核对注册、用户绑定及登录。
  `923a237244` 只填写在 audience 中；不要让普通用户提供调用方 `client_secret`。
- `sub_access_denied`、`act_access_denied`、`sub_act_access_denied`、`ric_feedback_required`：
  立即停止，按官方 Skill 展示返回的指引，不自动重试或切换身份。
- `MOA_NOT_LOGGED_IN` 或 `MOA_AUTH_REQUEST_PENDING`：官方本地换票已发起或等待大象 CIBA 授权卡片；
  用户确认后重新执行同一拉取。拒绝或冷却期也停止，不能绕过 CIBA 换用应用身份。
- 官方返回 `AT_FOR_GW_BASE64_` 网关占位符时按官方 Skill 原样注入，不能自行解码、签发或当成真实 Token 展示。

## 每个平台分别验收

用真实用户的新会话，在已关联且已订阅 L2 的前端仓库执行上述用户指令：

1. 用户无需手工复制票据，Agent 完成官方取票及 Runner 调用。
2. Runner 返回 `installed`，本地 manifest、文件 Hash 与 receipt 一致；包含前端 L1 和该仓库已生效的 L2。
3. 再执行一次返回 `not_modified`，本地无新 diff。
4. 取票或权限失败时展示可执行指引，保留原有本地规则包，不自动切换认证方式。

分别记录平台/版本、使用的 Skill 版本、仓库及上述结果；不记录 Token。
手工 curl 成功只证明票据和接口可用，不能代替真实 Agent 的依赖加载、注入和文件安装验收。
