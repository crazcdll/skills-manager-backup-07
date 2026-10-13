# mt-code-standards CLI 接入 mtcli

本地命令为 `mt-code-standards pull --transport mtcli`。mtcli 负责发现服务、官方 SSO 和 HTTP 调用，本 CLI 负责仓库定位、规则包校验、增量更新、用户文件保护及 `.mdp/rules/` 原子安装。直接执行 `mtcli … bundles resolve` 只返回 JSON，不会安装本地文件。

本次适配以官方 `@dp/mtcli 1.1.20` 的实际 dry-run 和执行输出为依据。公司接入入口说明见 [mtcli 文档](https://km.sankuai.com/collabpage/2754306714)。

## 1. 补充已有服务定义

2026-10-07 通过 CLIHub 管理接口回读：`mt-code-standards` 的工具 ID 为 `2851`，关联服务地址记录 ID 为 `1818`，类型为 `mtcli`，生产 SSO audience 为 `923a237244`。此前材料中的 `3469` 本次未能作为工具 ID 查到，不再据此定位管理页面。`bundles resolve` 的线上展开 Schema 已确认 `execution.skill_name` 枚举仅为 `mt-code-standards`，`skill_version` 为普通 string，不限定某个发布版本。数据库的新名称合同与生产 `rule-distribution` v7 曾在此前验收中回读；本轮没有重新执行生产拉取，bootstrap 也未补做真实未登记仓库验收。更新前应重新回读 [服务发现接口](https://friday.sankuai.com/open/cli/tool/services/mt-code-standards)，保留平台上其他人新增的方法及服务元数据。

将 [原生定义](../assets/mtcli-service.json) 中的 `resources.bundles` 作为登记材料，交由有权限的服务维护人在 mtcli 管理入口补充。文件采用服务发现接口的原生格式；它不是已验证的管理接口写入 payload，不自行猜测导入/更新命令。保留已有服务 ID、名称和归属，按管理入口要求填写实际 owner、服务 AppKey（若要求），不要将空 `serverAppKey` 当成已完成配置。

| 方法 | HTTP 路径 | 身份与用途 |
| --- | --- | --- |
| `mt-code-standards bundles resolve` | `POST /v1/effective-rule-bundles/resolve` | 正式仓库规则包，服务端写拉取记录 |
| `mt-code-standards bundles bootstrap` | `POST /v1/l1-rule-bundles/bootstrap` | 确认未登记的单领域仓库公开 L1，不写正式仓库拉取记录 |

两个方法的生产服务地址均为 `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution`，`authType=SSO`，目标 `clientId/clientIds` 为 `923a237244`。这是目标服务 audience，不是用户需要填写的调用方 secret。方法参数须保留 `body`（`type=object, location=body`），否则 mtcli 不会生成 `--json` 参数。

通过 `--params` 传入固定协议头：`X-Rule-Auth-Source=mtcli-sso`、`X-Rule-Protocol-Version=1.0`。请求体使用 `--json`。不在定义中放置 Authorization、Cookie、静态 token 或手工 MIS。`contentType=application/json`；真实 mtcli dry-run 不一定回显 Content-Type，适配器允许缺省，若回显则必须匹配。`authType=SSO` 的真实 mtcli 1.1.x 请求会自动携带目标 audience 对应的短期 `923a237244_ssoid` Cookie，不能假设它会发送 `Authorization: Bearer`；该来源只用于 mtcli 的短期 SSO 票据，网关严格提取目标 Cookie 后交由生产 NoCode 用户接口校验并记录返回的真实 MIS；显式 direct/Skill 路径继续使用原有 `nocode-agent-sso`。

## 2. 确认 SSO 与拉取审计

维护人与认证/服务负责人核对 mtcli 调用方是否已获得目标 audience 的官方 SSO 授权，及票据是否按 mtcli 约定传入。仅配置 `authType=SSO` 不能证明这一点；本地合成数据测试不代表真实 SSO 已联通。

mtcli-sso 分支兼容 mtcli 的 `923a237244_ssoid` Cookie（也保留 Bearer 兼容路径），由 Edge 调用生产 NoCode 用户接口校验短期票据并解析返回的真实 MIS；Skill 的 `nocode-agent-sso` 分支继续走同一接口。Edge 只接受精确目标 Cookie 名，拒绝错误 audience、空值、重复 Cookie 以及无效 Cookie。两条路径都不以 `--mis`、Git 作者或本机账号推断身份。无需新增数据库字段；正式 resolve 请求仍携带：

此前已确认 mtcli 1.1.20 的目标 audience Cookie 传输形态，并通过本地 mock 验证 Cookie 提取、拒绝异常 Cookie 及 Bearer 兼容路径。生产数据库合同和 Edge v7 已接受 `mt-code-standards`；本轮已回读 resolve 展开 Schema，但仍需用 Talos 实际发布的 npm 版本完成一次真实规范拉取和平台审计验收。

```json
{
  "repository_locator": "hfe/your-repository",
  "stage": "coding",
  "execution": {
    "pull_id": "<本次拉取 UUID>",
    "execution_agent": "cli",
    "execution_agent_source": "runner_explicit_v1",
    "skill_name": "mt-code-standards",
    "skill_version": "<当前 CLI 包版本>"
  }
}
```

当前 CLI 包版本可通过 `mt-code-standards --version` 查询，CLI 默认自动填入该值，不要求用户手工传入 `--skill-version`。

平台的 `effective_rule_bundle_pull_events` 记录服务端分发结果 `ready/not_modified`。通过 receipt 的 `pull_id` 回读对应记录，核对 actor MIS、仓库、快照、规则和 Release 引用、CLI 来源；本地 `installed` 不替代平台审计回读，平台 `ready` 也不证明本地安装成功。bootstrap 请求只保留既有仓库定位、领域、阶段和快照字段，不冒充正式仓库记录。

## 3. 服务定义回读与真实验收

登记后回读服务发现接口，确认两个方法、生产 URL、POST、SSO、audience、JSON body 和协议头。使用 `mtcli --no-cache … --dry-run` 核对新定义；此步骤不调用业务接口。随后使用实际有权访问的仓库：

```shell
npm install -g @dp/mtcli@1.1.20 --registry=http://r.npm.sankuai.com
mtcli auth sso login
mtcli auth sso whoami
mt-code-standards pull --repository '<namespace/repository>' \
  --stage coding --transport mtcli --output-dir '<验收目录>' --json
```

先在当前构建的本地 tarball 安装版本上验收，再开放给团队：

1. 在没有 `.git` 的目录按仓库名称拉取，确认 `.mdp/rules/`、manifest、逐文件 Hash 和 receipt 一致；指定输出目录时结果写入该目录。
2. 再次拉取收到 `not_modified`，仍有新的 `pull_id` 审计；同一个幂等 ID 重放不重复记账。
3. Java 仓库切换 `coding/cr`，核对阶段与文件集合，保留用户添加的规则。
4. 对无权限、未登记、名称歧义、SSO 失败和 Hash 异常，确认无部分安装、旧文件不变；仅显式 bootstrap 且满足原有条件时才能安装公开 L1。
5. 平台回读真实用户的正式拉取记录；登录成功但记录错误时不能作为接入验收通过。

如认证或响应不兼容，停止 mtcli 上线；公开仓库继续使用默认 public 路径，需要用户权限时显式使用 direct。不要修改为共享账号、静态票据或伪造用户身份。

## 4. 发布顺序与边界

1. 数据库的新名称合同与 `rule-distribution` Edge v7 已部署并回读；真实验收前再次核对健康检查的版本和能力，不能以源码替代线上状态。
2. 服务维护人回读 mtcli 服务定义，确认 `execution.skill_name` 的枚举只包含 `mt-code-standards`。保存后执行 `mtcli --no-cache --mtcli-schema-env prod schema mt-code-standards.bundles.resolve --resolve-refs`，确认展开结果与 [登记材料](../assets/mtcli-service.json) 一致，再完成真实 SSO 与审计验收。
3. CLI 维护人在本仓库根目录使用 Node.js 20 执行 `npm run build`、`npm test` 和 `npm pack --dry-run`；当前已在 Node.js 20.20.2 下验证构建、测试和 pack 入口。用 `--pack-destination` 打包到临时目录，通过 `mnpm install --prefix <临时目录> <实际 tgz>` 验证。npm 包仅通过 Talos 应用 `1000376` 发布；Talos 构建环境使用 Node.js 20，并自动递增、回写 npm 版本，禁止本地执行 `npm version`、`npm publish` 或 `mnpm publish`，也不得为了同步版本而修改 `SKILL.md`。
4. Friday Skill ID 为 `150847`，其版本与 npm 版本相互独立；后续必须单独执行 `nvm use 24`，再使用 `mtskills push --intro auto` 更新，不再次 `publish` 新条目。完成后如 CatX Managed Agent 实际使用该 Skill，再更新 CatX 技能包并回读实际版本；npm 发布不会更新 Friday 或 CatX。

本次代码迁移不需要修改 NoCode Board、数据库迁移、Edge Function 或业务环境变量；这些线上单元的现状仍需在最终验收时独立回读。客户端要求 Node.js >=18、公司内网访问和已安装的官方 mtcli；Talos 发布与本轮测试使用 Node.js 20，当前验证版本为 20.20.2。Friday 的 `mtskills` 操作仍使用 Node.js 24。客户端固定 prod schema/target，禁止继承环境选择到测试服务。

每次远程请求先校验 dry-run URL、POST、SSO、JSON body、协议头与空 query；拒绝附加静态认证头，业务响应仍限制 4 MiB。子进程只接收参数数组，不经 shell，不继承本 CLI 的 direct/Agent 票据；错误不回显原始 stdout/stderr。客户端关闭 mtcli 更新提示，保留 JSON 输出可解析性。

dry-run 和执行是两个 mtcli 进程，不能固定同一份远程定义；认证和 HTTP 重定向由官方 mtcli 管理。这一路径依赖可信的 mtcli 安装及服务登记，不宣称与 direct 的 `redirect: error` 完全相同。服务迁址或认证方式变更时须重新验收。CLI 的 `--gateway-url` 不改写 mtcli 注册地址；两端不匹配会在 dry-run 停止。

## 5. 已发布 npm 包登记到 CLIHub

### 5.1 本次确认的发布状态

2026-10-07 从公司 npm 源查询并在独立临时目录安装了 `@nibfe/mt-code-standards@1.2.1-beta.0`：包内共 9 个文件，bin 为 `mt-code-standards`，要求 Node.js >=18；在 Node.js 20.20.2 下 `--help`、`--version` 均通过。查询时 `beta` 和 `latest` 都指向此版本，这只是本次快照，后续以 `mnpm view` 为准。

```shell
mnpm view @nibfe/mt-code-standards version dist-tags bin engines --json
mnpm install -g @nibfe/mt-code-standards@1.2.1-beta.0
mnpm install -g @dp/mtcli@1.1.20
mt-code-standards --version
mt-code-standards --help
mtcli version
```

以上安装后的命令不依赖源码仓库路径。这里固定 beta 版本用于复现本次验收；推广新版本时使用 Talos 的实际发布版本，不在本地手工升版。

### 5.2 选择普通 npm CLI 登记

打开 [CLIHub 内部广场](https://friday.sankuai.com/skills/cli-market)，先搜索 `mt-code-standards`。当前已有条目是 [MTCLI 工具 2851](https://friday.sankuai.com/skills/cli-detail?activeTab=info&id=2851)，其作用是暴露远端 API；不得用 npm 工具登记覆盖它或直接切换其类型。

点击“提交 CLI 工具”，按官方快速导入说明，将“以 MTCLI 方式发布”选为“否”，安装方式选择 npm。建议先仅自己或团队可见，完成验收后再调整可见范围。

| 字段 | 本工具填写内容 |
| --- | --- |
| CLI 类型 | 普通/其他，对应 `cliType=other` |
| 安装方式 | npm，对应 `installType=npm` |
| 工具名称 | `mt-code-standards` 已被上述 MTCLI 条目占用；可拟用 `mt-code-standards-cli`，先通过平台名称与命令入口校验 |
| 中文别名 | 业务编码规范 CLI |
| npm 包 | `@nibfe/mt-code-standards`，体现在安装命令中 |
| 安装命令 | `mnpm install -g @nibfe/mt-code-standards@1.2.1-beta.0` |
| 管理员 | `zhangce07`，其他成员按实际需要添加 |
| 代码仓库 | `ssh://git@git.sankuai.com/nibfe/mt-coding-standards.git` |
| 关联 Skill | `150847`，保存前回读确认仍对应 `mt-code-standards` |
| 支持平台 | 本轮已验证 macOS；Linux/Windows 应在验收后再声明支持 |
| 使用示例 | `mt-code-standards --help` 及下一节的 pull 命令 |

可直接填写的工具描述：

> 按仓库名称或地址从业务研发平台拉取订阅的有效编码规范，支持在无 Git 的任意目录运行，并写入当前或指定目录的 .mdp/rules/。提供分阶段拉取、增量同步、文件校验和用户文件保护；可通过 mtcli SSO 调用平台，保留可信用户的正式拉取审计记录。

`mnpm` 是用户环境中的公司 npm 别名。如果平台自动安装环境没有这个别名，官方文档提供的等价安装形式为 `npm install -g @nibfe/mt-code-standards@1.2.1-beta.0 --registry=http://r.npm.sankuai.com`；如需私有安装凭据，沿用环境已有的公司源配置，不在登记材料中放 token。

工具名称全局唯一且创建后不可修改。`mt-code-standards-cli` 只是待确认的广场标识方案，当前 npm 包并没有这个 bin。官方资料未明确说明广场标识与实际 bin 不同的映射行为，因此不能据此宣称自动 Agent 路由或视图代理已可用。若创建页/命令树强制名称等于 bin，应先解决现有名称占用及入口映射，再提交；本轮没有新增命令别名、迁移现有服务或执行平台注册。

### 5.3 配置命令树与使用说明

本工具的可执行叶子命令是 `mt-code-standards pull`，`--help` 和 `--version` 是根命令选项。可以在新 npm 条目的命令树中手工维护；也可按 [快速导入命令树文档](https://km.sankuai.com/collabpage/2760640745) 安装 `mcphub-cli-tree-importer`，指定本仓库和新建的 npm CLI ID 生成并上传命令树。不要把 npm 命令树导入现有 MTCLI 条目 2851。

核心参数如下；完整参数以已安装包的 `mt-code-standards --help` 为准：

| 参数 | 类型/可选值 | 说明 |
| --- | --- | --- |
| `--repository` | string | 仓库名称或地址；无 Git 目录必须显式提供，Git 目录可自动探测 |
| `--output-dir` | string，可选 | 基目录；实际写入其下 `.mdp/rules/`，默认当前目录 |
| `--stage` | `design` / `coding` / `cr`，可选 | 不传时使用 legacy 规则包 |
| `--transport` | `public` / `direct` / `mtcli` | 当前代码默认 public；本接入示例显式指定 mtcli |
| `--json` | boolean | 输出机器可读结果 |
| `--non-interactive` | boolean | 禁止本 CLI 的 MIS 提示，不代替 mtcli 的预先登录 |

安装说明同时列出 Node.js >=18（推荐本次验证的 Node 20）与 `@dp/mtcli`。本 npm 包不会自动全局安装 mtcli；使用 mtcli transport 时必须单独准备。

### 5.4 在任意目录验收

```shell
mtcli --mtcli-target-env prod auth sso login --mis '<你的MIS>'
mtcli --no-cache --mtcli-schema-env prod \
  schema mt-code-standards.bundles.resolve --resolve-refs

RULE_TEST_DIR=$(mktemp -d /private/tmp/mt-code-standards-real.XXXXXX)
mt-code-standards pull \
  --repository l2-rules-test \
  --stage coding \
  --transport mtcli \
  --output-dir "$RULE_TEST_DIR" \
  --json
printf '规则目录：%s/.mdp/rules/\n' "$RULE_TEST_DIR"
```

`l2-rules-test` 是本维护人的测试仓库；其他用户需替换为平台已登记且自己有权访问的仓库。核对输出 `ok=true`、receipt 的 `installed/not_modified`、`authentication_mode=mtcli_sso`、实际规则文件，再通过同一个 `pull_id` 在平台回读真实用户与“独立 CLI”拉取记录。只有上述步骤均通过才算该已发布 npm 版本的真实拉取验收。本轮仅执行包安装/help/version 和线上 Schema/管理配置回读，未新增真实拉取记录。

### 5.5 可选的统一调用入口

普通 npm CLI 登记成功不等于新增 `mtcli mt-code-standards pull` 命令。当前官方 MTCLI 是动态 HTTP API 客户端，本地文件安装继续由 `mt-code-standards pull --transport mtcli` 执行；其调用仍使用已有 MTCLI 的 SSO 能力。

如希望统一安装和调用多个工具，可使用 CLIHub“视图管理”：创建视图、加入工具、保存并点击“上线”，再复制视图详情页右侧“代理命令安装”。官方无领域模式为 `<视图名> <CLI名> <命令> [参数...]`，有领域模式为 `<视图名> <领域名> <CLI名> <命令> [参数...]`。具体代理命令应从平台生成结果复制；必须先完成上述名称/bin 映射和端到端验收，不能自行假定代理名称或 mtcli 子命令。

### 5.6 官方参考

- [CLIHub 用户指南](https://km.sankuai.com/collabpage/2761369424)：内部版、npm 分发、MTCLI 与视图的能力范围。
- [CLIHub 内部版 OpenCLI 工具管理命令手册](https://km.sankuai.com/collabpage/2761861771)：登记字段与普通 npm / MTCLI 类型区别；执行管理命令前以当前 Schema 为准。
- [CLIHub 内部版快速导入命令树](https://km.sankuai.com/collabpage/2760640745)：选择非 MTCLI 方式及命令树导入 Skill。
- [视图管理——将多个 CLI 组合使用](https://km.sankuai.com/collabpage/2762471416)：统一安装、上线和视图代理格式。
- [MTCLI 使用说明](https://km.sankuai.com/collabpage/2754306714)：SSO、Schema、dry-run 与 HTTP 调用。
- [MNPM 常见问题](https://km.sankuai.com/collabpage/127620956)：mnpm 别名、公司源与 Talos 发包说明。
