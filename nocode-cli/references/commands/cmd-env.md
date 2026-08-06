# env 命令详细规则 — 对话/作品环境变量管理

## ⚠️ 触发条件

**只有当对话/作品需要区分线上 (Prod) / 线下 (Test) 环境变量时，才使用 `nocode env` 命令和 `deploy --chatEnv`。** 普通部署场景无需关心环境变量，直接 `nocode deploy <chatId>` 即可。

## 概述

管理对话/作品的环境变量。每个对话/作品支持两套环境变量：**线上 (prod)** 和 **线下 (test)**，通过 `--chatEnv` 指定操作哪套，默认 `prod`。


## 命令列表

### env list — 查看对话/作品全部环境变量

```bash
nocode env list <chatId>
nocode env list <chatId> --json    # JSON 格式输出
```

同时显示对话/作品线上 + 线下两套变量，并标识当前生效环境。

### env set — 设置对话/作品环境变量

**⛔ 必须先询问用户：** 执行 `env set` 前，必须暂停并明确询问用户以下信息，禁止自行猜测或编造变量名和值：
1. **变量名是什么？**（如 `VITE_API_URL`、`VITE_ENV`）
2. **变量值是什么？**（如 `https://api.example.com`、`production`）
3. **设置到哪套环境？**（线上 prod / 线下 test，默认 prod）

```bash
nocode env set <chatId> <key> <value>                    # 设置到对话/作品线上（默认）
nocode env set <chatId> <key> <value> --chatEnv test     # 设置到对话/作品线下
```

**规则：**
- 变量名必须以 `VITE_` 开头
- 变量名必须全部大写（小写会提示正确写法）
- 变量名只能由大写字母、数字和下划线组成，且以大写字母开头
- 变量值不能为空
- 变量已存在时自动更新，不存在时新增
- `--chatEnv` 只支持 `prod` 或 `test`

### env delete — 删除对话/作品环境变量

```bash
nocode env delete <chatId> <key>                    # 从对话/作品线上删除（默认）
nocode env delete <chatId> <key> --chatEnv test     # 从对话/作品线下删除
```

`--chatEnv` 只支持 `prod` 或 `test`。

### env switch — 切换对话/作品当前生效环境

```bash
nocode env switch <chatId>                    # 切换到对话/作品线上（默认）
nocode env switch <chatId> --chatEnv test     # 切换到对话/作品线下
```

切换后容器会使用对应环境的变量。已经是目标环境时会提示无需切换。

## 典型流程

```bash
# 1. 查看当前环境变量
nocode env list <chatId>

# 2. 配置对话/作品线上变量
nocode env set <chatId> VITE_ENV prod

# 3. 配置对话/作品线下变量
nocode env set <chatId> VITE_ENV test --chatEnv test

# 4. 切换到对话/作品线下环境
nocode env switch <chatId> --chatEnv test

# 5. 使用对话/作品线下环境变量部署
nocode deploy <chatId> --chatEnv test --skillId <SKILL_ID>

# 6. 切回对话/作品线上，使用线上环境变量部署
nocode env switch <chatId> --chatEnv prod
nocode deploy <chatId> --chatEnv prod --skillId <SKILL_ID>
```

## ⚠️ 注意事项

- 必须先通过 `env set` 配置了环境变量，才能通过 `deploy --chatEnv` 指定环境部署
- 部署前 `--chatEnv` 只做校验不会自动切换环境，环境不匹配时会报错并提示先执行 `env switch`
- `--chatEnv` 只支持 `prod` 或 `test`，传其他值会报错
- 环境变量的增删改会触发一次新版本生成
- 部署相关的详细规则见 [deploy 命令规则](cmd-deploy.md)

