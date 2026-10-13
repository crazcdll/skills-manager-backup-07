# mt-code-standards

独立拉取业务研发平台为仓库解析出的有效编码规范。CLI 与 `mt-code-standards` Skill 共用同一套下载、校验、增量更新和原子回滚实现。

## 安装

使用 Node.js 18 或更高版本，并从公司 npm 源安装：

```shell
mnpm install -g @nibfe/mt-code-standards
```

## 使用

在任意目录按精确 `namespace/repository` 匿名拉取，默认写入当前目录的 `.mdp/rules/`：

```shell
mt-code-standards pull --repository hfe/duo-hotel-order-submit
```

指定输出基目录：

```shell
mt-code-standards pull \
  --repository hfe/duo-hotel-order-submit \
  --output-dir /path/to/workspace
```

后端规则按研发阶段拉取：方案/编码阶段使用精简 L1，CR 阶段使用全量 L1：

```shell
mt-code-standards pull \
  --repository hbar/your-java-repo \
  --stage coding

mt-code-standards pull \
  --repository hbar/your-java-repo \
  --stage cr
```

`--repo-root` 用于兼容原 Setup Runner：它作为 Git 自动探测目录；没有 `--output-dir` 时也作为输出基目录。优先级为 `--output-dir`、`--repo-root`、当前目录。

`--stage` 可选值为 `design`、`coding`、`cr`。显式传入阶段时，规则包会校验阶段化响应和依赖哈希；不传时保持旧的 legacy 拉取行为。

CLI 默认使用 `public` 仓库级读取模式，无需传 `--transport`。服务端总开关开启后，可匿名读取所有 active 仓库的已发布 L1 与该仓库已生效的 L2，不再检查仓库的 `public_pull_enabled`；不发送 MIS、SSO token 或组织信息，也不会因匿名失败自动降级到认证接口。public 只接受精确 `namespace/repository` 或可归一化的线上 MCode Git 地址，不接受裸仓库名，也不支持 `--bootstrap`、`--mis`、`--auth-agent` 或 `--mtcli-service`。

默认 public 客户端发布前，必须先完成 Board 的数据库迁移、`rule-distribution` 部署和共享配额验收，再开启
`RULE_PUBLIC_PULL_ENABLED` 总开关。公共模式不需要网关凭据或可信 IP 头；所有匿名调用共享配额，当前固定窗口
合计每 60 秒最多 600 次请求、100 个不同仓库、60 个并发，单个仓库每窗口最多 300 次。实际策略以 Board 数据库
`public_rule_pull_quota_policy_v1` 为准。该初始值为 50 人同时拉取预留余量，但未经过生产压测；一个调用者仍可能耗尽额度并影响其他人。无法验证实际用户或
来源 IP，也无法保证阻止慢速或跨时间窗口爬取。仅发布 npm 包不会开启匿名接口；失败时保留本地规则，不自动取票或重试。

需要通过当前用户权限访问时，显式选择 direct：

```shell
mt-code-standards pull \
  --repository hfe/duo-hotel-order-submit \
  --transport direct \
  --mis '<你的MIS>' \
  --stage coding
```

direct 通过当前用户 CIBA 票据访问平台，`--mis`、`SSO_USER_ID` 或当前仓库本地 `.git/config` 的 `user.mis` 仅作为登录提示，优先级依次降低。可信操作人由服务端验证票据后确定；票据不会写入参数、规则文件、manifest 或公共输出。Git 配置不存在或没有合法 `user.mis` 时静默跳过；direct 非交互环境没有预注入票据时仍需要有效 MIS 提示。

## 通过 mtcli 拉取

从 1.1.0 起可选择 mtcli 负责远程调用和官方 SSO 登录，本地仍由本 CLI 校验和安装规则。使用前需完成 [mtcli 服务登记与验收](references/mtcli-integration.md)；仅安装 npm 包不会自动发布服务定义。

```shell
npm install -g @dp/mtcli@1.1.20 --registry=http://r.npm.sankuai.com
mtcli auth sso login

mt-code-standards pull \
  --repository hfe/duo-hotel-order-submit \
  --stage coding \
  --transport mtcli \
  --output-dir /path/to/workspace \
  --json
```

不传 `--output-dir` 时写入当前目录的 `.mdp/rules/`，目录不需要 `.git`。服务名默认为 `mt-code-standards`；确有其他已登记同合同服务时可加 `--mtcli-service <名称>`，目标网关仍受 allowlist 约束。

mtcli 模式不接受 `--mis`、`--auth-agent`，也不使用 direct 的用户票据环境变量。若 mtcli 的 CIBA 回退需要 MIS，在独立登录命令中使用 `mtcli auth sso login --mis '<你的MIS>'`。`--non-interactive` 只禁止本 CLI 的 MIS 提示，不替代 mtcli 登录；无人值守运行前应已完成官方登录。

调用固定使用生产服务定义和生产目标环境，先校验 dry-run，再调用 `bundles resolve`；显式 bootstrap 条件满足时才调用 `bundles bootstrap`。认证失败、未登记服务或返回异常时停止，不自动切回 direct。平台仍记录真实用户、`execution_agent=cli` 和同一次拉取的 `pull_id`。平台记录说明服务端已分发；本地 receipt 的 `installed/not_modified` 才说明本地结果。

正式拉取未匹配到已登记仓库时停止且不写文件。只有明确需要为未登记仓库安装公开 L1 时才使用 `--transport direct --bootstrap`（或显式 mtcli transport）；此模式需要精确的 `namespace/repository`，非 Git 目录还需 `--domain frontend|backend`。Bootstrap 没有已登记仓库身份，只生成本地回执，不写正式仓库拉取审计。

平台修改已登记仓库的前端/后端类型后，本地文件不会立即变化；升级到支持类型切换的 CLI，并在下一次成功拉取时，才会用新类型的规则替换原有托管文件。CLI 仅在平台返回的正式规则包与本地 manifest 的 `repository_id`、`canonical_key` 完全一致且完整性校验通过时执行替换；非托管文件冲突仍会终止安装并保留原文件。旧版 CLI 会以 `RULE_BUNDLE_DOMAIN_CHANGED` 拒绝此类更新，因此平台迁移仓库类型前应先完成 CLI 升级。

机器调用可增加 `--json`。成功输出 `{ "ok": true, "receipt": ... }`，失败输出 `{ "ok": false, "error": { "code", "message" } }` 并以状态码 2 退出。

## 发布

本仓库根目录同时是 npm 包根目录和 Friday Skill 根目录。Talos 构建使用 Node.js 20；当前已在 Node.js 20.20.2 下验证 `build`、98 项测试和 pack 入口。`build` 只执行语法、包结构、Skill 合同与 mtcli Schema 检查，不生成构建产物：

```shell
nvm use 20
npm run build
npm test
npm pack --dry-run
PACKAGE_DIR=$(mktemp -d /private/tmp/mt-code-standards-package.XXXXXX)
VERIFY_DIR=$(mktemp -d /private/tmp/mt-code-standards-install.XXXXXX)
PACKAGE_TGZ=$(npm pack --silent --pack-destination "$PACKAGE_DIR")
mnpm install --prefix "$VERIFY_DIR" "$PACKAGE_DIR/$PACKAGE_TGZ"
"$VERIFY_DIR/node_modules/.bin/mt-code-standards" --version
```

npm 只通过 Talos 应用 `1000376` 发布，不在本地执行 `npm publish` 或 `mnpm publish`；`mnpm` 仅用于公司源安装与发布结果查询。Talos 构建环境使用 Node.js 20（当前验证版本为 20.20.2），发布插件的包名必须为 `@nibfe/mt-code-standards`。npm 版本由 Talos 流水线自动递增并回写，开发者不在本地执行 `npm version`，也不为发布手工修改 `package.json`、`package-lock.json` 或 `SKILL.md` 的版本。npm 包与 Friday Skill 分别发布、分别管理版本；以 Talos 发布回执和公司 npm 源中的实际版本为准。不要直接套用其他项目的 `npmVersionType`、`npmDistTag`、`usePackageJsonVersion`、`onlyPushProdVersion` 或生产依赖选项；以应用 `1000376` 的实际 Talos 配置和本包合同为准。

Friday Skill ID 为 `150847`。其版本与 npm 版本相互独立；后续更新必须单独切换到 Node.js 24，再执行 `mtskills push --intro auto`，不要再次创建同名条目：

```shell
nvm use 24
mtskills push --intro auto
```

npm、Friday、CatX 和 mtcli 是独立发布单元；按 [接入说明](references/mtcli-integration.md) 分别回读和验收，本仓库提交不会自动完成任一线上发布。
