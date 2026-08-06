---
name: qahome
description: "QAHome 质量保障平台工具。当用户提到：查验证码、查短信、帮我查一下手机号的验证码、查一下 138xxxx 的验证码、获取登录验证码、短信验证码、qahome 短信、smsqueue、查userId、查手机号、userId查手机号、手机号查userId、用户信息查询、mobileNo查询、创建账号、注册账号、创建测试账号、注册新用户、regNewUser、新建账号、生成测试账号 时激活。NOT：与 qahome 无关的短信、其他平台验证码查询。"
version: "1.0.0"
appkey: com.sankuai.qahome.platform.web

skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - b399154e46
    prompt: 本技能所需的token占位符，请参考mtsso-skills-official的相关说明进行获取和注入

metadata:
  skillhub.creator: "chenlinjie03"
  skillhub.updater: "rennannan"
  skillhub.version: "V12"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "26639"
  skillhub.high_sensitive: "false"
---

ℹ️ 环境说明：本 Skill 所有操作均针对 QAHome 测试环境，查询对象为测试账户（测试手机号、测试 userId），无真实用户账户风险。

## 查验证码工作流

### 阶段 1：调用短信查询接口

⚠️ REQUIRED - 从用户输入中提取手机号，支持格式：11位数字、带+86前缀

> ⚠️ 安全提示：手机号仅用于构造查询请求，不得记录、存储或打印到日志。

`smsType` 为**可选参数**：用户未指定类型时不传该字段（查所有类型短信）；用户明确指定类型时才传。

```bash
# 不指定类型时（查所有类型）
curl -s -X POST "https://qahome.sankuai.com/smsqueue/query" \
  -H "Content-Type: application/json" \
  -H "access-token: ${user_access_token}" \
  -d '{"mobileNo":"<手机号>","id":""}'

# 指定类型时（如 19862 为登录验证码）
curl -s -X POST "https://qahome.sankuai.com/smsqueue/query" \
  -H "Content-Type: application/json" \
  -H "access-token: ${user_access_token}" \
  -d '{"mobileNo":"<手机号>","id":"","smsType":"<类型>"}'
```

⛔ BLOCKING：若命令返回非零退出码或 resultCode != 0，停止并展示错误信息，不继续提取验证码。

**错误处理速查**：

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| `resultCode: 1` | 手机号格式错误或接口异常 | 提示用户确认手机号是否为11位纯数字 |
| `result` 为空数组 | 该号码暂无短信记录 | 提示无记录，不报错 |
| `message` 中无验证码特征 | 非验证码类短信 | 返回完整 `message` 供用户判断 |
| 401 / 403 | SSO token 失效 | 平台会自动刷新，重新执行即可 |
| 命令超时 / 无响应 | 网络不通或 qahome 服务异常 | 提示检查网络，等待 30s 后可重试 |

### 阶段 2：提取验证码并输出

从返回的 `result` 数组中：
1. 接口已按 `addTime` 倒序返回，直接取 `result[0]` 即为最新一条
2. 从该条 `message` 字段提取验证码：
   - 优先用正则 `/(\d{4,6})(?=（)/` 匹配「数字+中文括号」格式（如 `2576（登录验证码...）`），兼容4~6位
   - 若未命中，fallback 到 `/\d{6}/` 匹配纯6位数字

输出格式：
```
📱 手机号 <脱敏手机号> 最新验证码：<验证码>
⏰ 短信时间：<addTimeFormat>
📄 短信内容：<message>
```

> 脱敏规则：手机号展示时中间4位替换为 `****`，如 `138****8540`（接口返回的 `mobileNo` 字段已脱敏，直接使用即可）。

若 `result` 为空或无法提取验证码：
> ❌ 未查询到该手机号的短信，请确认手机号是否正确，或该号码暂无短信记录。

## 反模式（禁止）

| # | 禁止行为 |
|---|---------|
| AP-1 | 把带 +86 前缀的号码原样传给接口（需去掉前缀，只传11位）|
| AP-2 | 返回列表不排序，直接取第一条（顺序不保证是最新）|
| AP-3 | 验证码提取失败时直接返回整段 message，不做提示 |
| AP-4 | 在输出或日志中展示完整11位手机号明文（必须使用脱敏格式）|
| AP-5 | 将本工具用于查询真实用户短信（仅限测试手机号）|

---

## 查询用户信息（手机号 ↔ userId）

### 触发条件

用户提到：查userId、查手机号、userId查手机号、手机号查userId、用户信息查询、这个手机号对应的userId是什么、mobileNo

> ℹ️ 本操作均针对 QAHome 测试环境账号，无线上风险。

### 阶段 1：调用用户查询接口

从用户输入中识别意图：
- 输入为 11 位数字 → 视为手机号，查 userId
- 输入为纯数字且长度 > 11 位 → 视为 userId，查手机号
- 用户明确说明查询方向时，按用户意图执行

```bash
# 根据手机号查 userId
curl -s -X POST "https://qahome.sankuai.com/user" \
  -H "Content-Type: application/json" \
  -H "access-token: ${user_access_token}" \
  -d '{"userId":"","mobileNo":"<手机号>"}'

# 根据 userId 查手机号
curl -s -X POST "https://qahome.sankuai.com/user" \
  -H "Content-Type: application/json" \
  -H "access-token: ${user_access_token}" \
  -d '{"userId":"<userId>","mobileNo":""}'
```

⛔ BLOCKING：若命令返回非零退出码或 resultCode != 0，停止并展示错误信息。

**错误处理速查**：

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| `status: 401` | SSO token 失效 | 平台会自动刷新，重新执行即可 |
| `resultCode: 0` 但 result 为空/null | 该手机号/userId 不存在 | 提示用户确认输入是否正确 |
| `resultCode` 非 0 | 接口异常 | 展示 message 字段信息 |

### 阶段 2：格式化输出

输出格式：
```
👤 用户信息查询结果（测试环境）：
━━━━━━━━━━━━━━━━━━━━
📱 手机号：<脱敏手机号>
🆔 userId：<userId>
📝 昵称：<userNickName>
📅 注册时间：<userAddDate 转为 YYYY-MM-DD HH:MM:SS>
🔗 来源：<userSource>
```

> 脱敏规则：手机号中间4位替换为 `****`，如 `132****8960`

若 result 为空或 null：
> ❌ 未查询到该手机号/userId 对应的用户，请确认输入是否正确（仅支持测试环境账号）。

---

## 创建测试账号

### 触发条件

用户提到：创建账号、注册账号、创建测试账号、注册新用户、regNewUser、新建账号、生成测试账号、帮我创建一个测试账号

> ℹ️ 本操作均针对 QAHome 测试环境，自动生成一个新测试账号，无线上风险。

### 调用接口

```bash
curl -s -X GET "https://qahome.sankuai.com/user/regNewUser/" \
  -H "access-token: ${user_access_token}"
```

⛔ BLOCKING：若命令返回非零退出码或 resultCode != 0，停止并展示错误信息。

**错误处理速查**：

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| HTTP 302 跳转 SSO | token 失效 | 平台自动刷新，重新执行 |
| `resultCode` 非 0 | 接口异常 | 展示 message 字段 |
| result 为 null | 创建失败 | 提示用户重试 |

### 格式化输出

> ℹ️ 本接口返回的是测试环境账号数据，无真实用户信息风险，**手机号无需脱敏，完整展示**。

输出格式：
```
✅ 测试账号创建成功（QAHome 测试环境）：
━━━━━━━━━━━━━━━━━━━━
📱 手机号：<完整手机号>
🆔 userId：<userId>
📝 昵称：<userNickName>
📅 注册时间：<userAddDate 转为 YYYY-MM-DD HH:MM:SS>
```

若 result 为空或创建失败：
> ❌ 账号创建失败，请稍后重试。（错误信息：<message>）

---

## 参考文档

- [references/sms-query.md](references/sms-query.md) — 短信查询接口详情、返回字段说明、错误处理
- [references/user-query.md](references/user-query.md) — 用户信息查询接口详情、返回字段说明
- [references/reg-new-user.md](references/reg-new-user.md) — 创建测试账号接口详情、返回字段说明

