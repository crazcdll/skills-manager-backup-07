---
name: mt-code-standards-setup
description: "按当前 Git 仓库从业务研发平台下载并安全同步有效编码规范。适用于已登记仓库的前端/Java L1 与已订阅 L2，也支持为服务端确认未登记的单领域仓库引导安装公开 L1；不用于代码审查或规则准入。"
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - 923a237244
    prompt: 本技能所需的 token 占位符，请参考 mtsso-skills-official 的相关说明进行获取和注入

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V11"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "141006"
  skillhub.high_sensitive: "false"
---

# 业务研发平台统一编码规范接入

## 目标与边界

本 Skill 只完成一件事：为 Git 仓库同步平台确认可用的编码规范。已登记且当前用户有权访问的仓库同步正式有效规则包；服务端确认全局未登记的仓库只引导安装对应领域的公开 L1。

- 前端仓库下载前端 L1 与该仓库当前订阅的前端/共享 L2。
- 后端仓库下载 Java L1 与该仓库当前订阅的后端/共享 L2。
- 正式包的仓库领域、组织关联、订阅、Release 有效性和最终规则集合均由平台判定。
- 正式解析未找到仓库时，不直接认定未登记。Runner 先用 Git 已跟踪文件判断 `frontend`、`backend`、`mixed` 或 `unknown`，再由独立 bootstrap 接口用精确 `namespace/repository` 跨可见性确认全局登记事实。
- 单一领域证据明确时自动拉取该领域已发布 L1；`mixed` 或 `unknown` 时停止并展示限量安全证据，由 Agent 询问用户后以 `--domain frontend|backend` 明确选择。
- 已登记、隐藏、未关联、停用或其他不可用仓库统一禁止 bootstrap，不借此探测仓库、组织或订阅信息。
- 只提供裸仓库名时不能执行 bootstrap；必须由用户补充 `namespace/repository` 或可归一化到该形式的完整 Git 地址。
- 不执行代码审查、规则准入、订阅变更、仓库登记、commit、push 或平台发布。

Agent 不得自行 clone 中心规范仓库、调用组织/订阅/规则明细等接口、解析页面或拼装规则。
唯一确定性 Runner 始终先调用 `POST /v1/effective-rule-bundles/resolve`；仅收到未找到且具备精确 canonical key 与单一领域后，才调用 `POST /v1/l1-rule-bundles/bootstrap`。两个响应均完整校验后再原子替换受管文件。

## 身份认证

采用官方指南的 **Prompt 标准注入**：执行 Agent 根据头部依赖声明，使用 `mtsso-skills-official`
为 NoCode 作品线上默认 audience `923a237244` 获取当前用户短期票据，再注入下方 Runner 命令。
用户只需调用本 Skill，不需要手工获取或粘贴 Token；统一 Runner 负责取票、下载和校验。

运行环境要求 Node.js `>= 18`。首次执行前先在当前 Node 环境检查 `oa-skills`；仅在依赖不存在时安装，供便携 CIBA
加载其内置的 `@it/oa-skills-shared >= 1.2.0`。不要在 Runner 内自动安装依赖：

```shell
node -e "const cp=require('child_process'),fs=require('fs'),p=require('path'),npm=process.platform==='win32'?'npm.cmd':'npm';try{const r=cp.execFileSync(npm,['root','-g'],{encoding:'utf8'}).trim();fs.accessSync(p.join(r,'@it','oa-skills','node_modules','@it','oa-skills-shared','package.json'))}catch{cp.execFileSync(npm,['install','-g','@it/oa-skills','--registry=http://r.npm.sankuai.com'],{stdio:'inherit'})}"
```

若 Runner 返回 `RULE_BUNDLE_SSO_PORTABLE_PROVIDER_REQUIRED`，说明当前 Node 下的包缺失或内置 shared 版本
低于要求；在同一 Node 环境更新 `@it/oa-skills` 后重试。

- 先读取或加载当前平台的 `mtsso-skills-official`，理解官方 V13 默认换票合同和错误分类；平台已适配官方
  SSO 时按该合同取票。
- 实际执行前再把 `${user_access_token}` 替换为官方用户票据。
- 票据只进入当前 Runner 的受控进程通信，不出现在参数、用户可见 stdout、manifest、规则文件或回复中。
- 不读取浏览器 Cookie，不用 Git 作者、系统账号、应用 owner 或手填 MIS 冒充当前用户。
- 优先使用运行环境已注入的官方用户票据。没有票据时，已知外部编码 Agent 直接使用
  `oa-skills-shared` 的便携 `sso-ciba`，避免先执行缺少宿主 `client_id` 的官方 CLI；公司内部宿主和未知
  宿主仍调用官方 `mtsso-moa-local-exchange`。官方 CLI 会按网关拦截、扩展 Agent、本地 MOA 的顺序换票。
- 外部直达 CIBA 是本 Setup Skill 针对独立编码 Agent 的认证路由，不是对官方 V13 默认合同的改写，也不
  冒充 `mtsso-moa-local-exchange` 的官方路径。20 个高覆盖外部 Agent 标识及选择规则见
  [平台条件与验收](references/sso-platforms.md)；它们不是严格市场份额排名。
- 未识别宿主走官方路径后，仅当官方返回明确的 Agent `client_id` 配置缺失或本地换票能力不可用时，才
  回退便携 CIBA；网络、超时、非法响应、权限拒绝、人工确认、用户拒绝和冷却期均不得触发便携回退。
- 便携 CIBA 需要当前操作者的公司 MIS，按 `--mis <MIS>` 或 `SSO_USER_ID` 读取。MIS 只作为 CIBA
  `login_hint`，不会写入规则请求或充当身份事实；业务 actor 仍由服务端验证短期用户票据后确定。
- 便携认证固定换发 audience `923a237244`，缓存只允许写入单次进程创建的 `0700` 临时目录，完成或失败后
  删除整个目录；不读取或复用 Citadel 的 token/cache，也不复制、展示或要求用户提供 `client_secret`。
- 便携 helper 仅供父 Runner 调用：票据通过父进程捕获的内部 stdout 返回，父 Runner 不转发该内容；不要单独
  执行 helper，也不要把 helper 输出写入终端、日志或文件。
- receipt 可记录不敏感的 `authentication_mode` 和 `authentication_route_reason`，但认证宿主标识和路由原因
  不得加入 Board 请求 Schema。
- 收到 `RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED` 时，在大象确认后重新执行同一拉取；收到拒绝或冷却提示时停止，不能自动重试。
- 官方换票的交互等待上限为 30 秒；便携 CIBA 单独允许最多 150 秒。超时均停止，由用户确认状态后重新执行。
- 新增的组织管理员在首次登录平台前标记为“未经登录核验”，不能拉取规范。Runner 收到 `repository_user_login_unverified` 时，提示用户先访问并登录 [业务研发平台编码规范管理平台](https://quality-gate.nocode.sankuai.com/) 后重新拉取。
- 官方换票失败时按 `mtsso-skills-official` 的错误分类停止；权限不足或需人工确认的错误不得自动重试。
- 不把 `catdesk auth exchange` 写成跨平台前置条件，不自行注册 Agent、复制其他平台凭据或修改宿主 SSO 配置。

便携路径能否线上使用还有一个发布前置：办公官方 Skills 默认调用方必须已获得对 `923a237244` 的 UAC
代理授权。已有 Codex 真实会话打通便携 CIBA 和规则安装，但这不能替代其余外部 Agent、用户权限和运行
环境的逐项验收。

CatDesk、CatPaw IDE、CatPaw 云端 Agent 和美团沙箱沿用同一份 Skill；前提是所在平台已完成官方 SSO
适配并绑定当前用户。首次接入或出现缺少 `client_id`、登录/权限错误时，读取
[平台条件与验收](references/sso-platforms.md)。`923a237244` 是目标服务 audience，不是待补填的调用方身份。

## 仓库定位

默认从目标仓库根目录执行，Runner 自动读取 `git remote get-url origin`。也可由用户明确提供以下任一种 locator：

- Code HTTPS 页面地址；
- `https://git.sankuai.com/...` clone 地址；
- `ssh://git@git.sankuai.com/...`；
- `git@git.sankuai.com:namespace/repository.git`；
- `namespace/repository`；
- 唯一仓库名，如 `rn_hotel_inland`。

locator 后可以带 `?` 或 `#` 参数。Runner 保留完整输入交给平台，平台只用主仓库身份匹配。仅仓库名匹配到
多条记录时，要求用户补充 `namespace/repository` 或完整地址；不要任选一条。当前目录没有 origin 时，向用户
询问仓库 locator。

## 唯一执行方式

先读取目标仓库的 `AGENTS.md`/`CLAUDE.md` 和工作区状态，确认本次仅管理 `.mdp/rules/` 下规则包文件。
随后执行随 Skill 分发的 Runner：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "$PWD"
```

Codex、Claude Code 会按高置信环境变量自动识别并直达便携 CIBA；若没有 `SSO_USER_ID`，还应传入当前
操作者 MIS 作为 CIBA 登录提示：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "$PWD" \
  --mis '<current-user-mis>'
```

其他已知外部编码 Agent 应显式传入独立的认证宿主标识；例如 Cursor：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "$PWD" \
  --auth-agent cursor \
  --mis '<current-user-mis>'
```

`--auth-agent` 只选择认证路径，不进入 Board 请求；允许值见
[平台条件与验收](references/sso-platforms.md)。不要用 `--execution-agent` 代替它。

用户明确提供 locator 时增加一个参数：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "$PWD" \
  --repository '<repository-locator>'
```

当 Runner 返回 `RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED` 时，Agent 根据错误中的 Git 已跟踪证据询问用户；用户明确领域后重试：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "$PWD" \
  --domain frontend
```

执行 Agent 应在可确认自身环境时传入 `--execution-agent`：`catdesk`、`catpaw`、`claude`、
`codex`、`agent_1024`、`sandbox` 或 `catx`。未传时 Runner 只按环境变量识别，不能识别会记录为
`unknown`，不猜测。该参数只用于 Board 观测，不能承载 Cursor 等外部认证宿主标识。不要改参数、复制脚本
逻辑或在失败后改走旧接口。Runner 的成功 stdout 是正式包的
`mt-effective-rule-bundle-install/v1` 或引导 L1 的 `mt-l1-bootstrap-install/v1` receipt；其他文字、Agent 回复或 HTTP `accepted` 均不能作为安装成功证据。

## 本地目录合同

平台响应中的 `files[].relative_path` 只用于校验来源和规则包完整性。Runner 将其映射为扁平的本地目录，
不在本地重复领域、层级或来源目录：

```text
.mdp/rules/
├── .mt-effective-rule-bundle.json
├── company/
│   └── <L1 原文件名>.md
└── team/
    └── <L2 规则集 ID>/<L2 原文件名>.md
```

前端和后端仓库均使用相同的 `company/`、`team/` 根目录；仓库领域仍由服务端校验并写入 manifest，
不作为本地目录层级。一个 Release/来源文件对应一个物理 Markdown，不按文档中的逻辑规则拆分。
同一目录内出现同名来源文件时，Runner 保留文件名并追加来源 Hash，避免覆盖。manifest 固定为
`.mdp/rules/.mt-effective-rule-bundle.json`，至少记录：

- `snapshot_id`、`manifest_hash`，新版另含 `resolver_version`；
- 仓库稳定身份和 `standard_domain`；
- L1/L2 `release_refs`；
- `managed_files`、逐文件 SHA-256 和总字节数；
- 本地安装时间。

未登记仓库的 L1 使用独立 `.mdp/rules/.mt-l1-bootstrap.json`，不包含仓库、组织、订阅或 L2 身份，也不冒充正式有效规则包。其受管文件仍位于 `company/`；仓库完成登记并成功取得正式包后，Runner 原子删除 bootstrap manifest 与其受管文件，再由正式 manifest 接管。两类 manifest 冲突、损坏或领域不一致时均失败关闭，不静默覆盖。

Runner 先在同一文件系统暂存完整领域目录，校验路径、字节数、文件哈希、manifest hash 和 snapshot hash，
再交换目录并最后更新 manifest；任一步失败都回滚。它只删除旧 manifest 明确登记的受管文件，保留未知文件，
遇到同名非受管文件、符号链接或路径穿越时失败关闭。

新版 `effective-rule-bundle/v2` 保留中文文件名和原始大小写，Unicode 统一为 NFC；例如
`.mdp/rules/company/ASYNC-异步与异常处理.md`，或
`.mdp/rules/team/git-1-fe-l2/L2-rules.md`。
控制字符、路径穿越和绝对路径仍拒绝；系统非法字符、保留名、过长路径及大小写/Unicode 重名由平台
确定性处理。路径最多 240 个 UTF-8 字节、单段最多 200 字节；长路径优先保留可读文件名，并追加来源 Hash。
Runner 不自行改写平台路径；比较路径时考虑 NFC 和大小写等效，避免覆盖等效名称的非受管文件。

## 增量更新

当前 Runner 同时接受 v1/v2 规则包与对应的本地 manifest。v2 的快照 Hash 包含 `resolver_version`，
文件清单使用固定的字符串二进制排序，不能沿用 v1 的快照或排序公式。
从 v1 升级时，先校验旧 manifest，再安装新包并移除旧清单登记的英文文件；保留用户自行添加的文件。
部署应先更新数据库、再发布此兼容 Runner，最后发布输出 v2 的 Edge。旧 Runner 收到 v2 会失败关闭，
因此必须先更新 Skill；错误时保留原有规则，不手动删文件或伪造 manifest。

Runner 只在本地 manifest 及所有受管文件仍通过 SHA-256 校验时发送 `known_snapshot_id`：

- 平台返回 `ready`：校验并安装完整规则包。
- 平台返回 `not_modified`：snapshot 必须与本地已校验值一致，且不得携带文件；本地不制造 diff。
- 本地文件被修改、丢失或 manifest 非法：不信任旧 snapshot，要求平台返回完整 `ready` 包。

禁止用旧缓存、部分文件或“上次成功”掩盖服务不可用。网络、认证、权限、登记、歧义、响应 Schema 或 Hash
任一失败时保持原规则包不变，并把 Runner 的稳定错误码和可执行提示交给用户。

## 验收与交付

成功后只依据 receipt 与本地文件复核：

1. receipt 为正式包 `mt-effective-rule-bundle-install/v1` 或引导 L1 `mt-l1-bootstrap-install/v1`，状态是 `installed` 或 `not_modified`。
2. 对应 manifest 的 `snapshot_id` 与 receipt 一致；bootstrap receipt 必须同时声明 `mode=l1_bootstrap` 与领域来源。
3. 每个 `managed_files` 都位于 `company/` 或 `team/<规则集 ID>/` 且 SHA-256 与 manifest 一致。
4. `release_refs` 至少包含当前领域 L1；L2 仅包含仓库实际订阅且已发布的 Release。
5. `git diff` 只包含本次受管规则包变更，未知文件和项目规则未改变。

每一次解析到规则包的拉取都会由平台记录可信 MIS、仓库、精确规则 UID 与 Release、执行 Agent、
Skill 和结果状态；相同规则包快照仍会去重。向用户报告仓库稳定身份、领域、L1/L2 Release、安装文件数、
总字节数以及 `installed/not_modified`。不要回显票据，不要声称未执行的部署或线上验证已经完成。
