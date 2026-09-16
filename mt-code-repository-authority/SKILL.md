---
name: mt-code-repository-authority
description: "执行平台签发的只读仓库权威任务，通过固定 Runner 获取 Code 仓库负责人及其 Yuntu 组织链并直回调平台。仅用于 CatX 仓库关联预览，不用于人工查人、组织搜索、订阅或 Git 写入。"
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - Metrics

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "141227"
  skillhub.high_sensitive: "false"
---

# 仓库负责人组织权威解析

## 作用和边界

本 Skill 只执行平台生成并挂载到当前 CatX Session 的 `repository-authority-task/v1`。它通过一个固定
Runner 完成以下确定性流程：

1. 校验 task 原始字节 Hash、Schema、身份、仓库 canonical 字段、deadline 和 callback capability。
2. 在 Session 私有目录安装并验证锁定的 `@ee/yuntu-cli@1.0.15`。
3. 使用 `code-cli repo -R <canonical-key> view --json` 读取仓库负责人。
4. 使用 `mtsso-skills-official` 换取 audience 为 `Metrics` 的当前用户票据。
5. 只通过 `YUNTU_ACCESS_TOKEN` 向 Yuntu 子进程临时注入票据，并以 JSON 模式读取负责人组织链。
6. Yuntu 成功后再次读取同一 canonical 仓库，确认负责人 MIS 和默认分支没有在查询窗口内变化。
7. 将 `confirmed`、`unresolved` 或 `failed` 结构化结果直接回调平台。

数据库 job/attempt 是业务状态权威。Agent 回复、Session 状态、工具事件、安装日志、stdout 和结果文件都
不能推进平台状态。Runner 不查询或接收目标组织、规则领域和展示名称，避免把用户期待答案传给解析过程。

平台当前由共享 CatX 账号 `zhangce07` 执行；各看板用户无需单独绑定。Vault/credential 均未配置时使用
CatX 原生 SSO，Edge 创建 Session 时省略 `vault_ids`；两项均配置时，Edge 在派发前校验官方凭据状态
及 owner 并挂载共享 Vault。仅配一项、格式错误或显式凭据未就绪时停止派发，不自动降级。
`task.actor.mis` 保留真实任务发起人，当前用户票据指 CatX 运行环境的执行身份，不从 task 或浏览器构造票据。
Code 和 Metrics 所需权限由共享账号在官方系统取得；配置完整或网关占位符不表示真实授权有效。
来源认证失败按既有合同回调，管理员恢复共享账号的 CatX 授权后才能重新发起，Runner 不自行改换账号或重试。
本 Skill 显式换取的 `Metrics` 票据仅供 Yuntu；`code-cli` 使用其自身认证机制。
验收必须在同一 Session 分别确认 Code 仓库读取、Metrics 换票和 Yuntu 查询成功，不能互相替代。

本 Skill 不执行仓库关联、组织认领、订阅、Git clone/commit/push、浏览器查询、`yuntu sso login` 或
任意员工搜索。IAM empId 增强已保留合同字段，当前版本固定为 `not_requested`，不阻断 Yuntu 组织确认。

## 唯一执行方式

平台消息必须提供任务挂载路径、上传前计算的 task artifact Hash 和结果路径。立即且只执行一次：

```shell
node <skill_dir>/scripts/run-repository-authority.mjs \
  --task /mnt/session/uploads/repository-authority-task.json \
  --task-artifact-hash '<sha256:64hex>' \
  --output /mnt/session/outputs/repository-authority-result.json
```

不要读取 task 后自行重写参数，不要复制 Runner 内部命令，不要手工安装 Yuntu，不要在失败后改用
`drill-org-lookup`、`org-http`、浏览器或说明文本解析。命令非零退出时也不要重跑；平台依据数据库 deadline
和 append-only attempt 提供重试。

Runner 的成功 stdout 只是 `repository-authority-local-receipt/v1` 本地传输回执。真正完成必须是受限 Edge
callback 返回 `repository-authority-callback-receipt/v1` 的 `accepted` 或 `duplicate`，并由平台重新读取
数据库 job 状态。

## 安全规则

- 用户票据必须来自官方 `mtsso-moa-local-exchange --audience Metrics`。`exit=42` 和官方权限错误禁止重试。
- CatX 网关的 `AT_FOR_GW_BASE64_...` 是合法票据占位符，不得把它误判成非 JWT。
- 票据不能进入 task、CLI 参数、结果文件、callback body、日志或回复；只进入单次 Yuntu 子进程环境。
- callback token 只用于 task 指定的 HTTPS host、attempt 路径和 Idempotency-Key，不得发送到其他地址。
- `code-cli` 和 Yuntu 均由 Node `execFile` 参数数组调用，不经过 shell；`~namespace/repository` 不得展开。
- Yuntu stdout 必须整体是 UTF-8 JSON。不得从前后夹杂的解释、Markdown 或日志中截取 JSON。
- 组织 `fullPath` 只用于交叉校验和展示；身份与层级以逐项配对的 `orgIdPath`/名称 chain 为准。
- `/` 是组织路径分隔符，叶子名称和 chain 的单级组织名称中不得包含 `/`，当前不定义转义协议。

跨层 Schema、状态含义和稳定错误码见 [references/contracts.md](references/contracts.md)。只有排障合同或修改
Runner 时才需要读取该文件；普通执行只运行上面的固定命令。
