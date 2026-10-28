# 业务研发平台统一编码规范 CLI

## 安装

```shell
npm install -g @nibfe/mt-code-standards --registry=http://r.npm.sankuai.com
```

## 统一拉取

```shell
mt-code-standards pull --repo-root ./my-project --domain frontend --stage coding
mt-code-standards pull --repository hfe/hotel-web --stage coding --output-dir ./rules
mt-code-standards pull --domain backend --stage cr --json
```

默认 public，一次请求返回领域/阶段匹配的 L1 和可获取的生效 L2。未登记、无 Git、没有 origin 或无可用 L2 时直接返回 L1，无需 bootstrap 参数和第二次请求。匿名保留 active 仓库现有 L2 公开分发策略；认证无可读关联时仅 L1。
阶段必须为 design/coding/cr。领域可从可读登记配置获取，否则需明确 frontend/backend；不扫描源码推断。显式错误地址/领域报具体错误；仓库地址支持完整 namespace/repository 和可归一化线上 MCode Git 地址，不接受裸名。
自动发现的 GitHub 等非 MCode origin 按身份不明处理，使用来源目录兜底取 L1，不访问 origin 主机；显式传入非法或不受支持地址仍报错。
`--repo-root` 或 cwd 为来源目录；能找到 Git 根则以 Git 根定位，无地址时用来源绝对路径作显示名称。`--output-dir` 只决定安装基目录，不参与名称兜底。
默认输出为 `<output-dir 或 repo-root 或 cwd>/.mdp/rules/`。

## 认证与 mtcli

```shell
mt-code-standards pull --repository hfe/hotel-web --stage coding --transport direct --mis your-mis
mt-code-standards pull --domain frontend --stage coding --transport mtcli --json
```

direct 使用官方用户票据，保持当前身份；public 不取票、不继承环境票据。public 的可选 --mis 仅自报标识，不作为权限事实。CLI 的执行 Agent 可通过 --execution-agent 明确，或环境识别；未知独立 CLI 记 cli。
mtcli 固定生产服务定义/环境，先核验 dry-run，再调用 `bundles resolve-unified`；部署前必须登记 assets/mtcli-service.json 的新方法和 Schema。不支持时明确停止，不自动切回 direct。
新请求 `rule-bundle-resolve/v1` 调用 `/v1/public/rule-bundles/resolve` 或 `/v1/rule-bundles/resolve`，只支持 rule-distribution 网关。旧 --bootstrap 仅作为 scope=l1 别名，保持所选认证方式。旧服务需升级，不降级重试旧入口。
认证失败、停用、L1缺失、损坏的订阅和服务失败均报具体 code/message/字段问题/request_id，不伪装无 L2 成功。

## 上报和安装

CLI 记录 client_type=cli、实际 npm name/version，skill_name/version 为 null；Skill 读取实际发行 SKILL.md，setup 和非 setup 名称分别记录，未知值为 null。平台展示名→完整仓库名→来源绝对路径兜底，配套名称来源，不重复上报路径。
服务端记录实际分发模式、原因、快照、Release、规则 UID、字节数及时间；匿名/自报/认证身份明确区分。服务器 ready/not_modified 不代表本地安装成功，本地结果目前不回传。

规则安装到 company/<fe|java>/<规则集名称>/ 与 team/<fe|java>/<规则集名称>/；project/ 为项目自管 L3。
生效包 manifest v8、L1 manifest v5 在旧内容 Hash 之外绑定 resolution 上下文，兼容读取旧清单；内包继续校验 effective-rule-bundle/v4 或 l1-bootstrap-bundle/v3 和 scope-domain-ruleset/v1。
模式切换时原子替换规则和索引，仅移除旧清单认领且未修改的文件；保护未知文件、人工修改、L3 和不同仓库身份。无仓库请求不能清理已有其他 canonical 的正式规则。索引沿用规则集 AGENTS.md 合同，缓存同样核对索引 Hash。
成功 receipt 为 mt-rule-bundle-install/v1，状态 installed/not_modified；展示名或选择原因变化而内容未变时只原子更新清单上下文。

## 发布

本仓库根目录同时是 npm 包根目录和 Friday Skill 根目录。Talos 构建使用 Node.js 20；当前已在 Node.js 20.20.2 下验证 `build`、测试和 pack 入口。`build` 只执行语法、包结构、Skill 合同与 mtcli Schema 检查，不生成构建产物：

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

Friday 上维护两个既有条目，均复用本仓库的同一套源码，不在仓库中维护第二份 Setup 源码：

- `mt-code-standards`：Friday Skill ID 为 `150847`，从仓库根目录直接发布。
- `mt-code-standards-setup`：Setup Skill ID 为 `141006`，通过固定脚本生成一次性临时包；脚本只修改
  `SKILL.md` 的顶层名称和 `agents/openai.yaml` 的默认调用令牌，运行期 Schema、npm 包名和 CLI 命令保持 canonical 值。

两个 Friday 版本均与 npm 版本相互独立。发布 canonical Skill 时必须单独切换到 Node.js 24，再从仓库根目录执行 `mtskills push --intro auto`，不要再次创建同名条目：

```shell
nvm use 24
mtskills push --intro auto
```

发布 Setup Skill 前先用 dry-run 核对目标 ID、文件数和内容 Hash。dry-run 只在系统临时目录生成并删除包，不安装工具、不联网，也不调用 `mtskills`：

```shell
nvm use 24
npm run ps -- --dry-run
npm run ps
```

`ps` 是 `skill:publish:setup` 的别名，长命令仍然保留；例如 `npm run skill:publish:setup -- --dry-run` 与上述预览命令等价。

正式 Setup 发布命令会先运行仓库校验，再从公司 npm 源全局更新 `@mtfe/mtskills`，最后在临时包目录固定执行 `mtskills push --intro auto`。更新全局发布工具是该命令的明确副作用；脚本不会发布 npm、提交或推送 Git，也不会安装全局 Skill。临时包在成功或失败后都会删除。发布完成后仍须从 Friday 回读 ID `141006` 的实际版本和文件内容；源码提交或命令调用成功不能替代线上回读。本轮加入发布脚本本身不表示已实际发布。

npm、Friday、CatX 和 mtcli 是独立发布单元；按 [接入说明](references/mtcli-integration.md) 分别回读和验收，本仓库提交不会自动完成任一线上发布。
