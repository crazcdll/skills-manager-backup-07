# 短信查询接口详情

## 接口信息

| 字段 | 值 |
|------|---|
| 地址 | `https://qahome.sankuai.com/smsqueue/query` |
| 方法 | POST |
| Content-Type | `application/json` |
| 鉴权 | SSO access-token（由 `bin/ciba-request.mjs` 自动处理） |

## 请求 Body

```json
{
  "mobileNo": "13800138000",
  "id": "",
  "smsType": "19862"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `mobileNo` | 是 | 11位纯数字手机号，不带+86前缀 |
| `id` | 否 | 短信ID，留空查全部 |
| `smsType` | 是 | 短信类型，登录验证码固定传 `19862` |

## 返回结构

```json
{
  "resultCode": 0,
  "message": "查询成功!",
  "result": [
    {
      "mobileNo": "138****8000",
      "message": "您的验证码为123456，5分钟内有效，请勿泄露。",
      "id": "msg_xxx",
      "smsType": "19862",
      "signature": "【美团】",
      "status": "success",
      "addTimeFormat": "2026-04-03 10:23:45",
      "updateTimeFormat": "2026-04-03 10:23:46"
    }
  ],
  "resultNum": 1
}
```

| 字段 | 说明 |
|------|------|
| `resultCode` | 0=成功，1=失败 |
| `result` | 短信列表，接口已按入库时间倒序返回，**直接取 `result[0]` 即为最新一条** |
| `mobileNo` | 脱敏后的手机号 |
| `message` | 短信原文，验证码在其中，用 `/\d{6}/` 提取 |
| `addTimeFormat` | 短信入库时间，格式 `yyyy-MM-dd HH:mm:ss` |

## 验证码提取逻辑

```javascript
// 接口已按 addTime 倒序返回，直接取第一条
const latest = result[0];
const match = latest.message.match(/\d{6}/);
const code = match ? match[0] : null;
```

## 常见错误处理

| 现象 | 原因 | 处理 |
|------|------|------|
| `resultCode: 1` | 手机号格式错误或无短信 | 提示用户确认手机号 |
| sso-auth-cli 执行失败 | Node.js < 18 或无法访问内网 npm | 检查 Node 版本，确认在内网环境 |
| `result` 为空数组 | 该号码无短信记录 | 提示无记录 |
| message 中无6位数字 | 非验证码类短信 | 返回完整 message 供用户判断 |
| 401 / 403 | SSO token 失效 | 重新执行，sso-auth-cli 会自动续期 |

