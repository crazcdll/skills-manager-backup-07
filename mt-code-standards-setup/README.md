# mt-code-standards

独立拉取业务研发平台为仓库解析出的有效编码规范。CLI 与 Setup Skill 共用同一套下载、校验、增量更新和原子回滚实现。

## 安装

使用 Node.js 18 或更高版本，并从公司 npm 源安装：

```shell
npm install -g mt-code-standards-setup --registry=http://r.npm.sankuai.com
```

## 使用

在任意目录按唯一仓库名拉取，默认写入当前目录的 `.mdp/rules/`：

```shell
mt-code-standards pull --repository duo-hotel-order-submit --mis '<你的MIS>'
```

指定输出基目录：

```shell
mt-code-standards pull \
  --repository hfe/duo-hotel-order-submit \
  --output-dir /path/to/workspace \
  --mis '<你的MIS>'
```

后端规则按研发阶段拉取：方案/编码阶段使用精简 L1，CR 阶段使用全量 L1：

```shell
mt-code-standards pull \
  --repository hbar/your-java-repo \
  --stage coding \
  --mis '<你的MIS>'

mt-code-standards pull \
  --repository hbar/your-java-repo \
  --stage cr \
  --mis '<你的MIS>'
```

`--repo-root` 用于兼容原 Setup Runner：它作为 Git 自动探测目录；没有 `--output-dir` 时也作为输出基目录。优先级为 `--output-dir`、`--repo-root`、当前目录。

`--stage` 可选值为 `design`、`coding`、`cr`。显式传入阶段时，规则包会校验阶段化响应和依赖哈希；不传时保持旧的 legacy 拉取行为。

CLI 使用当前用户 CIBA 票据访问平台，`--mis` 或 `SSO_USER_ID` 仅作为登录提示。可信操作人由服务端验证票据后确定；票据不会写入参数、规则文件、manifest 或公共输出。非交互环境必须显式提供 MIS。

正式拉取未匹配到已登记仓库时停止且不写文件。只有明确需要为未登记仓库安装公开 L1 时才使用 `--bootstrap`；此模式需要精确的 `namespace/repository`，非 Git 目录还需 `--domain frontend|backend`。Bootstrap 没有已登记仓库身份，只生成本地回执，不写正式仓库拉取审计。

机器调用可增加 `--json`。成功输出 `{ "ok": true, "receipt": ... }`，失败输出 `{ "ok": false, "error": { "code", "message" } }` 并以状态码 2 退出。

## 发布

当前仓库只准备了 npm 包，尚未发布。可以在 `setup-skills/` 执行 `npm pack`，再用生成的本地 `.tgz` 验证：

```shell
npm install -g ./mt-code-standards-setup-1.0.0.tgz
mt-code-standards --version
```

正式发布前使用 Node.js 24 执行测试和 `npm pack --dry-run`，再发布到 `publishConfig.registry`。本仓库变更不自动执行 npm 发布、Friday Skill 更新或 CatX 技能包更新。
