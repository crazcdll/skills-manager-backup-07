# mt-code-standards 统一拉取接入 mtcli

## 当前合同与发布前置

CLI 使用 `mt-code-standards pull --transport mtcli --domain frontend --stage coding`。
mtcli 负责服务发现、官方 SSO 与 HTTP；客户端负责本地上下文、响应校验和原子安装。
本轮仅交付本地定义，不代表线上已登记。服务维护人应回读实际服务元数据，再追加 [assets/mtcli-service.json](../assets/mtcli-service.json) 的统一方法，保留其他方法和实际 ID，不以历史文件中的 ID 猜测管理入口。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| bundles resolve-unified | POST /v1/rule-bundles/resolve | 新默认统一解析 |
| bundles resolve | POST /v1/effective-rule-bundles/resolve | 保留旧客户端兼容 |
| bundles bootstrap | POST /v1/l1-rule-bundles/bootstrap | 保留旧客户端兼容 |

统一入口固定 rule-distribution 网关、生产 schema/target、SSO audience `923a237244`。
新请求 `rule-bundle-resolve/v1` 的 repository_locator 可空，stage 必填；standard_domain 可由可读登记配置补齐，否则必须提供。
新 execution 支持 nullable skill_name/version（两个真实 Skill 名称 mt-code-standards、mt-code-standards-setup），以及 client_type/name/version。独立 CLI 上报真实 npm 名称与版本，Skill 字段为 null；Agent 来源独立记录。
目标信息仅为 target.display_name/source，不重复传目录字段；无仓库地址时使用来源目录绝对路径，不用于 L2 匹配。
响应 `rule-bundle-resolution/v1` 内包复用 effective-rule-bundle/v4 或 l1-bootstrap-bundle/v3，明确 bundle_kind、delivery_mode、selection_reason 与 request_id/pull_id。
旧 --bootstrap 参数变成统一请求 scope=l1，不切换认证。未登记、没有可获取的 L2 时正常返回 L1，SSO/停用/数据故障仍明确失败。

## dry-run 与真实验收

每次调用先验证 dry-run 的完整 URL、POST、SSO、body、协议头和空 query，再执行 resolve-unified。Schema 丢失 nullable 字段、改变请求或仍指旧路径时明确停止，不回退旧方法/direct。
子进程固定生产环境且不继承客户端 direct/Agent 票据；不输出原始 stdout/stderr 或认证凭据。
包目录和索引分别遵守 scope-domain-ruleset/v1 与 rule-set-agents-index/v1，完整业务规则保持原大小预算。

验收包含：已登记有 L2、无 L2、未登记、无地址目录、认证无关联、缺参数、非法参数、无匹配 L1、Hash 错误、幂等重放和本地文件保护。核对统一分发事件的已认证身份、真实客户端版本与字段来源；平台 ready 不代表本地 installed。
发布顺序为数据库前向迁移 → rule-distribution → mtcli 服务定义更新与回读 → CLI Talos/Friday 独立发布 → 实际使用者 CatX 技能包。npm 版本由 Talos 管理，不手工改号。Friday 发布使用 Node.js 24，不能用源码提交替代运行时验收。

## 历史 CLIHub 登记参考（2026-10-07）

下文只保留历史平台注册与版本回执，版本、接口、参数和安装命令不代表当前发布状态；当前使用以上统一合同，所有新拉取必须明确 stage。

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
