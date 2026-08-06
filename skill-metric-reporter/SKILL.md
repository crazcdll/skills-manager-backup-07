---
name: skill-metric-reporter
description: Skill 指标上报工具。由其他 Skill 在执行开始和结束时主动调用，用于上报执行时长、成功状态、Token 消耗等运行指标。

metadata:
  skillhub.creator: "liumingyu04"
  skillhub.updater: "liumingyu04"
  skillhub.version: "V15"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "28531"
  skillhub.high_sensitive: "false"
---

## 上报规则

每次执行目标 Skill 时，必须严格完成以下两次调用，不得跳过、合并或复用历史上报。

**脚本路径**：`{SKILL_DIR}/scripts/report_skill_metric.sh`（`{SKILL_DIR}` 为本 Skill 所在目录绝对路径）

**⚠️ 关键约束：`skill_start` 与 `skill_end` 必须使用完全相同的 `--request-id`，禁止在 `skill_end` 时重新获取或生成。**

**参数说明**：
- `{REQUEST_ID}`：
  - **`skill_start` 时**：依次取上下文中 `conversationId` → `requestId`/`turnId` → `sessionId`，均不存在则自行生成，格式为 `{目标Skill名}-{userMis}-{毫秒时间戳}`。其中毫秒时间戳为**13位纯数字**（当前 Unix 毫秒时间，格式如 `17441XXXXXXXX`，**禁止照抄此格式，必须使用当前真实时间对应的数值**），**禁止带任何字母后缀（如 `N`、`L`）**。**确定后立即记住该值并放入上下文。**
  - **`skill_end` 时**：**直接使用上面已记住的值，禁止重新生成。**
- `{USER_MIS}`：当前用户 MIS 号
- `{MODEL_NAME}`：当前模型名称
- `skill-name`：目标 Skill frontmatter 的 `name` 字段
- `skill-id`：目标 Skill frontmatter 的 `metadata.skillhub.skill_id`；不存在传空字符串
- `skill-version`：目标 Skill frontmatter 的 `metadata.skillhub.version`；不存在传空字符串
- `success`：`skill_end` 时必填；完整产出预期结果填 `true`，遇到工具报错/环境异常/流程中断/输出严重偏差填 `false`
- `failure-reason`：`success=false` 时填写，一句话描述阻断性问题；`success=true` 时省略
- `input-tokens`/`output-tokens`：**必填**，从上下文读取或估算当前对话的输入/输出 Token 数，无法精确读取时按内容量合理估算，不得省略
- `source`：当前客户端 Agent 类型，可选值为 `catclaw`（OpenClaw 也传此值）/ `catdesk` / `catpaw`；无法识别时传 `unknown`
- 时间戳由脚本内部自动获取，**无需手动传入**

**步骤一：目标 Skill 执行任何操作之前**

```bash
{SKILL_DIR}/scripts/report_skill_metric.sh \
  --request-id "{REQUEST_ID}" --user-mis "{USER_MIS}" \
  --skill-name "{目标Skill名}" --skill-id "{目标Skill ID}" --skill-version "{目标Skill版本}" \
  --phase skill_start --model-name "{MODEL_NAME}" --source "{SOURCE}"
```

**步骤二：目标 Skill 全部操作完成之后**

```bash
{SKILL_DIR}/scripts/report_skill_metric.sh \
  --request-id "{REQUEST_ID}" --user-mis "{USER_MIS}" \
  --skill-name "{目标Skill名}" --skill-id "{目标Skill ID}" --skill-version "{目标Skill版本}" \
  --phase skill_end --success {true|false} \
  --failure-reason "{失败原因}" --input-tokens {n} --output-tokens {n} --source "{SOURCE}"
```
