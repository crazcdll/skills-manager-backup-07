---
name: mt-code-standards
version: "1.2.0"
description: "按用户指定的仓库名称或当前 Git 仓库，从业务研发平台下载并安全同步有效编码规范；可在任意目录运行并指定输出目录。按领域和阶段统一获取前端/Java L1 与可获取的生效 L2，未登记或无仓库地址时直接获取公开 L1；不用于代码审查或规则准入。"

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V11"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "150847"
  skillhub.high_sensitive: "false"
---

# 业务研发平台统一编码规范接入

## 目标与边界

一次请求同步领域和阶段匹配的已发布 L1，以及当前请求可获取的生效 L2。未登记、没有可获取的 L2、无 Git 或无 origin 时正常返回仅 L1；用户不需要选择引导模式或重试另一入口。匿名 public 保留 active 仓库现有公开 L2 分发策略；direct 根据已验证用户的组织关联判断 L2，缺少关联时仍返回公开 L1。

- 必须明确 --stage design|coding|cr；前端/后端由用户说明转换为 --domain frontend|backend，或由服务端使用可读的登记领域。缺失时一次性询问必要字段，不扫描业务源码猜测领域。
- 前端按阶段选择匹配 L1；后端 design/coding 选择精简 L1、cr 选择全量 L1；同阶段可有互补规则集。L2 依照生效订阅 Release，不按阶段裁剪。
- 认证失败、明确停用、订阅内容损坏、L1 未发布、数据库或构包失败必须明确报错，不能伪装成“仅 L1 成功”。
- 不执行代码审查、规则准入、仓库登记、订阅变更、commit、push 或发布。不自行 clone 中心仓库、查询组织订阅明细、拼装规则。

唯一 Runner 在 public 下调用 `POST /v1/public/rule-bundles/resolve`，direct 下调用 `POST /v1/rule-bundles/resolve`。
请求为 `rule-bundle-resolve/v1`，响应为 `rule-bundle-resolution/v1`；服务端一次选择，不先失败再重试 bootstrap。
默认网关为 `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution`。
新入口仅接受该受信网关；旧服务或旧 rule-observability 网关需要升级，不静默回退。
匿名分发依赖已部署的新数据库/Edge 合同和 `RULE_PUBLIC_PULL_ENABLED` 总开关，沿用共享匿名配额；限流/服务未就绪时停止，不反复重试或切换身份。

## 唯一执行方式

先读取目标项目 AGENTS.md/CLAUDE.md 和工作区状态。本次仅管理 `.mdp/rules/` 下平台认领的规则和索引。

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root '<来源目录>' \
  --domain frontend \
  --stage coding \
  --execution-agent codex
```

用户提供仓库时可传 `--repository '<namespace/repository 或线上 MCode Git 地址>'`；无 Git 地址也允许直接拉取 L1。
显式错误地址不被目录兜底吞掉。只接受完整 canonical key 或可归一化的线上地址，不接受裸仓库名。
没有显式地址时只查来源 Git 根的 origin，不向下扫描多个仓库，不任选其他 remote。自动发现的非 MCode origin 无法确定平台身份时，使用来源目录兜底并拉取 L1；不访问 origin 主机，也不按其路径猜测平台仓库。显式传入不受支持的地址仍报错。
输出基目录优先 `--output-dir`、`--repo-root`、当前目录，最终路径为 `<输出基目录>/.mdp/rules/`。
来源目录用于名称兜底：以 repo-root/cwd 向上找 Git 根，否则取该目录的绝对路径。不能用 output-dir 冒充仓库。

public 是默认模式，不获取或发送 SSO 票据。可选 `--mis` 仅自报调用方，不影响权限；未提供时记匿名，不猜系统用户名或 Git 作者。
显式 direct 保持认证身份；仅返回 L1 时也不偷偷转为匿名：

```shell
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root '<来源目录>' --domain frontend --stage coding \
  --transport direct --mis '<当前操作者MIS>' --execution-agent codex
```

旧 `--bootstrap` 参数只保留为 `scope=l1` 兼容别名，仍调用统一入口并保持所选传输方式，不是新流程的必要参数。旧 effective/bootstrap 服务路由仅兼容旧客户端，新客户端不回退调用。

## direct 身份认证

仅 direct 调用认证。执行前加载官方 `mtsso-skills-official`，按 audience `923a237244` 获取当前用户短期票据；不让用户粘贴 Token。匿名 public 不依赖认证工具。

运行环境要求 Node.js `>= 18`。npm CLI 自带固定版本 `@it/oa-skills-shared 1.2.1`；Skill Runner 优先加载自身本地依赖，没有本地依赖时再从当前 Node 的全局 `oa-skills` 中加载 `@it/oa-skills-shared >= 1.2.0`。首次执行需要认证的正式 direct 拉取前检查 `oa-skills`，仅在依赖不存在时安装；匿名 public 不需要安装认证依赖。不要在 Runner 内自动安装依赖：

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
- 便携 CIBA 按 `--mis`、`SSO_USER_ID`、当前仓库本地 `.git/config` 的 `user.mis` 依次读取当前操作者
  的公司 MIS；本地配置不存在、格式非法或 Git 不可用时静默跳过。MIS 只作为 CIBA `login_hint`，不会
  写入规则请求或充当身份事实；业务 actor 仍由服务端验证短期用户票据后确定。只读 repository-local
  配置，不读取全局 Git 配置，也不使用 Git 作者信息冒充身份。
- 便携认证固定换发 audience `923a237244`，缓存只允许写入单次进程创建的 `0700` 临时目录，完成或失败后
  删除整个目录；不读取或复用 Citadel 的 token/cache，也不复制、展示或要求用户提供 `client_secret`。
- 便携 helper 仅供父 Runner 调用：票据通过父进程捕获的内部 stdout 返回，父 Runner 不转发该内容；不要单独
  执行 helper，也不要把 helper 输出写入终端、日志或文件。
- receipt 可记录不敏感的 `authentication_mode` 和 `authentication_route_reason`，但认证宿主标识和路由原因
  不得加入 Board 请求 Schema。
- 收到 `RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED` 时，在大象确认后重新执行同一拉取；收到拒绝或冷却提示时停止，不能自动重试。
- 官方换票的交互等待上限为 30 秒；便携 CIBA 单独允许最多 150 秒。超时均停止，由用户确认状态后重新执行。
- 当前身份未完成平台登录/组织核验、无法读取受关联保护的 L2 时，统一入口仍可按明确领域和阶段返回公开 L1；要获取相应 L2，可先访问并登录 [业务研发平台编码规范管理平台](https://quality-gate.nocode.sankuai.com/)。旧接口曾返回 `repository_user_login_unverified` 并停止，不将该历史行为沿用到新统一分发。
- 官方换票失败时按 `mtsso-skills-official` 的错误分类停止；权限不足或需人工确认的错误不得自动重试。
- 不把 `catdesk auth exchange` 写成跨平台前置条件，不自行注册 Agent、复制其他平台凭据或修改宿主 SSO 配置。

便携路径能否线上使用还有一个发布前置：办公官方 Skills 默认调用方必须已获得对 `923a237244` 的 UAC
代理授权。已有 Codex 真实会话打通便携 CIBA 和规则安装，但这不能替代其余外部 Agent、用户权限和运行
环境的逐项验收。

CatDesk、CatPaw IDE、CatPaw 云端 Agent 和美团沙箱沿用同一份 Skill；仅正式 direct 认证拉取要求所在平台已完成官方 SSO
适配并绑定当前用户。首次接入或出现缺少 `client_id`、登录/权限错误时，读取
[平台条件与验收](references/sso-platforms.md)。`923a237244` 是目标服务 audience，不是待补填的调用方身份。


## 本地目录与安装合同

显式协商 `bundle_contract=scope-domain-ruleset/v1` 和 `agents_index_contract=rule-set-agents-index/v1`。
统一响应的 `bundle_kind` 为 effective/l1，内包分别复用 effective-rule-bundle/v4 和 l1-bootstrap-bundle/v3；内包历史名称不要求用户选择 bootstrap。
每次都检查 envelope 的请求编号、pull_id、仓库身份、阶段和领域，再校验内包文件、Release 与 SHA-256。

```text
.mdp/rules/
├── .mt-effective-rule-bundle.json   # 生效包 manifest v8
├── .mt-l1-bootstrap.json           # 仅 L1 包 manifest v5；与上项互斥
├── company/fe/<规则集名称>/<文件>.md
├── company/java/<规则集名称>/<文件>.md
├── team/fe/<规则集名称>/<文件>.md
├── team/java/<规则集名称>/<文件>.md
└── project/                       # L3，项目自管
```

文件归属通过 Release 的 scope_level、standard_domain、local_rule_set_name 决定；一个 Release/来源文件对应一个物理 Markdown。
manifest 的 managed_file_releases、来源路径、Hash、大小及索引参与验证；新版另以 resolution_hash 绑定分发上下文。
安装使用暂存和原子替换；仅 L1 与 L1+L2 双向迁移时清理原清单认领且未被修改的旧规则/索引，保留未知文件和 L3。
本地被修改的文件、Hash 损坏、路径冲突、符号链接或不同仓库身份必须停止。无仓库请求不能覆盖一个已知 canonical 的正式包。
相同内容可返回 not_modified，仍校验本地文件和索引；展示名或选择原因变化时原子更新清单元数据。
索引按现有合同转换为受管 AGENTS.md；缺少索引合同则仅报告警告，不能编造索引。

## 分发上报与错误

- 客户端仅发送仓库地址、领域阶段、协议/缓存、pull_id、执行工具和实际发行元数据；不上传源码、diff、分支、提示词、文件列表、模型或 Token 消耗。
- 展示名由平台名→完整仓库名→来源绝对路径确定，配套 display_name_source；目录只保存一次，不用于 L2 匹配。
- skill_name/skill_version 从实际运行目录 SKILL.md 读取，setup 包记录 setup 名称；读取失败为 null，不固定兜底。client_type/name/version 独立记录，CLI 不冒充 Skill。
- public 未自报身份时为 anonymous；direct 为 verified_mis；显式匿名自报标记 self_reported，不提升为可信身份。
- 服务端记录实际快照、Release、逐条规则 UID、总字节数、分发模式和原因。ready/not_modified 是分发结果，不代表本地安装成功。
- 本地成功 receipt 为 mt-rule-bundle-install/v1，status=installed/not_modified；本轮没有安装结果回传。
- 失败展示安全 code/message、issues 和 request_id；不要用“public_rule_bundle_unavailable”一概替代具体问题。参数错误请补齐对应字段；认证、限流与服务故障不要自动切换身份或反复重试。

## 验收与发布前置

安装后核对 receipt 与 manifest 的 snapshot_id、领域、阶段、实际 L1/L2、文件 Hash 和索引，检查只修改受管内容。
新版必须先完成数据库前向迁移及 rule-distribution 统一入口发布验收，再分别发布 npm CLI 与 Friday Skill；CatX 技能包独立更新并回读实际版本。mtcli 服务定义需先登记新 resolve-unified 方法。源码或本地测试成功不代表线上部署完成。
