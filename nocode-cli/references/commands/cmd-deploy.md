# deploy 命令详细规则

## deploy — 部署应用

部署应用到线上。自动从版本列表获取最新版本的 commitId 进行部署，也可通过 `--commit-id` 指定版本。

```bash
nocode deploy <chatId> --skillId <SKILL_ID>                           # 部署最新版本
nocode deploy <chatId> --commit-id <commitId> --skillId <SKILL_ID>    # 部署指定版本
nocode deploy <chatId> --chatEnv test --skillId <SKILL_ID>            # 使用对话/作品线下环境变量部署
nocode deploy <chatId> --chatEnv prod --skillId <SKILL_ID>            # 使用对话/作品线上环境变量部署（默认）
```

**流程：**
1. 获取版本列表（`getVersions`）
2. 使用最新版本的 commitId（或用户指定的 commitId）
3. 如果指定了 `--chatEnv`，校验当前容器环境是否匹配，不匹配则报错
4. 调用部署 API（`deploy`）

**注意：** 部署不需要容器运行，只需要有效的 commitId。

## 对话/作品环境变量部署（--chatEnv）

**⚠️ 使用 `--chatEnv` 参数前，必须先读取 [env 命令规则](cmd-env.md) 并按其中的规则执行。**

**⚠️ 仅当对话/作品需要区分线上 (Prod) / 线下 (Test) 环境变量部署时才使用 `--chatEnv`。** 普通部署场景直接 `nocode deploy <chatId>` 即可，无需传 `--chatEnv`。

通过 `--chatEnv` 可以指定部署时使用哪套对话/作品环境变量：

- `--chatEnv prod`：使用对话/作品线上环境变量部署
- `--chatEnv test`：使用对话/作品线下环境变量部署

**前置条件：**
1. 必须先通过 `nocode env set` 配置了对应环境的变量
2. 当前容器生效环境必须与 `--chatEnv` 一致，否则会报错

**未指定 `--chatEnv` 时的行为：**
- 统一走线上部署，当前容器环境必须是 prod
- 如果当前环境是 test，报错提示切回线上或使用 `--chatEnv test`
- 如果当前环境是 prod 且配置了线上环境变量，自动携带 `deployEnv`

**指定 `--chatEnv` 时的校验顺序：**
1. 先检查当前容器环境是否与目标一致 → 不一致报错提示 `env switch`
2. 再检查目标环境是否已配置环境变量 → 未配置报错提示 `env set`

**报错情况：**
- 当前环境是 test 但未指定 `--chatEnv`：提示切回线上或使用 `--chatEnv test` 部署线下
- 环境不匹配时：`当前生效环境为线上 (prod)，与目标线下 (test)不一致`，并提示 `请先执行: nocode env switch <chatId> --chatEnv test`
- 未配置环境变量时：`作品未配置线下 (test)环境变量，请先通过 nocode env set 配置`

**完整流程示例：**
```bash
# 1. 配置对话/作品线下环境变量
nocode env set <chatId> VITE_ENV test --chatEnv test

# 2. 切换到对话/作品线下环境
nocode env switch <chatId> --chatEnv test

# 3. 部署（使用对话/作品线下环境变量）
nocode deploy <chatId> --chatEnv test --skillId <SKILL_ID>
```

## ⚠️ 渲染失败拦截

如果最新版本渲染失败（`renderStatus === false`），CLI 会直接报错中止：

```
最新版本 (xxxxxxxx) 渲染失败，无法部署。请进入对话查看异常渲染情况，有问题请联系 NoCode 研发协助处理
```

**⛔ 遇到此错误时，严禁自行尝试修复（如尝试通过 `nocode send` 修复渲染问题、反复重试部署等）。** 必须立即停止操作，引导用户联系 NoCode 研发排查处理。

## ⚠️ 最终展示格式（强制）

部署成功后，向用户展示部署地址。链接格式规则见 [SKILL.md](../../SKILL.md)「链接与展示」章节，部署地址使用 `[{externalUrl}]({externalUrl})` 格式。

## ⚠️ 常见错误

| 错误信息 | 处理方式 |
|---------|---------|
| `暂无可部署版本` | 先执行创建或修改命令生成代码 |
| `最新版本渲染失败，无法部署` | **⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查处理 |
| `指定的版本不存在` | 使用 `nocode versions <chatId>` 查看可用版本 |
| `作品未配置xx环境变量` | 先通过 `nocode env set` 添加环境变量 |
| `当前生效环境与目标不一致` | 先执行 `nocode env switch` 切换环境 |
| `当前作品生效环境为线下 (test)，默认部署需要线上 (prod) 环境` | 使用 `--chatEnv test` 部署线下，或 `env switch` 切回线上 |
| `--chatEnv 只支持 prod 或 test` | `--chatEnv` 仅接受 `prod` 或 `test` |

